"""
GIMP UI Controller
UI-facing half of the GIMP round-trip (export for editing, mask import),
including the plain-image mask import formats (Format A/B) which share the
import_mask() entry point. Runs GIMP subprocess calls off the UI thread via
GimpExportWorker, with a modal progress dialog.
"""

import os
import shutil
import numpy as np
from PyQt5.QtWidgets import (
    QMessageBox, QFileDialog, QDialog,
)
from PyQt5.QtCore import Qt, QDir, QEventLoop, QThread, pyqtSignal

from .dialogs import ColorObjectMappingDialog, GimpExportDialog, localize_standard_buttons
from .gimp_export_manager import STATUS_OK, STATUS_CANCELLED
from .file_utils import build_file_filter
from .progress_dialog import AnimatedProgressDialog


class GimpExportWorker(QThread):
    """
    Generic worker thread running a GIMP export/import callable off the UI
    thread — GIMP's startup and subprocess time would otherwise freeze the
    UI. task_fn receives a progress_callback(current, total) and returns
    its result value, forwarded via the finished signal.
    """

    progress = pyqtSignal(int, int)
    finished = pyqtSignal(object)

    def __init__(self, task_fn, parent=None):
        super().__init__(parent)
        self.task_fn = task_fn

    def run(self):
        result = self.task_fn(lambda cur, tot: self.progress.emit(cur, tot))
        self.finished.emit(result)


