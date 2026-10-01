"""
SAM2 Mask Synchronizer
Handles extraction and synchronization of masks from SAM2 state, including propagated masks
"""

import numpy as np
from PyQt5.QtGui import QColor
import random

class SAM2MaskSynchronizer:
    """Handles mask synchronization between SAM2 and Object Manager with enhanced propagated mask support"""
    
    def __init__(self, main_window, debug_mode=False):
        self.main_window = main_window
        self.debug_mode = debug_mode
    
    def synchronize_masks_from_sam2_state(self):
        """Extract masks from SAM2 state and synchronize with Object Manager - Enhanced version"""
        if self.debug_mode:
            print("\n=== ENHANCED SYNCHRONIZING MASKS FROM SAM2 STATE ===")
        
        try:
            inference_state = self.main_window.sam2_backend.inference_state
            if not inference_state:
                if self.debug_mode:
                    print("No inference state to synchronize")
                return
            
            # Get current frame index
            current_frame_idx = self.main_window.image_manager.current_image_idx
            
            # Extract object mappings
            obj_id_to_idx = inference_state.get('obj_id_to_idx', {})
            obj_idx_to_id = inference_state.get('obj_idx_to_id', {})
            
            if self.debug_mode:
                print(f"Current frame: {current_frame_idx}")
                print(f"Object mappings: id_to_idx={obj_id_to_idx}, idx_to_id={obj_idx_to_id}")
            
            # Strategy 1: Look for masks in temp_output_dict_per_obj (most current, includes propagated)
            temp_outputs = inference_state.get('temp_output_dict_per_obj', {})
            masks_from_temp = 0
            
            if temp_outputs:
                if self.debug_mode:
                    print(f"Found temp outputs for {len(temp_outputs)} objects")
                masks_from_temp = self._process_temp_outputs(temp_outputs, obj_idx_to_id)
            
            # Strategy 2: Look for masks in output_dict_per_obj (fallback for propagated masks)
            output_dict = inference_state.get('output_dict_per_obj', {})
            masks_from_output = 0
            
            if output_dict and masks_from_temp == 0:
                if self.debug_mode:
                    print(f"Found output dict for {len(output_dict)} objects")
                masks_from_output = self._process_output_dict(output_dict, obj_idx_to_id)
            
            total_masks = masks_from_temp + masks_from_output
            
            if self.debug_mode:
                print(f"=== ENHANCED MASK SYNCHRONIZATION COMPLETE: {total_masks} masks synchronized ===")
                print(f"  From temp_output: {masks_from_temp}")
                print(f"  From output_dict: {masks_from_output}")
                self._debug_object_manager_state()
        
        except Exception as e:
            if self.debug_mode:
                print(f"Error in enhanced mask synchronization: {e}")
                import traceback
                traceback.print_exc()
    
    def _process_temp_outputs(self, temp_outputs, obj_idx_to_id):
        """Process temporary outputs to extract masks (most current masks)"""
        masks_synchronized = 0
        
        for obj_idx, obj_data in temp_outputs.items():
            try:
                obj_idx = int(obj_idx)
                obj_id = obj_idx_to_id.get(obj_idx, obj_idx + 1)  # SAM2 uses 0-based, we use 1-based
                
                if self.debug_mode:
                    print(f"Processing temp output - object idx={obj_idx}, id={obj_id}")
                
                # Ensure object exists in Object Manager
                self._ensure_object_exists_in_manager(obj_id)
                
                # Process frames for this object from temp outputs
                masks_for_object = self._process_object_frames_enhanced(obj_id, obj_data)
                masks_synchronized += masks_for_object
            
            except Exception as e:
                if self.debug_mode:
                    print(f"Error processing temp output object {obj_idx}: {e}")
                continue
        
        return masks_synchronized
    
    def _process_output_dict(self, output_dict, obj_idx_to_id):
        """Process output_dict_per_obj to extract propagated masks"""
        masks_synchronized = 0
        
        for obj_idx, obj_data in output_dict.items():
            try:
                obj_idx = int(obj_idx)
                obj_id = obj_idx_to_id.get(obj_idx, obj_idx + 1)
                
                if self.debug_mode:
                    print(f"Processing output dict - object idx={obj_idx}, id={obj_id}")
                
                # Ensure object exists in Object Manager
                self._ensure_object_exists_in_manager(obj_id)
                
                # Process frames for this object from output dict
                masks_for_object = self._process_object_frames_enhanced(obj_id, obj_data)
                masks_synchronized += masks_for_object
            
            except Exception as e:
                if self.debug_mode:
                    print(f"Error processing output dict object {obj_idx}: {e}")
                continue
        
        return masks_synchronized
    
    def _process_object_frames_enhanced(self, obj_id, obj_data):
        """Process all frames for a specific object - Enhanced to handle both cond and non_cond outputs"""
        masks_synchronized = 0
        
        # Process both conditional and non-conditional frame outputs
        for output_type in ['cond_frame_outputs', 'non_cond_frame_outputs']:
            if output_type not in obj_data:
                continue
            
            frame_outputs = obj_data[output_type]
            
            if self.debug_mode:
                print(f"  Processing {output_type}: {len(frame_outputs)} frames")
            
            for frame_idx, frame_output in frame_outputs.items():
                try:
                    frame_idx = int(frame_idx)
                    
                    # Extract mask if available
                    pred_masks = frame_output.get('pred_masks')
                    
                    if pred_masks is not None and hasattr(pred_masks, 'shape'):
                        if self.debug_mode:
                            print(f"    Found mask for frame {frame_idx}: shape {pred_masks.shape}")
                        
                        # Process and store the mask
                        if self._process_and_store_mask(obj_id, frame_idx, pred_masks):
                            masks_synchronized += 1
                
                except Exception as e:
                    if self.debug_mode:
                        print(f"    Error processing frame {frame_idx}: {e}")
                    continue
        
        return masks_synchronized
    
    def _process_object_frames(self, obj_id, obj_data):
        """Process all frames for a specific object - Original method for compatibility"""
        masks_synchronized = 0
        cond_frame_outputs = obj_data.get('cond_frame_outputs', {})
        
        for frame_idx, frame_output in cond_frame_outputs.items():
            try:
                frame_idx = int(frame_idx)
                
                # Extract mask if available
                pred_masks = frame_output.get('pred_masks')
                
                if pred_masks is not None and hasattr(pred_masks, 'shape'):
                    if self.debug_mode:
                        print(f"  Found mask for frame {frame_idx}: shape {pred_masks.shape}")
                    
                    # Process and store the mask
                    if self._process_and_store_mask(obj_id, frame_idx, pred_masks):
                        masks_synchronized += 1
            
            except Exception as e:
                if self.debug_mode:
                    print(f"  Error processing frame {frame_idx}: {e}")
                continue
        
        return masks_synchronized
    
    def _process_and_store_mask(self, obj_id, frame_idx, pred_masks):
        """Process a single mask and store it in Object Manager"""
        try:
            # Process the mask
            mask = self._process_sam2_mask_for_object_manager(pred_masks)
            
            if mask is not None:
                # Store mask in Object Manager
                self.main_window.object_manager.object_masks[obj_id][frame_idx] = mask
                
                # Calculate and store centroid
                centroid = self.main_window.object_manager.calculate_centroid(mask)
                if centroid:
                    if obj_id not in self.main_window.object_manager.object_centroids:
                        self.main_window.object_manager.object_centroids[obj_id] = {}
                    self.main_window.object_manager.object_centroids[obj_id][frame_idx] = centroid
                
                if self.debug_mode:
                    print(f"    -> Synchronized mask for obj {obj_id}, frame {frame_idx}")
                    print(f"    -> Mask shape: {mask.shape}, active pixels: {np.sum(mask)}")
                
                return True
        
        except Exception as e:
            if self.debug_mode:
                print(f"Error processing mask for obj {obj_id}, frame {frame_idx}: {e}")
        
        return False
    
    def _process_sam2_mask_for_object_manager(self, pred_masks):
        """Convert SAM2 mask format to Object Manager format"""
        try:
            # Convert tensor to numpy if needed
            if hasattr(pred_masks, 'cpu'):
                mask_np = pred_masks.cpu().detach().numpy()
            else:
                mask_np = pred_masks
            
            # Handle different mask shapes
            if len(mask_np.shape) == 4:  # [1, 1, H, W]
                mask = mask_np[0, 0]
            elif len(mask_np.shape) == 3:  # [1, H, W]
                mask = mask_np[0]
            elif len(mask_np.shape) == 2:  # [H, W]
                mask = mask_np
            else:
                if self.debug_mode:
                    print(f"Unknown mask shape: {mask_np.shape}")
                return None
            
            # Convert to binary mask (SAM2 outputs logits, we need binary)
            binary_mask = mask > 0.0
            
            if self.debug_mode:
                print(f"      Processed mask: {mask.shape} -> {binary_mask.shape}, active pixels: {binary_mask.sum()}")
            
            return binary_mask.astype(bool)
        
        except Exception as e:
            if self.debug_mode:
                print(f"Error processing mask: {e}")
            return None
    
    def _ensure_object_exists_in_manager(self, obj_id):
        """Ensure object exists in Object Manager with all required properties"""
        object_manager = self.main_window.object_manager
        
        if obj_id not in object_manager.object_masks:
            object_manager.object_masks[obj_id] = {}
        
        if obj_id not in object_manager.object_colors:
            object_manager.object_colors[obj_id] = {
                'positive': QColor(0, 255, 0),
                'negative': QColor(255, 0, 0),
                'mask': QColor(random.randint(50, 255), random.randint(50, 255), random.randint(50, 255), 128)
            }
        
        if obj_id not in object_manager.object_names:
            object_manager.object_names[obj_id] = f"Object {obj_id}"
        
        if obj_id not in object_manager.object_markers:
            object_manager.object_markers[obj_id] = {'style': 'o', 'size': 5}
        
        if obj_id not in object_manager.object_show_points:
            object_manager.object_show_points[obj_id] = True
        
        if obj_id not in object_manager.object_centroids:
            object_manager.object_centroids[obj_id] = {}
        
        # Ensure object points exist
        if obj_id not in object_manager.object_points:
            object_manager.object_points[obj_id] = {}
        
        # Ensure the object appears in the objects list
        if hasattr(self.main_window, 'ui_manager'):
            self.main_window.ui_manager.update_objects_list()
    
    def _debug_object_manager_state(self):
        """Debug: Check what's actually in Object Manager"""
        if not self.debug_mode:
            return
        
        print("\n=== OBJECT MANAGER DEBUG ===")
        object_manager = self.main_window.object_manager
        
        for obj_id, masks in object_manager.object_masks.items():
            print(f"Object {obj_id}: {len(masks)} masks on frames {list(masks.keys())}")
            for frame_idx, mask in masks.items():
                coverage = np.sum(mask) / mask.size * 100
                print(f"  Frame {frame_idx}: shape {mask.shape}, type {type(mask)}, active pixels: {np.sum(mask)} ({coverage:.1f}%)")
        
        print("=== END OBJECT MANAGER DEBUG ===")
    
    def clear_object_manager(self):
        """Clear all object data from Object Manager"""
        try:
            if self.debug_mode:
                print("=== CLEARING OBJECT MANAGER ===")
            
            object_manager = self.main_window.object_manager
            
            # Clear all object data structures
            object_manager.object_masks.clear()
            object_manager.object_colors.clear()
            object_manager.object_names.clear()
            object_manager.object_markers.clear()
            object_manager.object_centroids.clear()
            object_manager.object_points.clear()
            
            if hasattr(object_manager, 'object_show_points'):
                object_manager.object_show_points.clear()
            
            if self.debug_mode:
                print("Object Manager cleared successfully")
        
        except Exception as e:
            if self.debug_mode:
                print(f"Error clearing Object Manager: {e}")
    
    def force_display_update(self):
        """Force display update after mask synchronization"""
        try:
            if self.debug_mode:
                print("=== FORCING DISPLAY UPDATE ===")
            
            # Update UI components
            if hasattr(self.main_window, 'ui_manager'):
                self.main_window.ui_manager.update_objects_list()
                self.main_window.ui_manager.update_object_ui()
            
            # Update display
            if hasattr(self.main_window, 'display_manager'):
                self.main_window.display_manager.update_display()
            
            # Process Qt events
            try:
                from PyQt5.QtWidgets import QApplication
                QApplication.processEvents()
            except:
                pass
            
            if self.debug_mode:
                print("Display update completed")
        
        except Exception as e:
            if self.debug_mode:
                print(f"Error updating display: {e}")
    
    def debug_sam2_state_contents(self):
        """Debug function to inspect SAM2 state contents"""
        if not self.debug_mode:
            return
        
        try:
            print("=== SAM2 STATE CONTENTS DEBUG ===")
            
            inference_state = self.main_window.sam2_backend.inference_state
            if not inference_state:
                print("No inference state available")
                return
            
            print(f"Main keys: {list(inference_state.keys())}")
            
            # Debug temp_output_dict_per_obj
            if 'temp_output_dict_per_obj' in inference_state:
                temp_dict = inference_state['temp_output_dict_per_obj']
                print(f"\ntemp_output_dict_per_obj: {len(temp_dict)} objects")
                for obj_idx, obj_data in temp_dict.items():
                    print(f"  Object {obj_idx}: {list(obj_data.keys())}")
                    for key, value in obj_data.items():
                        if isinstance(value, dict):
                            print(f"    {key}: {len(value)} items")
            
            # Debug output_dict_per_obj
            if 'output_dict_per_obj' in inference_state:
                output_dict = inference_state['output_dict_per_obj']
                print(f"\noutput_dict_per_obj: {len(output_dict)} objects")
                for obj_idx, obj_data in output_dict.items():
                    print(f"  Object {obj_idx}: {list(obj_data.keys())}")
                    for key, value in obj_data.items():
                        if isinstance(value, dict):
                            print(f"    {key}: {len(value)} items")
            
            print("=== END SAM2 STATE CONTENTS DEBUG ===")
        
        except Exception as e:
            print(f"Error in SAM2 state debug: {e}")
