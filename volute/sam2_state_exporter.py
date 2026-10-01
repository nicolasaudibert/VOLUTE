"""
SAM2 State Exporter
Handles export operations for SAM2 inference states with optional progress feedback
"""

import os
import pickle
import gzip
import numpy as np
from PyQt5.QtWidgets import QFileDialog, QApplication
from PyQt5.QtCore import QDir

from .sam2_serializer import SAM2Serializer
from .progress_dialog import SAM2ExportProgressDialog
from .progress_worker import run_with_progress
from .file_utils import build_file_filter

class SAM2StateExporter:
    """Handles SAM2 inference state export operations with optional progress tracking"""
    
    def __init__(self, main_window, debug_mode=False):
        self.main_window = main_window
        self.debug_mode = debug_mode
        self.serializer = SAM2Serializer(debug_mode=debug_mode)
        self.progress_dialog = None
        self.export_cancelled = False
    
    def export_sam2_inference_state_dialog(self):
        """Export SAM2 inference state with file dialog and progress"""
        try:
            # Check if there's something to export
            if not self._validate_export_prerequisites():
                return False
            
            # Get save location
            suggested_filename = self._get_suggested_filename()
            
            file_path, _ = QFileDialog.getSaveFileName(
                self.main_window,
                self.main_window.localization.get_text("export_sam2_state"),
                suggested_filename,
                build_file_filter(self.main_window.localization, 'voluteinf', 'all')
            )
            
            if not file_path:
                return False  # User cancelled
            
            # Ensure .voluteinf extension
            if not file_path.lower().endswith('.voluteinf'):
                file_path += '.voluteinf'
            
            # Show progress dialog
            self.progress_dialog = SAM2ExportProgressDialog(self.main_window)
            self.progress_dialog.cancelled.connect(self._cancel_export)
            self.export_cancelled = False
            
            # Start export with progress
            return self._export_with_progress(file_path)
            
        except Exception as e:
            self._handle_export_error(e)
            return False
    
    def export_to_path(self, file_path):
        """Export to an explicit path, without a file dialog.
        Runs without progress feedback; used by headless callers."""
        if not self._validate_export_prerequisites(require_masks=False):
            return False

        self.progress_dialog = None
        self.export_cancelled = False

        return self._export_with_progress(file_path)

    def _validate_export_prerequisites(self, require_masks=True):
        """Validate that we have something to export"""
        inference_state = self.main_window.sam2_backend.inference_state

        if not inference_state:
            self.main_window.ui_manager.show_message(
                "warning",
                self.main_window.localization.get_text("warning"),
                self.main_window.localization.get_text("no_sam2_state")
            )
            return False
        
        # Check if we have any objects with masks; path-based callers export
        # whatever the state holds, masks or not
        object_manager = self.main_window.object_manager
        if require_masks and not object_manager.object_masks:
            self.main_window.ui_manager.show_message(
                "warning",
                self.main_window.localization.get_text("warning"),
                self.main_window.localization.get_text("no_sam2_state")
            )
            return False
        
        return True
    
    def _get_suggested_filename(self):
        """Get suggested filename for export"""
        try:
            # Try to get folder name from SAM2 backend
            if (hasattr(self.main_window.sam2_backend, 'filename_manager') and 
                hasattr(self.main_window.sam2_backend.filename_manager, 'current_folder')):
                folder_path = self.main_window.sam2_backend.filename_manager.current_folder
            else:
                folder_path = self.main_window.image_manager.current_folder
            
            if folder_path:
                folder_name = os.path.basename(folder_path.rstrip(os.sep))
                return os.path.join(folder_path, f"{folder_name}.voluteinf")
            else:
                return os.path.join(QDir.homePath(), "sam2_inference_state.voluteinf")
                
        except Exception as e:
            if self.debug_mode:
                print(f"Error getting suggested filename: {e}")
            return os.path.join(QDir.homePath(), "sam2_inference_state.voluteinf")
    
    def _export_with_progress(self, file_path):
        """Export with optional progress tracking (progress_dialog may be None in headless mode)"""
        try:
            if self.progress_dialog:
                self.progress_dialog.show()
                QApplication.processEvents()
                completed = run_with_progress(
                    self.progress_dialog,
                    lambda report, is_cancelled: self._export_stages(file_path, report, is_cancelled),
                    on_report=self.progress_dialog.update_export_stage)
            else:
                # Headless callers may already run in a worker thread of their
                # own, so the export runs inline, without a dialog to report to
                completed = self._export_stages(
                    file_path, lambda *args: None, lambda: self.export_cancelled)
            if not completed:
                return False
            
            # Stage 6: Complete
            if self.progress_dialog:
                self.progress_dialog.update_export_stage('complete', 100,
                    f"Export completed: {os.path.basename(file_path)}")
            QApplication.processEvents()
            
            if self.progress_dialog:
                self.progress_dialog.complete_operation(True,
                    self.main_window.localization.get_text("progress_complete"))
            
            self.main_window.ui_manager.show_message(
                "info",
                self.main_window.localization.get_text("sam2_export_successful"),
                self.main_window.localization.get_text("sam2_state_exported", file_path)
            )
            
            return True
            
        except Exception as e:
            if self.progress_dialog:
                self.progress_dialog.complete_operation(False, f"Export failed: {str(e)}")
            self._handle_export_error(e)
            return False
        finally:
            if self.progress_dialog:
                self.progress_dialog.close()
                self.progress_dialog = None
    
    def _export_stages(self, file_path, report, is_cancelled):
        """Collect, serialise and save the state; returns False if cancelled.

        Runs in a worker thread when a dialog is shown, so it touches no widget:
        report(stage, progress, details) and is_cancelled() come from
        run_with_progress, or are stand-ins for headless callers.
        """
        # Stage 1: Initialize export
        report('initializing', 0,
            "Preparing SAM2 inference state for export")
        
        if is_cancelled():
            return False
        
        # Stage 2: Create state package
        report('serializing', 20,
            "Collecting inference state data")
        
        current_image_info = self._get_current_image_info()
        sam2_state_data = self._create_state_package(current_image_info)
        
        if is_cancelled():
            return False
        
        # Stage 3: Serialize state
        report('serializing', 40,
            "Serializing tensors and state data")
        
        serialized_state = self.serializer.serialize_sam2_state(
            self.main_window.sam2_backend.inference_state
        )
        sam2_state_data['inference_state'] = serialized_state
        
        if is_cancelled():
            return False
        
        # Stage 4: Add object metadata
        report('serializing', 60,
            "Adding object metadata and points")
        
        self._add_object_metadata(sam2_state_data)
        self._add_object_points(sam2_state_data)
        
        if is_cancelled():
            return False
        
        # Stage 5: Compress and save
        report('compressing', 80,
            "Compressing data for efficient storage")
        
        # Save with compression
        with gzip.open(file_path, 'wb') as f:
            pickle.dump(sam2_state_data, f, protocol=pickle.HIGHEST_PROTOCOL)
        
        if is_cancelled():
            return False
        
        return True
    
    def _cancel_export(self):
        """Handle export cancellation"""
        self.export_cancelled = True
        if self.debug_mode:
            print("Export cancelled by user")
    
    def _get_current_image_info(self):
        """Get current image information"""
        try:
            current_image = self.main_window.image_manager.get_current_image()
            if current_image is not None:
                return {
                    'dimensions': current_image.shape,
                    'current_frame': self.main_window.image_manager.current_image_idx,
                    'total_frames': len(self.main_window.image_manager.image_paths)
                }
            else:
                return {'dimensions': None, 'current_frame': 0, 'total_frames': 0}
        except Exception as e:
            if self.debug_mode:
                print(f"Error getting current image info: {e}")
            return {'dimensions': None, 'current_frame': 0, 'total_frames': 0}
    
    def _create_state_package(self, current_image_info):
        """Create the complete state package for export"""
        try:
            sam2_state_data = {
                'type': 'sam2_inference_state',
                'version': '1.0',
                'export_info': {
                    'image_dimensions': current_image_info.get('dimensions'),
                    'current_frame': current_image_info.get('current_frame', 0),
                    'total_frames': current_image_info.get('total_frames', 0),
                    'config_path': self.main_window.sam2_backend.sam2_config,
                    'checkpoint_path': self.main_window.sam2_backend.sam2_checkpoint,
                    'device': str(self.main_window.sam2_backend.device)
                }
            }
            
            if self.debug_mode:
                print(f"Created state package with export info: {sam2_state_data['export_info']}")
            
            return sam2_state_data
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error creating state package: {e}")
            raise
    
    def _add_object_metadata(self, sam2_state_data):
        """Add object metadata to export package"""
        try:
            object_metadata = {}
            object_manager = self.main_window.object_manager
            
            for obj_id in object_manager.object_masks.keys():
                metadata = {}
                
                # Object name
                if obj_id in object_manager.object_names:
                    metadata['name'] = object_manager.object_names[obj_id]
                
                # Object colors
                if obj_id in object_manager.object_colors:
                    colors = {}
                    for color_type, color in object_manager.object_colors[obj_id].items():
                        colors[color_type] = [color.red(), color.green(), color.blue(), color.alpha()]
                    metadata['colors'] = colors
                
                # Object markers
                if obj_id in object_manager.object_markers:
                    metadata['markers'] = object_manager.object_markers[obj_id]
                
                # Visibility settings
                if hasattr(object_manager, 'object_show_points') and obj_id in object_manager.object_show_points:
                    metadata['show_points'] = object_manager.object_show_points[obj_id]
                
                object_metadata[obj_id] = metadata
            
            sam2_state_data['object_metadata'] = object_metadata
            
            if self.debug_mode:
                print(f"Added metadata for {len(object_metadata)} objects")
                
        except Exception as e:
            if self.debug_mode:
                print(f"Error adding object metadata: {e}")
    
    def _add_object_points(self, sam2_state_data):
        """Add object points to export package"""
        try:
            object_points = {}
            object_manager = self.main_window.object_manager
            
            for obj_id, points_per_frame in object_manager.object_points.items():
                object_points[obj_id] = points_per_frame
            
            sam2_state_data['object_points'] = object_points
            
            if self.debug_mode:
                total_points = sum(len(frames) for frames in object_points.values())
                print(f"Added points for {len(object_points)} objects ({total_points} frames total)")
                
        except Exception as e:
            if self.debug_mode:
                print(f"Error adding object points: {e}")
    
    def _handle_export_error(self, error):
        """Handle export errors"""
        error_msg = f"Error exporting SAM2 inference state: {error}"
        if self.debug_mode:
            print(error_msg)
            import traceback
            traceback.print_exc()
        
        self.main_window.ui_manager.show_message(
            "error", 
            self.main_window.localization.get_text("sam2_export_failed"), 
            error_msg
        )
