"""
Export Utilities, supporting both folder-based and single file exports
Handles exporting of images, coordinates, centroids, and convex hulls using original filenames
"""

import os
import json
import pickle
import csv
import numpy as np
from PIL import Image
from .base_exporter import BaseExporter
from .file_utils import FileManager
from .reference_point_exporter import ClosestMaskPointExporter

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

class ImageExporter(BaseExporter):
    """Handles export of images with superimposed masks using original filenames"""
    
    
    def export_masked_images(self, image_paths, object_masks, object_colors,
                             export_folder, quality=95, bg_opacity=1.0):
        """
        Export images with superimposed masks using original filenames.
    
        Args:
            image_paths:   List of image file paths.
            object_masks:  Dict of {obj_id: {frame_idx: mask}}.
            object_colors: Dict of {obj_id: {'mask': QColor}}.
            export_folder: Destination folder.
            quality:       JPEG quality (1-100).
            bg_opacity:    Background image opacity in [0, 1].
    
        Returns:
            Number of images exported.
        """
        if not object_masks:
            return 0
    
        masked_folder = os.path.join(export_folder, "masked_images")
        FileManager.ensure_directory_exists(masked_folder)
    
        count = 0
    
        for idx, image_path in enumerate(image_paths):
            frame_has_masks = any(idx in obj_masks for obj_masks in object_masks.values())
            if not frame_has_masks:
                continue
    
            try:
                pil_image = Image.open(image_path).convert('RGB')
    
                if bg_opacity < 1.0:
                    white = Image.new('RGB', pil_image.size, (255, 255, 255))
                    pil_image = Image.blend(white, pil_image, bg_opacity)
    
                image = np.array(pil_image, dtype=np.float32)
                masked_image = image.copy()
    
                for obj_id, obj_masks in object_masks.items():
                    if idx not in obj_masks:
                        continue
    
                    mask = obj_masks[idx]
                    while len(mask.shape) > 2:
                        mask = mask.squeeze(0)
    
                    mask_color = object_colors[obj_id]['mask']
                    mask_color_rgb = np.array([
                        mask_color.red(),
                        mask_color.green(),
                        mask_color.blue()
                    ]) / 255.0
                    mask_opacity = mask_color.alphaF()
    
                    mask_bool = mask.astype(bool)
                    for c in range(3):
                        masked_image[:, :, c] = np.where(
                            mask_bool,
                            (1 - mask_opacity) * masked_image[:, :, c]
                            + mask_opacity * mask_color_rgb[c] * 255,
                            masked_image[:, :, c]
                        )
    
                result_image = Image.fromarray(masked_image.astype(np.uint8))
                export_filename = self.create_export_filename(idx, "masked", "jpg")
                result_image.save(os.path.join(masked_folder, export_filename),
                                  'JPEG', quality=quality)
                count += 1
    
                if self.debug_mode:
                    print(f"Exported: {self.get_original_filename(idx)} -> {export_filename}")
    
            except Exception as e:
                if self.debug_mode:
                    print(f"Error exporting image {image_path}: {e}")
                continue
    
        if self.debug_mode:
            print(f"Export completed: {count} images exported to {masked_folder}")

        return count

    def export_images_with_tracked_points(self, image_paths, object_tracked_points,
                                          object_colors, object_names,
                                          tracked_point_style, tracked_point_size,
                                          export_folder, quality=95):
        """
        Export images with SAM2++ tracked point markers superimposed.

        Uses matplotlib (Agg backend) to faithfully reproduce the marker style
        shown on screen, including the object name label next to each marker.

        Returns:
            Number of images exported.
        """
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        out_dir = os.path.join(export_folder, "images_with_tracked_points")
        FileManager.ensure_directory_exists(out_dir)
        count = 0

        for frame_idx, image_path in enumerate(image_paths):
            if not any(frame_idx in frames for frames in object_tracked_points.values()):
                continue
            try:
                img = Image.open(image_path).convert('RGB')
                w, h = img.size
                fig, ax = plt.subplots(figsize=(w / 100, h / 100), dpi=100)
                fig.subplots_adjust(0, 0, 1, 1)
                ax.imshow(img)
                ax.axis('off')
                for obj_id, frames in sorted(object_tracked_points.items()):
                    if frame_idx not in frames:
                        continue
                    x_px, y_px = frames[frame_idx]
                    color = object_colors[obj_id]['mask']
                    ax.plot(x_px, y_px, marker=tracked_point_style,
                            color=color.name(), markersize=tracked_point_size,
                            markeredgewidth=1.5, markeredgecolor='white',
                            linestyle='None', zorder=5)
                    ax.annotate(
                        object_names.get(obj_id, f"Object {obj_id}"),
                        (x_px, y_px), xytext=(6, 4),
                        textcoords='offset points',
                        color=color.name(), fontsize=9, fontweight='bold', zorder=6,
                    )
                fname = self.create_export_filename(frame_idx, "tracked", "jpg")
                fig.savefig(os.path.join(out_dir, fname), dpi=100,
                            bbox_inches='tight', pad_inches=0,
                            pil_kwargs={'quality': quality})
                plt.close(fig)
                count += 1
            except Exception as e:
                if self.debug_mode:
                    print(f"Tracked point image export error ({image_path}): {e}")

        if self.debug_mode:
            print(f"Export completed: {count} images with tracked points exported to {out_dir}")

        return count

