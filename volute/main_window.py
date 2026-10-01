"""
Main Window
The main application window that coordinates all components, using an
external configuration manager for settings
"""

import os
import numpy as np
from PyQt5.QtWidgets import (
    QMainWindow, QMessageBox, QFileDialog,
    QDialog, QSpinBox, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QLabel,
    QRadioButton, QGridLayout, QComboBox, QApplication,
)
from PyQt5.QtCore import Qt, QDir, QEventLoop

from .config_manager import ConfigManager
from .localization import LocalizationManager
from .file_utils import FileManager
from .loading_worker import LoadFolderWorker
from .sam2_backend import SAM2Backend
from .object_manager import ObjectManager
from .ui_manager import UIManager
from .image_manager import ImageManager
from .prediction_manager import PredictionManager
from .display_manager import DisplayManager
from .event_manager import EventManager
from .export_manager import ExportManager
from .inference_state_manager import InferenceStateManager
from .batch_dialog import BatchDialog
from .progress_dialog import AnimatedProgressDialog
from .reference_point_manager import ReferencePointManager
from .imported_point_manager import ImportedPointManager
from .history_manager import HistoryManager
from .gimp_export_manager import GimpExportManager
from .gimp_ui_controller import GimpUIController
from .export_actions import ExportActions
from .property_controller import PropertyController
from .dialogs import localized_question
from .file_utils import build_file_filter

# Import SAM2 at main level to avoid Hydra issues
try:
    from sam2.build_sam import build_sam2_video_predictor
    SAM2_AVAILABLE = True
except ImportError as e:
    print(f"Error importing SAM2: {e}")
    print("Make sure SAM2 is installed correctly.")
    SAM2_AVAILABLE = False
    build_sam2_video_predictor = None

