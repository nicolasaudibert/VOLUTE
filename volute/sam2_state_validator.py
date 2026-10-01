"""
SAM2 State Validator Module
Handles validation and repair of SAM2 inference states
"""

import torch
import numpy as np

class SAM2StateValidator:
    """Validates and repairs SAM2 inference states"""
    
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
    
    def validate_and_fix_sam2_state(self, inference_state):
        """Validate and fix SAM2 state after restoration"""
        if self.debug_mode:
            print("\n=== VALIDATING SAM2 STATE ===")
        
        try:
            if not inference_state:
                if self.debug_mode:
                    print("No inference state to validate")
                return False
            
            # Check for required keys
            required_keys = ['temp_output_dict_per_obj', 'obj_id_to_idx', 'obj_idx_to_id']
            
            for key in required_keys:
                if key not in inference_state:
                    if self.debug_mode:
                        print(f"Missing required key: {key}")
                    return False
            
            # Check and fix temp_output_dict_per_obj
            temp_outputs = inference_state.get('temp_output_dict_per_obj', {})
            state_is_valid = True
            
            for obj_idx, obj_data in temp_outputs.items():
                cond_frame_outputs = obj_data.get('cond_frame_outputs', {})
                
                for frame_idx, frame_output in cond_frame_outputs.items():
                    # Check for missing object_score_logits
                    if 'object_score_logits' not in frame_output and 'pred_masks' in frame_output:
                        try:
                            pred_masks = frame_output['pred_masks']
                            
                            # Create score based on mask coverage
                            if hasattr(pred_masks, 'shape'):
                                mask_area = torch.sum(pred_masks > 0.0).float()
                                total_area = torch.numel(pred_masks)
                                score = torch.clamp(mask_area / total_area * 10.0, 0.1, 10.0)
                                
                                object_score_logits = torch.full((1,), score.item(), 
                                                               device=pred_masks.device, 
                                                               dtype=torch.float32)
                                
                                frame_output['object_score_logits'] = object_score_logits
                                
                                if self.debug_mode:
                                    print(f"    Fixed missing object_score_logits for obj {obj_idx}, frame {frame_idx}")
                            
                        except Exception as e:
                            if self.debug_mode:
                                print(f"    Failed to fix object_score_logits: {e}")
                            state_is_valid = False
            
            if self.debug_mode:
                print(f"SAM2 state validation result: {'PASSED' if state_is_valid else 'FAILED'}")
                print("=== END SAM2 STATE VALIDATION ===\n")
            
            return state_is_valid
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error during SAM2 state validation: {e}")
                import traceback
                traceback.print_exc()
            return False
    
    def check_image_data_corruption(self, inference_state):
        """Check if image data in SAM2 state is corrupted"""
        if self.debug_mode:
            print("=== CHECKING IMAGE DATA CORRUPTION ===")
        
        try:
            # Check main images tensor
            if 'images' in inference_state:
                images_data = inference_state['images']
                if isinstance(images_data, str) or not hasattr(images_data, 'shape'):
                    if self.debug_mode:
                        print(f"Main images data corrupted: {type(images_data)}")
                    return True
            
            # Check cached_features for corrupted image data
            if 'cached_features' in inference_state:
                cached_features = inference_state['cached_features']
                if isinstance(cached_features, dict):
                    for frame_idx, frame_data in cached_features.items():
                        if isinstance(frame_data, dict):
                            # Check for corrupted image tensors in cached features
                            for key, value in frame_data.items():
                                if isinstance(value, str) and 'image' in str(key).lower():
                                    if self.debug_mode:
                                        print(f"Corrupted image data found in cached_features[{frame_idx}][{key}]")
                                    return True
            
            if self.debug_mode:
                print("No image data corruption detected")
            return False
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error checking image data corruption: {e}")
            return True  # Assume corruption if we can't check
    
    def extract_essential_data(self, inference_state):
        """Extract essential data before state reset"""
        essential_data = {}
        
        try:
            # Extract object mappings
            essential_data['obj_id_to_idx'] = inference_state.get('obj_id_to_idx', {}).copy()
            essential_data['obj_idx_to_id'] = inference_state.get('obj_idx_to_id', {}).copy()
            essential_data['obj_ids'] = inference_state.get('obj_ids', []).copy()
            
            # Extract point inputs
            essential_data['point_inputs_per_obj'] = {}
            point_inputs = inference_state.get('point_inputs_per_obj', {})
            for obj_idx, frames_data in point_inputs.items():
                essential_data['point_inputs_per_obj'][obj_idx] = {}
                for frame_idx, frame_data in frames_data.items():
                    essential_data['point_inputs_per_obj'][obj_idx][frame_idx] = frame_data.copy()
            
            if self.debug_mode:
                print(f"Extracted essential data: {list(essential_data.keys())}")
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error extracting essential data: {e}")
        
        return essential_data
    
    def restore_essential_data(self, inference_state, essential_data):
        """Restore essential data to inference state"""
        try:
            for key in ['obj_id_to_idx', 'obj_idx_to_id', 'obj_ids']:
                if key in essential_data:
                    inference_state[key] = essential_data[key]
            
            if 'point_inputs_per_obj' in essential_data:
                inference_state['point_inputs_per_obj'] = essential_data['point_inputs_per_obj']
            
            if self.debug_mode:
                print("Essential data restored to inference state")
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error restoring essential data: {e}")
    
    def inspect_sam2_inference_state(self, inference_state):
        """Inspect SAM2 inference state for debugging"""
        if not inference_state:
            print("No SAM2 inference state available")
            return
        
        print("\n=== SAM2 INFERENCE STATE INSPECTION ===")
        print(f"Type: {type(inference_state)}")
        print(f"Keys: {list(inference_state.keys()) if isinstance(inference_state, dict) else 'Not a dict'}")
        
        if isinstance(inference_state, dict):
            for key, value in list(inference_state.items())[:10]:  # First 10 items
                if torch.is_tensor(value):
                    print(f"  {key}: tensor {value.shape} ({value.dtype}, {value.device})")
                elif isinstance(value, dict):
                    print(f"  {key}: dict with {len(value)} items")
                elif isinstance(value, list):
                    print(f"  {key}: list with {len(value)} items")
                else:
                    print(f"  {key}: {type(value)} - {value}")
        
        print("=== END INSPECTION ===\n")