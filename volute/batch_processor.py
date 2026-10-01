"""
Batch Processor
Headless batch processing pipeline for SAM2 segmentation tasks
"""

import os
import json
import gzip
import pickle
import numpy as np
from collections import defaultdict
from PyQt5.QtGui import QColor
from .object_manager import ObjectManager, _default_points
from .imported_point_manager import ImportedPointManager

# ------------------------------------------------------------------
# Minimal main_window proxy for SAM2StateManager compatibility
# ------------------------------------------------------------------

class _SilentUIManager:
    """No-op UI manager used in headless context"""
    def show_message(self, *args, **kwargs):
        return None
    def get_control(self, *args, **kwargs):
        return None


class MainWindowProxy:
    """
    Minimal proxy exposing the attributes SAM2StateManager requires,
    without depending on the full Qt main window.

    If SAM2StateManager.export_sam2_inference_state references additional
    attributes, add them here.
    """
    def __init__(self, sam2_backend, object_manager, image_manager_proxy,
                 localization, debug_mode=False):
        self.sam2_backend   = sam2_backend
        self.object_manager = object_manager
        self.image_manager  = image_manager_proxy
        self.localization   = localization
        self.debug_mode     = debug_mode
        self.ui_manager     = _SilentUIManager()


class _ImageManagerProxy:
    """Minimal image manager proxy carrying only what SAM2StateManager needs"""
    def __init__(self, image_paths, current_folder):
        self.image_paths    = image_paths
        self.current_folder = current_folder
        self.current_image_idx = 0

    def has_images(self):
        return bool(self.image_paths)

    def get_current_image(self):
        # Not needed for headless export; returning None is handled by the caller
        return None

    def get_current_image_info(self):
        if not self.image_paths:
            return None
        from PIL import Image as PILImage
        with PILImage.open(self.image_paths[0]) as img:
            w, h = img.size
        return {'height': h, 'width': w,
                'index': 0, 'total_images': len(self.image_paths),
                'path': self.image_paths[0]}

    def get_all_image_paths(self):
        return list(self.image_paths)


# ------------------------------------------------------------------
# Batch Processor
# ------------------------------------------------------------------

