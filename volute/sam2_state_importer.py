"""
SAM2 State Importer, with progress bar
Handles import operations for SAM2 inference states with robust corruption handling
and enhanced mask synchronization for propagated masks
"""

import os
import pickle
import gzip
import numpy as np
from PyQt5.QtWidgets import QMessageBox, QApplication
import torch

from .sam2_serializer import SAM2Serializer
from .dialogs import localize_standard_buttons
from .sam2_state_validator import SAM2StateValidator
from .sam2_compatibility_checker import SAM2CompatibilityChecker
from .sam2_object_synchronizer import SAM2ObjectSynchronizer
from .progress_dialog import SAM2ImportProgressDialog
from .progress_worker import run_with_progress

class SAM2StateImporter:
    """Handles SAM2 inference state import operations with enhanced propagated mask support"""
    
    def __init__(self, main_window, debug_mode=False):
        self.main_window = main_window
        self.debug_mode = debug_mode
        
        # Initialize specialized components
        self.serializer = SAM2Serializer(debug_mode=debug_mode)
        self.validator = SAM2StateValidator(debug_mode=debug_mode)
        self.compatibility_checker = SAM2CompatibilityChecker(main_window, debug_mode=debug_mode)
        self.object_synchronizer = SAM2ObjectSynchronizer(main_window, debug_mode=debug_mode)
        
        # Progress dialog
        self.progress_dialog = None
        self.import_cancelled = False
    
    def import_sam2_inference_state(self, file_path):
        """Import SAM2 inference state from file with robust error handling and progress"""
        if not os.path.exists(file_path):
            self.main_window.ui_manager.show_message(
                "error", 
                "File Not Found", 
                f"File not found: {file_path}"
            )
            return False
        
        try:
            # Show progress dialog
            self.progress_dialog = SAM2ImportProgressDialog(self.main_window)
            self.progress_dialog.cancelled.connect(self._cancel_import)
            self.import_cancelled = False
            
            # Start import with progress
            return self._import_with_progress(file_path)
            
        except Exception as e:
            self._handle_import_error(e)
            return False
        finally:
            if self.progress_dialog:
                self.progress_dialog.close()
                self.progress_dialog = None
    
    def _import_with_progress(self, file_path):
        """Import with progress tracking"""
        try:
            self.progress_dialog.show()
            QApplication.processEvents()
            
            # Stage 1: Load file
            self.progress_dialog.update_import_stage('loading', 10,
                f"Loading file: {os.path.basename(file_path)}")
            QApplication.processEvents()
            
            if self.import_cancelled:
                return False
            
            sam2_state_data = self._load_state_file(file_path)
            if not sam2_state_data:
                return False
            
            # Stage 2: Validate compatibility
            self.progress_dialog.update_import_stage('validating', 20,
                "Checking file compatibility and integrity")
            QApplication.processEvents()
            
            if self.import_cancelled:
                return False
            
            if not self.compatibility_checker.check_compatibility(sam2_state_data):
                return False
            
            # Get user confirmation
            if not self._get_user_confirmation():
                return False
            
            # Stage 3: Prepare for import
            self.progress_dialog.update_import_stage('deserializing', 30,
                "Preparing application for import")
            QApplication.processEvents()
            
            if self.import_cancelled:
                return False
            
            self._prepare_for_import()
            
            # Stage 4: Import state data
            self.progress_dialog.update_import_stage('restoring', 50,
                "Restoring SAM2 inference state")
            QApplication.processEvents()
            
            if self.import_cancelled:
                return False
            
            if not self._import_state_data(sam2_state_data):
                return False
            
            # Stage 5: Synchronize masks
            self.progress_dialog.update_import_stage('synchronizing', 70,
                "Synchronizing masks with object manager")
            QApplication.processEvents()
            
            if self.import_cancelled:
                return False
            
            # Enhanced mask synchronization is already done in _import_state_data
            
            # Stage 6: Correct dimensions if needed
            self.progress_dialog.update_import_stage('correcting_dimensions', 85,
                "Checking and correcting mask dimensions")
            QApplication.processEvents()
            
            if self.import_cancelled:
                return False
            
            # The dimension correction is already handled by the display updater
            
            # Stage 7: Finalize
            self.progress_dialog.update_import_stage('finalizing', 95,
                "Finalizing import and updating display")
            QApplication.processEvents()
            
            if self.import_cancelled:
                return False
            
            self._finalize_import(file_path)
            
            # Stage 8: Complete
            self.progress_dialog.update_import_stage('complete', 100,
                f"Import completed: {os.path.basename(file_path)}")
            QApplication.processEvents()
            
            # Show completion for a moment
            self.progress_dialog.complete_operation(True, 
                "SAM2 inference state imported successfully")
            
            return True
            
        except Exception as e:
            self.progress_dialog.complete_operation(False, f"Import failed: {str(e)}")
            self._handle_import_error(e)
            return False
    
    def _run_off_gui_thread(self, work):
        """Return work() computed in a worker thread, the progress dialog
        repainting meanwhile; computed directly when there is no dialog.

        For the heavy steps that touch no widget. Messages, the confirmation
        and synchronizing the masks, which updates the objects list, stay on
        the GUI thread.
        """
        if self.progress_dialog is None:
            return work()
        return run_with_progress(self.progress_dialog,
                                 lambda report, is_cancelled: work(),
                                 on_report=lambda *args: None)

    def _cancel_import(self):
        """Handle import cancellation"""
        self.import_cancelled = True
        if self.debug_mode:
            print("Import cancelled by user")
    
    def _load_state_file(self, file_path):
        """Load and validate state file"""
        try:
            def read():
                with gzip.open(file_path, 'rb') as f:
                    return pickle.load(f)
            sam2_state_data = self._run_off_gui_thread(read)
            
            # Validate format
            if sam2_state_data.get('type') != 'sam2_inference_state':
                self.main_window.ui_manager.show_message(
                    "error", 
                    "Invalid File", 
                    "This file does not contain SAM2 inference state data."
                )
                return None
            
            if self.debug_mode:
                print(f"Loaded SAM2 state file: {file_path}")
                print(f"File keys: {list(sam2_state_data.keys())}")
            
            return sam2_state_data
            
        except Exception as e:
            self.main_window.ui_manager.show_message(
                "error",
                "File Load Error",
                f"Cannot load state file: {e}"
            )
            return None
    
    def _get_user_confirmation(self):
        """Get user confirmation for import with configurable default"""
        try:
            # Get default response from configuration
            default_yes = True
            if hasattr(self.main_window, 'config_manager'):
                default_yes = self.main_window.config_manager.get_import_confirmation_default()
            
            # Create custom message box with configurable default
            from PyQt5.QtWidgets import QMessageBox
            
            loc = self.main_window.localization
            msg_box = QMessageBox(self.main_window)
            msg_box.setWindowTitle(loc.get_text("import_sam2_state"))
            msg_box.setText(loc.get_text("import_sam2_state_warning"))
            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            localize_standard_buttons(msg_box, loc)
            
            # Set default button based on configuration
            if default_yes:
                msg_box.setDefaultButton(QMessageBox.Yes)
            else:
                msg_box.setDefaultButton(QMessageBox.No)
            
            reply = msg_box.exec_()
            return reply == QMessageBox.Yes
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error in confirmation dialog: {e}")
            # Fall back to the simpler show_message dialog
            reply = self.main_window.ui_manager.show_message(
                "question",
                self.main_window.localization.get_text("import_sam2_state"),
                self.main_window.localization.get_text("import_sam2_state_warning")
            )
            return reply == QMessageBox.Yes
    
    def _prepare_for_import(self):
        """Prepare application for import"""
        # Clear existing object data
        self.object_synchronizer.clear_object_manager()
        
        # Ensure clean SAM2 initialization
        if not self._ensure_clean_sam2_initialization():
            raise Exception("Failed to initialize clean SAM2 state")
    
    def _ensure_clean_sam2_initialization(self):
        """Ensure SAM2 is properly initialized with clean state"""
        if self.debug_mode:
            print("=== ENSURING CLEAN SAM2 INITIALIZATION ===")
        
        try:
            # Reset current state completely
            if self.main_window.sam2_backend:
                self.main_window.sam2_backend.reset_state()
            
            # Verify we have images to work with
            if not self.main_window.image_manager.current_folder:
                self.main_window.ui_manager.show_message(
                    "error",
                    "No Images Loaded",
                    "Please load images before importing SAM2 state."
                )
                return False
            
            # Initialize SAM2 with current images
            self._run_off_gui_thread(lambda: self.main_window.sam2_backend.init_inference_state(
                self.main_window.image_manager.current_folder
            ))
            
            # Verify initialization
            if not self._verify_initialization():
                raise Exception("SAM2 initialization verification failed")
            
            if self.debug_mode:
                print("SAM2 successfully initialized with clean state")
            
            return True
            
        except Exception as e:
            if self.debug_mode:
                print(f"Failed to initialize SAM2: {e}")
                import traceback
                traceback.print_exc()
            
            self.main_window.ui_manager.show_message(
                "error",
                "SAM2 Initialization Failed",
                f"Cannot initialize SAM2 with current images: {e}"
            )
            return False
        
        finally:
            if self.debug_mode:
                print("=== SAM2 INITIALIZATION COMPLETE ===")
    
    def _verify_initialization(self):
        """Verify SAM2 initialization was successful"""
        inference_state = self.main_window.sam2_backend.inference_state
        
        if not inference_state:
            raise Exception("SAM2 initialization failed - no inference state")
        
        # Verify images tensor
        if 'images' in inference_state:
            images_tensor = inference_state['images']
            if isinstance(images_tensor, str) or not hasattr(images_tensor, 'shape'):
                raise Exception("Images tensor is corrupted after initialization")
            
            if self.debug_mode:
                print(f"Images tensor shape: {images_tensor.shape}")
        
        return True
    
    def _import_state_data(self, sam2_state_data):
        """Import the actual state data with enhanced propagated mask support"""
        if 'inference_state' not in sam2_state_data:
            self.main_window.ui_manager.show_message(
                "error",
                "Invalid File",
                "No SAM2 inference state found in file."
            )
            return False
        
        try:
            # Restore state with robust handling
            success = self._run_off_gui_thread(
                lambda: self._restore_sam2_state_robust(sam2_state_data['inference_state']))
            
            if not success:
                raise Exception("Failed to restore inference state")
            
            # Synchronize masks via the object synchronizer
            if self.debug_mode:
                print("=== STARTING ENHANCED MASK SYNCHRONIZATION ===")
            
            self.object_synchronizer.synchronize_masks_from_sam2_state()
            
            # Additional debug: Check if masks were properly synchronized
            if self.debug_mode:
                self._debug_synchronization_result()
            
            # Restore object metadata if available
            self._restore_object_metadata(sam2_state_data)
            
            # Restore object points if available
            self._restore_object_points(sam2_state_data)
            
            return True
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error importing state data: {e}")
                import traceback
                traceback.print_exc()
            
            self.main_window.ui_manager.show_message(
                "error",
                "SAM2 Import Failed",
                f"Failed to restore SAM2 inference state: {e}"
            )
            return False
    
    def _debug_synchronization_result(self):
        """Debug the result of mask synchronization"""
        try:
            print("=== SYNCHRONIZATION RESULT DEBUG ===")
            
            object_manager = self.main_window.object_manager
            current_frame = self.main_window.image_manager.current_image_idx
            
            print(f"Current frame: {current_frame}")
            print(f"Objects in Object Manager: {list(object_manager.object_masks.keys())}")
            
            total_masks = 0
            current_frame_masks = 0
            
            for obj_id, masks in object_manager.object_masks.items():
                total_masks += len(masks)
                frames = list(masks.keys())
                print(f"Object {obj_id}: {len(masks)} masks on frames {frames[:10]}...")
                
                if current_frame in masks:
                    current_frame_masks += 1
                    mask = masks[current_frame]
                    active_pixels = np.sum(mask)
                    print(f"  Frame {current_frame}: mask shape {mask.shape}, active pixels: {active_pixels}")
                else:
                    print(f"  Frame {current_frame}: NO MASK")
            
            print(f"Total masks in Object Manager: {total_masks}")
            print(f"Masks on current frame {current_frame}: {current_frame_masks}")
            
            # If no masks on current frame, try to find a frame with masks
            if current_frame_masks == 0 and total_masks > 0:
                print("WARNING: No masks on current frame, looking for frames with masks...")
                for obj_id, masks in object_manager.object_masks.items():
                    if masks:
                        available_frames = sorted(masks.keys())
                        print(f"  Object {obj_id} has masks on frames: {available_frames[:5]}...")
            
            print("=== END SYNCHRONIZATION RESULT DEBUG ===")
            
        except Exception as e:
            print(f"Error in synchronization debug: {e}")
    
    def _clean_corrupted_cache(self, inference_state):
        """
        Clean corrupted cached features that can cause propagation errors
        
        Args:
            inference_state: SAM2 inference state
            
        Returns:
            dict: Cleaned inference state
        """
        try:
            if self.debug_mode:
                print("=== CLEANING CORRUPTED CACHE ===")
            
            # Clear cached features - they will be regenerated during propagation
            if 'cached_features' in inference_state:
                original_count = len(inference_state['cached_features'])
                inference_state['cached_features'] = {}
                
                if self.debug_mode:
                    print(f"Cleared {original_count} cached features entries")
            
            # Validate that 'images' is actually a tensor
            if 'images' in inference_state:
                images = inference_state['images']
                if isinstance(images, dict):
                    if self.debug_mode:
                        print("ERROR: 'images' is still a dict after deserialization!")
                    raise Exception("Images tensor was not properly deserialized")
                elif isinstance(images, torch.Tensor):
                    if self.debug_mode:
                        print(f"Images tensor validated: shape {images.shape}")
                else:
                    if self.debug_mode:
                        print(f"WARNING: Unknown images type: {type(images)}")
            
            if self.debug_mode:
                print("=== CACHE CLEANING COMPLETE ===")
            
            return inference_state
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error cleaning cache: {e}")
            raise
    
    def _restore_sam2_state_robust(self, serialized_state):
        """Robust SAM2 state restoration with enhanced propagated mask support"""
        if self.debug_mode:
            print("=== ROBUST SAM2 STATE RESTORATION ===")
        
        try:
            # Extract essential data first
            essential_data = self._extract_essential_data_from_serialized(serialized_state)
            
            # Filter out invalid objects BEFORE restoration
            essential_data = self._filter_valid_objects(essential_data)
            
            # Deserialize state
            current_device = self.main_window.sam2_backend.device
            restored_state = self.serializer.deserialize_sam2_state(serialized_state, current_device)
            
            restored_state = self._clean_corrupted_cache(restored_state)
            
            if restored_state is None:
                raise Exception("Failed to deserialize SAM2 state")
            
            # Apply state while preserving clean components
            self._apply_restored_state(restored_state, essential_data)
            
            # Validate final state
            current_state = self.main_window.sam2_backend.inference_state
            if not self.validator.validate_and_fix_sam2_state(current_state):
                if self.debug_mode:
                    print("Warning: SAM2 state validation failed")
            
            # Debug the restored state's contents
            if self.debug_mode:
                self._debug_restored_state_contents(current_state)
            
            if self.debug_mode:
                print("=== ROBUST SAM2 STATE RESTORATION COMPLETE ===")
            
            return True
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error in robust SAM2 state restoration: {e}")
                import traceback
                traceback.print_exc()
            return False
    
    def _debug_restored_state_contents(self, inference_state):
        """Debug the contents of the restored state to check for propagated masks"""
        try:
            print("=== RESTORED STATE CONTENTS DEBUG ===")
            
            # Check main keys
            main_keys = list(inference_state.keys())
            print(f"Main inference state keys: {main_keys}")
            
            # Check for temp_output_dict_per_obj (most likely to contain propagated masks)
            if 'temp_output_dict_per_obj' in inference_state:
                temp_output = inference_state['temp_output_dict_per_obj']
                print(f"temp_output_dict_per_obj: {len(temp_output)} objects")
                
                for obj_idx, obj_data in temp_output.items():
                    print(f"  Object {obj_idx} keys: {list(obj_data.keys())}")
                    
                    total_frames = 0
                    for output_type in ['cond_frame_outputs', 'non_cond_frame_outputs']:
                        if output_type in obj_data:
                            frames = obj_data[output_type]
                            total_frames += len(frames)
                            print(f"    {output_type}: {len(frames)} frames")
                            
                            # Check a sample frame for mask data
                            if frames:
                                sample_frame_idx = list(frames.keys())[0]
                                sample_frame = frames[sample_frame_idx]
                                if isinstance(sample_frame, dict):
                                    frame_keys = list(sample_frame.keys())
                                    print(f"      Sample frame {sample_frame_idx} keys: {frame_keys}")
                                    
                                    if 'pred_masks' in sample_frame:
                                        mask_tensor = sample_frame['pred_masks']
                                        if hasattr(mask_tensor, 'shape'):
                                            print(f"        pred_masks shape: {mask_tensor.shape}")
                    
                    print(f"  Object {obj_idx} total frames: {total_frames}")
            
            # Check for output_dict_per_obj (alternative location for propagated masks)
            if 'output_dict_per_obj' in inference_state:
                output_dict = inference_state['output_dict_per_obj']
                print(f"output_dict_per_obj: {len(output_dict)} objects")
                
                for obj_idx, obj_data in output_dict.items():
                    total_frames = 0
                    for output_type in ['cond_frame_outputs', 'non_cond_frame_outputs']:
                        if output_type in obj_data:
                            frames = obj_data[output_type]
                            total_frames += len(frames)
                    print(f"  Object {obj_idx}: {total_frames} total frames in output_dict")
            
            # Check object mappings
            if 'obj_id_to_idx' in inference_state:
                print(f"Object mappings: {inference_state['obj_id_to_idx']}")
            
            print("=== END RESTORED STATE CONTENTS DEBUG ===")
            
        except Exception as e:
            print(f"Error in restored state debug: {e}")
    
    def _extract_essential_data_from_serialized(self, serialized_state):
        """Extract essential data directly from serialized state"""
        essential_data = {}
        
        try:
            # Extract object mappings
            for key in ['obj_id_to_idx', 'obj_idx_to_id', 'obj_ids']:
                if key in serialized_state:
                    essential_data[key] = serialized_state[key]
            
            # Extract point inputs
            if 'point_inputs_per_obj' in serialized_state:
                point_inputs_serialized = serialized_state['point_inputs_per_obj']
                essential_data['point_inputs_per_obj'] = self._deserialize_point_inputs(point_inputs_serialized)
            
            if self.debug_mode:
                print(f"Extracted essential data: {list(essential_data.keys())}")
                if 'obj_id_to_idx' in essential_data:
                    print(f"Original object mappings: {essential_data['obj_id_to_idx']}")
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error extracting essential data: {e}")
        
        return essential_data
    
    def _filter_valid_objects(self, essential_data):
        """Filter out invalid objects and fix mappings"""
        if self.debug_mode:
            print("=== FILTERING VALID OBJECTS ===")
        
        try:
            point_inputs = essential_data.get('point_inputs_per_obj', {})
            
            # Find objects that have actual point inputs (valid objects)
            valid_obj_indices = []
            for obj_idx_str, frames_data in point_inputs.items():
                obj_idx = int(obj_idx_str)
                
                # Check if this object has valid point data
                has_valid_points = False
                for frame_idx, frame_data in frames_data.items():
                    if 'point_coords' in frame_data and 'point_labels' in frame_data:
                        has_valid_points = True
                        break
                
                if has_valid_points:
                    valid_obj_indices.append(obj_idx)
                elif self.debug_mode:
                    print(f"Filtering out invalid object {obj_idx} (no valid points)")
            
            if self.debug_mode:
                print(f"Valid object indices: {valid_obj_indices}")
            
            # Reconstruct clean mappings for valid objects only
            if valid_obj_indices:
                # Create clean mappings starting from valid objects
                clean_obj_id_to_idx = {}
                clean_obj_idx_to_id = {}
                clean_obj_ids = []
                
                for new_idx, old_idx in enumerate(valid_obj_indices):
                    # Use 1-based IDs for UI (SAM2 uses 0-based internally)
                    obj_id = new_idx + 1
                    
                    clean_obj_id_to_idx[obj_id] = new_idx
                    clean_obj_idx_to_id[new_idx] = obj_id
                    clean_obj_ids.append(obj_id)
                
                # Filter point inputs to keep only valid objects
                clean_point_inputs = {}
                for new_idx, old_idx in enumerate(valid_obj_indices):
                    if str(old_idx) in point_inputs:
                        clean_point_inputs[str(new_idx)] = point_inputs[str(old_idx)]
                
                # Update essential data with clean mappings
                essential_data['obj_id_to_idx'] = clean_obj_id_to_idx
                essential_data['obj_idx_to_id'] = clean_obj_idx_to_id
                essential_data['obj_ids'] = clean_obj_ids
                essential_data['point_inputs_per_obj'] = clean_point_inputs
                
                if self.debug_mode:
                    print(f"Clean object mappings: id_to_idx={clean_obj_id_to_idx}")
                    print(f"Clean point inputs: {len(clean_point_inputs)} objects")
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error filtering valid objects: {e}")
                import traceback
                traceback.print_exc()
        
        finally:
            if self.debug_mode:
                print("=== OBJECT FILTERING COMPLETE ===")
        
        return essential_data
    
    def _deserialize_point_inputs(self, point_inputs_serialized):
        """Deserialize point inputs specifically"""
        point_inputs = {}
        
        try:
            for obj_idx, frames_data in point_inputs_serialized.items():
                point_inputs[obj_idx] = {}
                
                for frame_idx, frame_data in frames_data.items():
                    point_inputs[obj_idx][frame_idx] = {}
                    
                    for key, value in frame_data.items():
                        if isinstance(value, dict) and value.get('type') == 'tensor':
                            current_device = self.main_window.sam2_backend.device
                            tensor = self.serializer._restore_tensor(value, current_device)
                            if tensor is not None:
                                point_inputs[obj_idx][frame_idx][key] = tensor
                        else:
                            point_inputs[obj_idx][frame_idx][key] = value
            
            if self.debug_mode:
                print(f"Deserialized point inputs for {len(point_inputs)} objects")
                
        except Exception as e:
            if self.debug_mode:
                print(f"Error deserializing point inputs: {e}")
        
        return point_inputs
    
    def _apply_restored_state(self, restored_state, essential_data):
        """Apply restored state while preserving clean components"""
        current_state = self.main_window.sam2_backend.inference_state
        
        # Preserve clean components
        clean_images = current_state.get('images')
        clean_device = current_state.get('device')
        clean_storage_device = current_state.get('storage_device')
        
        # Update with restored data
        current_state.clear()
        current_state.update(restored_state)
        
        # Restore clean components
        if clean_images is not None:
            current_state['images'] = clean_images
        if clean_device is not None:
            current_state['device'] = clean_device
        if clean_storage_device is not None:
            current_state['storage_device'] = clean_storage_device
        
        # Apply essential data with clean mappings
        for key in ['obj_id_to_idx', 'obj_idx_to_id', 'obj_ids']:
            if key in essential_data:
                current_state[key] = essential_data[key]
        
        # Recreate predictions
        if 'point_inputs_per_obj' in essential_data:
            current_state['point_inputs_per_obj'] = essential_data['point_inputs_per_obj']
            self._recreate_predictions_from_essential_data(current_state, essential_data)
    
    def _recreate_predictions_from_essential_data(self, inference_state, essential_data):
        """Recreate predictions from essential data - FIXED VERSION"""
        if self.debug_mode:
            print("=== RECREATING PREDICTIONS FROM ESSENTIAL DATA ===")
        
        try:
            point_inputs = essential_data.get('point_inputs_per_obj', {})
            predictions_created = 0
            
            # Create a copy of items to avoid "dictionary changed size during iteration"
            point_inputs_items = list(point_inputs.items())
            
            for obj_idx_str, frames_data in point_inputs_items:
                obj_idx = int(obj_idx_str)
                
                # Create copy of frames_data items too
                frames_data_items = list(frames_data.items())
                
                for frame_idx_str, frame_data in frames_data_items:
                    frame_idx = int(frame_idx_str)
                    
                    try:
                        point_coords = frame_data.get('point_coords')
                        point_labels = frame_data.get('point_labels')
                        
                        if point_coords is not None and point_labels is not None:
                            coords_np, labels_np = self._prepare_point_data(point_coords, point_labels)
                            
                            if coords_np is not None and labels_np is not None:
                                self._add_points_to_sam2(inference_state, frame_idx, obj_idx, coords_np, labels_np)
                                predictions_created += 1
                                
                                if self.debug_mode:
                                    print(f"  Recreated obj {obj_idx}, frame {frame_idx}")
                    
                    except Exception as e:
                        if self.debug_mode:
                            print(f"  Error processing obj {obj_idx}, frame {frame_idx}: {e}")
                        continue
            
            if self.debug_mode:
                print(f"=== PREDICTIONS RECREATION COMPLETE: {predictions_created} predictions created ===")
        
        except Exception as e:
            if self.debug_mode:
                print(f"Error recreating predictions: {e}")
                import traceback
                traceback.print_exc()
    
    def _prepare_point_data(self, point_coords, point_labels):
        """Prepare point data for SAM2"""
        try:
            # Convert to numpy arrays
            if hasattr(point_coords, 'cpu'):
                coords_np = point_coords.cpu().numpy()
            else:
                coords_np = np.array(point_coords)
                
            if hasattr(point_labels, 'cpu'):
                labels_np = point_labels.cpu().numpy()
            else:
                labels_np = np.array(point_labels)
            
            # Handle tensor shapes
            if len(coords_np.shape) == 3:  # [1, N, 2]
                coords_np = coords_np[0]
            if len(labels_np.shape) == 2:  # [1, N]
                labels_np = labels_np[0]
            
            return coords_np, labels_np
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error preparing point data: {e}")
            return None, None
    
    def _add_points_to_sam2(self, inference_state, frame_idx, obj_idx, coords_np, labels_np):
        """Add points to SAM2 to recreate predictions"""
        try:
            _, _, _ = self.main_window.sam2_backend.video_predictor.add_new_points_or_box(
                inference_state=inference_state,
                frame_idx=frame_idx,
                obj_id=obj_idx,
                points=coords_np,
                labels=labels_np,
            )
        except Exception as e:
            if self.debug_mode:
                print(f"Failed to add points to SAM2: {e}")
            raise
    
    def _finalize_import(self, file_path):
        """Finalize the import process"""
        # Force display update using enhanced synchronizer
        self.object_synchronizer.force_display_update()
        
        if self.debug_mode:
            print(f"Successfully imported SAM2 inference state from {file_path}")
    
    def _handle_import_error(self, error):
        """Handle import errors"""
        error_msg = f"Error importing SAM2 inference state: {error}"
        if self.debug_mode:
            print(error_msg)
            import traceback
            traceback.print_exc()
        self.main_window.ui_manager.show_message("error", "SAM2 Import Error", error_msg)
    
    def _restore_object_metadata(self, sam2_state_data):
        """Restore object metadata (names, colors, etc.) if available"""
        if 'object_metadata' not in sam2_state_data:
            if self.debug_mode:
                print("No object metadata to restore")
            return
        
        try:
            if self.debug_mode:
                print("=== RESTORING OBJECT METADATA ===")
            
            object_metadata = sam2_state_data['object_metadata']
            object_manager = self.main_window.object_manager
            
            for obj_id_str, obj_meta in object_metadata.items():
                try:
                    obj_id = int(obj_id_str) if isinstance(obj_id_str, str) else obj_id_str
                    
                    # Only restore metadata for objects that actually exist
                    if obj_id not in object_manager.object_masks:
                        continue
                    
                    if self.debug_mode:
                        print(f"Restoring metadata for object {obj_id}")
                    
                    # Restore name
                    if 'name' in obj_meta:
                        object_manager.object_names[obj_id] = obj_meta['name']
                        if self.debug_mode:
                            print(f"  Restored name: {obj_meta['name']}")
                    
                    # Restore colors
                    if 'colors' in obj_meta:
                        from PyQt5.QtGui import QColor
                        restored_colors = {}
                        for color_type, rgba in obj_meta['colors'].items():
                            if isinstance(rgba, (list, tuple)) and len(rgba) >= 3:
                                if len(rgba) == 3:
                                    restored_colors[color_type] = QColor(rgba[0], rgba[1], rgba[2])
                                else:
                                    restored_colors[color_type] = QColor(rgba[0], rgba[1], rgba[2], rgba[3])
                        
                        if restored_colors:
                            object_manager.object_colors[obj_id] = restored_colors
                            if self.debug_mode:
                                print(f"  Restored colors: {list(restored_colors.keys())}")
                    
                    # Restore markers
                    if 'markers' in obj_meta:
                        object_manager.object_markers[obj_id] = obj_meta['markers']
                        if self.debug_mode:
                            print(f"  Restored markers: {obj_meta['markers']}")
                    
                    # Restore visibility
                    if 'show_points' in obj_meta and hasattr(object_manager, 'object_show_points'):
                        object_manager.object_show_points[obj_id] = obj_meta['show_points']
                        if self.debug_mode:
                            print(f"  Restored visibility: {obj_meta['show_points']}")
                
                except Exception as e:
                    if self.debug_mode:
                        print(f"Error restoring metadata for object {obj_id_str}: {e}")
                    continue
            
            if self.debug_mode:
                print("=== OBJECT METADATA RESTORATION COMPLETE ===")
        
        except Exception as e:
            if self.debug_mode:
                print(f"Error restoring object metadata: {e}")
                import traceback
                traceback.print_exc()
    
    def _restore_object_points(self, sam2_state_data):
        """Restore object points if available"""
        if 'object_points' not in sam2_state_data:
            if self.debug_mode:
                print("No object points to restore")
            return
        
        try:
            if self.debug_mode:
                print("=== RESTORING OBJECT POINTS ===")
            
            object_points = sam2_state_data['object_points']
            object_manager = self.main_window.object_manager
            
            for obj_id_str, frames_points in object_points.items():
                try:
                    obj_id = int(obj_id_str) if isinstance(obj_id_str, str) else obj_id_str
                    
                    # Only restore points for objects that actually exist
                    if obj_id not in object_manager.object_masks:
                        continue
                    
                    if self.debug_mode:
                        print(f"Restoring points for object {obj_id}")
                    
                    # Ensure object points structure exists
                    if obj_id not in object_manager.object_points:
                        object_manager.object_points[obj_id] = {}
                    
                    for frame_idx_str, frame_points in frames_points.items():
                        try:
                            frame_idx = int(frame_idx_str) if isinstance(frame_idx_str, str) else frame_idx_str
                            
                            # Restore points for this frame
                            restored_frame_points = {
                                'positive': [],
                                'negative': []
                            }
                            
                            for point_type in ['positive', 'negative']:
                                if point_type in frame_points and frame_points[point_type]:
                                    points_list = []
                                    for point in frame_points[point_type]:
                                        if isinstance(point, (list, tuple)) and len(point) >= 2:
                                            points_list.append([float(point[0]), float(point[1])])
                                    
                                    if points_list:
                                        restored_frame_points[point_type] = points_list
                            
                            # Only add if we have points
                            if restored_frame_points['positive'] or restored_frame_points['negative']:
                                object_manager.object_points[obj_id][frame_idx] = restored_frame_points
                                
                                if self.debug_mode:
                                    pos_count = len(restored_frame_points['positive'])
                                    neg_count = len(restored_frame_points['negative'])
                                    print(f"  Frame {frame_idx}: {pos_count} positive, {neg_count} negative points")
                        
                        except Exception as e:
                            if self.debug_mode:
                                print(f"Error restoring points for frame {frame_idx_str}: {e}")
                            continue
                
                except Exception as e:
                    if self.debug_mode:
                        print(f"Error restoring points for object {obj_id_str}: {e}")
                    continue
            
            if self.debug_mode:
                print("=== OBJECT POINTS RESTORATION COMPLETE ===")
        
        except Exception as e:
            if self.debug_mode:
                print(f"Error restoring object points: {e}")
                import traceback
                traceback.print_exc()
    
    def inspect_sam2_inference_state(self):
        """Inspect SAM2 inference state for debugging"""
        inference_state = self.main_window.sam2_backend.inference_state
        self.validator.inspect_sam2_inference_state(inference_state)
    
    def debug_import_process(self, file_path):
        """Debug helper to analyze import process step by step"""
        if not self.debug_mode:
            return
        
        try:
            print("=== SAM2 IMPORT PROCESS DEBUG ===")
            print(f"File: {file_path}")
            
            # Load file
            sam2_state_data = self._load_state_file(file_path)
            if sam2_state_data:
                print(f"File loaded successfully")
                print(f"Top-level keys: {list(sam2_state_data.keys())}")
                
                # Check inference state contents
                if 'inference_state' in sam2_state_data:
                    inf_state = sam2_state_data['inference_state']
                    print(f"Inference state keys: {list(inf_state.keys())}")
                    
                    # Check for propagated masks
                    mask_locations = []
                    if 'temp_output_dict_per_obj' in inf_state:
                        mask_locations.append('temp_output_dict_per_obj')
                    if 'output_dict_per_obj' in inf_state:
                        mask_locations.append('output_dict_per_obj')
                    
                    print(f"Potential mask locations: {mask_locations}")
                
                # Check metadata
                if 'object_metadata' in sam2_state_data:
                    metadata = sam2_state_data['object_metadata']
                    print(f"Object metadata for {len(metadata)} objects")
                
                print("File analysis complete")
            else:
                print("Failed to load file")
            
            print("=== END IMPORT PROCESS DEBUG ===")
            
        except Exception as e:
            print(f"Error in import debug: {e}")
    
    def test_mask_synchronization(self):
        """Test helper to verify mask synchronization is working"""
        if not self.debug_mode:
            return
        
        try:
            print("=== TESTING MASK SYNCHRONIZATION ===")
            
            # Test the object synchronizer directly
            if hasattr(self.object_synchronizer, 'debug_sam2_state_contents'):
                self.object_synchronizer.debug_sam2_state_contents()
            
            # Force synchronization
            self.object_synchronizer.synchronize_masks_from_sam2_state()
            
            # Check results
            self._debug_synchronization_result()
            
            print("=== END MASK SYNCHRONIZATION TEST ===")
            
        except Exception as e:
            print(f"Error in mask synchronization test: {e}")
            import traceback
            traceback.print_exc()