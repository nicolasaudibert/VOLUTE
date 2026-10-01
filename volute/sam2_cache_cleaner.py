"""
SAM2 Cache Cleaner
Utility to clean corrupted cached features in SAM2 inference state
"""

import torch

class SAM2CacheCleaner:
    """Utility to clean and repair corrupted SAM2 cached features"""
    
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
    
    def clean_inference_state(self, inference_state):
        """
        Clean corrupted cached features from SAM2 inference state
        
        Args:
            inference_state: SAM2 inference state dictionary
            
        Returns:
            dict: Cleaned inference state
        """
        try:
            if self.debug_mode:
                print("=== CLEANING SAM2 INFERENCE STATE ===")
            
            # Clean cached features which often cause propagation issues
            if 'cached_features' in inference_state:
                if self.debug_mode:
                    original_count = len(inference_state['cached_features'])
                    print(f"Original cached features count: {original_count}")
                
                # Clear all cached features - they will be regenerated
                inference_state['cached_features'] = {}
                
                if self.debug_mode:
                    print("Cleared cached_features - will be regenerated during propagation")
            
            # Validate image tensors
            if 'images' in inference_state:
                images = inference_state['images']
                if isinstance(images, dict):
                    if self.debug_mode:
                        print("WARNING: 'images' is a dict instead of tensor - attempting to fix")
                    
                    # Try to extract tensor from dict if it's a serialized tensor
                    if 'data' in images and 'shape' in images:
                        if self.debug_mode:
                            print("Found serialized tensor in 'images' - this should have been deserialized")
                        # This indicates a deserialization problem
                        raise Exception("Images tensor was not properly deserialized")
                elif isinstance(images, torch.Tensor):
                    if self.debug_mode:
                        print(f"Images tensor OK: shape {images.shape}, device {images.device}")
                else:
                    if self.debug_mode:
                        print(f"WARNING: Unknown images type: {type(images)}")
            
            # Clean output dictionaries of potentially corrupted tensors
            self._clean_output_dicts(inference_state)
            
            if self.debug_mode:
                print("=== SAM2 INFERENCE STATE CLEANING COMPLETE ===")
            
            return inference_state
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error cleaning inference state: {e}")
            raise
    
    def _clean_output_dicts(self, inference_state):
        """Clean output dictionaries of corrupted tensors"""
        try:
            output_dict_keys = ['output_dict_per_obj', 'temp_output_dict_per_obj']
            
            for dict_key in output_dict_keys:
                if dict_key not in inference_state:
                    continue
                
                if self.debug_mode:
                    print(f"Cleaning {dict_key}")
                
                for obj_idx, obj_dict in inference_state[dict_key].items():
                    # Clean cond_frame_outputs and non_cond_frame_outputs
                    for output_type in ['cond_frame_outputs', 'non_cond_frame_outputs']:
                        if output_type in obj_dict:
                            cleaned_outputs = {}
                            for frame_idx, frame_output in obj_dict[output_type].items():
                                try:
                                    # Validate that tensors in frame_output are actually tensors
                                    cleaned_output = self._validate_frame_output(frame_output, f"{dict_key}.{obj_idx}.{output_type}.{frame_idx}")
                                    if cleaned_output is not None:
                                        cleaned_outputs[frame_idx] = cleaned_output
                                except Exception as e:
                                    if self.debug_mode:
                                        print(f"  -> Skipping corrupted frame output {dict_key}.{obj_idx}.{output_type}.{frame_idx}: {e}")
                                    continue
                            
                            obj_dict[output_type] = cleaned_outputs
                            
                            if self.debug_mode:
                                print(f"  -> Cleaned {output_type} for obj {obj_idx}: {len(cleaned_outputs)} frames")
        
        except Exception as e:
            if self.debug_mode:
                print(f"Error cleaning output dicts: {e}")
    
    def _validate_frame_output(self, frame_output, path):
        """Validate and clean a single frame output"""
        try:
            if not isinstance(frame_output, dict):
                return None
            
            cleaned_output = {}
            
            for key, value in frame_output.items():
                if isinstance(value, torch.Tensor):
                    # Tensor is OK
                    cleaned_output[key] = value
                elif isinstance(value, dict) and 'data' in value and 'shape' in value:
                    if self.debug_mode:
                        print(f"  -> WARNING: Found serialized tensor at {path}.{key} - should have been deserialized")
                    # Skip this corrupted tensor - it will be regenerated
                    continue
                else:
                    # Other data types are OK
                    cleaned_output[key] = value
            
            return cleaned_output if cleaned_output else None
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error validating frame output at {path}: {e}")
            return None

# Usage function to integrate into import process
def clean_sam2_state_before_propagation(inference_state, debug_mode=False):
    """
    Clean SAM2 inference state before propagation to prevent errors
    
    Args:
        inference_state: SAM2 inference state
        debug_mode: Enable debug output
        
    Returns:
        dict: Cleaned inference state
    """
    cleaner = SAM2CacheCleaner(debug_mode=debug_mode)
    return cleaner.clean_inference_state(inference_state)