class BatchProcessor:
    """
    Headless processor for batch SAM2 segmentation.

    Reuses the application's existing SAM2Backend instance to avoid
    reloading the model for each item.
    """

    def __init__(self, sam2_backend, localization, debug_mode=False):
        self.sam2_backend = sam2_backend
        self.localization = localization
        self.debug_mode   = debug_mode
        self._cancelled   = False

    def cancel(self):
        """Request cancellation of the running batch"""
        self._cancelled = True

    def _is_point_mode(self):
        """Return True when the backend is SAM2++ in point task."""
        return (getattr(self.sam2_backend, 'is_sam2plus', False) and
                getattr(self.sam2_backend, 'sam2plus_task', 'mask') == 'point')

    # ------------------------------------------------------------------
    # Data loading helpers
    # ------------------------------------------------------------------

    def load_sam2_file(self, file_path):
        """Load object data dict from a .volute project file"""
        with gzip.open(file_path, 'rb') as f:
            project_data = pickle.load(f)
        return project_data.get('object_data', {})

    def get_image_paths(self, folder):
        """Return sorted image paths from folder using the backend's file logic"""
        files = self.sam2_backend._get_image_files(folder)
        return [os.path.join(folder, f) for f in files]

    def build_object_manager(self, object_data):
        """Construct an ObjectManager populated from deserialized object_data"""
        om = ObjectManager(self.localization, self.debug_mode)
        for attr in ('object_points', 'object_masks', 'object_colors',
                     'object_markers', 'object_names', 'object_show_points',
                     'object_centroids', 'object_boxes',
                     'mask_imported_frames', 'mask_import_origin'):
            getattr(om, attr).clear()

        for obj_id, frames in object_data.get('object_points', {}).items():
            oid = int(obj_id)
            om.object_points[oid] = defaultdict(_default_points)
            for frame_idx, pts in frames.items():
                om.object_points[oid][int(frame_idx)] = {
                    'positive': pts.get('positive', []),
                    'negative': pts.get('negative', [])
                }

        for obj_id, frames in object_data.get('object_boxes', {}).items():
            om.object_boxes[int(obj_id)] = {
                int(frame_idx): tuple(box) for frame_idx, box in frames.items()
            }

        # Imported masks, when the project file carries them: stored through
        # store_mask so centroids/hulls/contours follow, and flagged so the
        # reference-frame pass re-registers them with SAM2 as conditioning.
        for obj_id, frames in object_data.get('object_masks', {}).items():
            oid = int(obj_id)
            for frame_idx, mask_data in frames.items():
                if isinstance(mask_data, dict) and 'data' in mask_data:
                    mask = mask_data['data']
                    if mask_data.get('dtype') == 'bool':
                        mask = mask.astype(bool)
                    om.store_mask(oid, int(frame_idx), mask)

        for obj_id, frames in object_data.get('mask_import_origin', {}).items():
            oid = int(obj_id)
            restored = {int(f) for f in frames if int(f) in om.object_masks.get(oid, {})}
            if restored:
                om.mask_import_origin[oid] = set(restored)
                om.mask_imported_frames[oid] = set(restored)

        for obj_id, colors in object_data.get('object_colors', {}).items():
            oid = int(obj_id)
            om.object_colors[oid] = {
                ctype: QColor(cd['red'], cd['green'], cd['blue'], cd['alpha'])
                for ctype, cd in colors.items()
            }

        for obj_id, name in object_data.get('object_names', {}).items():
            om.object_names[int(obj_id)] = name
        for obj_id, marker in object_data.get('object_markers', {}).items():
            om.object_markers[int(obj_id)] = marker
        for obj_id, sp in object_data.get('object_show_points', {}).items():
            om.object_show_points[int(obj_id)] = sp

        om.current_object_id = int(object_data.get(
            'current_object_id',
            min(om.object_colors.keys()) if om.object_colors else 1
        ))
        return om

    def get_reference_frame(self, object_manager, forced_ref_frame=None):
        """Return reference frame index (forced override, or the first frame
        carrying any object definition: points, a box, or an imported mask)"""
        if forced_ref_frame is not None:
            return int(forced_ref_frame)
        frames = [
            frame_idx
            for frames in object_manager.object_points.values()
            for frame_idx, pts in frames.items()
            if pts['positive'] or pts['negative']
        ]
        for boxes in object_manager.object_boxes.values():
            frames.extend(boxes.keys())
        for imported in object_manager.mask_import_origin.values():
            frames.extend(imported)
        return min(frames) if frames else 0

    # ------------------------------------------------------------------
    # Core processing steps
    # ------------------------------------------------------------------

    def _objects_on_reference_frame(self, object_manager, ref_frame_idx):
        """Objects carrying a definition on the reference frame: points, a box,
        or an imported mask."""
        objects = {
            obj_id for obj_id, frames in object_manager.object_points.items()
            if (frames.get(ref_frame_idx, {}).get('positive') or
                frames.get(ref_frame_idx, {}).get('negative'))
        }
        objects |= {obj_id for obj_id, boxes in object_manager.object_boxes.items()
                    if ref_frame_idx in boxes}
        objects |= {obj_id for obj_id, frames in object_manager.mask_import_origin.items()
                    if ref_frame_idx in frames}
        return sorted(objects)

    def _register_reference_prompts(self, object_manager, obj_id, ref_frame_idx,
                                    image_w, image_h):
        """Register an object's conditioning on the reference frame, mirroring the
        interactive flow: an imported mask is resent first, since the prompt call
        would otherwise discard it, then the points and box.

        Returns the backend's (obj_ids, mask_logits), or None when the object has
        nothing to register on this frame.
        """
        result = None
        if ref_frame_idx in object_manager.mask_import_origin.get(obj_id, set()):
            stored_mask = object_manager.object_masks.get(obj_id, {}).get(ref_frame_idx)
            if stored_mask is not None:
                result = self.sam2_backend.add_mask(ref_frame_idx, obj_id, stored_mask)

        points, labels = object_manager.get_points_for_sam(
            obj_id, ref_frame_idx, image_w, image_h
        )
        box = object_manager.get_box_for_sam(obj_id, ref_frame_idx, image_w, image_h)
        if len(points) == 0 and box is None:
            return result

        return self.sam2_backend.predict_mask(
            ref_frame_idx, obj_id, points, labels, box=box
        )

    def predict_reference_frame(self, object_manager, ref_frame_idx,
                                image_w, image_h,
                                mask_progress_callback=None):
        """
        Run SAM2 prediction on the reference frame for every object defined
        there — by points, by a box, or by an imported mask.

        Args:
            mask_progress_callback: optional callable(current, total, label)

        Returns:
            (list of predicted obj_ids, list of error strings)
        """
        objects_to_predict = self._objects_on_reference_frame(object_manager, ref_frame_idx)
        total_objs = len(objects_to_predict)
        predicted, errors = [], []

        for obj_idx, obj_id in enumerate(objects_to_predict):
            if mask_progress_callback:
                mask_progress_callback(
                    obj_idx, total_objs,
                    f"Predicting object {obj_id} ({obj_idx + 1}/{total_objs})"
                )

            try:
                result = self._register_reference_prompts(
                    object_manager, obj_id, ref_frame_idx, image_w, image_h
                )
                if result is None:
                    continue
                out_obj_ids, out_mask_logits = result
                for i, ret_id in enumerate(out_obj_ids):
                    if ret_id == obj_id and i < out_mask_logits.shape[0]:
                        mask = self.sam2_backend.process_mask_output(out_mask_logits[i])
                        object_manager.store_mask(obj_id, ref_frame_idx, mask)
                        predicted.append(obj_id)
            except Exception as e:
                errors.append(f"Prediction error (obj {obj_id}): {e}")

        if mask_progress_callback:
            mask_progress_callback(total_objs, total_objs, "Prediction complete")

        return predicted, errors

    def _consume_propagation(self, object_manager, start_frame_idx, reverse,
                             total_frames, label, report, skip_existing=False):
        """Consume one propagation span, storing every mask it yields for the
        objects the project defines.

        skip_existing leaves frames that already carry a mask untouched — the
        backward pass must not overwrite what the forward pass produced.

        Returns (frames_processed, error string or None).
        """
        frame_count = 0
        report(0, total_frames, f"{label}…")
        try:
            for frame_idx, out_obj_ids, out_mask_logits in \
                    self.sam2_backend.propagate_masks(start_frame_idx, reverse=reverse):
                for i, obj_id in enumerate(out_obj_ids):
                    if obj_id not in object_manager.object_colors or i >= out_mask_logits.shape[0]:
                        continue
                    if skip_existing and frame_idx in object_manager.object_masks.get(obj_id, {}):
                        continue
                    mask = self.sam2_backend.process_mask_output(out_mask_logits[i])
                    object_manager.store_mask(obj_id, frame_idx, mask)
                frame_count += 1
                report(frame_count, total_frames, f"{label}… (frame {frame_idx})")
                if self._cancelled:
                    break
        except Exception as e:
            return frame_count, f"{label} error: {e}"
        return frame_count, None

    def propagate_video(self, object_manager, ref_frame_idx,
                        image_folder, image_w, image_h, obj_ids,
                        total_frames=0, mask_progress_callback=None):
        """
        Propagate masks forward (and backward if ref_frame_idx > 0).

        Args:
            total_frames:           Total frame count, used for progress reporting.
            mask_progress_callback: optional callable(current, total, label)

        Returns:
            List of error strings.
        """
        errors = []

        def _report(current, total, label):
            if mask_progress_callback:
                mask_progress_callback(current, total, label)

        if self._is_point_mode():
            return self._propagate_point_tracks_video(
                object_manager, ref_frame_idx, mask_progress_callback
            )

        # Forward pass
        _, error = self._consume_propagation(
            object_manager, ref_frame_idx, False, total_frames, "Forward propagation", _report)
        if error:
            errors.append(error)

        # Backward pass (only when reference is not the first frame)
        if ref_frame_idx > 0 and not self._cancelled:
            try:
                self.sam2_backend.reset_state()
                self.sam2_backend.init_inference_state(image_folder)

                # Same conditioning as the forward pass — mask, then points and box
                for obj_id in obj_ids:
                    self._register_reference_prompts(
                        object_manager, obj_id, ref_frame_idx, image_w, image_h
                    )
            except Exception as e:
                errors.append(f"Backward propagation error: {e}")
                return errors

            _, error = self._consume_propagation(
                object_manager, ref_frame_idx, True, ref_frame_idx, "Backward propagation",
                _report, skip_existing=True)
            if error:
                errors.append(error)

        return errors

    def _predict_point_track_reference(self, object_manager, ref_frame_idx,
                                        image_w, image_h, mask_progress_callback=None):
        """Predict initial tracking points on reference frame (point mode)."""
        objects = [
            oid for oid, frames in object_manager.object_points.items()
            if frames.get(ref_frame_idx, {}).get('positive')
        ]
        predicted, errors = [], []
        for idx, obj_id in enumerate(objects):
            if mask_progress_callback:
                mask_progress_callback(idx, len(objects),
                                       f"Point-tracking obj {obj_id}")
            pos = object_manager.object_points[obj_id][ref_frame_idx]['positive']
            if not pos:
                continue
            norm_x, norm_y = pos[0]
            px, py = int(norm_x * image_w), int(norm_y * image_h)
            try:
                out_ids, out_heatmaps = self.sam2_backend.predict_point_track(
                    ref_frame_idx, obj_id, (px, py)
                )
                for i, ret_id in enumerate(out_ids):
                    if ret_id == obj_id and i < len(out_heatmaps):
                        coord = self.sam2_backend._extract_point_from_heatmap(
                            out_heatmaps[i]
                        )
                        if coord is not None:
                            if obj_id not in object_manager.object_tracked_points:
                                object_manager.object_tracked_points[obj_id] = {}
                            object_manager.object_tracked_points[obj_id][ref_frame_idx] = coord
                            predicted.append(obj_id)
            except Exception as e:
                errors.append(f"Point track prediction error (obj {obj_id}): {e}")
        if mask_progress_callback:
            mask_progress_callback(len(objects), len(objects), "Done")
        return predicted, errors
    
    def _propagate_point_tracks_video(self, object_manager, ref_frame_idx,
                                       mask_progress_callback=None):
        """Propagate point tracks forward (and backward) through the video (point mode)."""
        errors = []
        frame_count = 0
    
        def _report(cur, tot, label):
            if mask_progress_callback:
                mask_progress_callback(cur, tot, label)
    
        _report(0, 0, "Forward point-track propagation…")
        try:
            for frame_idx, coords in self.sam2_backend.propagate_point_tracks(
                ref_frame_idx, reverse=False
            ):
                for obj_id, (x, y) in coords.items():
                    if obj_id not in object_manager.object_tracked_points:
                        object_manager.object_tracked_points[obj_id] = {}
                    object_manager.object_tracked_points[obj_id][frame_idx] = (x, y)
                frame_count += 1
                _report(frame_count, 0, f"Forward… (frame {frame_idx})")
                if self._cancelled:
                    return errors
        except Exception as e:
            errors.append(f"Forward point-track propagation error: {e}")
    
        if ref_frame_idx > 0 and not self._cancelled:
            try:
                for frame_idx, coords in self.sam2_backend.propagate_point_tracks(
                    ref_frame_idx, reverse=True
                ):
                    for obj_id, (x, y) in coords.items():
                        if obj_id not in object_manager.object_tracked_points:
                            object_manager.object_tracked_points[obj_id] = {}
                        if frame_idx not in object_manager.object_tracked_points[obj_id]:
                            object_manager.object_tracked_points[obj_id][frame_idx] = (x, y)
                    frame_count += 1
                    _report(frame_count, 0, f"Backward… (frame {frame_idx})")
                    if self._cancelled:
                        return errors
            except Exception as e:
                errors.append(f"Backward point-track propagation error: {e}")
    
        return errors

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------

    def export_masked_images(self, object_manager, image_paths, output_folder,
                             bg_opacity=1.0):
        """Export images with coloured mask overlays."""
        from PIL import Image as PILImage

        os.makedirs(output_folder, exist_ok=True)
        exported = 0

        for frame_idx, image_path in enumerate(image_paths):
            has_mask = any(
                frame_idx in masks
                for masks in object_manager.object_masks.values()
            )
            if not has_mask:
                continue

            try:
                with PILImage.open(image_path) as img:
                    img_rgb = img.convert('RGB')
                    w, h = img_rgb.size

                    # Blend image with white background to apply background opacity
                    if bg_opacity < 1.0:
                        white = PILImage.new('RGB', (w, h), (255, 255, 255))
                        img_rgb = PILImage.blend(white, img_rgb, bg_opacity)

                    img = img_rgb.convert('RGBA')

                    for obj_id, masks in sorted(object_manager.object_masks.items()):
                        if frame_idx not in masks:
                            continue
                        mask = masks[frame_idx]
                        while len(mask.shape) > 2:
                            mask = mask.squeeze(0)
                        color = object_manager.object_colors[obj_id]['mask']
                        overlay = np.zeros((h, w, 4), dtype=np.uint8)
                        overlay[mask.astype(bool)] = [
                            color.red(), color.green(),
                            color.blue(), color.alpha()
                        ]
                        img = PILImage.alpha_composite(
                            img, PILImage.fromarray(overlay, 'RGBA')
                        )

                    out_path = os.path.join(output_folder, os.path.basename(image_path))
                    img.convert('RGB').save(out_path, quality=95)
                    exported += 1

            except Exception as e:
                if self.debug_mode:
                    print(f"Image export error ({image_path}): {e}")

        return exported

    def export_centroids(self, object_manager, image_paths, output_path):
        """Export centroids via CentroidExporter, with JSON fallback"""
        try:
            from .exporters import CentroidExporter
            exporter = CentroidExporter(self.debug_mode)
            return exporter.export_centroids(
                object_manager.object_centroids,
                object_manager.object_names,
                image_paths,
                output_path
            )
        except Exception as e:
            if self.debug_mode:
                print(f"CentroidExporter failed ({e}), using JSON fallback")
            return self._export_centroids_json(object_manager, image_paths, output_path)

    def _export_centroids_json(self, object_manager, image_paths, output_path):
        """JSON fallback for centroid export"""
        image_names = [os.path.basename(p) for p in image_paths]
        data = {'objects': {}}
        for obj_id, frames in object_manager.object_centroids.items():
            obj_name = object_manager.object_names.get(obj_id, f"Object {obj_id}")
            data['objects'][str(obj_id)] = {
                'name': obj_name,
                'centroids': {
                    str(fidx): {
                        'x': float(cx), 'y': float(cy),
                        'image': image_names[fidx] if fidx < len(image_names) else str(fidx)
                    }
                    for fidx, (cx, cy) in frames.items()
                }
            }
        json_path = os.path.splitext(output_path)[0] + '.json'
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
        return sum(len(obj['centroids']) for obj in data['objects'].values())

    def export_coordinates(self, object_manager, image_paths, output_path):
        """
        Export mask pixel coordinates for all objects to a single JSON file.

        Format: { "images": [...], "objects": { "1": { "name": ..., "frames": {
            "0": { "image": ..., "pixel_count": N, "x": [...], "y": [...] } } } } }
        """
        image_names = [os.path.basename(p) for p in image_paths]
        data = {'images': image_names, 'objects': {}}

        for obj_id in sorted(object_manager.object_masks.keys()):
            obj_name = object_manager.object_names.get(obj_id, f"Object {obj_id}")
            frames_data = {}
            for frame_idx, mask in object_manager.object_masks[obj_id].items():
                while len(mask.shape) > 2:
                    mask = mask.squeeze(0)
                mask_bool = mask.astype(bool)
                y_coords, x_coords = np.where(mask_bool)
                frames_data[str(frame_idx)] = {
                    'image': image_names[frame_idx] if frame_idx < len(image_names) else str(frame_idx),
                    'pixel_count': int(mask_bool.sum()),
                    'x': x_coords.tolist(),
                    'y': y_coords.tolist()
                }
            data['objects'][str(obj_id)] = {'name': obj_name, 'frames': frames_data}

        with open(output_path, 'w') as f:
            json.dump(data, f)

        return sum(len(obj['frames']) for obj in data['objects'].values())

    def load_reference_points(self, file_path):
        """Load reference_point_data from a .volute project file."""
        with gzip.open(file_path, 'rb') as f:
            project_data = pickle.load(f)
        return project_data.get('reference_point_data', {})

    def load_imported_points(self, file_path):
        """Load imported_point_data from a .volute project file, mirroring load_reference_points()."""
        with gzip.open(file_path, 'rb') as f:
            project_data = pickle.load(f)
        return project_data.get('imported_point_data', {})

    def import_tracked_points_for_item(self, tracked_points_file, image_paths,
                                       imported_point_manager):
        """
        Headless port of main_window.import_tracked_points's parsing/validation/
        matching logic, populating imported_point_manager in place.
    
        All checks are non-blocking (returned as warning strings) per the batch
        headless-validation policy, except a hard parse failure or zero filename
        matches, which raises — the caller is responsible for treating that as a
        skipped import step rather than an item failure.
        """
        from .file_utils import FileManager
        warnings = []
    
        rows = FileManager.read_tracked_points_file(tracked_points_file)
        if not rows:
            return warnings
    
        current_basenames = [os.path.basename(p) for p in image_paths]
        imported_filenames = sorted({r['original_filename'] for r in rows})
    
        if len(imported_filenames) != len(current_basenames):
            warnings.append(
                f"Tracked points frame count mismatch: {len(imported_filenames)} "
                f"imported vs {len(current_basenames)} in folder"
            )
    
        basename_to_frame = {name: idx for idx, name in enumerate(current_basenames)}
        matched_rows = []
        unmatched = set()
        for r in rows:
            frame_idx = basename_to_frame.get(r['original_filename'])
            if frame_idx is None:
                unmatched.add(r['original_filename'])
            else:
                matched_rows.append((r['name'], frame_idx, r['x_px'], r['y_px']))
    
        if not matched_rows:
            raise ValueError("None of the imported filenames match the current image folder")
    
        if unmatched:
            warnings.append(f"{len(unmatched)} imported filename(s) unmatched and skipped")
    
        for name, frame_idx, x_px, y_px in matched_rows:
            imported_point_manager.add_point(name, frame_idx, x_px, y_px)
    
        if image_paths:
            from PIL import Image as PILImage
            with PILImage.open(image_paths[0]) as img:
                width, height = img.size
            imported_names = sorted({name for name, *_ in matched_rows})
            flagged = [
                name for name in imported_names
                if imported_point_manager.out_of_bounds_count(name, width, height) > 0
            ]
            if flagged:
                warnings.append(f"Out-of-bounds imported points for: {', '.join(flagged[:10])}")
    
        return warnings

    def export_point_mask_analysis(self, om, imported_point_manager, image_paths,
                                   output_path, pairs=None):
        """Thin wrapper around ImportedPointMaskAnalysisExporter.export_point_mask_analysis."""
        from .imported_point_mask_analysis_exporter import ImportedPointMaskAnalysisExporter
        exporter = ImportedPointMaskAnalysisExporter(debug_mode=self.debug_mode)
        return exporter.export_point_mask_analysis(
            object_masks=om.object_masks,
            object_names=om.object_names,
            object_centroids=om.object_centroids,
            object_hulls=om.object_hulls,
            object_contours=om.object_contours,
            imported_point_manager=imported_point_manager,
            image_paths=image_paths,
            export_file=output_path,
            pairs=pairs,
            total_frames=len(image_paths),
        )

    def _resolve_named_pairs(self, raw_pairs, om, target_key_fn, target_type_const):
        """
        Resolve name-based (object, target[, target_type]) pairs from the batch
        dialog into (obj_id, target_type, target_key) triples.
    
        target_key_fn(target_raw, target_type, name_to_id) -> resolved target key,
        or None if invalid/unknown. Pairs may be 2-tuples (object, target), which
        default to target_type_const, or 3-tuples with an explicit target type
        (used by the reference-point export, which mixes ref points and objects).
        """
        if raw_pairs is None:
            return None
        name_to_id = {v: k for k, v in om.object_names.items()}
        resolved = []
        for item in raw_pairs:
            if len(item) == 2:
                obj_raw, tgt_raw, t_type = item[0], item[1], target_type_const
            else:
                obj_raw, tgt_raw, t_type = item
            obj_id = name_to_id.get(obj_raw) if isinstance(obj_raw, str) else obj_raw
            if obj_id is None:
                continue
            tgt_key = target_key_fn(tgt_raw, t_type, name_to_id)
            if tgt_key is not None:
                resolved.append((obj_id, t_type, tgt_key))
        return resolved or None

    def export_closest_mask_points(
        self, object_manager, ref_point_manager, image_paths, output_path,
        pairs=None, include_object_distances=False
    ) -> int:
        """Export closest mask points via ClosestMaskPointExporter, JSON fallback."""
        try:
            from .reference_point_exporter import ClosestMaskPointExporter
            exporter = ClosestMaskPointExporter(debug_mode=self.debug_mode)
            return exporter.export_closest_mask_points(
                object_masks=object_manager.object_masks,
                object_names=object_manager.object_names,
                reference_point_manager=ref_point_manager,
                image_paths=image_paths,
                export_file=output_path,
                pairs=pairs,
                total_frames=len(image_paths),
                include_object_distances=include_object_distances,
            )
        except Exception as e:
            if self.debug_mode:
                print(f"ClosestMaskPointExporter failed ({e}), using JSON fallback")
            return self._export_closest_points_json(
                object_manager, ref_point_manager, image_paths, output_path, pairs
            )

    def _export_closest_points_json(
            self, object_manager, ref_point_manager, image_paths, output_path, pairs
        ) -> int:
            """JSON fallback for closest mask points export."""
            import json
            total = len(image_paths)
            ref_names = ref_point_manager.get_names()
            if pairs is None:
                pairs = [
                    (oid, 'ref_point', rn)
                    for oid in sorted(object_manager.object_masks.keys())
                    for rn in ref_names
                ]
            rows = []
            for pair in pairs:
                # Normalize 2-tuples (legacy) to 3-tuples
                if len(pair) == 2:
                    obj_id, t_key, t_type = pair[0], pair[1], 'ref_point'
                else:
                    obj_id, t_type, t_key = pair
    
                if obj_id not in object_manager.object_masks:
                    continue
                obj_name = object_manager.object_names.get(obj_id, f"Object {obj_id}")
    
                for frame_idx in range(total):
                    if frame_idx not in object_manager.object_masks[obj_id]:
                        continue
    
                    src_mask = object_manager.object_masks[obj_id][frame_idx]
                    while len(src_mask.shape) > 2:
                        src_mask = src_mask.squeeze(0)
                    H, W = src_mask.shape
                    ys, xs = np.where(src_mask.astype(bool))
                    if len(xs) == 0:
                        continue
    
                    if t_type == 'ref_point':
                        coords = ref_point_manager.get_interpolated_coords(t_key, frame_idx)
                        if coords is None:
                            continue
                        ref_px, ref_py = coords[0] * W, coords[1] * H
                        target_label = t_key
                    else:  # inter-object: true minimum inter-mask distance
                        if t_key not in object_manager.object_masks or \
                                frame_idx not in object_manager.object_masks[t_key]:
                            continue
                        tgt_mask = object_manager.object_masks[t_key][frame_idx]
                        while len(tgt_mask.shape) > 2:
                            tgt_mask = tgt_mask.squeeze(0)
                        tys_t, txs_t = np.where(tgt_mask.astype(bool))
                        if len(txs_t) == 0:
                            continue
                        # Find closest pixel of target mask to source mask
                        dx = xs[:, None].astype(np.float32) - txs_t[None, :]
                        dy = ys[:, None].astype(np.float32) - tys_t[None, :]
                        dist_mat = np.hypot(dx, dy)
                        si, ti = np.unravel_index(np.argmin(dist_mat), dist_mat.shape)
                        ref_px, ref_py = float(txs_t[ti]), float(tys_t[ti])
                        target_label = object_manager.object_names.get(t_key, f"Object {t_key}")
    
                    dists = np.hypot(xs - ref_px, ys - ref_py)
                    idx_min = np.argmin(dists)
                    fname = (
                        os.path.basename(image_paths[frame_idx])
                        if frame_idx < len(image_paths) else str(frame_idx)
                    )
                    rows.append({
                        'Object_Name':       obj_name,
                        'Object_ID':         obj_id,
                        'Target_Type':       t_type,
                        'Target_Name':       target_label,
                        'Frame_Index':       frame_idx,
                        'Original_Filename': fname,
                        'Closest_X':         int(xs[idx_min]),
                        'Closest_Y':         int(ys[idx_min]),
                        'Distance_px':       float(dists[idx_min]),
                        'Ref_X_px':          float(ref_px),
                        'Ref_Y_px':          float(ref_py),
                    })
    
            json_path = os.path.splitext(output_path)[0] + '.json'
            with open(json_path, 'w') as f:
                json.dump(rows, f, indent=2)
            return len(rows)

    def export_inference_state(self, output_path, object_manager=None,
                               image_paths=None, image_folder=None):
        """
        Export current SAM2 inference state using SAM2StateManager when possible,
        falling back to a raw compressed pickle.

        Args:
            object_manager: ObjectManager instance for the current item.
            image_paths:    Sorted list of image paths for the current item.
            image_folder:   Source image folder path.

        Raises:
            RuntimeError: if no inference state is available. The pickle
                          fallback cannot help in that case, and writing it out
                          would produce a file that looks like a valid export.
        """
        if not self.sam2_backend.inference_state:
            raise RuntimeError("no SAM2 inference state to export")

        try:
            from .sam2_state_manager import SAM2StateManager
            img_proxy = _ImageManagerProxy(image_paths or [], image_folder or '')
            proxy = MainWindowProxy(
                sam2_backend=self.sam2_backend,
                object_manager=object_manager,
                image_manager_proxy=img_proxy,
                localization=self.localization,
                debug_mode=self.debug_mode
            )
            manager = SAM2StateManager(proxy)
            if manager.export_sam2_inference_state(output_path):
                return
            reason = "structured export rejected the state"
        except Exception as e:
            reason = str(e)

        if self.debug_mode:
            print(f"SAM2StateManager export failed ({reason}), using pickle fallback")
        with gzip.open(output_path, 'wb') as f:
            pickle.dump(self.sam2_backend.inference_state, f,
                        protocol=pickle.HIGHEST_PROTOCOL)

    # ------------------------------------------------------------------
    # Main entry points
    # ------------------------------------------------------------------

    def process_item(self, sam2_file, image_folder, options, output_dir,
                 ref_frame=None, tracked_points_file=None,
                 progress_callback=None, mask_progress_callback=None):
        """
        Process a single (sam2_file, image_folder) pair.

        Args:
            sam2_file:              Path to .volute project file.
            image_folder:           Path to image folder.
            options:                Dict of processing options (see process_batch).
            output_dir:             Root output directory.
            ref_frame:              Optional reference frame index override.
            progress_callback:      Optional callable(message: str) for step messages.
            mask_progress_callback: Optional callable(current, total, label) for
                                    per-frame / per-object progress during SAM2 tasks.

        Returns:
            Dict: success (bool), errors (list), output_folder (str), stats (dict).
        """
        def _log(msg):
            if progress_callback:
                progress_callback(msg)
            if self.debug_mode:
                print(f"[Batch] {msg}")

        folder_name = os.path.basename(image_folder.rstrip(os.sep))
        item_out = os.path.join(output_dir, folder_name)
        os.makedirs(item_out, exist_ok=True)

        result = {'success': False, 'errors': [], 'warnings': [],
                  'output_folder': item_out, 'stats': {}}

        try:
            _log(f"Loading {os.path.basename(sam2_file)}…")
            object_data = self.load_sam2_file(sam2_file)
            om = self.build_object_manager(object_data)
            om.hull_smoothing = options.get('hull_smoothing', 0.0)
            om.contour_smoothing  = options.get('contour_smoothing', 0.0)

            if not om.object_colors:
                result['errors'].append("No objects found in .volute file")
                return result

            _log("Loading images…")
            image_paths = self.get_image_paths(image_folder)
            if not image_paths:
                result['errors'].append(f"No images found in {image_folder}")
                return result
            
            # Import tracked points (per-item file takes priority over
            # imported_point_data already stored in the .volute file; all
            # validation checks are non-blocking warnings in headless batch mode)
            ipm = ImportedPointManager()
            try:
                if tracked_points_file:
                    _log("Importing tracked points…")
                    import_warnings = self.import_tracked_points_for_item(
                        tracked_points_file, image_paths, ipm
                    )
                    result['warnings'].extend(import_warnings)
                else:
                    imported_data = self.load_imported_points(sam2_file)
                    for name, frames in imported_data.get('imported_points', {}).items():
                        for fidx, coords in frames.items():
                            ipm.add_point(name, int(fidx), float(coords[0]), float(coords[1]))
            except Exception as e:
                result['warnings'].append(f"Tracked points import skipped: {e}")
            
            from PIL import Image as PILImage
            with PILImage.open(image_paths[0]) as img:
                image_w, image_h = img.size

            ref_frame_idx = self.get_reference_frame(om, ref_frame)
            _log(f"Reference frame: {ref_frame_idx} / {len(image_paths) - 1}")

            _log("Initializing SAM2…")
            self.sam2_backend.reset_state()
            if not self.sam2_backend.init_inference_state(image_folder):
                result['errors'].append("SAM2 initialization failed")
                return result

            if self._cancelled:
                return result

            # Predict reference frame
            _log("Predicting reference frame…")
            obj_ids_predicted, pred_errors = self.predict_reference_frame(
                om, ref_frame_idx, image_w, image_h,
                mask_progress_callback=mask_progress_callback
            )
            result['errors'].extend(pred_errors)
            result['stats']['predicted_objects'] = len(obj_ids_predicted)

            if options.get('export_state_predict', False):
                _log("Exporting inference state (prediction)…")
                state_path = os.path.join(item_out, f"{folder_name}_predict.voluteinf")
                try:
                    self.export_inference_state(state_path, om, image_paths, image_folder)
                except Exception as e:
                    result['errors'].append(f"State export (predict): {e}")

            if self._cancelled:
                return result

            if options.get('propagate', True):
                _log("Propagating masks…")
                prop_errors = self.propagate_video(
                    om, ref_frame_idx, image_folder,
                    image_w, image_h, obj_ids_predicted,
                    total_frames=len(image_paths),
                    mask_progress_callback=mask_progress_callback
                )
                result['errors'].extend(prop_errors)
                result['stats']['total_masks'] = sum(
                    len(masks) for masks in om.object_masks.values()
                )

            if self._cancelled:
                return result

            if options.get('export_state_propagate', False) and options.get('propagate', True):
                _log("Exporting inference state (propagation)…")
                state_path = os.path.join(item_out, f"{folder_name}_propagate.voluteinf")
                try:
                    self.export_inference_state(state_path, om, image_paths, image_folder)
                except Exception as e:
                    result['errors'].append(f"State export (propagate): {e}")

            if options.get('export_images', True) and not self._cancelled:
                _log("Exporting masked images…")
                try:
                    n = self.export_masked_images(
                        om, image_paths,
                        os.path.join(item_out, "masked_images"),
                        bg_opacity=options.get('bg_opacity', 1.0)
                    )
                    result['stats']['exported_images'] = n
                    _log(f"  {n} images exported")
                except Exception as e:
                    result['errors'].append(f"Image export: {e}")

            if options.get('export_centroids', True) and not self._cancelled:
                _log("Exporting centroids…")
                try:
                    n = self.export_centroids(
                        om, image_paths,
                        os.path.join(item_out, f"{folder_name}_centroids.xlsx")
                    )
                    result['stats']['exported_centroids'] = n
                except Exception as e:
                    result['errors'].append(f"Centroids export: {e}")

            if options.get('export_coordinates', True) and not self._cancelled:
                _log("Exporting mask coordinates…")
                try:
                    n = self.export_coordinates(
                        om, image_paths,
                        os.path.join(item_out, f"{folder_name}_coordinates.json")
                    )
                    result['stats']['exported_coordinates'] = n
                except Exception as e:
                    result['errors'].append(f"Coordinates export: {e}")

            if options.get('export_contour_coords', False) and not self._cancelled:
                _log("Exporting contour coordinates…")
                try:
                    from .exporters import MaskContourExporter
                    exporter = MaskContourExporter(debug_mode=self.debug_mode)
                    n = exporter.export_contour_coordinates(
                        om.object_contours,
                        om.object_names,
                        image_paths,
                        os.path.join(item_out, f"{folder_name}_contour_coordinates.xlsx"),
                        object_contour_coverage=om.object_contour_coverage,
                    )
                    result['stats']['exported_contour_coords'] = n
                except Exception as e:
                    result['errors'].append(f"Contour coordinates export: {e}")

            if options.get('export_closest_points', False) and not self._cancelled:
                _log("Exporting hull coordinates…")
                try:
                    from .exporters import ConvexHullExporter
                    exporter = ConvexHullExporter(debug_mode=self.debug_mode)
                    n = exporter.export_hull_coordinates(
                        om.object_hulls,
                        om.object_names,
                        image_paths,
                        os.path.join(item_out, f"{folder_name}_hull_coordinates.xlsx"),
                        object_hull_coverage=om.object_hull_coverage,
                    )
                    result['stats']['exported_hull_coords'] = n
                except Exception as e:
                    result['errors'].append(f"Hull coordinates export: {e}")

            if options.get('export_tracked_points', False) and not self._cancelled:
                _log("Exporting tracked points…")
                try:
                    from .exporters import TrackedPointExporter
                    exporter = TrackedPointExporter(debug_mode=self.debug_mode)
                    n = exporter.export_tracked_points(
                        om.object_tracked_points,
                        om.object_names,
                        image_paths,
                        os.path.join(item_out, f"{folder_name}_tracked_points.xlsx"),
                    )
                    result['stats']['exported_tracked_points'] = n
                except Exception as e:
                    result['errors'].append(f"Tracked points export: {e}")

            if options.get('export_closest_points', False) and not self._cancelled:
                _log("Exporting closest mask points…")
                try:
                    from .reference_point_exporter import TARGET_REF, TARGET_OBJ
                    from .reference_point_manager import ReferencePointManager
                    ref_data = self.load_reference_points(sam2_file)
                    rpm = ReferencePointManager()
                    for name, frames in ref_data.get('reference_points', {}).items():
                        for fidx, coords in frames.items():
                            rpm.add_point(name, int(fidx), float(coords[0]), float(coords[1]))
                    
                    def _ref_target_key(tgt_raw, t_type, name_to_id):
                        if t_type == TARGET_REF:
                            return tgt_raw if tgt_raw in rpm.reference_points else None
                        return name_to_id.get(tgt_raw) if isinstance(tgt_raw, str) else tgt_raw
                    
                    resolved = self._resolve_named_pairs(
                        options.get('ref_point_pairs'), om, _ref_target_key, TARGET_REF
                    )
                    n = self.export_closest_mask_points(
                        om, rpm, image_paths,
                        os.path.join(item_out, f"{folder_name}_closest_mask_points.xlsx"),
                        pairs=resolved,
                        include_object_distances=options.get('include_object_distances', False),
                    )
                    result['stats']['exported_closest_points'] = n
                except Exception as e:
                    result['errors'].append(f"Closest mask points export: {e}")

            if options.get('export_point_mask_analysis', False) and not self._cancelled:
                _log("Exporting point/mask analysis…")
                try:
                    from .pair_selection_dialog import TARGET_IMPORTED
            
                    def _imported_target_key(tgt_raw, t_type, name_to_id):
                        return tgt_raw if tgt_raw in ipm.imported_points else None
            
                    resolved_imported = self._resolve_named_pairs(
                        options.get('imported_point_pairs'), om, _imported_target_key, TARGET_IMPORTED
                    )
                    n = self.export_point_mask_analysis(
                        om, ipm, image_paths,
                        os.path.join(item_out, f"{folder_name}_point_mask_analysis.xlsx"),
                        pairs=resolved_imported,
                    )
                    result['stats']['exported_point_mask_analysis'] = n
                except Exception as e:
                    result['errors'].append(f"Point/mask analysis export: {e}")

            result['success'] = not self._cancelled
            return result

        except Exception as e:
            result['errors'].append(f"Unexpected error: {e}")
            if self.debug_mode:
                import traceback
                traceback.print_exc()
            return result

        finally:
            self.sam2_backend.reset_state()

    def process_batch(self, items, options, output_dir,
                      item_callback=None, progress_callback=None,
                      mask_progress_callback=None):
        """
        Process a list of (sam2_file, image_folder, ref_frame_or_None) tuples.

        Args:
            items:                  List of (sam2_file, image_folder, ref_frame) tuples.
            options:                Processing options dict with keys:
                                      propagate (bool, default True)
                                      export_images (bool, default True)
                                      export_centroids (bool, default True)
                                      export_coordinates (bool, default True)
                                      export_state_predict (bool, default False)
                                      export_state_propagate (bool, default False)
                                      bg_opacity (float 0-1, default 1.0)
            output_dir:             Root directory for all outputs.
            item_callback:          Optional callable(idx, total, result) after each item.
            progress_callback:      Optional callable(message) for step-level messages.
            mask_progress_callback: Optional callable(current, total, label) for
                                    per-frame / per-object progress.

        Returns:
            List of result dicts (one per item).
        """
        self._cancelled = False
        results = []

        for i, (sam2_file, image_folder, ref_frame, tracked_points_file) in enumerate(items):
            if self._cancelled:
                break
        
            if progress_callback:
                progress_callback(
                    f"[{i + 1}/{len(items)}] {os.path.basename(image_folder)}"
                )
        
            result = self.process_item(
                sam2_file, image_folder, options, output_dir,
                ref_frame=ref_frame or None,
                tracked_points_file=tracked_points_file or None,
                progress_callback=progress_callback,
                mask_progress_callback=mask_progress_callback
            )
            results.append(result)

            if item_callback:
                item_callback(i, len(items), result)

        return results