class CoordinateExporter(BaseExporter):
    """Handles export of mask coordinates using original filenames"""
    
    def export_mask_coordinates(self, masks, image_paths, masks_scores, export_file):
        """
        Export mask coordinates to file using original filenames
        
        Args:
            masks: Dict of {frame_idx: mask}
            image_paths: List of image paths
            masks_scores: Dict of {frame_idx: score}
            export_file: Output file path
            
        Returns:
            Number of masks exported
        """
        if not masks:
            return 0
        
        self.ensure_directory(export_file)
        
        export_data = {}
        for idx, mask in masks.items():
            if idx >= len(image_paths):
                continue
                
            original_filename = self.get_original_filename(idx)
            image_path = image_paths[idx]
            
            h, w = mask.shape
            mask_coords = []
            for y in range(h):
                for x in range(w):
                    if mask[y, x]:
                        mask_coords.append((x, y))
            
            export_data[original_filename] = {
                "original_filename": original_filename,
                "image_path": image_path,
                "mask_coords": mask_coords,
                "score": float(masks_scores.get(idx, 0)),
                "frame_index": idx,
                "active_pixels": len(mask_coords)
            }
        
        try:
            if export_file.lower().endswith(".json"):
                for img_name in export_data:
                    export_data[img_name]["mask_coords"] = [
                        list(coord) for coord in export_data[img_name]["mask_coords"]
                    ]
                with open(export_file, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
            elif export_file.lower().endswith(".csv"):
                self._export_coordinates_csv(export_data, export_file)
            else:
                with open(export_file, 'wb') as f:
                    pickle.dump(export_data, f)
            
            if self.debug_mode:
                print(f"Exported coordinates for {len(export_data)} masks to {export_file}")
            
            return len(export_data)
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error exporting coordinates: {e}")
            raise
    
    def _export_coordinates_csv(self, export_data, export_file):
        """Export coordinates to CSV format"""
        with open(export_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Original_Filename', 'Frame_Index', 'Image_Path', 'Active_Pixels', 'Score', 'Coordinate_X', 'Coordinate_Y'])
            for filename, data in export_data.items():
                for coord in data['mask_coords']:
                    writer.writerow([
                        data['original_filename'],
                        data['frame_index'],
                        data['image_path'],
                        data['active_pixels'],
                        data['score'],
                        coord[0],
                        coord[1]
                    ])
    
    def export_coordinates_to_file(self, export_file, file_format='json'):
        """Export coordinates from current object manager state to single file"""
        try:
            if not self.main_window:
                return False
            
            object_masks = self.main_window.object_manager.object_masks
            object_names = self.main_window.object_manager.object_names
            image_paths = self.main_window.image_manager.image_paths
            
            if not object_masks:
                if self.debug_mode:
                    print("No masks to export")
                return False
            
            self.ensure_directory(export_file)
            
            export_data = {}
            
            for obj_id, masks in object_masks.items():
                obj_name = object_names.get(obj_id, f"Object_{obj_id}")
                export_data[obj_name] = {}
                
                for frame_idx, mask in masks.items():
                    if frame_idx >= len(image_paths):
                        continue
                    
                    original_filename = self.get_original_filename(frame_idx)
                    
                    mask_coords = []
                    if mask is not None:
                        h, w = mask.shape
                        for y in range(h):
                            for x in range(w):
                                if mask[y, x]:
                                    mask_coords.append([x, y])
                    
                    export_data[obj_name][original_filename] = {
                        "original_filename": original_filename,
                        "frame_index": frame_idx,
                        "image_path": image_paths[frame_idx],
                        "mask_coords": mask_coords,
                        "active_pixels": len(mask_coords),
                        "object_id": obj_id,
                        "object_name": obj_name
                    }
            
            if file_format == 'json' or export_file.lower().endswith('.json'):
                with open(export_file, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
            elif file_format == 'csv' or export_file.lower().endswith('.csv'):
                self._export_object_coordinates_csv(export_data, export_file)
            elif file_format == 'pickle' or export_file.lower().endswith('.pkl'):
                with open(export_file, 'wb') as f:
                    pickle.dump(export_data, f)
            else:
                with open(export_file, 'w', encoding='utf-8') as f:
                    json.dump(export_data, f, indent=2, ensure_ascii=False)
            
            if self.debug_mode:
                total_frames = sum(len(obj_data) for obj_data in export_data.values())
                print(f"Exported coordinates for {len(export_data)} objects ({total_frames} frames) to {export_file}")
            
            return True
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error in export_coordinates_to_file: {e}")
                import traceback
                traceback.print_exc()
            return False
    
    def _export_object_coordinates_csv(self, export_data, export_file):
        """Export object coordinates to CSV format"""
        with open(export_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Object_Name', 'Object_ID', 'Original_Filename', 'Frame_Index', 
                           'Image_Path', 'Active_Pixels', 'Coordinate_X', 'Coordinate_Y'])
            for obj_name, obj_data in export_data.items():
                for filename, frame_data in obj_data.items():
                    for coord in frame_data['mask_coords']:
                        writer.writerow([
                            frame_data['object_name'],
                            frame_data['object_id'],
                            frame_data['original_filename'],
                            frame_data['frame_index'],
                            frame_data['image_path'],
                            frame_data['active_pixels'],
                            coord[0],
                            coord[1]
                        ])

class CentroidExporter(BaseExporter):
    """Handles export of centroid coordinates using original filenames"""
    
    def export_centroids(self, object_centroids, object_names, image_paths, export_file):
        """
        Export centroid coordinates to file using original filenames
        
        Args:
            object_centroids: Dict of {obj_id: {frame_idx: (x, y)}}
            object_names: Dict of {obj_id: name}
            image_paths: List of image paths
            export_file: Output file path
            
        Returns:
            Total number of centroids exported
        """
        if not object_centroids:
            return 0
        
        self.ensure_directory(export_file)
        
        export_data = {}
        
        for obj_id, centroids in object_centroids.items():
            obj_name = object_names.get(obj_id, f"Object {obj_id}")
            export_data[obj_name] = {}
            
            for frame_idx, (centroid_x, centroid_y) in centroids.items():
                if frame_idx >= len(image_paths):
                    continue
                
                original_filename = self.get_original_filename(frame_idx)
                
                export_data[obj_name][original_filename] = {
                    "frame_index": frame_idx,
                    "original_filename": original_filename,
                    "centroid_x": float(centroid_x),
                    "centroid_y": float(centroid_y),
                    "image_path": image_paths[frame_idx],
                    "object_id": obj_id,
                    "object_name": obj_name
                }
        
        try:
            if export_file.lower().endswith(".xlsx"):
                return self._export_centroids_excel(export_data, export_file)
            elif export_file.lower().endswith(".json"):
                return self._export_centroids_json(export_data, export_file)
            elif export_file.lower().endswith(".csv"):
                return self._export_centroids_csv(export_data, export_file)
            else:
                return self._export_centroids_json(export_data, export_file)
                
        except Exception as e:
            if self.debug_mode:
                print(f"Error exporting centroids: {e}")
            raise
    
    def _export_centroids_excel(self, export_data, export_file):
        """Export centroids to Excel format"""
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas and openpyxl are required for Excel export")
        
        rows = []
        for obj_name, centroids in export_data.items():
            for original_filename, data in centroids.items():
                rows.append({
                    'Object_Name': obj_name,
                    'Object_ID': data['object_id'],
                    'Frame_Index': data['frame_index'],
                    'Original_Filename': data['original_filename'],
                    'Centroid_X': data['centroid_x'],
                    'Centroid_Y': data['centroid_y'],
                    'Image_Path': data['image_path']
                })
        
        df = pd.DataFrame(rows)
        df.to_excel(export_file, index=False, engine='openpyxl')
        
        if self.debug_mode:
            print(f"Exported {len(rows)} centroids to Excel: {export_file}")
        
        return len(rows)
    
    def _export_centroids_json(self, export_data, export_file):
        """Export centroids to JSON format"""
        with open(export_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        total_centroids = sum(len(centroids) for centroids in export_data.values())
        
        if self.debug_mode:
            print(f"Exported {total_centroids} centroids to JSON: {export_file}")
        
        return total_centroids
    
    def _export_centroids_csv(self, export_data, export_file):
        """Export centroids to CSV format"""
        with open(export_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Object_Name', 'Object_ID', 'Frame_Index', 'Original_Filename', 
                           'Centroid_X', 'Centroid_Y', 'Image_Path'])
            
            row_count = 0
            for obj_name, centroids in export_data.items():
                for original_filename, data in centroids.items():
                    writer.writerow([
                        obj_name,
                        data['object_id'],
                        data['frame_index'],
                        data['original_filename'],
                        data['centroid_x'],
                        data['centroid_y'],
                        data['image_path']
                    ])
                    row_count += 1
        
        if self.debug_mode:
            print(f"Exported {row_count} centroids to CSV: {export_file}")
        
        return row_count
    
    def export_centroids_to_file(self, export_file, file_format='excel'):
        """Export centroids from current object manager state to single file"""
        try:
            if not self.main_window:
                return False
            
            object_centroids = self.main_window.object_manager.object_centroids
            object_names = self.main_window.object_manager.object_names
            image_paths = self.main_window.image_manager.image_paths
            
            if not object_centroids:
                if self.debug_mode:
                    print("No centroids to export")
                return False
            
            count = self.export_centroids(object_centroids, object_names, image_paths, export_file)
            return count > 0
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error in export_centroids_to_file: {e}")
                import traceback
                traceback.print_exc()
            return False


class ConvexHullExporter(BaseExporter):
    """Handles export of per-object convex hull vertex coordinates"""

    def export_hull_coordinates(self, object_hulls, object_names, image_paths,
                                    export_file, object_hull_coverage=None):
            """
            Export convex hull vertices for all objects and frames.
    
            Args:
                object_hulls:          Dict of {obj_id: {frame_idx: np.ndarray (N, 2) normalized}}.
                object_names:          Dict of {obj_id: name}.
                image_paths:           List of image file paths.
                export_file:           Output path (.xlsx primary, .csv and .json as fallback).
                object_hull_coverage:  Optional dict {obj_id: {frame_idx: float}} — fraction of
                                       mask pixels inside the hull (added as Mask_Coverage column).
    
            Returns:
                Total number of vertex rows exported.
            """
            if not object_hulls or not any(bool(f) for f in object_hulls.values()):
                return 0
    
            self.ensure_directory(export_file)
    
            # Infer image dimensions from the first readable image
            img_w, img_h = 1, 1
            for path in image_paths:
                try:
                    from PIL import Image as PILImage
                    with PILImage.open(path) as img:
                        img_w, img_h = img.size
                    break
                except Exception:
                    continue
    
            image_names = [os.path.basename(p) for p in image_paths]
            rows = []
    
            for obj_id in sorted(object_hulls.keys()):
                obj_name = object_names.get(obj_id, f"Object {obj_id}")
                for frame_idx in sorted(object_hulls[obj_id].keys()):
                    verts = object_hulls[obj_id][frame_idx]
                    if verts is None or len(verts) == 0:
                        continue
                    orig_fn = image_names[frame_idx] if frame_idx < len(image_names) else str(frame_idx)
                    # Coverage is frame-level — same value repeated for all vertices of the frame
                    cov = None
                    if object_hull_coverage is not None:
                        cov = (object_hull_coverage.get(obj_id) or {}).get(frame_idx)
                    for v_idx, (xn, yn) in enumerate(verts):
                        row = {
                            'Object_Name':       obj_name,
                            'Object_ID':         obj_id,
                            'Frame_Index':       frame_idx,
                            'Original_Filename': orig_fn,
                            'Vertex_Index':      v_idx,
                            'X_norm':            float(xn),
                            'Y_norm':            float(yn),
                            'X_px':              float(xn * img_w),
                            'Y_px':              float(yn * img_h),
                        }
                        if object_hull_coverage is not None:
                            row['Mask_Coverage'] = round(cov, 6) if cov is not None else None
                        rows.append(row)
    
            if not rows:
                return 0
    
            try:
                if export_file.lower().endswith('.xlsx'):
                    return self._export_xlsx(rows, export_file)
                elif export_file.lower().endswith('.csv'):
                    return self._export_csv(rows, export_file)
                else:
                    return self._export_json(rows, export_file)
            except Exception as e:
                if self.debug_mode:
                    print(f"Hull export error: {e}")
                raise

    def _export_xlsx(self, rows, path):
        """Export rows to Excel format"""
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas and openpyxl are required for Excel export")
        df = pd.DataFrame(rows)
        df.to_excel(path, index=False, engine='openpyxl')
        if self.debug_mode:
            print(f"Exported {len(rows)} hull vertices to Excel: {path}")
        return len(rows)

    def _export_csv(self, rows, path):
        """Export rows to CSV format"""
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        if self.debug_mode:
            print(f"Exported {len(rows)} hull vertices to CSV: {path}")
        return len(rows)

    def _export_json(self, rows, path):
        """Export rows to JSON format"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(rows, f, indent=2)
        if self.debug_mode:
            print(f"Exported {len(rows)} hull vertices to JSON: {path}")
        return len(rows)

class MaskContourExporter(BaseExporter):
    """Handles export of per-object outer contour vertex coordinates"""

    def export_contour_coordinates(self, object_contours, object_names, image_paths,
                                   export_file, object_contour_coverage=None):
        """
        Export outer contour vertices for all objects and frames.

        Args:
            object_contours:         Dict of {obj_id: {frame_idx: np.ndarray (N, 2) normalized}}.
            object_names:            Dict of {obj_id: name}.
            image_paths:             List of image file paths.
            export_file:             Output path (.xlsx primary, .csv and .json as fallback).
            object_contour_coverage: Optional dict {obj_id: {frame_idx: float}} — fraction of
                                     mask pixels inside the contour (added as Mask_Coverage column).

        Returns:
            Total number of vertex rows exported.
        """
        if not object_contours or not any(bool(f) for f in object_contours.values()):
            return 0

        self.ensure_directory(export_file)

        # Infer image dimensions from the first readable image
        img_w, img_h = 1, 1
        for path in image_paths:
            try:
                from PIL import Image as PILImage
                with PILImage.open(path) as img:
                    img_w, img_h = img.size
                break
            except Exception:
                continue

        image_names = [os.path.basename(p) for p in image_paths]
        rows = []

        for obj_id in sorted(object_contours.keys()):
            obj_name = object_names.get(obj_id, f"Object {obj_id}")
            for frame_idx in sorted(object_contours[obj_id].keys()):
                verts = object_contours[obj_id][frame_idx]
                if verts is None or len(verts) == 0:
                    continue
                orig_fn = image_names[frame_idx] if frame_idx < len(image_names) else str(frame_idx)
                # Coverage is frame-level — same value repeated for all vertices of the frame
                cov = None
                if object_contour_coverage is not None:
                    cov = (object_contour_coverage.get(obj_id) or {}).get(frame_idx)
                for v_idx, (xn, yn) in enumerate(verts):
                    row = {
                        'Object_Name':       obj_name,
                        'Object_ID':         obj_id,
                        'Frame_Index':       frame_idx,
                        'Original_Filename': orig_fn,
                        'Vertex_Index':      v_idx,
                        'X_norm':            float(xn),
                        'Y_norm':            float(yn),
                        'X_px':              float(xn * img_w),
                        'Y_px':              float(yn * img_h),
                    }
                    if object_contour_coverage is not None:
                        row['Mask_Coverage'] = round(cov, 6) if cov is not None else None
                    rows.append(row)

        if not rows:
            return 0

        try:
            if export_file.lower().endswith('.xlsx'):
                return self._export_xlsx(rows, export_file)
            elif export_file.lower().endswith('.csv'):
                return self._export_csv(rows, export_file)
            else:
                return self._export_json(rows, export_file)
        except Exception as e:
            if self.debug_mode:
                print(f"Contour export error: {e}")
            raise

    def _export_xlsx(self, rows, path):
        """Export rows to Excel format"""
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas and openpyxl are required for Excel export")
        df = pd.DataFrame(rows)
        df.to_excel(path, index=False, engine='openpyxl')
        if self.debug_mode:
            print(f"Exported {len(rows)} contour vertices to Excel: {path}")
        return len(rows)

    def _export_csv(self, rows, path):
        """Export rows to CSV format"""
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        if self.debug_mode:
            print(f"Exported {len(rows)} contour vertices to CSV: {path}")
        return len(rows)

    def _export_json(self, rows, path):
        """Export rows to JSON format"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(rows, f, indent=2)
        if self.debug_mode:
            print(f"Exported {len(rows)} contour vertices to JSON: {path}")
        return len(rows)

class DataExporter:
    """Combined exporter for all data types with original filename support"""
    
    def __init__(self, main_window=None, debug_mode=False):
        self.main_window = main_window
        self.debug_mode = debug_mode
        self.image_exporter = ImageExporter(main_window, debug_mode)
        self.coordinate_exporter = CoordinateExporter(main_window, debug_mode)
        self.centroid_exporter = CentroidExporter(main_window, debug_mode)
        self.closest_mask_exporter = ClosestMaskPointExporter(main_window, debug_mode)
    
    def export_all_data(self, export_folder, image_paths, object_masks, object_colors, 
                       object_names, object_centroids, masks=None, masks_scores=None):
        """Export all data types to specified folder using original filenames"""
        results = {
            'images': 0,
            'coordinates': 0,
            'centroids': 0,
            'errors': []
        }
        
        try:
            results['images'] = self.image_exporter.export_masked_images(
                image_paths, object_masks, object_colors, export_folder
            )
        except Exception as e:
            results['errors'].append(f"Image export failed: {e}")
        
        try:
            if masks and masks_scores:
                coord_file = os.path.join(export_folder, "mask_coordinates.json")
                results['coordinates'] = self.coordinate_exporter.export_mask_coordinates(
                    masks, image_paths, masks_scores, coord_file
                )
        except Exception as e:
            results['errors'].append(f"Coordinate export failed: {e}")
        
        try:
            if object_centroids:
                centroid_file = os.path.join(export_folder, "centroids.xlsx")
                results['centroids'] = self.centroid_exporter.export_centroids(
                    object_centroids, object_names, image_paths, centroid_file
                )
        except Exception as e:
            results['errors'].append(f"Centroid export failed: {e}")
        
        if self.debug_mode:
            print(f"Export summary: {results}")
        
        return results
    
    def export_masked_images(self, export_folder, quality=None, progress_callback=None):
        """Export masked images using original filenames (simplified interface)"""
        try:
            if not self.main_window:
                return False
    
            if quality is None and hasattr(self.main_window, 'config_manager'):
                quality = self.main_window.config_manager.get_image_quality()
            elif quality is None:
                quality = 95
    
            bg_opacity = 1.0
            if hasattr(self.main_window, 'ui_manager'):
                slider = self.main_window.ui_manager.get_control('background_opacity_slider')
                if slider is not None:
                    bg_opacity = slider.value() / 100.0
    
            image_paths   = self.main_window.image_manager.image_paths
            object_masks  = self.main_window.object_manager.object_masks
            object_colors = self.main_window.object_manager.object_colors
    
            count = self.image_exporter.export_masked_images(
                image_paths, object_masks, object_colors,
                export_folder, quality, bg_opacity=bg_opacity
            )
    
            return count > 0
    
        except Exception as e:
            if self.debug_mode:
                print(f"Error in export_masked_images: {e}")
            return False
    
    def export_coordinates_to_file(self, export_file, file_format='json'):
        """Export mask coordinates to single file"""
        return self.coordinate_exporter.export_coordinates_to_file(export_file, file_format)
    
    def export_centroids_to_file(self, export_file, file_format='excel'):
        """Export centroids to single file"""
        return self.centroid_exporter.export_centroids_to_file(export_file, file_format)
    
    def export_closest_mask_points_to_file(self, export_file, reference_point_manager, pairs=None):
        """Export closest mask points to file (simplified interface for main_window)."""
        try:
            if not self.main_window:
                return False
            exporter = ClosestMaskPointExporter(self.main_window, self.debug_mode)
            n = exporter.export_closest_mask_points(
                object_masks=self.main_window.object_manager.object_masks,
                object_names=self.main_window.object_manager.object_names,
                reference_point_manager=reference_point_manager,
                image_paths=self.main_window.image_manager.image_paths,
                export_file=export_file,
                pairs=pairs,
            )
            return n > 0
        except Exception as e:
            if self.debug_mode:
                print(f"Error in export_closest_mask_points_to_file: {e}")
            return False
    
    # Legacy compatibility methods (for folder-based exports)
    def export_coordinates(self, export_folder, file_format='json', progress_callback=None):
        """Export mask coordinates to folder (legacy interface)"""
        try:
            if not self.main_window:
                return False
            
            if file_format == 'json':
                export_file = os.path.join(export_folder, "mask_coordinates.json")
            elif file_format == 'csv':
                export_file = os.path.join(export_folder, "mask_coordinates.csv")
            else:
                export_file = os.path.join(export_folder, "mask_coordinates.pkl")
            
            return self.coordinate_exporter.export_coordinates_to_file(export_file, file_format)
        except Exception as e:
            if self.debug_mode:
                print(f"Error in export_coordinates: {e}")
            return False
    
    def export_centroids(self, export_folder, file_format='excel', progress_callback=None):
        """Export centroid data to folder (legacy interface)"""
        try:
            if not self.main_window:
                return False
            
            if file_format == 'excel':
                export_file = os.path.join(export_folder, "centroids.xlsx")
            elif file_format == 'csv':
                export_file = os.path.join(export_folder, "centroids.csv")
            else:
                export_file = os.path.join(export_folder, "centroids.json")
            
            return self.centroid_exporter.export_centroids_to_file(export_file, file_format)
        except Exception as e:
            if self.debug_mode:
                print(f"Error in export_centroids: {e}")
            return False

class TrackedPointExporter(BaseExporter):
    """Handles export of SAM2++ tracked point coordinates."""

    def export_tracked_points(self, object_tracked_points, object_names,
                              image_paths, export_file):
        """
        Export per-frame tracked point coordinates for all objects.

        Columns: Object_Name, Object_ID, Frame_Index, Original_Filename, X_px, Y_px.

        Returns number of rows exported.
        """
        if not object_tracked_points or not any(object_tracked_points.values()):
            return 0

        self.ensure_directory(export_file)
        image_names = [os.path.basename(p) for p in image_paths]
        rows = []

        for obj_id in sorted(object_tracked_points.keys()):
            obj_name = object_names.get(obj_id, f"Object {obj_id}")
            for frame_idx, (x_px, y_px) in sorted(
                object_tracked_points[obj_id].items()
            ):
                orig_fn = (image_names[frame_idx]
                           if frame_idx < len(image_names) else str(frame_idx))
                rows.append({
                    'Object_Name':       obj_name,
                    'Object_ID':         obj_id,
                    'Frame_Index':       frame_idx,
                    'Original_Filename': orig_fn,
                    'X_px':              x_px,
                    'Y_px':              y_px,
                })

        if not rows:
            return 0

        try:
            if export_file.lower().endswith('.xlsx'):
                return self._write_xlsx(rows, export_file)
            elif export_file.lower().endswith('.csv'):
                return self._write_csv(rows, export_file)
            else:
                return self._write_json(rows, export_file)
        except Exception as e:
            if self.debug_mode:
                print(f"TrackedPointExporter error: {e}")
            raise

    def _write_xlsx(self, rows, path):
        if not PANDAS_AVAILABLE:
            raise ImportError("pandas and openpyxl required for Excel export")
        pd.DataFrame(rows).to_excel(path, index=False, engine='openpyxl')
        if self.debug_mode:
            print(f"Exported {len(rows)} tracked-point rows to Excel: {path}")
        return len(rows)

    def _write_csv(self, rows, path):
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return len(rows)

    def _write_json(self, rows, path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(rows, f, indent=2)
        return len(rows)
