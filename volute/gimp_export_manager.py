"""
GIMP Export Manager
Handles export of the current frame's background image plus one mask
image per object as a starting point for external editing in GIMP, either
assembled into a single multi-layer .xcf file (via GIMP batch-mode
Python-Fu) or as separate plain image files when GIMP's command-line
executable isn't available.
"""

import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import numpy as np
from PIL import Image


# Outcome of a long-running export/import operation. Cancellation is
# reported separately from failure so callers can show a neutral info
# message instead of an error dialog after a deliberate cancellation.
STATUS_OK = 'ok'
STATUS_CANCELLED = 'cancelled'
STATUS_ERROR = 'error'


def sanitize_folder_name(name):
    """Sanitize an object name for use as a filesystem folder component."""
    cleaned = re.sub(r'[^\w\-. ]', '_', name).strip()
    return cleaned or "object"


class GimpExportManager:
    """
    Detects a usable GIMP command-line executable and exports the current
    frame (background + one mask layer per object) either as a single
    .xcf file (GIMP batch-mode assembly) or as separate plain image files.
    """

    # Separator used in exported .xcf layer names to embed the object id,
    # object name, and target filename with no other per-frame state —
    # the extraction script (scripts/volute_extract_layers.py) relies
    # entirely on parsing this convention.
    LAYER_NAME_SEP = "::"

    # Name of the per-item progress file written by the generated Python-Fu
    # scripts inside the operation's temp folder: one line appended after
    # each fully written frame/file, so the polling loop below knows both
    # how far the batch got and which outputs are complete.
    PROGRESS_FILENAME = "progress.txt"

    # Poll interval of the subprocess wait loop, and grace period left to
    # GIMP after terminate() before falling back to kill().
    POLL_INTERVAL = 0.2
    TERMINATE_GRACE = 3.0

    # Looked into when neither name is on PATH. A macOS install puts none of
    # GIMP's executables on PATH, so the bundle has to be searched; the
    # unversioned names there are symlinks that keep pointing at the right
    # binary across a GIMP update, unlike the versioned ones beside them.
    # Where the executables are on PATH, as they are on Linux, this is unused.
    BUNDLED_CANDIDATES = (
        '/Applications/GIMP.app/Contents/MacOS/gimp-console',
        '/Applications/GIMP.app/Contents/MacOS/gimp',
    )

    def __init__(self, main_window, debug_mode=False):
        self.main_window = main_window
        self.debug_mode = debug_mode
        self._gimp_executable = None
        self._detected = False
        # Set from the UI thread, polled from the worker thread running the
        # export/import — mirrors BatchProcessor's cooperative cancel flag.
        self._cancel_event = threading.Event()

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    def cancel(self):
        """Request cancellation of the running export/import (thread-safe)."""
        self._cancel_event.set()

    def reset_cancel(self):
        """Clear a pending cancellation request; called by every public
        entry point before starting its work."""
        self._cancel_event.clear()

    def is_cancelled(self):
        return self._cancel_event.is_set()

    # ------------------------------------------------------------------
    # GIMP CLI detection
    # ------------------------------------------------------------------

    def detect_gimp_executable(self, force=False):
        """
        Resolve a usable GIMP executable path: an explicit override from
        configuration takes precedence and is NOT silently ignored if
        invalid (an invalid override is reported as "not detected" rather
        than falling back to a search); otherwise 'gimp-console' then
        'gimp' are looked up on PATH, and failing that in
        BUNDLED_CANDIDATES.

        'gimp-console' is preferred at every step: it carries no GUI, so
        it opens no window, flashes no Dock icon, and cannot fail for want
        of a display connection — which the full binary can, even under
        -i, since it still brings up GTK.
        """
        if self._detected and not force:
            return self._gimp_executable

        override = self.main_window.config_manager.get_gimp_path()
        if override:
            self._gimp_executable = override if self._is_executable(override) else None
            self._detected = True
            return self._gimp_executable

        found = next(
            (p for p in (shutil.which('gimp-console'), shutil.which('gimp')) if p),
            None,
        )
        if found is None:
            found = next(
                (p for p in self.BUNDLED_CANDIDATES if self._is_executable(p)),
                None,
            )

        self._gimp_executable = found
        self._detected = True
        return found

    @staticmethod
    def _is_executable(path):
        return os.path.isfile(path) and os.access(path, os.X_OK)

    def is_available(self):
        return self.detect_gimp_executable() is not None

    # ------------------------------------------------------------------
    # Mask layer preparation
    # ------------------------------------------------------------------

    @staticmethod
    def _build_mask_image(mask, color, width, height):
        """
        Build an RGBA image for one object's mask layer: pixels inside the
        mask filled with the object's display color at full opacity
        (ignores the color's own display alpha); pixels
        outside are fully transparent, with RGB left at (0, 0, 0) so that
        converting to a non-alpha format later still matches the app's
        black = background convention. A None mask (no prediction yet on
        this frame) produces a fully transparent image, ready to be
        hand-painted.
        """
        arr = np.zeros((height, width, 4), dtype=np.uint8)
        if mask is not None:
            m = mask
            while len(m.shape) > 2:
                m = m.squeeze(0)
            arr[m.astype(bool)] = [color.red(), color.green(), color.blue(), 255]
        return Image.fromarray(arr, mode='RGBA')

    @staticmethod
    def _save_mask_image(img, path):
        """
        Save a built mask image using the format implied by its
        extension, so the file can keep the exact source frame's
        basename (Import Mask... matches by plain basename
        equality, extension included). JPEG/BMP have no alpha channel;
        dropping it is safe here since transparent regions are pure black
        (RGB 0,0,0) by construction.
        """
        ext = os.path.splitext(path)[1].lower()
        fmt = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.bmp': 'BMP',
               '.tif': 'TIFF', '.tiff': 'TIFF', '.png': 'PNG'}.get(ext, 'PNG')
        if fmt in ('JPEG', 'BMP'):
            img = img.convert('RGB')
        img.save(path, fmt)

    def _gather_objects(self, object_ids=None, frame_idx=None):
        """
        Collect (obj_id, name, mask, color) tuples for the objects to
        export, in ascending object ID order. object_ids=None exports all
        objects. frame_idx=None uses the currently displayed frame.
        """
        om = self.main_window.object_manager
        if frame_idx is None:
            frame_idx = self.main_window.image_manager.current_image_idx
        ids = sorted(object_ids) if object_ids is not None else om.get_object_ids()
        objects = []
        for obj_id in ids:
            name = om.object_names.get(obj_id, f"Object {obj_id}")
            mask = om.object_masks.get(obj_id, {}).get(frame_idx)
            color = om.object_colors[obj_id]['mask']
            objects.append((obj_id, name, mask, color))
        return objects

    # ------------------------------------------------------------------
    # Python-Fu assembly (XCF mode)
    # ------------------------------------------------------------------

    @staticmethod
    def _py_string(value):
        """Escape a Python string as a Python-Fu source literal (via repr)."""
        return repr(str(value))

    def _progress_lines(self, progress_path):
        """Python-Fu statements appending one line to the progress file.
        Opened and closed around every write so each item is flushed to
        disk immediately — the polling loop (and the partial-output
        cleanup after a cancellation) depends on it."""
        if not progress_path:
            return []
        return [
            f'_progress = open({self._py_string(progress_path)}, "a", encoding="utf-8")',
            '_progress.write("1\\n")',
            '_progress.close()',
        ]

    def _frame_assembly_lines(self, background_path, mask_entries, output_path,
                              progress_path=None):
        """Python-Fu statements assembling one frame's .xcf (load background,
        insert mask layers, save, delete) — shared by the single-frame and
        multi-frame (batched) assembly script builders. The progress line is
        written only once the frame's file is fully saved."""
        lines = [
            f'bg_file = Gio.File.new_for_path({self._py_string(background_path)})',
            'image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, bg_file)',
            'bg_layer = image.get_layers()[0]',
            f'bg_layer.set_name({self._py_string("background")})',
        ]
        for path, layer_name in mask_entries:
            lines.append(f'layer_file = Gio.File.new_for_path({self._py_string(path)})')
            lines.append(
                'layer = Gimp.file_load_layer(Gimp.RunMode.NONINTERACTIVE, image, layer_file)'
            )
            lines.append('image.insert_layer(layer, None, 0)')
            lines.append(f'layer.set_name({self._py_string(layer_name)})')
        lines.append(f'out_file = Gio.File.new_for_path({self._py_string(output_path)})')
        lines.append('Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, out_file, None)')
        lines.append('image.delete()')
        lines.extend(self._progress_lines(progress_path))
        return lines

    def _build_assembly_script(self, background_path, mask_entries, output_path):
        """Python-Fu assembly script for a single frame, executed via
        --batch-interpreter=python-fu-eval."""
        lines = ['from gi.repository import Gimp, Gio']
        lines.extend(self._frame_assembly_lines(background_path, mask_entries, output_path))
        return '\n'.join(lines)

    def _build_multi_frame_assembly_script(self, frames, progress_path=None):
        """
        Python-Fu script assembling multiple frames' .xcf files in a single
        GIMP invocation: one shared import, then one load/insert/save/delete
        block per frame — avoids paying GIMP's startup cost once per frame.
        frames: list of (background_path, mask_entries, output_path).
        """
        lines = ['from gi.repository import Gimp, Gio']
        for background_path, mask_entries, output_path in frames:
            lines.extend(
                self._frame_assembly_lines(background_path, mask_entries, output_path,
                                           progress_path=progress_path)
            )
        return '\n'.join(lines)

    # ------------------------------------------------------------------
    # GIMP batch invocation
    # ------------------------------------------------------------------

    @staticmethod
    def _read_progress(progress_path):
        """Number of items the running script reports as fully written."""
        if not progress_path:
            return 0
        try:
            with open(progress_path, encoding="utf-8") as f:
                return sum(1 for line in f if line.strip())
        except OSError:
            return 0

    def _terminate_process(self, proc):
        """Stop a live GIMP process: terminate(), then kill() if it hasn't
        exited within the grace period. GIMP's non-interactive batch mode
        has no dialog or unsaved state to intercept, so the graceful/forced
        distinction only matters for letting it close its own files."""
        try:
            proc.terminate()
            proc.wait(timeout=self.TERMINATE_GRACE)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except Exception:
                pass
        except Exception:
            pass

    def _run_gimp_batch(self, script, timeout=120, progress_path=None,
                        progress_callback=None, progress_total=0):
        """
        Invoke GIMP non-interactively with the given Python-Fu batch script,
        polling for completion so a cancellation request can kill the live
        process mid-script. Returns
        (status, combined_stdout_stderr, completed_items).
        """
        gimp_exe = self.detect_gimp_executable()
        if not gimp_exe:
            return STATUS_ERROR, "GIMP executable not found.", 0

        cmd = [gimp_exe, '-i', '--batch-interpreter=python-fu-eval',
               '-b', script, '--quit']
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, stdin=subprocess.DEVNULL,
            )
        except Exception as e:
            return STATUS_ERROR, str(e), 0

        deadline = time.monotonic() + timeout
        completed = 0
        cancelled = False
        timed_out = False

        while proc.poll() is None:
            if self._cancel_event.is_set():
                cancelled = True
                self._terminate_process(proc)
                break
            if time.monotonic() > deadline:
                timed_out = True
                self._terminate_process(proc)
                break

            current = self._read_progress(progress_path)
            if current != completed:
                completed = current
                if progress_callback:
                    progress_callback(completed, progress_total)
            time.sleep(self.POLL_INTERVAL)

        try:
            stdout, stderr = proc.communicate(timeout=self.TERMINATE_GRACE)
        except Exception:
            stdout, stderr = "", ""

        # Final read: the last item may have completed between two polls.
        completed = max(completed, self._read_progress(progress_path))
        if progress_callback and not cancelled:
            progress_callback(completed, progress_total)

        if cancelled:
            return STATUS_CANCELLED, "", completed
        if timed_out:
            return STATUS_ERROR, "GIMP batch invocation timed out.", completed

        output = ((stdout or "") + "\n" + (stderr or "")).strip()
        status = STATUS_OK if proc.returncode == 0 else STATUS_ERROR
        return status, output, completed

    @staticmethod
    def _remove_files(paths):
        """Delete output files left incomplete by a cancelled invocation
        (only the file being written when GIMP was killed can actually
        exist here, but the whole tail is cleared for safety)."""
        for path in paths:
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Public export entry points
    # ------------------------------------------------------------------

    def export_as_xcf(self, output_path, object_ids=None):
        """
        Export the current frame as a single multi-layer .xcf file.
        Returns (status, message) — message is empty on success and on
        cancellation, and holds GIMP's error output verbatim on failure.
        A cancelled single-frame export leaves no output behind: the
        possibly truncated .xcf is removed.
        """
        self.reset_cancel()
        im = self.main_window.image_manager
        image_info = im.get_current_image_info()
        if not image_info:
            return STATUS_ERROR, self.main_window.localization.get_text("no_image_loaded")
        width, height = image_info['width'], image_info['height']
        background_source = im.get_all_image_paths()[im.current_image_idx]
        frame_basename = os.path.basename(background_source)

        objects = self._gather_objects(object_ids)

        temp_dir = tempfile.mkdtemp(prefix="sam2_gimp_export_")
        mask_entries = []
        for obj_id, name, mask, color in objects:
            img = self._build_mask_image(mask, color, width, height)
            mask_path = os.path.join(temp_dir, f"mask_{obj_id}.png")
            img.save(mask_path, 'PNG')
            layer_name = self.LAYER_NAME_SEP.join(["mask", str(obj_id), name, frame_basename])
            mask_entries.append((mask_path, layer_name))

        script = self._build_assembly_script(background_source, mask_entries, output_path)
        status, message, _ = self._run_gimp_batch(script)

        if status == STATUS_CANCELLED:
            self._remove_files([output_path])
        elif status == STATUS_OK and not os.path.isfile(output_path):
            status = STATUS_ERROR
            message = message or "GIMP reported success but produced no .xcf file."

        # Always clean up the temp PNGs, except in debug mode on failure,
        # where they're kept on disk for troubleshooting.
        if status != STATUS_ERROR or not self.debug_mode:
            shutil.rmtree(temp_dir, ignore_errors=True)
        elif self.debug_mode:
            print(f"[GIMP export] Kept temp folder for debugging: {temp_dir}")

        return status, message

    def export_as_files(self, output_folder, object_ids=None):
        """
        Export the current frame as separate plain image files: the
        background copied to the export root, and one mask image per
        object inside a per-object subfolder (a subfolder
        per object is required, not just for navigation: every mask file
        must keep the exact source frame basename, so two objects' masks
        cannot share one flat folder). Usable as-is as Format A Import
        Mask... input, no GIMP round-trip needed. No subprocess involved,
        so cancellation is a plain cooperative check between objects.
        Returns (status, message).
        """
        self.reset_cancel()
        im = self.main_window.image_manager
        image_info = im.get_current_image_info()
        if not image_info:
            return STATUS_ERROR, self.main_window.localization.get_text("no_image_loaded")
        width, height = image_info['width'], image_info['height']
        background_source = im.get_all_image_paths()[im.current_image_idx]
        frame_basename = os.path.basename(background_source)

        objects = self._gather_objects(object_ids)

        try:
            os.makedirs(output_folder, exist_ok=True)
            shutil.copy2(background_source, os.path.join(output_folder, frame_basename))

            for obj_id, name, mask, color in objects:
                if self._cancel_event.is_set():
                    return STATUS_CANCELLED, ""
                subfolder = os.path.join(
                    output_folder, f"obj{obj_id}_{sanitize_folder_name(name)}"
                )
                os.makedirs(subfolder, exist_ok=True)
                img = self._build_mask_image(mask, color, width, height)
                self._save_mask_image(img, os.path.join(subfolder, frame_basename))

            return STATUS_OK, ""
        except Exception as e:
            return STATUS_ERROR, str(e)

    def export_all_frames_as_xcf(self, output_folder, frame_indices, object_ids=None,
                                 progress_callback=None):
        """
        Export every frame in frame_indices as its own multi-layer .xcf file,
        all assembled in a single GIMP invocation (one process for every
        frame, not one per frame — GIMP's startup cost would otherwise
        dominate for large frame counts). Output filenames follow each
        frame's original basename with a .xcf extension, placed directly in
        output_folder.

        On cancellation the frames already fully written stay on disk (an
        output folder chosen by the person may hold pre-existing files, so
        wiping it is not an option); only the frame being written when GIMP
        was killed — possibly truncated — is removed.

        Returns (status, message, completed_frames).
        """
        self.reset_cancel()
        im = self.main_window.image_manager
        all_paths = im.get_all_image_paths()
        total = len(frame_indices)

        os.makedirs(output_folder, exist_ok=True)
        temp_dir = tempfile.mkdtemp(prefix="sam2_gimp_export_")
        progress_path = os.path.join(temp_dir, self.PROGRESS_FILENAME)
        frames = []
        try:
            for frame_idx in frame_indices:
                if self._cancel_event.is_set():
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return STATUS_CANCELLED, "", 0

                background_source = all_paths[frame_idx]
                frame_basename = os.path.basename(background_source)
                with Image.open(background_source) as img:
                    width, height = img.size

                objects = self._gather_objects(object_ids=object_ids, frame_idx=frame_idx)
                mask_entries = []
                for obj_id, name, mask, color in objects:
                    img_mask = self._build_mask_image(mask, color, width, height)
                    mask_path = os.path.join(temp_dir, f"mask_{frame_idx}_{obj_id}.png")
                    img_mask.save(mask_path, 'PNG')
                    layer_name = self.LAYER_NAME_SEP.join(["mask", str(obj_id), name, frame_basename])
                    mask_entries.append((mask_path, layer_name))

                output_path = os.path.join(
                    output_folder, os.path.splitext(frame_basename)[0] + ".xcf"
                )
                frames.append((background_source, mask_entries, output_path))
        except Exception as e:
            shutil.rmtree(temp_dir, ignore_errors=True)
            return STATUS_ERROR, str(e), 0

        script = self._build_multi_frame_assembly_script(frames, progress_path=progress_path)
        status, message, completed = self._run_gimp_batch(
            script, timeout=120 + 30 * len(frames),
            progress_path=progress_path, progress_callback=progress_callback,
            progress_total=total,
        )

        if status == STATUS_CANCELLED:
            self._remove_files([p for _, _, p in frames[completed:]])
        elif status == STATUS_OK:
            missing = [p for _, _, p in frames if not os.path.isfile(p)]
            if missing:
                status = STATUS_ERROR
                message = message or f"GIMP reported success but {len(missing)} .xcf file(s) are missing."

        if status != STATUS_ERROR or not self.debug_mode:
            shutil.rmtree(temp_dir, ignore_errors=True)
        elif self.debug_mode:
            print(f"[GIMP export] Kept temp folder for debugging: {temp_dir}")

        return status, message, completed

    def export_all_frames_as_files(self, output_root, frame_indices, object_ids=None,
                                    progress_callback=None):
        """
        Export every frame in frame_indices as separate plain image files,
        each frame in its own subfolder named after the frame's basename
        (mask filenames must keep the exact source frame basename, so
        frames can't share one flat folder — same constraint as objects in
        export_as_files). No GIMP involved, so cancellation is a plain
        cooperative check between frames; frames already written are kept.
        Returns (status, message, completed_frames).
        """
        self.reset_cancel()
        im = self.main_window.image_manager
        all_paths = im.get_all_image_paths()
        total = len(frame_indices)
        completed = 0

        try:
            os.makedirs(output_root, exist_ok=True)
            for i, frame_idx in enumerate(frame_indices):
                if self._cancel_event.is_set():
                    return STATUS_CANCELLED, "", completed

                background_source = all_paths[frame_idx]
                frame_basename = os.path.basename(background_source)
                with Image.open(background_source) as img:
                    width, height = img.size

                frame_folder = os.path.join(output_root, os.path.splitext(frame_basename)[0])
                os.makedirs(frame_folder, exist_ok=True)
                shutil.copy2(background_source, os.path.join(frame_folder, frame_basename))

                objects = self._gather_objects(object_ids=object_ids, frame_idx=frame_idx)
                for obj_id, name, mask, color in objects:
                    subfolder = os.path.join(
                        frame_folder, f"obj{obj_id}_{sanitize_folder_name(name)}"
                    )
                    os.makedirs(subfolder, exist_ok=True)
                    img_mask = self._build_mask_image(mask, color, width, height)
                    self._save_mask_image(img_mask, os.path.join(subfolder, frame_basename))

                completed = i + 1
                if progress_callback:
                    progress_callback(completed, total)

            return STATUS_OK, "", completed
        except Exception as e:
            return STATUS_ERROR, str(e), completed

    # ------------------------------------------------------------------
    # XCF mask import (extraction with alpha preserved — no flattening)
    # ------------------------------------------------------------------

    def _build_xcf_extraction_script(self, xcf_paths, temp_dir, progress_path=None):
        """
        Python-Fu script that batch-loads each given .xcf file, isolates
        every mask::<id>::<name>::<filename> layer into its own RGBA PNG
        (alpha preserved, no flattening — unlike the person-run extraction
        script, the alpha channel itself becomes the imported mask
        boundary here) under temp_dir, and writes one tab-separated line
        per extracted layer to manifest.txt (xcf_index, obj_id, obj_name,
        filename, png_path) so the calling process can locate results
        without parsing GIMP's own output. One progress line is appended
        per fully processed .xcf file.
        """
        manifest_path = os.path.join(temp_dir, "manifest.txt")
        lines = [
            'from gi.repository import Gimp, Gio',
            f'manifest = open({self._py_string(manifest_path)}, "w", encoding="utf-8")',
            'counter = 0',
        ]
        for xcf_idx, xcf_path in enumerate(xcf_paths):
            lines.append(f'xcf_file = Gio.File.new_for_path({self._py_string(xcf_path)})')
            lines.append('image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, xcf_file)')
            lines.append('for layer in image.get_layers():')
            lines.append('    lname = layer.get_name()')
            lines.append(f'    if not lname.startswith("mask{self.LAYER_NAME_SEP}"):')
            lines.append('        continue')
            lines.append(f'    parts = lname.split({self._py_string(self.LAYER_NAME_SEP)})')
            lines.append('    if len(parts) < 4:')
            lines.append('        continue')
            lines.append('    obj_id, obj_name, fname = parts[1], parts[2], parts[3]')
            lines.append('    counter += 1')
            lines.append(f'    out_path = {self._py_string(temp_dir)} + "/m" + str(counter) + ".png"')
            lines.append(
                '    tmp_image = Gimp.Image.new(image.get_width(), image.get_height(), Gimp.ImageBaseType.RGB)'
            )
            lines.append('    tmp_layer = Gimp.Layer.new_from_drawable(layer, tmp_image)')
            lines.append('    tmp_image.insert_layer(tmp_layer, None, 0)')
            lines.append('    out_file = Gio.File.new_for_path(out_path)')
            lines.append('    Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, tmp_image, out_file, None)')
            lines.append('    tmp_image.delete()')
            lines.append(
                f'    manifest.write(str({xcf_idx}) + "\\t" + obj_id + "\\t" + obj_name '
                '+ "\\t" + fname + "\\t" + out_path + "\\n")'
            )
            lines.append('image.delete()')
            lines.append('manifest.flush()')
            lines.extend(self._progress_lines(progress_path))
        lines.append('manifest.close()')
        return '\n'.join(lines)

    def extract_masks_from_xcf_files(self, xcf_paths, progress_callback=None):
        """
        Batch-extract mask layers from the given .xcf files (see
        _build_xcf_extraction_script) via a single GIMP invocation. Returns
        (status, message, entries, temp_dir) where entries is a list of
        dicts: {'xcf_index', 'obj_id', 'obj_name', 'filename', 'path'} —
        'path' is a temp RGBA PNG whose alpha channel is the mask boundary.
        Caller is responsible for deleting temp_dir once done with entries.

        Cancellation is all-or-nothing by construction: this step only
        writes temp artifacts, nothing is applied to the session until the
        caller iterates over entries, so a cancelled extraction simply
        returns no entries and leaves the session untouched.
        """
        self.reset_cancel()
        temp_dir = tempfile.mkdtemp(prefix="sam2_gimp_xcf_import_")
        progress_path = os.path.join(temp_dir, self.PROGRESS_FILENAME)
        script = self._build_xcf_extraction_script(xcf_paths, temp_dir,
                                                   progress_path=progress_path)
        status, message, _ = self._run_gimp_batch(
            script, timeout=120 + 30 * len(xcf_paths),
            progress_path=progress_path, progress_callback=progress_callback,
            progress_total=len(xcf_paths),
        )

        if status == STATUS_CANCELLED:
            return status, "", [], temp_dir

        manifest_path = os.path.join(temp_dir, "manifest.txt")
        entries = []
        if status == STATUS_OK and os.path.isfile(manifest_path):
            with open(manifest_path, encoding="utf-8") as f:
                for line in f:
                    parts = line.rstrip("\n").split("\t")
                    if len(parts) != 5:
                        continue
                    xcf_idx, obj_id, obj_name, filename, path = parts
                    entries.append({
                        'xcf_index': int(xcf_idx), 'obj_id': int(obj_id),
                        'obj_name': obj_name, 'filename': filename, 'path': path,
                    })
        elif status == STATUS_OK:
            status = STATUS_ERROR
            message = message or "GIMP reported success but produced no manifest."

        return status, message, entries, temp_dir
