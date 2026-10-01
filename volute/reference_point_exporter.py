"""
Reference Point Exporter
Exports, for each (object, target) pair, the mask pixel of object closest to
the target position on each frame.

Target can be:
  - a named reference point (interpolated via ReferencePointManager)
  - another object's mask (inter-object distances)

Backward compatible: pairs may be given as (obj_id, ref_name) 2-tuples,
treated as (obj_id, TARGET_REF, ref_name).
"""

import os
import csv
import json
import numpy as np

from .base_exporter import BaseExporter

# Target-type constants — must match pair_selection_dialog.py
TARGET_REF = 'ref_point'
TARGET_OBJ = 'object'

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


class ClosestMaskPointExporter(BaseExporter):
    """
    Finds the closest mask pixel to a reference position for each
    (object, target, frame) triple and exports the result.
    """

    def export_closest_mask_points(
        self,
        object_masks,                # Dict[obj_id, Dict[frame_idx, np.ndarray]]
        object_names,                # Dict[obj_id, str]
        reference_point_manager,     # ReferencePointManager
        image_paths,                 # List[str]
        export_file,                 # str
        pairs=None,                  # Optional list of 2- or 3-tuples; None = all
        total_frames=None,           # inferred from image_paths if None
        include_object_distances=False,  # generate obj-vs-obj pairs when pairs=None
    ) -> int:
        """Export closest mask points. Returns the number of rows exported."""
        if total_frames is None:
            total_frames = len(image_paths)

        ref_names  = reference_point_manager.get_names()
        norm_pairs = self._normalize_pairs(
            pairs, object_masks, ref_names, include_object_distances
        )

        rows = []
        for obj_id, t_type, t_key in norm_pairs:
            if obj_id not in object_masks:
                continue
            obj_name       = object_names.get(obj_id, f"Object {obj_id}")
            masks_by_frame = object_masks[obj_id]

            for frame_idx in range(total_frames):
                if frame_idx not in masks_by_frame:
                    continue

                src_mask = masks_by_frame[frame_idx]
                ref_px, ref_py, target_label = self._resolve_target(
                    t_type, t_key, frame_idx,
                    reference_point_manager, object_masks, object_names, src_mask
                )
                if ref_px is None:
                    continue

                mask = src_mask
                while len(mask.shape) > 2:
                    mask = mask.squeeze(0)
                ys, xs = np.where(mask.astype(bool))
                if len(xs) == 0:
                    continue

                dists   = np.hypot(xs - ref_px, ys - ref_py)
                idx_min = np.argmin(dists)
                fname   = (
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

        if not rows:
            return 0

        self.ensure_directory(export_file)
        ext = os.path.splitext(export_file)[1].lower()
        if ext == '.xlsx':
            self._export_excel(rows, export_file)
        elif ext == '.csv':
            self._export_csv(rows, export_file)
        else:
            self._export_json(rows, export_file)
        return len(rows)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _normalize_pairs(self, pairs, object_masks, ref_names, include_obj_dist):
        """Normalize pairs to List[(obj_id, target_type, target_key)]."""
        if pairs is None:
            result = []
            for obj_id in sorted(object_masks.keys()):
                for rn in ref_names:
                    result.append((obj_id, TARGET_REF, rn))
                if include_obj_dist:
                    for obj_id2 in sorted(object_masks.keys()):
                        if obj_id2 != obj_id:
                            result.append((obj_id, TARGET_OBJ, obj_id2))
            return result
        # Convert 2-tuples (backward compat) to 3-tuples
        return [
            (p[0], TARGET_REF, p[1]) if len(p) == 2 else tuple(p)
            for p in pairs
        ]


    def _resolve_target(
        self, t_type, t_key, frame_idx,
        rpm, object_masks, object_names, src_mask
    ):
        """
        Resolve target to (ref_px, ref_py, label) in pixel coordinates,
        or return (None, None, None) if unavailable.

        TARGET_REF: interpolated reference point position.
        TARGET_OBJ: pixel of the target object's mask that is closest to the
                    source object's mask (true minimum inter-mask distance).
                    Ref_X_px / Ref_Y_px in the output row therefore hold that
                    closest pixel of the target object, not the centroid.
        """
        if t_type == TARGET_REF:
            if t_key not in rpm.reference_points:
                return None, None, None
            coords = rpm.get_interpolated_coords(t_key, frame_idx)
            if coords is None:
                return None, None, None
            ref_nx, ref_ny = coords
            mask = src_mask
            while len(mask.shape) > 2:
                mask = mask.squeeze(0)
            H, W = mask.shape
            return ref_nx * W, ref_ny * H, t_key

        else:  # TARGET_OBJ — true minimum inter-mask distance
            if t_key not in object_masks or frame_idx not in object_masks[t_key]:
                return None, None, None
            tgt_mask = object_masks[t_key][frame_idx]
            while len(tgt_mask.shape) > 2:
                tgt_mask = tgt_mask.squeeze(0)
            tys, txs = np.where(tgt_mask.astype(bool))
            if len(txs) == 0:
                return None, None, None

            # Flatten source mask to pixel coordinates
            s_mask = src_mask
            while len(s_mask.shape) > 2:
                s_mask = s_mask.squeeze(0)
            sys_, sxs = np.where(s_mask.astype(bool))
            if len(sxs) == 0:
                return None, None, None

            # For each source pixel find distance to nearest target pixel.
            # Vectorised: (N_src, 1) vs (1, N_tgt) broadcasting.
            # For very large masks this could be memory-intensive; chunked if needed.
            if len(sxs) * len(txs) <= 50_000_000:  # ~50 M comparisons, ~400 MB float32
                dx = sxs[:, None].astype(np.float32) - txs[None, :]
                dy = sys_[:, None].astype(np.float32) - tys[None, :]
                dist_mat = np.hypot(dx, dy)
                src_idx, tgt_idx = np.unravel_index(np.argmin(dist_mat), dist_mat.shape)
            else:
                # Chunked fallback to avoid OOM on very large masks
                best_dist = np.inf
                src_idx = tgt_idx = 0
                chunk = 1000
                for start in range(0, len(sxs), chunk):
                    dx = sxs[start:start + chunk, None].astype(np.float32) - txs[None, :]
                    dy = sys_[start:start + chunk, None].astype(np.float32) - tys[None, :]
                    d = np.hypot(dx, dy)
                    local_flat = np.argmin(d)
                    local_si, local_ti = np.unravel_index(local_flat, d.shape)
                    if d[local_si, local_ti] < best_dist:
                        best_dist = d[local_si, local_ti]
                        src_idx   = start + local_si
                        tgt_idx   = local_ti

            label = object_names.get(t_key, f"Object {t_key}")
            # Return the closest pixel of the TARGET object; the main loop will
            # then find the closest pixel of the SOURCE object to this point,
            # which is exactly src_idx — giving the correct Closest_X/Y pair.
            return float(txs[tgt_idx]), float(tys[tgt_idx]), label

    # ------------------------------------------------------------------
    # Format writers
    # ------------------------------------------------------------------

    def _export_excel(self, rows, path):
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas and openpyxl are required for Excel export")
        import pandas as pd
        pd.DataFrame(rows).to_excel(path, index=False, engine='openpyxl')

    def _export_csv(self, rows, path):
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    def _export_json(self, rows, path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)

class TrackedPointDistanceExporter(BaseExporter):
    """
    Same (object, target) pairing logic as ClosestMaskPointExporter, but for
    SAM2++ point tracking mode: computes the Euclidean distance between each
    object's tracked point position and its target (reference point or
    another object's tracked point) on each frame.
    """

    def export_tracked_point_distances(
        self,
        object_tracked_points,       # Dict[obj_id, Dict[frame_idx, (x_px, y_px)]]
        object_names,
        reference_point_manager,
        image_paths,
        export_file,
        image_width,
        image_height,
        pairs=None,
        total_frames=None,
        include_object_distances=False,
    ) -> int:
        """Export tracked point distances. Returns the number of rows exported."""
        if total_frames is None:
            total_frames = len(image_paths)

        ref_names  = reference_point_manager.get_names()
        norm_pairs = self._normalize_pairs(
            pairs, object_tracked_points, ref_names, include_object_distances
        )

        rows = []
        for obj_id, t_type, t_key in norm_pairs:
            if obj_id not in object_tracked_points:
                continue
            obj_name     = object_names.get(obj_id, f"Object {obj_id}")
            pts_by_frame = object_tracked_points[obj_id]

            for frame_idx in range(total_frames):
                if frame_idx not in pts_by_frame:
                    continue
                src_x, src_y = pts_by_frame[frame_idx]

                tgt_x, tgt_y, target_label = self._resolve_target(
                    t_type, t_key, frame_idx, reference_point_manager,
                    object_tracked_points, object_names, image_width, image_height
                )
                if tgt_x is None:
                    continue

                dist  = float(np.hypot(src_x - tgt_x, src_y - tgt_y))
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
                    'Point_X_px':        float(src_x),
                    'Point_Y_px':        float(src_y),
                    'Target_X_px':       float(tgt_x),
                    'Target_Y_px':       float(tgt_y),
                    'Distance_px':       dist,
                })

        if not rows:
            return 0

        self.ensure_directory(export_file)
        ext = os.path.splitext(export_file)[1].lower()
        if ext == '.xlsx':
            self._export_excel(rows, export_file)
        elif ext == '.csv':
            self._export_csv(rows, export_file)
        else:
            self._export_json(rows, export_file)
        return len(rows)

    def _normalize_pairs(self, pairs, object_tracked_points, ref_names, include_obj_dist):
        """Same logic as ClosestMaskPointExporter._normalize_pairs, over tracked-point objects."""
        if pairs is None:
            result = []
            for obj_id in sorted(object_tracked_points.keys()):
                for rn in ref_names:
                    result.append((obj_id, TARGET_REF, rn))
                if include_obj_dist:
                    for obj_id2 in sorted(object_tracked_points.keys()):
                        if obj_id2 != obj_id:
                            result.append((obj_id, TARGET_OBJ, obj_id2))
            return result
        return [
            (p[0], TARGET_REF, p[1]) if len(p) == 2 else tuple(p)
            for p in pairs
        ]

    def _resolve_target(
        self, t_type, t_key, frame_idx,
        rpm, object_tracked_points, object_names, image_width, image_height
    ):
        """
        Resolve target to (x_px, y_px, label) in pixel coordinates, or
        (None, None, None) if unavailable. Reference points are stored
        normalized (0-1) and are scaled here using the image dimensions.
        """
        if t_type == TARGET_REF:
            if t_key not in rpm.reference_points:
                return None, None, None
            coords = rpm.get_interpolated_coords(t_key, frame_idx)
            if coords is None:
                return None, None, None
            ref_nx, ref_ny = coords
            return ref_nx * image_width, ref_ny * image_height, t_key
        else:  # TARGET_OBJ
            tgt_frames = object_tracked_points.get(t_key)
            if not tgt_frames or frame_idx not in tgt_frames:
                return None, None, None
            tx, ty = tgt_frames[frame_idx]
            label = object_names.get(t_key, f"Object {t_key}")
            return tx, ty, label
