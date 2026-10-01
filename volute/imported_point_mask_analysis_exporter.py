"""
Imported Point / Mask Analysis Exporter
Exports containment and distance metrics between each imported point
(from a SAM2++ point-mode export) and each mask-mode object, per frame.

Unlike ClosestMaskPointExporter (one distance per row), this export produces
several containment flags and several distances per (object, imported point,
frame) row, so it gets its own exporter class rather than extending the
existing one.
"""

import os
import csv
import json
import numpy as np

from .base_exporter import BaseExporter
from .object_manager import ObjectManager
from .pair_selection_dialog import TARGET_IMPORTED

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


class ImportedPointMaskAnalysisExporter(BaseExporter):
    """
    For each (object, imported point) pair and each frame where both a mask
    and an imported point position exist, computes containment (mask / hull /
    contour) and distance (to centroid / mask / hull boundary / contour
    boundary) metrics.
    """

    def export_point_mask_analysis(
        self,
        object_masks,             # Dict[obj_id, Dict[frame_idx, np.ndarray]]
        object_names,             # Dict[obj_id, str]
        object_centroids,         # Dict[obj_id, Dict[frame_idx, (x_px, y_px)]]
        object_hulls,             # Dict[obj_id, Dict[frame_idx, np.ndarray (N,2) normalized]]
        object_contours,          # Dict[obj_id, Dict[frame_idx, np.ndarray (N,2) normalized]]
        imported_point_manager,   # ImportedPointManager
        image_paths,              # List[str]
        export_file,              # str
        pairs=None,                # Optional list of (obj_id, TARGET_IMPORTED, name); None = all
        total_frames=None,
    ) -> int:
        """Export point/mask analysis rows. Returns the number of rows exported."""
        if total_frames is None:
            total_frames = len(image_paths)

        imported_names = imported_point_manager.get_names()
        norm_pairs = self._normalize_pairs(pairs, object_masks, imported_names)

        rows = []
        for obj_id, t_type, name in norm_pairs:
            if t_type != TARGET_IMPORTED or obj_id not in object_masks:
                continue
            obj_name = object_names.get(obj_id, f"Object {obj_id}")
            masks_by_frame = object_masks[obj_id]
            hulls_by_frame = object_hulls.get(obj_id, {})
            contours_by_frame = object_contours.get(obj_id, {})
            centroids_by_frame = object_centroids.get(obj_id, {})

            for frame_idx in range(total_frames):
                if frame_idx not in masks_by_frame:
                    continue
                point = imported_point_manager.get_coords(name, frame_idx)
                if point is None:
                    continue
                x_px, y_px = point
                src_mask = masks_by_frame[frame_idx]

                m = src_mask
                while len(m.shape) > 2:
                    m = m.squeeze(0)
                img_h, img_w = m.shape

                inside_mask = ObjectManager.point_in_mask(x_px, y_px, src_mask)

                hull_verts = hulls_by_frame.get(frame_idx)
                inside_hull = ObjectManager.point_in_polygon(
                    x_px, y_px, hull_verts, img_w, img_h
                ) if hull_verts is not None else None

                contour_verts = contours_by_frame.get(frame_idx)
                inside_contour = ObjectManager.point_in_polygon(
                    x_px, y_px, contour_verts, img_w, img_h
                ) if contour_verts is not None else None

                centroid = centroids_by_frame.get(frame_idx)
                dist_centroid = (
                    float(np.hypot(x_px - centroid[0], y_px - centroid[1]))
                    if centroid is not None else None
                )

                _, _, dist_mask = ObjectManager.point_to_mask_distance(x_px, y_px, src_mask)

                dist_hull = ObjectManager.point_to_polygon_boundary_distance(
                    x_px, y_px, hull_verts, img_w, img_h
                ) if hull_verts is not None else None

                dist_contour = ObjectManager.point_to_polygon_boundary_distance(
                    x_px, y_px, contour_verts, img_w, img_h
                ) if contour_verts is not None else None

                fname = (
                    os.path.basename(image_paths[frame_idx])
                    if frame_idx < len(image_paths) else str(frame_idx)
                )
                rows.append({
                    'Object_Name':             obj_name,
                    'Object_ID':               obj_id,
                    'Imported_Point_Name':     name,
                    'Frame_Index':             frame_idx,
                    'Original_Filename':       fname,
                    'Point_X_px':              float(x_px),
                    'Point_Y_px':              float(y_px),
                    'Inside_Mask':             inside_mask,
                    'Inside_Hull':             inside_hull,
                    'Inside_Contour':          inside_contour,
                    'Distance_To_Centroid_px': dist_centroid,
                    'Distance_To_Mask_px':     dist_mask,
                    'Distance_To_Hull_px':     dist_hull,
                    'Distance_To_Contour_px':  dist_contour,
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

    def _normalize_pairs(self, pairs, object_masks, imported_names):
        """Normalize pairs to List[(obj_id, TARGET_IMPORTED, name)]."""
        if pairs is None:
            return [
                (obj_id, TARGET_IMPORTED, name)
                for obj_id in sorted(object_masks.keys())
                for name in imported_names
            ]
        # Defensive: silently drop any non-TARGET_IMPORTED entries, since this
        # export's pair-selection dialog is restricted to that target type only.
        return [(p[0], p[1], p[2]) for p in pairs if len(p) == 3 and p[1] == TARGET_IMPORTED]

    # ------------------------------------------------------------------
    # Format writers
    # ------------------------------------------------------------------

    def _export_excel(self, rows, path):
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas and openpyxl are required for Excel export")
        pd.DataFrame(rows).to_excel(path, index=False, engine='openpyxl')

    def _export_csv(self, rows, path):
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    def _export_json(self, rows, path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(rows, f, indent=2, ensure_ascii=False)