class SAM2VideoSegmentationApp(QMainWindow):
    """Main application window with external configuration support"""
    
    # Tab indices, fixed by setup_control_panels() — kept in sync manually
    TAB_OBJECTS_POINTS = 0
    TAB_REF_POINTS     = 1
    TAB_PREDICTION     = 2
    
    def __init__(self, debug_mode=False, config_path=None, checkpoint_path=None, sam2plus_task='mask'):
        super().__init__()
        
        self.debug_mode = debug_mode
        self._sam2plus_task_override = sam2plus_task
        
        # Initialize configuration manager FIRST
        self.config_manager = ConfigManager(debug_mode=debug_mode)
        
        # Override debug mode from config if not explicitly set
        if not debug_mode:
            self.debug_mode = self.config_manager.is_debug_enabled()
        
        if self.debug_mode:
            print("=== SAM2 VIDEO SEGMENTATION APP STARTING ===")
            self.config_manager.print_config()
        
        # Initialize localization with configured default language
        default_lang = self.config_manager.get_default_language()
        self.localization = LocalizationManager(default_language=default_lang)

        # File dialogs: the system ones keep the platform look, but on macOS the
        # panel is drawn by another process and stays in the system language.
        # Qt's own follow the application language (set before any dialog exists).
        if not self.config_manager.use_native_file_dialogs():
            QApplication.setAttribute(Qt.AA_DontUseNativeDialogs, True)
        
        # Initialize core managers
        self.file_manager = FileManager(self.debug_mode)
        self.object_manager = ObjectManager(self.localization, self.debug_mode)
        self.ref_point_manager = ReferencePointManager()
        self.imported_point_manager = ImportedPointManager()
        
        # Initialize SAM2 backend with filename management
        self.sam2_backend = None
        self.init_sam2_backend(config_path, checkpoint_path)
        
        # Initialize specialized managers
        # Initialize specialized managers
        self.image_manager = ImageManager(self)
        self.prediction_manager = PredictionManager(self)
        self.display_manager = DisplayManager(self)
        self.event_manager = EventManager(self)
        self.export_manager = ExportManager(self)
        self.inference_state_manager = InferenceStateManager(self)
        self.history_manager = HistoryManager(self)
        self.gimp_export_manager = GimpExportManager(self, debug_mode=self.debug_mode)
        self.gimp_ui_controller = GimpUIController(self)
        self.export_actions = ExportActions(self)
        self.property_controller = PropertyController(self)
        
        # Global toggle for points visibility (shows only current object's points)
        self.show_points_global = True
        
        # Tracks which control-panel tab is active, to gate canvas click behavior
        self.active_tab_index = self.TAB_OBJECTS_POINTS

        # Session-only flag: the reference-box clipping warning is shown once
        self._box_clipping_reference_warned = False
        
        # Initialize UI (must be last as it needs other managers)
        self.ui_manager = UIManager(self, self.localization, self.object_manager)
        self.ui_manager.setup_ui()
        
        # Connect managers
        self.connect_managers()
        
        # Show window
        self.show()
        self.ui_manager.apply_initial_splitter_sizes()
        
        # Update window title with model name (after show())
        if hasattr(self, 'sam2_backend') and self.sam2_backend:
            checkpoint_path = self.sam2_backend.sam2_checkpoint
            if checkpoint_path:
                self.update_window_title(checkpoint_path)
        
        if self.debug_mode:
            print("SAM2 Video Segmentation App initialized successfully with configuration management")
    
    def update_undo_redo_actions(self):
        """Delegate to UI manager"""
        self.ui_manager.update_undo_redo_actions()
        
    def on_active_tab_changed(self, index):
        """Track which control-panel tab is active, to gate canvas click behavior"""
        self.active_tab_index = index
    
    def init_sam2_backend(self, config_path=None, checkpoint_path=None):
        """Initialize SAM2 backend with configuration support and MedSAM2 detection"""
        if not SAM2_AVAILABLE:
            raise RuntimeError("SAM2 is not available. Please install SAM2.")
        
        try:
            # Use provided paths or fallback to defaults
            if config_path and checkpoint_path:
                final_config_path = config_path
                final_checkpoint_path = checkpoint_path
                if self.debug_mode:
                    print("Using provided paths from command line")
            else:
                final_config_path = self.get_default_config_path()
                final_checkpoint_path = self.get_default_checkpoint_path()
                if self.debug_mode:
                    print("Using hardcoded default paths")
            
            # Detect model type from ACTUAL checkpoint being used
            is_sam2plus = "SAM2-Plus" in (final_checkpoint_path or "")
            is_medsam2  = "MedSAM2"   in (final_checkpoint_path or "")
            model_type  = ("SAM2++" if is_sam2plus else
               "MedSAM2" if is_medsam2 else "SAM2")
            
            if self.debug_mode:
                print(f"Model type: {model_type}")
                print(f"Config path: {final_config_path}")
                print(f"Checkpoint path: {final_checkpoint_path}")
            
            # Initialize SAM2 backend
            self.sam2_backend = SAM2Backend(debug_mode=self.debug_mode)
            # SAM2++ specific task - CLI overrides YAML
            self.sam2_backend.sam2plus_task = self._sam2plus_task_override or \
                self.config_manager.get('models.sam2plus.task', 'mask')
            
            # Initialize model
            success = self.sam2_backend.initialize(final_checkpoint_path, final_config_path)
            
            if not success:
                raise Exception("Failed to initialize SAM2 backend")

            self.object_manager.set_point_mode(self.is_point_mode())

            if self.debug_mode:
                device_info = self.sam2_backend.get_device_info()
                print(f"Backend initialized: {device_info}")
                
        except Exception as e:
            QMessageBox.critical(self, "Model Error", f"Failed to initialize model: {e}")
            if self.debug_mode:
                import traceback
                traceback.print_exc()
            raise
            
    def get_default_config_path(self):
        """Get default SAM2 config path - hardcoded for Hydra compatibility"""
        # Check if we should use SAM2++
        if self.is_sam2plus_model():
            return "configs/sam2.1/sam2.1_hiera_b+_predmasks_decoupled_MAME.yaml"
        # Check if we should use MedSAM2 (no config file needed)
        if self.is_medsam2_model():
            return "configs/medsam2_configs/sam2.1_hiera_t512.yaml"
        return "configs/sam2.1/sam2.1_hiera_l.yaml"
    
    def is_sam2plus_model(self):
        """Check if we're using a SAM2++ model"""
        cp = self.get_default_checkpoint_path()
        return "SAM2-Plus" in cp if cp else False
    
    def get_default_checkpoint_path(self):
        """Get default checkpoint path - hardcoded for Hydra compatibility"""
        sam2plus_path = "./checkpoints/SAM2-Plus/checkpoint_phase123.pt"
        if os.path.exists(sam2plus_path):
            return sam2plus_path
        # Check for MedSAM2 checkpoints first (order by preference)
        medsam2_paths = [
            "./checkpoints/MedSAM2_latest.pt",
            "./checkpoints/MedSAM2_2411.pt",
            "./checkpoints/MedSAM2_US_Heart.pt",
            "./checkpoints/MedSAM2_MRI_LiverLesion.pt",
            "./checkpoints/MedSAM2_CTLesion.pt"
        ]
        
        for path in medsam2_paths:
            if os.path.exists(path):
                # print(f"[DEBUG] Found MedSAM2 checkpoint: {path}")  # Debug
                return path
            # else:
                # print(f"[DEBUG] MedSAM2 checkpoint not found: {path}")  # Debug
        
        # Fallback to standard SAM2
        # print("[DEBUG] Using SAM2 checkpoint")  # Debug
        return "./checkpoints/sam2.1_hiera_large.pt"
    
    def is_medsam2_model(self):
        """Check if we're using a MedSAM2 model"""
        checkpoint_path = self.get_default_checkpoint_path()
        return "medsam2" in checkpoint_path.lower() if checkpoint_path else False
    
    def is_point_mode(self):
        """Return True when SAM2++ point tracking mode is active."""
        return (getattr(self.sam2_backend, 'is_sam2plus', False) and
                getattr(self.sam2_backend, 'sam2plus_task', 'mask') == 'point')
    
    def select_sam2_files(self):
        """Allow user to select SAM2 configuration and checkpoint files with fallbacks"""
        # Get default paths (hardcoded for compatibility)
        default_config = self.get_default_config_path()
        default_checkpoint = self.get_default_checkpoint_path()
        
        ret = localized_question(
            self, self.localization,
            self.localization.get_text("sam2_config_title"),
            self.localization.get_text("sam2_config_question"),
            informative=self.localization.get_text(
                "sam2_config_defaults", default_config, default_checkpoint),
        )

        if ret == QMessageBox.Yes:
            # Select checkpoint file
            checkpoint_file, _ = QFileDialog.getOpenFileName(
                self,
                self.localization.get_text("sam2_config_select_checkpoint"),
                os.path.dirname(default_checkpoint) if default_checkpoint else "",
                build_file_filter(self.localization, 'pt')
            )

            if not checkpoint_file:
                checkpoint_file = default_checkpoint

            # Select configuration file
            config_file, _ = QFileDialog.getOpenFileName(
                self,
                self.localization.get_text("sam2_config_select_config"),
                os.path.dirname(default_config) if default_config else "",
                build_file_filter(self.localization, 'yaml')
            )
            
            if not config_file:
                config_file = default_config
        else:
            # Use default paths
            checkpoint_file = default_checkpoint
            config_file = default_config
        
        return config_file, checkpoint_file
    
    def update_window_title(self, checkpoint_path):
        """Update window title to include model name and, for SAM2++, the active sub-mode"""
        try:
            self._last_checkpoint_path = checkpoint_path  # remembered for language changes

            if "SAM2-Plus" in checkpoint_path:
                model_name = "SAM2++"
            else:
                model_name = os.path.splitext(os.path.basename(checkpoint_path))[0]

            base_title = self.localization.get_text("window_title")
            new_title = f"{base_title} - {model_name}"

            if self.sam2_backend and getattr(self.sam2_backend, 'is_sam2plus', False):
                mode_key = "mode_point_tracking" if self.is_point_mode() else "mode_mask"
                new_title += f" - {self.localization.get_text(mode_key)}"

            self.setWindowTitle(new_title)

            if self.debug_mode:
                print(f"Window title updated: {new_title}")

        except Exception as e:
            if self.debug_mode:
                print(f"Error updating window title: {e}")
            self.setWindowTitle(self.localization.get_text("window_title"))
    
    def connect_managers(self):
        """Connect managers together"""
        # Connect UI to managers
        self.event_manager.connect_to_ui(self.ui_manager)
        self.display_manager.connect_to_ui(self.ui_manager)
        
        # Set toolbar parent for zoom management
        if hasattr(self.ui_manager, 'toolbar'):
            self.ui_manager.toolbar.set_parent_app(self.display_manager)
    
    def keyPressEvent(self, event):
        """Handle keyboard events"""
        self.event_manager.handle_key_press(event)
    
    def closeEvent(self, event):
        """Handle application close event"""
        try:
            # Clean up SAM2 backend
            if self.sam2_backend:
                self.sam2_backend.reset_state()
            
            # Clean up managers
            if hasattr(self, 'ui_manager') and self.ui_manager:
                self.ui_manager.cleanup()
            
            if self.debug_mode:
                print("Application closed successfully")
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error during application shutdown: {e}")
        
        # Accept the close event
        event.accept()
    
    # Delegate methods to appropriate managers
    
    # Image management
    def select_folder(self):
        """Delegate to image manager"""
        return self.image_manager.select_folder()
    
    def load_images_from_folder(self, folder):
            """Load images and initialize SAM2; image preparation runs in a background thread."""
            try:
                if self.debug_mode:
                    print(f"=== LOADING IMAGES FROM FOLDER ===\n  Folder: {folder}")
    
                # Fast path on main thread: file listing + first image display
                success = self.image_manager.load_images_from_folder(folder)
                if not success:
                    return False
    
                # Heavy path in background: image prep + SAM2 init_state
                n_images = len(self.image_manager.image_paths)
                n_label  = os.path.basename(folder.rstrip(os.sep))
    
                progress_dlg = AnimatedProgressDialog(
                    self.localization.get_text("status_loading_images", n_label),
                    self.localization.get_text("cancel"),   # add "cancel" key to TSV files
                    0, n_images, self,
                )
                progress_dlg.setWindowTitle(n_label)
                progress_dlg.setWindowModality(Qt.WindowModal)
                progress_dlg.setMinimumDuration(300)   # skip dialog for fast cache-hit loads
                progress_dlg.setValue(0)
    
                worker     = LoadFolderWorker(self.sam2_backend, folder, parent=self)
                loop       = QEventLoop(self)
                sam2_ok    = [False]
                worker_err = [None]
    
                def on_progress(cur, tot, phase):
                    if phase == "init":
                        progress_dlg.setLabelText(
                            self.localization.get_text("status_initializing_sam2"))
                        progress_dlg.setMaximum(0)   # indeterminate spinner
                    else:
                        progress_dlg.setValue(cur)
    
                def on_finished(ok):
                    sam2_ok[0] = ok
                    # close() emits canceled(), which would flag the finished
                    # worker as cancelled and so hide any error it reported
                    progress_dlg.canceled.disconnect(worker.cancel)
                    progress_dlg.close()
                    loop.quit()
    
                def on_error(msg):
                    worker_err[0] = msg
    
                worker.progress.connect(on_progress)
                worker.finished.connect(on_finished)
                worker.error.connect(on_error)
                progress_dlg.canceled.connect(worker.cancel)
    
                worker.start()
                loop.exec_()
                worker.wait()   # ensure thread has fully exited before accessing shared state
    
                if worker_err[0] and not worker.cancelled:
                    self.ui_manager.show_message(
                        "error", self.localization.get_text("error"), worker_err[0])
                elif not sam2_ok[0] and not worker.cancelled:
                    # init_inference_state reports most failures by returning
                    # False rather than raising, so there is no message to relay
                    self.ui_manager.show_message(
                        "error", self.localization.get_text("error"),
                        self.localization.get_text("sam2_init_failed", n_label))
    
                if sam2_ok[0]:
                    if self.debug_mode and self.config_manager.show_filename_mappings():
                        stats = self.sam2_backend.filename_manager.get_statistics()
                        print(f"Filename mappings: {stats}")
                        is_consistent = self.sam2_backend.filename_manager.validate_consistency()
                        print(f"Mapping consistency check: {is_consistent}")
                    self.update_display()
    
                return sam2_ok[0]
    
            except Exception as e:
                if self.debug_mode:
                    import traceback; traceback.print_exc()
                return False
    
    def prev_image(self):
        """Delegate to image manager"""
        return self.image_manager.prev_image()
    
    def next_image(self):
        """Delegate to image manager"""
        return self.image_manager.next_image()
    
    def slider_changed(self):
        """Delegate to image manager"""
        return self.image_manager.slider_changed()
    
    # Prediction management
    def predict_current_image(self):
        """Delegate to prediction manager"""
        return self.prediction_manager.predict_current_image()
    
    def propagate_masks(self):
        """Delegate to prediction manager"""
        return self.prediction_manager.propagate_masks()
    
    def _refresh_repropagate_button_state(self):
        """Enable "Re-propagate from this frame…" only when the currently
        selected object has a pending correction on the current frame
        (precise per-object/per-frame tracking)."""
        btn = self.ui_manager.get_control('repropagate_btn')
        if not btn:
            return
        if (self.is_point_mode()
                or len(self.object_manager.selected_object_ids) != 1
                or not self.image_manager.has_images()):
            btn.setEnabled(False)
            return
        obj_id = self.object_manager.current_object_id
        frame_idx = self.image_manager.current_image_idx
        corrected = self.object_manager.object_corrected_frames.get(obj_id, set())
        btn.setEnabled(frame_idx in corrected)
    
    def repropagate_from_current_frame(self):
        """Re-propagate the currently selected object's masks from the current
        frame, over an optionally bounded span (an explicit action,
        not triggered automatically by a correction click)."""
        if self.is_point_mode():
            return
        if len(self.object_manager.selected_object_ids) != 1:
            self.ui_manager.show_message(
                "warning", self.localization.get_text("warning"),
                self.localization.get_text("multi_selection_add_points_blocked"),
            )
            return
        obj_id = self.object_manager.current_object_id
        frame_idx = self.image_manager.current_image_idx
        if frame_idx not in self.object_manager.object_masks.get(obj_id, {}):
            self.ui_manager.show_message(
                "warning", self.localization.get_text("warning"),
                self.localization.get_text("no_mask_on_frame_to_repropagate"),
            )
            return

        dlg = RepropagationSpanDialog(self.localization, self)
        if dlg.exec_() != QDialog.Accepted:
            return
        forward_frames, backward_frames = dlg.get_spans()

        self.prediction_manager.repropagate_object_from_frame(
            obj_id, frame_idx, forward_frames=forward_frames, backward_frames=backward_frames
        )
    
    # Display management
    def update_display(self, maintain_global_zoom=False):
        """Delegate to display manager"""
        return self.display_manager.update_display(maintain_global_zoom)
    
    def reset_global_zoom(self):
        """Delegate to display manager"""
        return self.display_manager.reset_global_zoom()
    
    def capture_global_zoom_state(self):
        """Delegate to display manager"""
        return self.display_manager.capture_global_zoom_state()
    
    # Event management (points and clicks)
    def clear_points(self):
        """Delegate to event manager"""
        return self.event_manager.clear_points()

    def remove_box(self):
        """Delegate to event manager"""
        return self.event_manager.remove_box()

    def _refresh_remove_box_button_state(self):
        """Enable "Remove box" only for a single selection whose object has a
        box on the current frame."""
        btn = self.ui_manager.get_control('remove_box_btn')
        if not btn:
            return
        if (len(self.object_manager.selected_object_ids) != 1
                or not self.image_manager.has_images()):
            btn.setEnabled(False)
            return
        btn.setEnabled(self.object_manager.get_box(
            self.object_manager.current_object_id,
            self.image_manager.current_image_idx) is not None)

    # SAM2++ point tracking display controls
    def update_tracked_point_style(self):
        """Delegate to property controller"""
        return self.property_controller.update_tracked_point_style()

    def update_tracked_point_size(self):
        """Delegate to property controller"""
        return self.property_controller.update_tracked_point_size()
    
    # Object management
    def change_current_object(self, index):
        """Change currently selected object"""
        obj_ids = sorted(self.object_manager.object_colors.keys())
        if 0 <= index < len(obj_ids):
            self.object_manager.current_object_id = obj_ids[index]
            self.ui_manager.update_object_ui()
            self.update_display(maintain_global_zoom=True)
    
    def on_objects_selection_changed(self):
        """Handle multi-selection changes in the objects/points list"""
        list_widget = self.ui_manager.get_control('objects_list')
        if not list_widget:
            return
        obj_ids = sorted(self.object_manager.object_colors.keys())
        rows = sorted(idx.row() for idx in list_widget.selectedIndexes())
        selected_ids = [obj_ids[r] for r in rows if 0 <= r < len(obj_ids)]
        if not selected_ids:
            return
        self.object_manager.selected_object_ids = set(selected_ids)
        self.object_manager.current_object_id = selected_ids[-1]
        self.ui_manager.update_object_ui()
        self.update_display(maintain_global_zoom=True)
    
    def add_new_object(self):
        """Add new object, select it exclusively (clearing prior selection), with undo support"""
        from .history_manager import Command
        om = self.object_manager
        prev_current = om.current_object_id
        prev_selected = set(om.selected_object_ids)

        new_id = om.add_new_object()
        snapshot = om.snapshot_object(new_id)

        om.current_object_id = new_id
        om.selected_object_ids = {new_id}
        self.ui_manager.update_objects_list()
        self.ui_manager.update_object_ui()
        # The list rebuild runs with its signals blocked, so the selection change
        # never reaches on_objects_selection_changed: without this the canvas
        # keeps showing the previous object's points until the next click.
        self.update_display(maintain_global_zoom=True)

        def _undo():
            om.remove_object(new_id)
            om.current_object_id = prev_current
            om.selected_object_ids = set(prev_selected)
            self.ui_manager.update_objects_list()
            self.ui_manager.update_object_ui()
            self.update_display(maintain_global_zoom=True)

        def _redo():
            om.restore_object(new_id, snapshot)
            om.current_object_id = new_id
            om.selected_object_ids = {new_id}
            self.ui_manager.update_objects_list()
            self.ui_manager.update_object_ui()
            self.update_display(maintain_global_zoom=True)

        self.history_manager.push(Command(undo_fn=_undo, redo_fn=_redo, label="Add object"))

        if self.debug_mode:
            print(f"Added new object with ID {new_id}")
    
    def remove_current_object(self):
        """Remove all currently selected objects/points, with undo support"""
        from .history_manager import Command
        om = self.object_manager
        selected = sorted(oid for oid in om.selected_object_ids if oid in om.object_colors)
        remaining_after = om.get_object_count() - len(selected)
        if remaining_after < 1:
            key = "cannot_remove_all_points" if self.is_point_mode() else "cannot_remove_all_objects"
            self.ui_manager.show_message("warning",
                                       self.localization.get_text("warning"),
                                       self.localization.get_text(key))
            return

        if len(selected) == 1:
            obj_name = om.object_names.get(selected[0], f"Object {selected[0]}")
            confirm_msg = self.localization.get_text("confirm_remove_object", obj_name)
        else:
            confirm_msg = self.localization.get_text("confirm_remove_objects", len(selected))

        reply = self.ui_manager.show_message("question",
                                            self.localization.get_text("confirmation"),
                                            confirm_msg)
        if reply != QMessageBox.Yes:
            return

        snapshots = {oid: om.snapshot_object(oid) for oid in selected}
        prev_current = om.current_object_id
        prev_selected = set(om.selected_object_ids)

        for obj_id in selected:
            om.remove_object(obj_id)

        remaining_ids = om.get_object_ids()
        new_current = remaining_ids[0] if remaining_ids else None
        om.current_object_id = new_current
        om.selected_object_ids = {new_current} if new_current else set()

        self.ui_manager.update_objects_list()
        self.ui_manager.update_object_ui()
        self.update_display(maintain_global_zoom=True)

        def _undo():
            for oid in selected:
                om.restore_object(oid, snapshots[oid])
            om.current_object_id = prev_current
            om.selected_object_ids = set(prev_selected)
            self.ui_manager.update_objects_list()
            self.ui_manager.update_object_ui()
            self.update_display(maintain_global_zoom=True)

        def _redo():
            for oid in selected:
                om.remove_object(oid)
            om.current_object_id = new_current
            om.selected_object_ids = {new_current} if new_current else set()
            self.ui_manager.update_objects_list()
            self.ui_manager.update_object_ui()
            self.update_display(maintain_global_zoom=True)

        self.history_manager.push(Command(undo_fn=_undo, redo_fn=_redo, label="Remove objects"))
    
    def update_object_name(self):
        """Update current object name"""
        name_edit = self.ui_manager.get_control('obj_name_edit')
        if not name_edit:
            return
        
        obj_id = self.object_manager.current_object_id
        new_name = name_edit.text()
        
        if not new_name:
            key = "point" if self.object_manager.point_mode else "object"
            new_name = f"{self.localization.get_text(key)} {obj_id}"
        
        self.object_manager.update_object_name(obj_id, new_name)
        
        # Update objects list
        self.ui_manager.update_objects_list()
    
    def commit_object_name_history(self):
        """Push an undo command for the object name once editing finishes (debounced)"""
        from .history_manager import Command
        name_edit = self.ui_manager.get_control('obj_name_edit')
        if not name_edit:
            return
        obj_id = self.object_manager.current_object_id
        before = getattr(name_edit, 'focus_in_text', '')
        after = self.object_manager.object_names.get(obj_id, '')
        if before == after:
            return

        def _apply(value):
            self.object_manager.update_object_name(obj_id, value)
            self.ui_manager.update_objects_list()
            if self.object_manager.current_object_id == obj_id:
                name_edit.blockSignals(True)
                name_edit.setText(value)
                name_edit.blockSignals(False)

        self.history_manager.push(Command(
            undo_fn=lambda: _apply(before),
            redo_fn=lambda: _apply(after),
            label="Rename object",
        ))
        name_edit.focus_in_text = after
    
    def choose_object_color(self, color_type):
        """Delegate to property controller"""
        return self.property_controller.choose_object_color(color_type)

    def update_object_marker_style(self):
        """Delegate to property controller"""
        return self.property_controller.update_object_marker_style()

    def update_object_marker_size(self):
        """Delegate to property controller"""
        return self.property_controller.update_object_marker_size()

    def update_object_mask_opacity(self):
        """Delegate to property controller"""
        return self.property_controller.update_object_mask_opacity()
    
    def choose_ref_point_color(self):
        """Delegate to property controller"""
        return self.property_controller.choose_ref_point_color()

    def update_ref_point_marker_style(self):
        """Delegate to property controller"""
        return self.property_controller.update_ref_point_marker_style()

    def update_ref_point_marker_size(self):
        """Delegate to property controller"""
        return self.property_controller.update_ref_point_marker_size()
    
    def toggle_ref_advanced_mode(self):
        """Toggle the reference-point advanced mode (per-frame positions).
        Disabling advanced mode is blocked while any reference point still has
        more than one explicitly defined frame."""
        checkbox = self.ui_manager.get_control('ref_advanced_mode_checkbox')
        if not checkbox:
            return
        rpm = self.ref_point_manager
        if not checkbox.isChecked():
            multi_frame_names = rpm.names_with_multi_frame_data()
            if multi_frame_names:
                names_str = '\n'.join(f"  • {n}" for n in multi_frame_names)
                self.ui_manager.show_message(
                    "warning",
                    self.localization.get_text("warning"),
                    self.localization.get_text("ref_advanced_mode_blocked").format(names_str),
                )
                checkbox.blockSignals(True)
                checkbox.setChecked(True)
                checkbox.blockSignals(False)
                return
        rpm.advanced_mode = checkbox.isChecked()
        self.ui_manager.ref_point_controls.update_ref_point_ui()
    
    def update_ref_point_extrapolation_policy(self):
        """Delegate to property controller"""
        return self.property_controller.update_ref_point_extrapolation_policy()
    
    def update_ref_point_interpolation_mode(self):
        """Delegate to property controller"""
        return self.property_controller.update_ref_point_interpolation_mode()
    
    def toggle_imported_points_display(self):
        """Toggle global visibility of imported points"""
        checkbox = self.ui_manager.get_control('show_imported_points_checkbox')
        if checkbox:
            self.imported_point_manager.show_imported_points = checkbox.isChecked()
            self.update_display(maintain_global_zoom=True)

    def choose_imported_point_color(self):
        """Delegate to property controller"""
        return self.property_controller.choose_imported_point_color()

    def update_imported_point_marker_style(self):
        """Delegate to property controller"""
        return self.property_controller.update_imported_point_marker_style()

    def update_imported_point_marker_size(self):
        """Delegate to property controller"""
        return self.property_controller.update_imported_point_marker_size()

    def remove_imported_point(self, name):
        """Remove an imported point (all frames), with confirmation and undo support"""
        import copy
        from PyQt5.QtWidgets import QMessageBox
        from .history_manager import Command

        ipm = self.imported_point_manager
        confirm_msg = self.localization.get_text("confirm_remove_imported_point", name)
        reply = self.ui_manager.show_message(
            "question", self.localization.get_text("confirmation"), confirm_msg
        )
        if reply != QMessageBox.Yes:
            return

        snapshot = {
            'frames': copy.deepcopy(ipm.imported_points.get(name, {})),
            'color': QColor(ipm.imported_point_colors[name]) if name in ipm.imported_point_colors else None,
            'marker': dict(ipm.imported_point_markers[name]) if name in ipm.imported_point_markers else None,
        }
        prev_current = ipm.current_imported_point_name
        prev_selected = set(ipm.selected_imported_point_names)

        ipm.remove_all_points(name)
        remaining = ipm.get_names()
        new_current = remaining[0] if remaining else None
        ipm.current_imported_point_name = new_current
        ipm.selected_imported_point_names = {new_current} if new_current else set()

        self.ui_manager.imported_point_controls._refresh_list()
        self.ui_manager.imported_point_controls.update_imported_point_ui()
        self.update_display(maintain_global_zoom=True)

        def _undo():
            ipm.imported_points[name] = copy.deepcopy(snapshot['frames'])
            if snapshot['color'] is not None:
                ipm.imported_point_colors[name] = QColor(snapshot['color'])
            if snapshot['marker'] is not None:
                ipm.imported_point_markers[name] = dict(snapshot['marker'])
            ipm.current_imported_point_name = prev_current
            ipm.selected_imported_point_names = set(prev_selected)
            self.ui_manager.imported_point_controls._refresh_list()
            self.ui_manager.imported_point_controls.update_imported_point_ui()
            self.update_display(maintain_global_zoom=True)

        def _redo():
            ipm.remove_all_points(name)
            ipm.current_imported_point_name = new_current
            ipm.selected_imported_point_names = {new_current} if new_current else set()
            self.ui_manager.imported_point_controls._refresh_list()
            self.ui_manager.imported_point_controls.update_imported_point_ui()
            self.update_display(maintain_global_zoom=True)

        self.history_manager.push(Command(undo_fn=_undo, redo_fn=_redo, label="Remove imported point"))
    
    def import_tracked_points(self):
        """
        Import a tracked-point file (SAM2++ point mode "Export tracked points")
        into the current mask-mode session. Points are matched to the current
        image folder by Original_Filename, not by the source session's
        Frame_Index (which may not align across sessions/orderings).
        """
        from PyQt5.QtWidgets import QMessageBox

        if self.is_point_mode():
            return
        if not self.image_manager.has_images():
            self.ui_manager.show_message(
                "warning", self.localization.get_text("warning"),
                self.localization.get_text("no_image_loaded"),
            )
            return

        path, _ = QFileDialog.getOpenFileName(
            self, self.localization.get_text("import_tracked_points"), "",
            build_file_filter(self.localization, 'xlsx', 'csv', 'json', 'all')
        )
        if not path:
            return

        try:
            rows = self.file_manager.read_tracked_points_file(path)
        except Exception as e:
            self.ui_manager.show_message(
                "error", self.localization.get_text("error"), str(e)
            )
            return
        if not rows:
            return

        # --- Validation 1: frame count, upfront -----------------------------
        current_paths = self.image_manager.get_all_image_paths()
        current_basenames = [os.path.basename(p) for p in current_paths]
        imported_filenames = sorted({r['original_filename'] for r in rows})

        if len(imported_filenames) != len(current_basenames):
            reply = localized_question(
                self, self.localization,
                self.localization.get_text("warning"),
                self.localization.get_text(
                    "imported_points_count_mismatch",
                    len(imported_filenames), len(current_basenames)
                ),
                icon=QMessageBox.Warning,
            )
            if reply != QMessageBox.Yes:
                return

        # --- Validation 2: filename matching ---------------------------------
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
            self.ui_manager.show_message(
                "error", self.localization.get_text("error"),
                self.localization.get_text("imported_points_no_match"),
            )
            return

        if unmatched:
            names_str = '\n'.join(f"  • {n}" for n in sorted(unmatched)[:10])
            if len(unmatched) > 10:
                names_str += f"\n  ({len(unmatched) - 10} more\u2026)"
            self.ui_manager.show_message(
                "warning", self.localization.get_text("warning"),
                self.localization.get_text(
                    "imported_points_filenames_unmatched", len(unmatched), names_str
                ),
            )

        # --- Cross-name conflicts (objects + reference points) ---------------
        imported_names = sorted({name for name, *_ in matched_rows})
        existing_names = (
            set(self.object_manager.object_names.values())
            | set(self.ref_point_manager.reference_points.keys())
        )
        conflicts = [n for n in imported_names if n in existing_names]
        if conflicts:
            txt = "\n".join(conflicts[:10])
            if len(conflicts) > 10:
                txt += f"\n({len(conflicts) - 10} more\u2026)"
            self.ui_manager.show_message(
                "warning",
                self.localization.get_text("import_cross_names_title"),
                self.localization.get_text("import_cross_names_msg", txt),
            )

        # --- Store points ------------------------------------------------------
        ipm = self.imported_point_manager
        for name, frame_idx, x_px, y_px in matched_rows:
            ipm.add_point(name, frame_idx, x_px, y_px)

        # --- Validation 3: coordinate bounds, a posteriori ----------------------
        image_info = self.image_manager.get_current_image_info()
        if image_info:
            width, height = image_info['width'], image_info['height']
            flagged = []
            for name in imported_names:
                n_oob = ipm.out_of_bounds_count(name, width, height)
                if n_oob > 0:
                    flagged.append(f"  • {name}: {n_oob}")
            if flagged:
                self.ui_manager.show_message(
                    "warning", self.localization.get_text("warning"),
                    self.localization.get_text(
                        "imported_points_out_of_bounds_warning", '\n'.join(flagged[:10])
                    ),
                )

        if not ipm.current_imported_point_name and imported_names:
            ipm.current_imported_point_name = imported_names[0]
            ipm.selected_imported_point_names = {imported_names[0]}

        self.ui_manager.imported_point_controls._refresh_list()
        self.ui_manager.imported_point_controls.update_imported_point_ui()
        self.update_display(maintain_global_zoom=True)

        self.ui_manager.show_message(
            "info", self.localization.get_text("success"),
            self.localization.get_text("imported_points_imported", len(matched_rows)),
        )
    
    # Delegate methods to appropriate managers
    
    def import_mask(self):
        """Delegate to GIMP UI controller"""
        return self.gimp_ui_controller.import_mask()

    def export_frame_for_gimp(self):
        """Delegate to GIMP UI controller"""
        return self.gimp_ui_controller.export_frame_for_gimp()

    def export_all_frames_for_gimp(self):
        """Delegate to GIMP UI controller"""
        return self.gimp_ui_controller.export_all_frames_for_gimp()
    
    def goto_prev_ref_point_frame(self):
        """Jump to the previous frame where the selected reference point has an
        explicitly defined position (not interpolated)."""
        rpm = self.ref_point_manager
        if len(rpm.selected_ref_point_names) > 1 or not rpm.current_ref_point_name:
            return
        current_frame = self.image_manager.current_image_idx
        target = rpm.get_adjacent_defined_frame(rpm.current_ref_point_name, current_frame, forward=False)
        if target is not None:
            self.image_manager.load_image(target)
    
    def goto_next_ref_point_frame(self):
        """Jump to the next frame where the selected reference point has an
        explicitly defined position (not interpolated)."""
        rpm = self.ref_point_manager
        if len(rpm.selected_ref_point_names) > 1 or not rpm.current_ref_point_name:
            return
        current_frame = self.image_manager.current_image_idx
        target = rpm.get_adjacent_defined_frame(rpm.current_ref_point_name, current_frame, forward=True)
        if target is not None:
            self.image_manager.load_image(target)
    
    def toggle_object_points_visibility(self):
        """Toggle point visibility for all selected objects"""
        checkbox = self.ui_manager.get_control('obj_show_points_checkbox')
        if checkbox:
            visible = checkbox.isChecked()
            for oid in self.object_manager.selected_object_ids:
                self.object_manager.set_object_points_visibility(oid, visible)
            self.update_display(maintain_global_zoom=True)
    
    def toggle_global_points_visibility(self):
        """Toggle global points visibility for the currently selected object"""
        checkbox = self.ui_manager.get_control('show_points_global_checkbox')
        if checkbox:
            self.show_points_global = checkbox.isChecked()
            self.update_display(maintain_global_zoom=True)
    
    # Centroid management
    def toggle_centroids_display(self):
        """Toggle centroid display"""
        checkbox = self.ui_manager.get_control('show_centroids_checkbox')
        if checkbox:
            self.object_manager.show_centroids = checkbox.isChecked()
            self.update_display(maintain_global_zoom=True)
    
    def choose_centroid_color(self):
        """Choose centroid color"""
        from PyQt5.QtWidgets import QColorDialog
        
        color = QColorDialog.getColor(self.object_manager.centroid_color, self, "Choose centroid color")
        if color.isValid():
            self.object_manager.centroid_color = color
            btn = self.ui_manager.get_control('centroid_color_btn')
            if btn:
                btn.setStyleSheet(f"background-color: {color.name()};")
            self.update_display(maintain_global_zoom=True)
    
    def update_centroid_size(self):
        """Update centroid size"""
        slider = self.ui_manager.get_control('centroid_size_slider')
        if slider:
            self.object_manager.centroid_size = slider.value()
            self.update_display(maintain_global_zoom=True)
    
    # ------------------------------------------------------------------
    # Convex hull management
    # ------------------------------------------------------------------

    def toggle_hulls_display(self):
        """Toggle global convex hull visibility"""
        checkbox = self.ui_manager.get_control('show_hulls_checkbox')
        if checkbox:
            self.object_manager.show_hulls = checkbox.isChecked()
            self.update_display(maintain_global_zoom=True)

    def update_hull_smoothing(self):
        """Update B-spline smoothing factor and recompute all stored hulls."""
        slider = self.ui_manager.get_control('hull_smoothing_slider')
        if slider:
            self.object_manager.hull_smoothing = slider.value() / 100.0
            self._recompute_hulls()
            self.update_display(maintain_global_zoom=True)

    def update_hull_line_width(self):
        """Update hull contour line width"""
        slider = self.ui_manager.get_control('hull_line_width_slider')
        if slider:
            self.object_manager.hull_line_width = slider.value()
            self.update_display(maintain_global_zoom=True)

    def toggle_hull_outline(self):
        """Toggle optional outer hull contour"""
        checkbox = self.ui_manager.get_control('hull_outline_checkbox')
        if checkbox:
            self.object_manager.hull_outline_visible = checkbox.isChecked()
            self.update_display(maintain_global_zoom=True)

    def choose_hull_outline_color(self):
        """Choose outer hull contour color"""
        from PyQt5.QtWidgets import QColorDialog
        color = QColorDialog.getColor(
            self.object_manager.hull_outline_color, self, "Choose hull outline color"
        )
        if color.isValid():
            self.object_manager.hull_outline_color = color
            btn = self.ui_manager.get_control('hull_outline_color_btn')
            if btn:
                btn.setStyleSheet(f"background-color: {color.name()};")
            self.update_display(maintain_global_zoom=True)

    # ------------------------------------------------------------------
    # Strict box clipping
    # ------------------------------------------------------------------

    def toggle_strict_box_clipping(self):
        """Toggle strict confinement of predicted masks to the object's box.
        Applies to subsequent predictions and propagations only — masks already
        clipped cannot be restored by turning the option back off."""
        checkbox = self.ui_manager.get_control('strict_box_clipping_checkbox')
        if not checkbox:
            return
        self.object_manager.strict_box_clipping = checkbox.isChecked()
        combo = self.ui_manager.get_control('box_clipping_mode_combo')
        if combo:
            combo.setEnabled(checkbox.isChecked())
        if (checkbox.isChecked()
                and self.object_manager.box_clipping_mode == 'reference_box'):
            self._warn_reference_box_clipping()

    def update_box_clipping_mode(self):
        """Select which box constrains a frame: only the frame's own box, or the
        object's reference box everywhere."""
        combo = self.ui_manager.get_control('box_clipping_mode_combo')
        if not combo:
            return
        mode = combo.currentData()
        if mode is None:
            return
        self.object_manager.box_clipping_mode = mode
        if mode == 'reference_box' and self.object_manager.strict_box_clipping:
            self._warn_reference_box_clipping()

    def _warn_reference_box_clipping(self):
        """Warn once per session that a reference box stops describing the object
        as soon as it moves."""
        if self._box_clipping_reference_warned:
            return
        self._box_clipping_reference_warned = True
        self.ui_manager.show_message(
            "warning", self.localization.get_text("warning"),
            self.localization.get_text("box_clipping_reference_warning"))

    def _recompute_hulls(self):
        """Recompute all stored hulls with the current smoothing parameter."""
        om = self.object_manager
        for obj_id, masks in om.object_masks.items():
            for frame_idx, mask in masks.items():
                verts = om.compute_hull(mask)
                if verts is not None:
                    verts = om.smooth_hull(verts, om.hull_smoothing)
                    if obj_id not in om.object_hulls:
                        om.object_hulls[obj_id] = {}
                    om.object_hulls[obj_id][frame_idx] = verts
                    coverage = om.compute_hull_coverage(mask, verts)
                    if obj_id not in om.object_hull_coverage:
                        om.object_hull_coverage[obj_id] = {}
                    om.object_hull_coverage[obj_id][frame_idx] = coverage
                elif obj_id in om.object_hulls:
                    om.object_hulls[obj_id].pop(frame_idx, None)
                    if obj_id in om.object_hull_coverage:
                        om.object_hull_coverage[obj_id].pop(frame_idx, None)

    # ------------------------------------------------------------------
    # Outer contour management
    # ------------------------------------------------------------------

    def toggle_contours_display(self):
        """Toggle global outer contour visibility"""
        checkbox = self.ui_manager.get_control('show_contours_checkbox')
        if checkbox:
            self.object_manager.show_contours = checkbox.isChecked()
            self.update_display(maintain_global_zoom=True)

    def update_contour_smoothing(self):
        """Update smoothing factor and recompute all stored contours."""
        slider = self.ui_manager.get_control('contour_smoothing_slider')
        if slider:
            self.object_manager.contour_smoothing = slider.value() / 100.0
            self._recompute_contours()
            self.update_display(maintain_global_zoom=True)

    def update_contour_line_width(self):
        """Update contour line width"""
        slider = self.ui_manager.get_control('contour_line_width_slider')
        if slider:
            self.object_manager.contour_line_width = slider.value()
            self.update_display(maintain_global_zoom=True)

    def toggle_contour_outline(self):
        """Toggle optional outer contour border"""
        checkbox = self.ui_manager.get_control('contour_outline_checkbox')
        if checkbox:
            self.object_manager.contour_outline_visible = checkbox.isChecked()
            self.update_display(maintain_global_zoom=True)

    def choose_contour_outline_color(self):
        """Choose outer contour border color"""
        from PyQt5.QtWidgets import QColorDialog
        color = QColorDialog.getColor(
            self.object_manager.contour_outline_color, self, "Choose contour outline color"
        )
        if color.isValid():
            self.object_manager.contour_outline_color = color
            btn = self.ui_manager.get_control('contour_outline_color_btn')
            if btn:
                btn.setStyleSheet(f"background-color: {color.name()};")
            self.update_display(maintain_global_zoom=True)

    def _recompute_contours(self):
        """Recompute all stored contours with the current smoothing parameter."""
        om = self.object_manager
        for obj_id, masks in om.object_masks.items():
            for frame_idx, mask in masks.items():
                verts = om.compute_contour(mask)
                if verts is not None:
                    verts = om.smooth_contour(verts, om.contour_smoothing)
                    if obj_id not in om.object_contours:
                        om.object_contours[obj_id] = {}
                    om.object_contours[obj_id][frame_idx] = verts
                    coverage = om.compute_contour_coverage(mask, verts)
                    if obj_id not in om.object_contour_coverage:
                        om.object_contour_coverage[obj_id] = {}
                    om.object_contour_coverage[obj_id][frame_idx] = coverage
                elif obj_id in om.object_contours:
                    om.object_contours[obj_id].pop(frame_idx, None)
                    if obj_id in om.object_contour_coverage:
                        om.object_contour_coverage[obj_id].pop(frame_idx, None)

    # Export management with configuration support
    def export_masked_images(self):
        """Delegate to export actions controller"""
        return self.export_actions.export_masked_images()

    def export_mask_coordinates(self):
        """Delegate to export actions controller"""
        return self.export_actions.export_mask_coordinates()

    def export_centroids(self):
        """Delegate to export actions controller"""
        return self.export_actions.export_centroids()

    def export_hull_coordinates(self):
        """Delegate to export actions controller"""
        return self.export_actions.export_hull_coordinates()

    def export_contour_coordinates(self):
        """Delegate to export actions controller"""
        return self.export_actions.export_contour_coordinates()

    def export_closest_mask_points(self):
        """Delegate to export actions controller"""
        return self.export_actions.export_closest_mask_points()

    def export_tracked_points(self):
        """Delegate to export actions controller"""
        return self.export_actions.export_tracked_points()

    def export_closest_tracked_points(self):
        """Delegate to export actions controller"""
        return self.export_actions.export_closest_tracked_points()

    def export_point_mask_analysis(self):
        """Delegate to export actions controller"""
        return self.export_actions.export_point_mask_analysis()

    def export_images_with_tracked_points(self):
        """Delegate to export actions controller"""
        return self.export_actions.export_images_with_tracked_points()

    def open_settings_dialog(self):
        """Open the settings dialog; most changes apply at the next start, the
        language and the file-dialog style being read once at startup."""
        from .settings_dialog import SettingsDialog

        dialog = SettingsDialog(self.localization, self.config_manager, self)
        if dialog.exec_() == QDialog.Accepted:
            self.ui_manager.show_message(
                "info", self.localization.get_text("settings_title"),
                self.localization.get_text("settings_saved"))

    def open_batch_dialog(self):
        """Open the batch processing dialog"""
        dialog = BatchDialog(self)
        dialog.exec_()
    
    # Inference state management
    def export_inference_state(self):
        """Export current project data (points, masks, objects)"""
        return self.inference_state_manager.export_inference_state_dialog()
    
    def import_inference_state(self):
        """Import saved project data (points, masks, objects)"""
        return self.inference_state_manager.import_inference_state_dialog()
    
    def export_sam2_inference_state(self):
        """Export SAM2 inference state with progress"""
        return self.inference_state_manager.export_sam2_inference_state_dialog()
    
    def import_sam2_inference_state(self):
        """Import SAM2 inference state with progress"""
        return self.inference_state_manager.import_sam2_inference_state_dialog()
    
    # Configuration management methods
    def get_config_info(self):
        """Get information about current configuration"""
        return self.config_manager.get_config_info()
    
    def save_current_config(self):
        """Save current configuration to file"""
        return self.config_manager.save_config()
    
    def reload_config(self):
        """Reload configuration from file"""
        self.config_manager = ConfigManager(debug_mode=self.debug_mode)
        if self.debug_mode:
            print("Configuration reloaded")
            self.config_manager.print_config()
    
    # Debug methods with configuration
    def debug_current_state(self):
        """Debug current state with configuration-aware output"""
        if not self.debug_mode:
            return
        
        try:
            print("=== CURRENT APPLICATION STATE DEBUG ===")
            
            # Configuration info
            config_info = self.config_manager.get_config_info()
            print(f"Configuration source: {config_info}")
            
            # Debug filename mappings if enabled
            if (hasattr(self.sam2_backend, 'filename_manager') and 
                self.config_manager.show_filename_mappings()):
                stats = self.sam2_backend.filename_manager.get_statistics()
                print(f"Filename mappings: {stats}")
                
                current_frame = self.image_manager.current_image_idx
                original_name = self.sam2_backend.filename_manager.get_original_filename(current_frame)
                print(f"Current frame {current_frame} -> original: {original_name}")
            
            # Debug masks if enabled
            if self.config_manager.show_mask_sync_details():
                current_frame = self.image_manager.current_image_idx
                print(f"Current frame: {current_frame}")
                
                total_masks = 0
                for obj_id, masks in self.object_manager.object_masks.items():
                    frames_with_masks = list(masks.keys())
                    total_masks += len(frames_with_masks)
                    print(f"Object {obj_id}: {len(frames_with_masks)} frames with masks")
                    
                    if current_frame in masks:
                        mask = masks[current_frame]
                        active_pixels = np.sum(mask)
                        print(f"  Current frame mask: shape {mask.shape}, active pixels: {active_pixels}")
                
                print(f"Total masks in application: {total_masks}")
            
            print("=== END STATE DEBUG ===")
            
        except Exception as e:
            print(f"Error in state debug: {e}")
    
    def debug_filename_mappings(self):
        """Debug filename mappings if enabled in configuration"""
        if not self.debug_mode or not self.config_manager.show_filename_mappings():
            return
        
        try:
            print("=== FILENAME MAPPINGS DEBUG ===")
            
            if hasattr(self.sam2_backend, 'filename_manager'):
                fm = self.sam2_backend.filename_manager
                
                # Check consistency
                is_consistent = fm.validate_consistency()
                print(f"Mapping consistency: {is_consistent}")
                
                # Show sample mappings
                print("Sample mappings:")
                for i in range(min(5, len(fm.frame_to_original))):
                    original = fm.get_original_filename(i)
                    temp = f"{i:05d}.jpg"
                    print(f"  Frame {i}: {temp} -> {original}")
                
                # Test reverse mapping
                if fm.frame_to_original:
                    test_original = list(fm.frame_to_original.values())[0]
                    frame_idx = fm.get_frame_index(test_original)
                    print(f"Reverse mapping test: {test_original} -> frame {frame_idx}")
            
            print("=== END FILENAME MAPPINGS DEBUG ===")
            
        except Exception as e:
            print(f"Error in filename mappings debug: {e}")