class GimpUIController:
    """UI actions for the GIMP mask export/import round-trip, plus the
    plain-image (non-GIMP) mask import formats. Accesses main_window's
    managers via self.main_window.<attr> rather than caching references,
    so it keeps working if a manager is ever re-instantiated."""

    def __init__(self, main_window):
        self.main_window = main_window

    def _run_with_progress(self, task_fn, message_key="gimp_export_in_progress",
                            title_key="gimp_export_frame"):
        """
        Run task_fn(progress_callback) in a background thread with a modal
        progress dialog — GIMP's startup/subprocess time would otherwise
        freeze the UI. The dialog starts indeterminate, since GIMP's startup
        dominates before the first progress report lands and a determinate
        bar stuck at zero looks frozen; on_progress switches it to
        determinate as soon as a total is reported. Returns task_fn's return
        value. The cancel button forwards to GimpExportManager.cancel(),
        which kills the live GIMP process (or stops between items for the
        plain-file exports).
        """
        mw = self.main_window
        progress_dlg = AnimatedProgressDialog(
            mw.localization.get_text(message_key),
            mw.localization.get_text("cancel"), 0, 0, mw,
        )
        progress_dlg.setWindowTitle(mw.localization.get_text(title_key))
        progress_dlg.setWindowModality(Qt.WindowModal)
        progress_dlg.setMinimumDuration(300)
        # Left at their defaults, reaching the maximum would call reset(), which
        # hides the dialog while GIMP may still be finishing and so hands the
        # main window back too early; both are disabled and the dialog is closed
        # explicitly once the worker returns.
        progress_dlg.setAutoClose(False)
        progress_dlg.setAutoReset(False)

        worker = GimpExportWorker(task_fn, parent=mw)
        loop = QEventLoop(mw)
        result = [None]
        finished = [False]

        def on_progress(cur, tot):
            if tot and tot != progress_dlg.maximum():
                progress_dlg.setMaximum(tot)
            progress_dlg.setValue(cur)

        def on_cancel():
            # close() also emits canceled(): ignore it once the task is done.
            if finished[0]:
                return
            mw.gimp_export_manager.cancel()
            # cancel() hides the dialog immediately; keep it up, and modal,
            # until the worker actually returns (killing GIMP is not instant).
            progress_dlg.setLabelText(mw.localization.get_text("progress_cancelled"))
            progress_dlg.show()

        def on_finished(value):
            result[0] = value
            finished[0] = True
            progress_dlg.close()
            loop.quit()

        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        progress_dlg.canceled.connect(on_cancel)
        worker.start()
        loop.exec_()
        worker.wait()

        return result[0]

    def export_frame_for_gimp(self):
        """Export the current frame's background plus one mask image per
        object as a starting point for external editing (GIMP .xcf, or
        plain files for any editor)."""
        mw = self.main_window
        if mw.is_point_mode():
            return
        if not mw.image_manager.has_images():
            mw.ui_manager.show_message(
                "warning", mw.localization.get_text("warning"),
                mw.localization.get_text("no_image_loaded"),
            )
            return

        gimp_available = mw.gimp_export_manager.is_available()
        dlg = GimpExportDialog(mw.localization, gimp_available, mw)
        if dlg.exec_() != QDialog.Accepted:
            return
        mode = dlg.get_mode()

        if mode == 'xcf':
            # Same naming as the multi-frame export: the source frame's basename,
            # which is also what the .xcf layer names carry for re-import matching.
            background_source = mw.image_manager.get_all_image_paths()[
                mw.image_manager.current_image_idx
            ]
            default_filename = os.path.splitext(os.path.basename(background_source))[0] + ".xcf"
            output_path, _ = QFileDialog.getSaveFileName(
                mw, mw.localization.get_text("gimp_export_frame"),
                default_filename, build_file_filter(mw.localization, 'xcf'),
            )
            if not output_path:
                return
            status, message = self._run_with_progress(
                lambda progress_cb: mw.gimp_export_manager.export_as_xcf(output_path)
            )
        else:
            output_folder = QFileDialog.getExistingDirectory(
                mw, mw.localization.get_text("select_export_folder"), QDir.homePath()
            )
            if not output_folder:
                return
            status, message = self._run_with_progress(
                lambda progress_cb: mw.gimp_export_manager.export_as_files(output_folder)
            )

        if status == STATUS_OK:
            mw.ui_manager.show_message(
                "info", mw.localization.get_text("success"),
                mw.localization.get_text("gimp_export_successful"),
            )
        elif status == STATUS_CANCELLED:
            mw.ui_manager.show_message(
                "info", mw.localization.get_text("confirmation"),
                mw.localization.get_text("gimp_export_cancelled"),
            )
        else:
            mw.ui_manager.show_message(
                "error", mw.localization.get_text("export_error"), message
            )

    def export_all_frames_for_gimp(self):
        """
        Export every frame with at least one defined mask — one .xcf per
        frame assembled in a single batched GIMP invocation, or one
        plain-files subfolder per frame — after a confirmation dialog
        stating how many frames will be exported.
        """
        mw = self.main_window
        if mw.is_point_mode():
            return
        if not mw.image_manager.has_images():
            mw.ui_manager.show_message(
                "warning", mw.localization.get_text("warning"),
                mw.localization.get_text("no_image_loaded"),
            )
            return

        frame_indices = mw.object_manager.get_frames_with_any_mask()
        if not frame_indices:
            mw.ui_manager.show_message(
                "warning", mw.localization.get_text("warning"),
                mw.localization.get_text("no_masks_for_closest"),
            )
            return

        reply = mw.ui_manager.show_message(
            "question", mw.localization.get_text("confirmation"),
            mw.localization.get_text("gimp_export_all_frames_confirm", len(frame_indices)),
        )
        if reply != QMessageBox.Yes:
            return

        gimp_available = mw.gimp_export_manager.is_available()
        dlg = GimpExportDialog(
            mw.localization, gimp_available, mw,
            title_key="gimp_export_all_dialog_title", hint_key="gimp_export_all_dialog_hint",
            xcf_key="gimp_export_all_mode_xcf", files_key="gimp_export_all_mode_files",
        )
        if dlg.exec_() != QDialog.Accepted:
            return
        mode = dlg.get_mode()

        if mode == 'xcf':
            output_path = QFileDialog.getExistingDirectory(
                mw, mw.localization.get_text("gimp_export_all_frames"), QDir.homePath()
            )
        else:
            output_path = QFileDialog.getExistingDirectory(
                mw, mw.localization.get_text("select_export_folder"), QDir.homePath()
            )
        if not output_path:
            return

        if mode == 'xcf':
            status, message, completed = self._run_with_progress(
                lambda progress_cb: mw.gimp_export_manager.export_all_frames_as_xcf(
                    output_path, frame_indices, progress_callback=progress_cb
                )
            )
        else:
            status, message, completed = self._run_with_progress(
                lambda progress_cb: mw.gimp_export_manager.export_all_frames_as_files(
                    output_path, frame_indices, progress_callback=progress_cb
                )
            )

        if status == STATUS_OK:
            mw.ui_manager.show_message(
                "info", mw.localization.get_text("success"),
                mw.localization.get_text("gimp_export_all_frames_successful", len(frame_indices)),
            )
        elif status == STATUS_CANCELLED:
            # Frames already fully written are kept on disk; only the one being
            # written when GIMP was killed is removed by the export manager.
            key = "gimp_export_partial_cancelled" if completed else "gimp_export_cancelled"
            mw.ui_manager.show_message(
                "info", mw.localization.get_text("confirmation"),
                mw.localization.get_text(key, completed, len(frame_indices)),
            )
        else:
            mw.ui_manager.show_message(
                "error", mw.localization.get_text("export_error"), message
            )

    def _confirm_box_mask_conflict(self, n_conflicts):
        """Confirm before importing masks onto (object, frame) pairs that already
        carry a box prompt (decision D7). Asked once for the whole import."""
        mw = self.main_window
        box = QMessageBox(mw)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(mw.localization.get_text("confirmation"))
        box.setText(mw.localization.get_text("box_mask_import_conflict_batch", n_conflicts))
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        box.setDefaultButton(QMessageBox.Cancel)
        localize_standard_buttons(box, mw.localization)
        return box.exec_() == QMessageBox.Yes

    def import_mask(self):
        """
        Import an externally-composed binary mask as conditioning input for
        one or more frames. Plain image files use the existing color-based
        detection: Format A (single dominant non-background color, always
        targets the currently selected object) or Format B (multi-object
        color-composite, via a one-time color→object mapping dialog).
        .xcf files (as exported by this app's "Export Frame for Editing…")
        skip that heuristic entirely — each mask layer's name already
        carries its object and source frame unambiguously (see
        _import_masks_from_xcf).
        """
        mw = self.main_window
        if mw.is_point_mode():
            return
        if not mw.image_manager.has_images():
            mw.ui_manager.show_message(
                "warning", mw.localization.get_text("warning"),
                mw.localization.get_text("no_image_loaded"),
            )
            return
        if len(mw.object_manager.selected_object_ids) != 1:
            mw.ui_manager.show_message(
                "warning", mw.localization.get_text("warning"),
                mw.localization.get_text("multi_selection_add_points_blocked"),
            )
            return

        paths, _ = QFileDialog.getOpenFileNames(
            mw, mw.localization.get_text("import_mask"), "",
            build_file_filter(mw.localization, 'mask', 'image', 'xcf', 'all')
        )
        if not paths:
            return

        xcf_paths = [p for p in paths if p.lower().endswith('.xcf')]
        image_paths_selected = [p for p in paths if p not in xcf_paths]

        imported_count = 0
        created_objects = False
        imported_frames = set()

        if xcf_paths:
            n, created, frames = self._import_masks_from_xcf(xcf_paths)
            imported_count += n
            created_objects = created_objects or created
            imported_frames |= frames

        obj_id = mw.object_manager.current_object_id

        # Single file: applied to the current frame directly.
        # Multiple files: matched to frames by original filename, mirroring
        # import_tracked_points' filename-matching philosophy.
        file_frame_map = {}
        if image_paths_selected:
            if len(image_paths_selected) == 1:
                file_frame_map = {image_paths_selected[0]: mw.image_manager.current_image_idx}
            else:
                current_basenames = {
                    os.path.basename(p): idx
                    for idx, p in enumerate(mw.image_manager.get_all_image_paths())
                }
                unmatched = []
                for p in image_paths_selected:
                    frame_idx = current_basenames.get(os.path.basename(p))
                    if frame_idx is None:
                        unmatched.append(os.path.basename(p))
                    else:
                        file_frame_map[p] = frame_idx
                if unmatched:
                    names_str = '\n'.join(f"  • {n}" for n in sorted(unmatched)[:10])
                    if len(unmatched) > 10:
                        names_str += f"\n  ({len(unmatched) - 10} more\u2026)"
                    mw.ui_manager.show_message(
                        "warning", mw.localization.get_text("warning"),
                        mw.localization.get_text(
                            "imported_mask_filenames_unmatched", len(unmatched), names_str
                        ),
                    )

        if file_frame_map:
            # --- Pass 1: classify each file as Format A / Format B / empty -------
            # Colors covering at least 0.5% of pixels are significant (ignores
            # anti-aliasing/compression noise); pure black is treated as background.
            file_info = {}
            format_b_colors = set()
            for path, frame_idx in file_frame_map.items():
                try:
                    arr = mw.file_manager.load_image_as_array(path)
                except Exception as e:
                    mw.ui_manager.show_message(
                        "error", mw.localization.get_text("error"), str(e)
                    )
                    continue

                colors, counts = np.unique(arr.reshape(-1, arr.shape[-1]), axis=0, return_counts=True)
                total_px = arr.shape[0] * arr.shape[1]
                significant = counts >= max(1, int(total_px * 0.005))
                non_black = colors.any(axis=1)
                sig_colors = [
                    tuple(int(x) for x in c)
                    for c, keep in zip(colors, significant & non_black) if keep
                ]

                if not sig_colors:
                    file_info[path] = {'frame_idx': frame_idx, 'array': arr, 'colors': [], 'format': 'empty'}
                elif len(sig_colors) == 1:
                    file_info[path] = {'frame_idx': frame_idx, 'array': arr, 'colors': sig_colors, 'format': 'A'}
                else:
                    file_info[path] = {'frame_idx': frame_idx, 'array': arr, 'colors': sig_colors, 'format': 'B'}
                    format_b_colors.update(sig_colors)

            # --- Color/object mapping dialog, once, only if any Format B file ----
            color_mapping = {}
            if format_b_colors:
                dlg = ColorObjectMappingDialog(
                    sorted(format_b_colors), mw.object_manager, mw.localization, mw
                )
                if dlg.exec_() != QDialog.Accepted:
                    return
                color_mapping = dlg.get_mapping()

            # --- Box conflict check, asked once for the whole batch (D7) ---------
            conflicts = []
            for info in file_info.values():
                if info['format'] == 'empty':
                    continue
                candidates = ([obj_id] if info['format'] == 'A'
                              else [color_mapping[c] for c in info['colors'] if c in color_mapping])
                conflicts += [
                    (oid, info['frame_idx']) for oid in candidates
                    if mw.object_manager.get_box(oid, info['frame_idx']) is not None
                ]
            if conflicts and not self._confirm_box_mask_conflict(len(conflicts)):
                # Cancelling drops the plain-image import; masks already imported
                # from .xcf files stay and are still reported below.
                file_info = {}

            # --- Pass 2: decompose and add_mask per (file, matched color) --------
            for path, info in file_info.items():
                if info['format'] == 'empty':
                    continue
                frame_idx, arr = info['frame_idx'], info['array']
                if info['format'] == 'A':
                    targets = [(info['colors'][0], obj_id)]
                else:
                    targets = [(c, color_mapping[c]) for c in info['colors'] if c in color_mapping]

                for color, target_obj_id in targets:
                    if target_obj_id not in mw.object_manager.object_colors:
                        created_objects = True  # newly created via "Create new object"
                    mask = np.all(arr[..., :3] == np.array(color, dtype=arr.dtype), axis=-1)
                    had_mask_before = frame_idx in mw.object_manager.object_masks.get(target_obj_id, {})
                    try:
                        out_obj_ids, out_mask_logits = mw.sam2_backend.add_mask(frame_idx, target_obj_id, mask)
                        obj_index = next(
                            (i for i, ret_id in enumerate(out_obj_ids) if ret_id == target_obj_id), None
                        )
                        if obj_index is not None:
                            stored_mask = mw.sam2_backend.process_mask_output(out_mask_logits[obj_index])
                            mw.object_manager.store_mask(target_obj_id, frame_idx, stored_mask)
                            mw.object_manager.mask_imported_frames.setdefault(target_obj_id, set()).add(frame_idx)
                            mw.object_manager.mask_import_origin.setdefault(target_obj_id, set()).add(frame_idx)
                            if had_mask_before:
                                mw.object_manager.object_corrected_frames.setdefault(target_obj_id, set()).add(frame_idx)
                            imported_count += 1
                            imported_frames.add(frame_idx)
                    except Exception as e:
                        mw.ui_manager.show_message(
                            "error", mw.localization.get_text("error"), str(e)
                        )

        if imported_count:
            if created_objects:
                mw.ui_manager.update_objects_list()
            mw.update_display(maintain_global_zoom=True)
            mw.ui_manager.refresh_export_state()
            # Multi-frame imports report both counts; a single-frame import
            # would only repeat "1 frame", so the plain message stays.
            key = ("imported_mask_imported_multi_frame" if len(imported_frames) > 1
                   else "imported_mask_imported")
            mw.ui_manager.show_message(
                "info", mw.localization.get_text("success"),
                mw.localization.get_text(key, imported_count, len(imported_frames)),
            )

    def _import_masks_from_xcf(self, xcf_paths):
        """
        Import mask layers from one or more .xcf files exported by this app
        (export_as_xcf / export_all_frames_as_xcf). No color-detection
        heuristics needed: each layer's name already carries its object
        id/name and source frame filename explicitly (see
        GimpExportManager.extract_masks_from_xcf_files). Objects are
        matched by name; an unmatched name gets a newly created object —
        unless the session currently has only the untouched default object
        (no points, no masks), in which case the person is offered to
        replace it with the imported object(s) instead of adding to it.
        Frames are matched by original filename against the current image
        folder, same as the multi-file plain-image path in import_mask().

        Temp PNGs are loaded directly via PIL (not file_manager.load_image_as_array,
        used elsewhere for user-facing color-composite detection) since these
        are internal artifacts of known RGBA format. The mask boundary is
        alpha >= 128 rather than any nonzero alpha, to ignore faint
        anti-aliasing artifacts GIMP's paint/selection tools can leave at
        edited edges.

        Returns (imported_count, created_objects, imported_frame_indices).
        """
        from PIL import Image as PILImage

        mw = self.main_window

        status, message, entries, temp_dir = self._run_with_progress(
            lambda progress_cb: mw.gimp_export_manager.extract_masks_from_xcf_files(
                xcf_paths, progress_callback=progress_cb
            ),
            message_key="gimp_import_in_progress", title_key="import_mask",
        )
        if status == STATUS_CANCELLED:
            # Nothing has been applied to the session yet at this stage — the
            # extraction only writes temp artifacts — so cancelling is
            # all-or-nothing and needs no rollback.
            shutil.rmtree(temp_dir, ignore_errors=True)
            mw.ui_manager.show_message(
                "info", mw.localization.get_text("confirmation"),
                mw.localization.get_text("gimp_import_cancelled"),
            )
            return 0, False, set()
        if status != STATUS_OK:
            mw.ui_manager.show_message(
                "error", mw.localization.get_text("export_error"), message
            )
            return 0, False, set()
        if not entries:
            shutil.rmtree(temp_dir, ignore_errors=True)
            mw.ui_manager.show_message(
                "warning", mw.localization.get_text("warning"),
                mw.localization.get_text("imported_mask_no_xcf_layers"),
            )
            return 0, False, set()

        if mw.debug_mode:
            print(f"[XCF import] {len(entries)} mask layer(s) extracted: "
                  f"{[(e['obj_name'], e['filename']) for e in entries]}")

        om = mw.object_manager

        # Offer to replace the untouched default object (no points, no masks)
        # rather than adding imported objects alongside it.
        replace_default_id = None
        existing_ids = om.get_object_ids()
        if len(existing_ids) == 1:
            only_id = existing_ids[0]
            has_points = any(
                pts['positive'] or pts['negative']
                for pts in om.object_points.get(only_id, {}).values()
            )
            has_masks = bool(om.object_masks.get(only_id))
            if not has_points and not has_masks:
                imported_names = sorted({e['obj_name'] for e in entries})
                default_name = om.object_names.get(only_id, '')
                if imported_names != [default_name]:
                    reply = mw.ui_manager.show_message(
                        "question", mw.localization.get_text("confirmation"),
                        mw.localization.get_text(
                            "gimp_import_replace_default_object", default_name, len(imported_names)
                        ),
                    )
                    if reply == QMessageBox.Yes:
                        replace_default_id = only_id

        current_basenames = {
            os.path.basename(p): idx
            for idx, p in enumerate(mw.image_manager.get_all_image_paths())
        }
        name_to_obj_id = {name: oid for oid, name in om.object_names.items()}

        # Box conflict check, asked once for the whole batch (D7). Objects
        # created later by this import have no box, hence no conflict.
        conflicts = [
            e for e in entries
            if e['obj_name'] in name_to_obj_id and e['filename'] in current_basenames
            and om.get_box(name_to_obj_id[e['obj_name']],
                           current_basenames[e['filename']]) is not None
        ]
        if conflicts and not self._confirm_box_mask_conflict(len(conflicts)):
            shutil.rmtree(temp_dir, ignore_errors=True)
            return 0, False, set()

        imported_count = 0
        created_objects = False
        imported_frame_indices = set()
        unmatched_frames = set()

        try:
            for entry in entries:
                frame_idx = current_basenames.get(entry['filename'])
                if frame_idx is None:
                    unmatched_frames.add(entry['filename'])
                    if mw.debug_mode:
                        print(f"[XCF import] Skipped (no matching frame): {entry['filename']}")
                    continue

                target_obj_id = name_to_obj_id.get(entry['obj_name'])
                if target_obj_id is None:
                    target_obj_id = om.add_new_object()
                    om.update_object_name(target_obj_id, entry['obj_name'])
                    name_to_obj_id[entry['obj_name']] = target_obj_id
                    created_objects = True

                try:
                    with PILImage.open(entry['path']) as im:
                        arr = np.array(im.convert('RGBA'))
                except Exception as e:
                    mw.ui_manager.show_message(
                        "error", mw.localization.get_text("error"), str(e)
                    )
                    continue
                mask = arr[..., 3] >= 128
                if mw.debug_mode:
                    print(f"[XCF import] {entry['obj_name']} / frame {frame_idx}: "
                          f"active pixels = {mask.sum()}")
                if not mask.any():
                    continue  # fully transparent layer — nothing to import

                had_mask_before = frame_idx in om.object_masks.get(target_obj_id, {})
                try:
                    out_obj_ids, out_mask_logits = mw.sam2_backend.add_mask(frame_idx, target_obj_id, mask)
                    obj_index = next(
                        (i for i, ret_id in enumerate(out_obj_ids) if ret_id == target_obj_id), None
                    )
                    if obj_index is not None:
                        stored_mask = mw.sam2_backend.process_mask_output(out_mask_logits[obj_index])
                        om.store_mask(target_obj_id, frame_idx, stored_mask)
                        om.mask_imported_frames.setdefault(target_obj_id, set()).add(frame_idx)
                        om.mask_import_origin.setdefault(target_obj_id, set()).add(frame_idx)
                        if had_mask_before:
                            om.object_corrected_frames.setdefault(target_obj_id, set()).add(frame_idx)
                        imported_count += 1
                        imported_frame_indices.add(frame_idx)
                except Exception as e:
                    mw.ui_manager.show_message(
                        "error", mw.localization.get_text("error"), str(e)
                    )
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        if replace_default_id is not None and created_objects and replace_default_id in om.object_colors:
            om.remove_object(replace_default_id)
            remaining_ids = om.get_object_ids()
            if remaining_ids:
                om.current_object_id = remaining_ids[0]
                om.selected_object_ids = {remaining_ids[0]}
            mw.ui_manager.update_object_ui()

        if unmatched_frames:
            names_str = '\n'.join(f"  • {n}" for n in sorted(unmatched_frames)[:10])
            if len(unmatched_frames) > 10:
                names_str += f"\n  ({len(unmatched_frames) - 10} more\u2026)"
            mw.ui_manager.show_message(
                "warning", mw.localization.get_text("warning"),
                mw.localization.get_text(
                    "imported_mask_filenames_unmatched", len(unmatched_frames), names_str
                ),
            )

        return imported_count, created_objects, imported_frame_indices
