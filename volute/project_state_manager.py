"""
Project State Manager
Handles saving and loading of project data (.volute files)
Contains points, colors, names, and display settings
"""

import os
import pickle
import gzip
import numpy as np
from pathlib import Path
from PyQt5.QtWidgets import QMessageBox, QFileDialog
from PyQt5.QtCore import QDir
from PyQt5.QtGui import QColor
from collections import defaultdict
from .object_manager import _default_points  # for pickle-safe defaultdict factory
from .file_utils import build_file_filter

class ProjectStateManager:
    """Manages project data save/load operations"""

    # 1.1 adds object_boxes, and the optional imported masks with their origin.
    # Older files simply lack those keys and import unchanged.
    PROJECT_VERSION = '1.1'
    SUPPORTED_VERSIONS = ('1.0', '1.1')


    def __init__(self, main_window):
        self.main_window = main_window
        self.debug_mode = main_window.debug_mode
    
    def export_project_data_dialog(self):
        """Show dialog to export project data"""
        loc = self.main_window.localization
        # Generate default filename
        folder_name = "project"
        if self.main_window.image_manager.current_folder:
            folder_name = os.path.basename(self.main_window.image_manager.current_folder) + "_objects"
        
        default_filename = f"{folder_name}.volute"
        default_path = os.path.join(QDir.homePath(), default_filename)
        
        # Show save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            loc.get_text("export_project_data"),
            default_path,
            build_file_filter(self.main_window.localization, 'volute', 'all')
        )
        
        if file_path:
            return self.export_project_data(file_path)
        return False
    
    def import_project_data_dialog(self):
        """Show dialog to import project data"""
        loc = self.main_window.localization
        # Show open dialog
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            loc.get_text("import_project_data"),
            QDir.homePath(),
            build_file_filter(self.main_window.localization, 'volute', 'all')
        )
        
        if file_path:
            return self.import_project_data(file_path)
        return False
    
    def export_project_data(self, file_path):
        """Export project data to file"""
        loc = self.main_window.localization
        try:
            if self.debug_mode:
                print("Starting project data export...")
            
            # Get current image dimensions
            current_image_info = self.main_window.image_manager.get_current_image_info()
            if not current_image_info:
                self.main_window.ui_manager.show_message(
                    "error",
                    loc.get_text("error"),
                    loc.get_text("project_export_no_dimensions")
                )
                return False
            
            # Create project data
            project_data = self._create_project_data(
                current_image_info, self._ask_include_imported_masks())
            
            # Save to compressed file
            with gzip.open(file_path, 'wb') as f:
                pickle.dump(project_data, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            file_size = os.path.getsize(file_path)
            if self.debug_mode:
                print(f"Exported project data: {file_size} bytes ({file_size / 1024:.2f} KB)")
            
            self.main_window.ui_manager.show_message(
                "info",
                loc.get_text("success"),
                loc.get_text("project_data_exported", file_path, f"{file_size / 1024:.1f}")
            )
            
            return True
            
        except Exception as e:
            error_msg = self.main_window.localization.get_text("project_export_error", e)
            if self.debug_mode:
                print(error_msg)
                import traceback
                traceback.print_exc()
            self.main_window.ui_manager.show_message(
                "error", self.main_window.localization.get_text("error"), error_msg)
            return False
    
    def _imported_mask_count(self):
        """Number of stored masks that came from an import, and so cannot be
        regenerated from the prompts saved in the project file."""
        om = self.main_window.object_manager
        return sum(
            1
            for obj_id, frames in om.mask_import_origin.items()
            for frame_idx in frames
            if frame_idx in om.object_masks.get(obj_id, {})
        )

    def _ask_include_imported_masks(self):
        """Ask whether imported masks should travel with the project file.
        Returns True when there is nothing to ask about, so a project without
        imported masks is exported without any extra dialog."""
        from PyQt5.QtWidgets import QMessageBox
        from .dialogs import localized_question

        count = self._imported_mask_count()
        if not count:
            return True
        loc = self.main_window.localization
        return localized_question(
            self.main_window, loc,
            loc.get_text("project_include_imported_masks_title"),
            loc.get_text("project_include_imported_masks_msg", count),
            default=QMessageBox.Yes,
        ) == QMessageBox.Yes

    def import_project_data(self, file_path):
        """Import project data from file"""
        loc = self.main_window.localization
        if not os.path.exists(file_path):
            self.main_window.ui_manager.show_message(
                "error",
                self.main_window.localization.get_text("error"),
                self.main_window.localization.get_text("file_not_found", file_path)
            )
            return False
        
        try:
            if self.debug_mode:
                file_size = os.path.getsize(file_path)
                print(f"Importing project data: {file_path} ({file_size} bytes)")
            
            # Load project data
            with gzip.open(file_path, 'rb') as f:
                project_data = pickle.load(f)
            
            # Validate and check compatibility
            if not self._validate_project_data(project_data):
                return False
            
            # Show confirmation dialog
            reply = self.main_window.ui_manager.show_message(
                "question",
                loc.get_text("import_project_data"),
                loc.get_text("import_project_warning")
            )
            
            if reply != QMessageBox.Yes:
                return False
            
            # Reset current data and import
            self._reset_object_data()
            success = self._import_object_data(project_data.get('object_data', {}))

            # Import reference points (backward-compatible: absent key is silently ignored)
            self._import_reference_points(project_data.get('reference_point_data', {}))

            # Import points imported from SAM2++ point mode (backward-compatible: absent key ignored)
            self._import_imported_points(project_data.get('imported_point_data', {}))
            
            if success:
                # Recreate SAM2 points from imported data
                self._recreate_sam2_points()
                
                # Update UI
                self.main_window.ui_manager.update_objects_list()
                self.main_window.ui_manager.update_object_ui()
                self.main_window.ui_manager.update_ref_points_list()
                if hasattr(self.main_window.ui_manager, 'update_imported_points_list'):
                    self.main_window.ui_manager.update_imported_points_list()
                self.main_window.display_manager.update_display()
                
                self.main_window.ui_manager.show_message(
                    "info",
                    loc.get_text("success"),
                    loc.get_text("project_data_imported", file_path)
                )
                
                if self.debug_mode:
                    print(f"Successfully imported project data from {file_path}")
                
                return True
            else:
                self.main_window.ui_manager.show_message(
                    "error",
                    loc.get_text("error"),
                    loc.get_text("project_import_failed")
                )
                return False
            
        except Exception as e:
            error_msg = self.main_window.localization.get_text("project_import_error", e)
            if self.debug_mode:
                print(error_msg)
                import traceback
                traceback.print_exc()
            self.main_window.ui_manager.show_message(
                "error", self.main_window.localization.get_text("error"), error_msg)
            return False
    
    def _create_project_data(self, current_image_info, include_imported_masks=True):
        """Create project data structure (object definitions, points, boxes, and
        reference points). Masks are excluded except the imported ones, which no
        prompt can regenerate and which are saved unless the caller opts out."""
        project_data = {
            'version': self.PROJECT_VERSION,
            'type': 'project_data',
            'image_dimensions': {
                'height': current_image_info['height'],
                'width': current_image_info['width']
            },
            'total_frames': len(self.main_window.image_manager.image_paths),
            'current_folder': self.main_window.image_manager.current_folder,
            'sam2_config': {
                'config_path': getattr(self.main_window.sam2_backend, 'sam2_config', ''),
                'checkpoint_path': getattr(self.main_window.sam2_backend, 'sam2_checkpoint', '')
            },
            'object_data': {},
            'reference_point_data': self._serialize_reference_points(),
            'imported_point_data': self._serialize_imported_points(),
        }
        
        try:
            project_data['object_data']['object_points'] = self._serialize_object_points()
            project_data['object_data']['object_colors'] = self._serialize_object_colors()
            project_data['object_data']['object_names'] = dict(self.main_window.object_manager.object_names)
            project_data['object_data']['object_markers'] = dict(self.main_window.object_manager.object_markers)
            project_data['object_data']['object_show_points'] = dict(self.main_window.object_manager.object_show_points)
            # Tracked points (SAM2++ point mode; omitted when empty for backward compatibility)
            tracked = {
                oid: {fidx: list(coords) for fidx, coords in frames.items()}
                for oid, frames in self.main_window.object_manager.object_tracked_points.items()
                if frames
            }
            if tracked:
                project_data['object_data']['object_tracked_points'] = tracked
            project_data['object_data']['object_boxes'] = self._serialize_object_boxes()

            # Imported masks: the only masks a reload cannot recompute from prompts
            om = self.main_window.object_manager
            if include_imported_masks and self._imported_mask_count():
                origin = {oid: set(frames) for oid, frames in om.mask_import_origin.items() if frames}
                project_data['object_data']['object_masks'] = self._serialize_object_masks(origin)
                project_data['object_data']['mask_import_origin'] = {
                    oid: sorted(frames) for oid, frames in origin.items()
                }
            project_data['object_data']['current_object_id'] = self.main_window.object_manager.current_object_id
            
            if self.debug_mode:
                print(f"Serialized project data for {len(project_data['object_data']['object_points'])} objects")
                
        except Exception as e:
            if self.debug_mode:
                print(f"Error serializing project data: {e}")
            project_data['object_data'] = {
                'object_points': {},
                'object_colors': {},
                'object_names': {},
                'object_markers': {},
                'object_show_points': {},
                'current_object_id': 1
            }
            project_data['export_note'] = 'Minimal export due to serialization issues'
        
        return project_data

    def _serialize_reference_points(self):
        """Serialize reference_point_manager data."""
        rpm = getattr(self.main_window, 'ref_point_manager', None)
        if not rpm:
            return {'reference_points': {}}
        return {
            'reference_points': {
                name: dict(frames)
                for name, frames in rpm.reference_points.items()
            }
        }

    def _serialize_imported_points(self):
        """Serialize imported_point_manager data (positions only, mirroring reference points)."""
        ipm = getattr(self.main_window, 'imported_point_manager', None)
        if not ipm:
            return {'imported_points': {}}
        return {
            'imported_points': {
                name: dict(frames)
                for name, frames in ipm.imported_points.items()
            }
        }

    def _import_reference_points(self, ref_data):
        """Import reference point data into ref_point_manager (backward-compatible)."""
        rpm = getattr(self.main_window, 'ref_point_manager', None)
        if not rpm:
            return
        rpm.clear()
        for name, frames in ref_data.get('reference_points', {}).items():
            for frame_idx, coords in frames.items():
                rpm.add_point(name, int(frame_idx), float(coords[0]), float(coords[1]))
        if self.debug_mode:
            print(f"Imported {len(rpm.reference_points)} reference points")

    def _import_imported_points(self, imported_data):
        """Import imported-point data into imported_point_manager (backward-compatible)."""
        ipm = getattr(self.main_window, 'imported_point_manager', None)
        if not ipm:
            return
        ipm.clear()
        for name, frames in imported_data.get('imported_points', {}).items():
            for frame_idx, coords in frames.items():
                ipm.add_point(name, int(frame_idx), float(coords[0]), float(coords[1]))
        if self.debug_mode:
            print(f"Imported {len(ipm.imported_points)} imported points")

    def _serialize_object_points(self):
        """Serialize object points data"""
        serialized = {}
        for obj_id, frames_data in self.main_window.object_manager.object_points.items():
            serialized[obj_id] = {}
            for frame_idx, point_data in frames_data.items():
                serialized[obj_id][frame_idx] = dict(point_data)
        return serialized
    
    def _serialize_object_boxes(self):
        """Serialize object boxes as {obj_id: {frame_idx: [x0, y0, x1, y1]}}"""
        return {
            obj_id: {frame_idx: list(box) for frame_idx, box in frames.items()}
            for obj_id, frames in self.main_window.object_manager.object_boxes.items()
            if frames
        }

    def _serialize_object_masks(self, only_frames=None):
        """Serialize object masks data, restricted to the {obj_id: {frame_idx}}
        pairs of `only_frames` when given (all masks otherwise)"""
        serialized = {}
        for obj_id, masks in self.main_window.object_manager.object_masks.items():
            if only_frames is not None and obj_id not in only_frames:
                continue
            serialized[obj_id] = {}
            for frame_idx, mask in masks.items():
                if only_frames is not None and frame_idx not in only_frames[obj_id]:
                    continue
                if isinstance(mask, np.ndarray):
                    # Ensure mask is 2D
                    if len(mask.shape) > 2:
                        if len(mask.shape) == 4:  # (1, 1, H, W)
                            mask = mask[0, 0]
                        elif len(mask.shape) == 3:  # (1, H, W) or (H, W, 1)
                            if mask.shape[0] == 1:
                                mask = mask[0]
                            elif mask.shape[2] == 1:
                                mask = mask[:, :, 0]
                            else:
                                mask = mask[0]
                    
                    # Convert to boolean and then to uint8 for compression
                    mask_bool = mask.astype(bool)
                    mask_uint8 = mask_bool.astype(np.uint8)
                    
                    serialized[obj_id][frame_idx] = {
                        'data': mask_uint8,
                        'shape': mask_bool.shape,
                        'dtype': 'bool'
                    }
        return serialized
    
    def _serialize_object_colors(self):
        """Serialize QColor objects"""
        serialized = {}
        for obj_id, colors in self.main_window.object_manager.object_colors.items():
            serialized[obj_id] = {}
            for color_type, color in colors.items():
                if isinstance(color, QColor):
                    serialized[obj_id][color_type] = {
                        'red': color.red(),
                        'green': color.green(),
                        'blue': color.blue(),
                        'alpha': color.alpha()
                    }
        return serialized
    
    def _validate_project_data(self, project_data):
        """Validate imported project data"""
        loc = self.main_window.localization
        # Check version
        if project_data.get('version') not in self.SUPPORTED_VERSIONS:
            self.main_window.ui_manager.show_message(
                "warning",
                loc.get_text("warning"),
                loc.get_text("project_version_mismatch")
            )
        
        # Check for minimal export
        if 'export_note' in project_data:
            self.main_window.ui_manager.show_message(
                "warning",
                loc.get_text("warning"),
                loc.get_text("project_minimal_export", project_data['export_note'])
            )
        
        # Check image dimensions compatibility
        if self.main_window.image_manager.has_images():
            current_image_info = self.main_window.image_manager.get_current_image_info()
            saved_dimensions = project_data.get('image_dimensions', {})
            
            current_height = current_image_info['height']
            current_width = current_image_info['width']
            saved_height = saved_dimensions.get('height')
            saved_width = saved_dimensions.get('width')
            
            if saved_height and saved_width:
                if current_height != saved_height or current_width != saved_width:
                    reply = self.main_window.ui_manager.show_message(
                        "question",
                        loc.get_text("warning"),
                        loc.get_text("dimension_mismatch",
                                     current_width, current_height,
                                     saved_width, saved_height)
                    )
                    
                    return reply == QMessageBox.Yes
        
        return True

    def _reset_object_data(self):
        """Reset object manager data — same per-object dictionaries as
        ObjectManager.clear_all_data(), so no stale entry survives an import"""
        om = self.main_window.object_manager
        for d in (
            om.object_points, om.object_masks, om.object_colors,
            om.object_markers, om.object_names, om.object_show_points,
            om.object_centroids,
            om.object_hulls, om.object_hull_coverage,
            om.object_contours, om.object_contour_coverage,
            om.object_tracked_points, om.object_boxes,
            om.mask_imported_frames, om.mask_import_origin,
            om.object_corrected_frames,
        ):
            d.clear()


        if self.main_window.sam2_backend:
            # Preserve the prep cache: _recreate_sam2_points will reload the same folder
            folder = self.main_window.image_manager.current_folder
            preserve = (
                folder is not None
                and self.main_window.sam2_backend._is_prep_cache_valid(folder)
            )
            self.main_window.sam2_backend.reset_state(preserve_prep_cache=preserve)

        # Reset reference point manager
        rpm = getattr(self.main_window, 'ref_point_manager', None)
        if rpm:
            rpm.clear()

        # Reset imported point manager
        ipm = getattr(self.main_window, 'imported_point_manager', None)
        if ipm:
            ipm.clear()
        
        self.main_window.object_manager.current_object_id = 1
        self.main_window.object_manager.object_points[1] = defaultdict(_default_points)
        self.main_window.object_manager.object_masks[1] = {}
        self.main_window.object_manager.object_colors[1] = {
            'positive': QColor(0, 255, 0),
            'negative': QColor(255, 0, 0),
            'mask': QColor(0, 0, 255, 128)
        }
        self.main_window.object_manager.object_markers[1] = {'style': 'o', 'size': 5}
        self.main_window.object_manager.object_names[1] = self.main_window.localization.get_text("object") + " 1"
        self.main_window.object_manager.object_show_points[1] = True
        
        if self.debug_mode:
            print("Reset object data")
    
    def _import_object_data(self, object_data):
        """Import object data into object manager"""
        if not object_data:
            if self.debug_mode:
                print("No object data to import")
            return False
        
        imported_count = 0
        
        # Import object points
        if 'object_points' in object_data:
            points_data = object_data['object_points']
            self.main_window.object_manager.object_points = {}
            for obj_id, frames_data in points_data.items():
                obj_id = int(obj_id)
                self.main_window.object_manager.object_points[obj_id] = defaultdict(_default_points)
                for frame_idx, point_data in frames_data.items():
                    frame_idx = int(frame_idx)
                    if isinstance(point_data, dict):
                        self.main_window.object_manager.object_points[obj_id][frame_idx] = {
                            'positive': point_data.get('positive', []),
                            'negative': point_data.get('negative', [])
                        }
            
            if self.debug_mode:
                print(f"Imported points for {len(points_data)} objects")
            imported_count += len(points_data)
        
        # Import object masks — through store_mask, so centroids, hulls and
        # contours are recomputed instead of being left missing
        if 'object_masks' in object_data:
            masks_data = object_data['object_masks']
            self.main_window.object_manager.object_masks = {}
            for obj_id, frames_data in masks_data.items():
                obj_id = int(obj_id)
                self.main_window.object_manager.object_masks[obj_id] = {}
                for frame_idx, mask_data in frames_data.items():
                    frame_idx = int(frame_idx)
                    if isinstance(mask_data, dict) and 'data' in mask_data:
                        mask = mask_data['data']
                        if mask_data.get('dtype') == 'bool':
                            mask = mask.astype(bool)
                        self.main_window.object_manager.store_mask(obj_id, frame_idx, mask)

            total_masks = sum(len(frames) for frames in masks_data.values())
            if self.debug_mode:
                print(f"Imported {total_masks} masks for {len(masks_data)} objects")

        # Import boxes (absent from files written before version 1.1)
        if 'object_boxes' in object_data:
            self.main_window.object_manager.object_boxes = {
                int(obj_id): {int(frame_idx): tuple(box) for frame_idx, box in frames.items()}
                for obj_id, frames in object_data['object_boxes'].items()
            }

        # Imported-mask origin: durable record, plus the transient conditioning
        # flag that makes the next prediction resend the mask to SAM2
        if 'mask_import_origin' in object_data:
            om = self.main_window.object_manager
            for obj_id, frames in object_data['mask_import_origin'].items():
                obj_id = int(obj_id)
                restored = {int(f) for f in frames if int(f) in om.object_masks.get(obj_id, {})}
                if restored:
                    om.mask_import_origin[obj_id] = set(restored)
                    om.mask_imported_frames[obj_id] = set(restored)

        # Import object colors
        if 'object_colors' in object_data:
            colors_data = object_data['object_colors']
            self.main_window.object_manager.object_colors = {}
            for obj_id, colors in colors_data.items():
                obj_id = int(obj_id)
                self.main_window.object_manager.object_colors[obj_id] = {}
                for color_type, color_data in colors.items():
                    if isinstance(color_data, dict):
                        color = QColor(
                            color_data['red'],
                            color_data['green'],
                            color_data['blue'],
                            color_data['alpha']
                        )
                        self.main_window.object_manager.object_colors[obj_id][color_type] = color
            
            if self.debug_mode:
                print(f"Imported colors for {len(colors_data)} objects")
        
        # Import other object data
        if 'object_names' in object_data:
            names_data = object_data['object_names']
            self.main_window.object_manager.object_names = {int(k): v for k, v in names_data.items()}
        
        if 'object_markers' in object_data:
            markers_data = object_data['object_markers']
            self.main_window.object_manager.object_markers = {int(k): v for k, v in markers_data.items()}
        
        if 'object_show_points' in object_data:
            show_points_data = object_data['object_show_points']
            self.main_window.object_manager.object_show_points = {int(k): v for k, v in show_points_data.items()}
        
        if 'object_tracked_points' in object_data:
            self.main_window.object_manager.object_tracked_points = {
                int(oid): {int(fidx): tuple(coords)
                           for fidx, coords in frames.items()}
                for oid, frames in object_data['object_tracked_points'].items()
            }
        
        if 'object_centroids' in object_data:
            centroids_data = object_data['object_centroids']
            self.main_window.object_manager.object_centroids = {int(k): v for k, v in centroids_data.items()}
        
        if 'current_object_id' in object_data:
            self.main_window.object_manager.current_object_id = object_data['current_object_id']
        
        return imported_count > 0
    
    def _recreate_sam2_points(self):
        """Recreate SAM2 points from imported Object Manager data"""
        if self.debug_mode:
            print("\n=== RECREATING SAM2 POINTS FROM IMPORTED DATA ===")
        
        try:
            # Initialize SAM2 state for current folder
            if self.main_window.image_manager.current_folder:
                self.main_window.sam2_backend.init_inference_state(
                    self.main_window.image_manager.current_folder
                )
            
            om = self.main_window.object_manager
            current_frame_idx = self.main_window.image_manager.current_image_idx
            current_image_info = self.main_window.image_manager.get_current_image_info()
            if not current_image_info:
                return
            height, width = current_image_info['height'], current_image_info['width']

            # Imported masks first: re-register the conditioning the reset dropped.
            # mask_imported_frames, restored alongside, still makes the next
            # prediction resend the mask before its points, as at import time.
            for obj_id, frames in om.mask_import_origin.items():
                for frame_idx in sorted(frames):
                    stored_mask = om.object_masks.get(obj_id, {}).get(frame_idx)
                    if stored_mask is None:
                        continue
                    try:
                        self.main_window.sam2_backend.add_mask(frame_idx, obj_id, stored_mask)
                        if self.debug_mode:
                            print(f"  -> Re-registered imported mask for obj {obj_id}, frame {frame_idx}")
                    except Exception as e:
                        if self.debug_mode:
                            print(f"  -> Warning: Could not re-register mask for object {obj_id}: {e}")

            # Then the prompts, for one frame per object: the current one when it
            # carries a prompt, the object's first prompted frame otherwise
            for obj_id in sorted(set(om.object_points) | set(om.object_boxes)):
                if self.debug_mode:
                    print(f"Recreating prompts for object {obj_id}")

                prompt_frames = {
                    frame_idx
                    for frame_idx, pts in om.object_points.get(obj_id, {}).items()
                    if pts['positive'] or pts['negative']
                } | set(om.object_boxes.get(obj_id, {}))
                if not prompt_frames:
                    continue
                target_frame_idx = (current_frame_idx if current_frame_idx in prompt_frames
                                    else min(prompt_frames))

                points, labels = om.get_points_for_sam(obj_id, target_frame_idx, width, height)
                box = om.get_box_for_sam(obj_id, target_frame_idx, width, height)

                try:
                    self.main_window.sam2_backend.predict_mask(
                        target_frame_idx, obj_id, points, labels, box=box)
                    if self.debug_mode:
                        print(f"  -> Recreated {len(points)} point(s)"
                              f"{' and a box' if box is not None else ''} "
                              f"for obj {obj_id}, frame {target_frame_idx}")
                except Exception as e:
                    if self.debug_mode:
                        print(f"  -> Warning: Could not recreate SAM2 state for object {obj_id}: {e}")
            
            if self.debug_mode:
                print("=== SAM2 POINTS RECREATION COMPLETE ===\n")
                
        except Exception as e:
            if self.debug_mode:
                print(f"Error recreating SAM2 points: {e}")
                import traceback
                traceback.print_exc()
