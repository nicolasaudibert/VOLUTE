"""
SAM2 Serializer - Enhanced with BFloat16 support
Handles serialization and deserialization of SAM2 inference states with BFloat16 compatibility
"""

import torch
import numpy as np
import pickle
import gzip
from pathlib import Path

class SAM2Serializer:
    """Enhanced SAM2 state serializer with BFloat16 support"""
    
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
    
    def serialize_sam2_state(self, sam2_state):
        """
        Serialize SAM2 inference state with enhanced BFloat16 support
        
        Args:
            sam2_state: SAM2 inference state dictionary
            
        Returns:
            dict: Serialized state data
        """
        try:
            if self.debug_mode:
                print(f"Serializing SAM2 inference state: {type(sam2_state)}")
                print(f"Processing SAM2 state dictionary with {len(sam2_state)} keys")
            
            serialized_state = {}
            tensor_count = 0
            total_elements = 0
            
            for key, value in sam2_state.items():
                try:
                    if isinstance(value, torch.Tensor):
                        serialized_state[key] = self._serialize_tensor_with_bfloat16_fix(value, key)
                        tensor_count += 1
                        total_elements += value.numel()
                        if self.debug_mode:
                            print(f"  -> Serialized tensor '{key}': shape {value.shape}")
                    
                    elif isinstance(value, torch.device):
                        serialized_state[key] = str(value)
                        if self.debug_mode:
                            print(f"  -> Serialized device '{key}': {value}")
                    
                    elif isinstance(value, dict):
                        serialized_state[key] = self._serialize_nested_object_with_bfloat16_fix(value, key)
                        if self.debug_mode:
                            print(f"  -> Serialized nested dict '{key}'")
                    
                    elif isinstance(value, list):
                        serialized_state[key] = self._serialize_nested_object_with_bfloat16_fix(value, key)
                        if self.debug_mode:
                            print(f"  -> Serialized list '{key}'")
                    
                    else:
                        # For other types, store as-is
                        serialized_state[key] = value
                        if self.debug_mode:
                            print(f"  -> Serialized {type(value).__name__} '{key}'")
                
                except Exception as e:
                    if self.debug_mode:
                        print(f"  -> Error serializing '{key}': {e}")
                    # Skip problematic keys but continue
                    continue
            
            # Add serialization metadata
            serialized_state['_serialization_metadata'] = {
                'method': 'sam2_dict_enhanced_bfloat16',
                'tensors': tensor_count,
                'objects': len(serialized_state),
                'skipped': len(sam2_state) - len(serialized_state) + 1,  # +1 for metadata
                'total_tensor_elements': total_elements
            }
            
            if self.debug_mode:
                print(f"Serialization complete: {tensor_count} tensors, {total_elements} elements")
            
            return serialized_state
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error in serialize_sam2_state: {e}")
                import traceback
                traceback.print_exc()
            raise
    
    def deserialize_sam2_state(self, serialized_data, target_device=None):
        """
        Deserialize SAM2 inference state with enhanced BFloat16 support
        
        Args:
            serialized_data: Serialized state data
            target_device: Target device for tensors (optional, for compatibility)
            
        Returns:
            dict: Restored SAM2 inference state
        """
        try:
            if self.debug_mode:
                metadata = serialized_data.get('_serialization_metadata', {})
                print(f"Restoration metadata: {metadata}")
                if target_device:
                    print(f"Target device: {target_device}")
            
            restored_state = {}
            tensor_count = 0
            
            for key, value in serialized_data.items():
                if key == '_serialization_metadata':
                    continue  # Skip metadata
                
                try:
                    if isinstance(value, dict) and 'data' in value and 'shape' in value:
                        # This is a serialized tensor
                        restored_tensor = self._deserialize_tensor_with_bfloat16_fix(value, key)
                        
                        # Move to target device if specified
                        if target_device and restored_tensor.device != target_device:
                            try:
                                restored_tensor = restored_tensor.to(target_device)
                                if self.debug_mode:
                                    print(f"  -> Moved tensor '{key}' to {target_device}")
                            except Exception as device_error:
                                if self.debug_mode:
                                    print(f"  -> Could not move tensor '{key}' to {target_device}: {device_error}")
                        
                        restored_state[key] = restored_tensor
                        tensor_count += 1
                        if self.debug_mode:
                            print(f"  -> Restored tensor '{key}': {restored_state[key].shape}")
                    
                    elif isinstance(value, str) and ('cpu' in value or 'cuda' in value or 'mps' in value):
                        # This is a device string - use target_device if specified
                        if target_device:
                            restored_state[key] = target_device
                            if self.debug_mode:
                                print(f"  -> Restored device '{key}': {target_device} (overridden)")
                        else:
                            restored_state[key] = torch.device(value)
                            if self.debug_mode:
                                print(f"  -> Restored device '{key}': {value}")
                    
                    elif isinstance(value, dict):
                        # Nested dictionary
                        restored_state[key] = self._deserialize_nested_object_with_bfloat16_fix(value, key, target_device)
                        if self.debug_mode:
                            print(f"  -> Restored nested dict '{key}'")
                    
                    elif isinstance(value, list):
                        # List object
                        restored_state[key] = self._deserialize_nested_object_with_bfloat16_fix(value, key, target_device)
                        if self.debug_mode:
                            print(f"  -> Restored list '{key}'")
                    
                    else:
                        # Other objects, restore as-is
                        restored_state[key] = value
                        if self.debug_mode:
                            print(f"  -> Restored {type(value).__name__} '{key}'")
                
                except Exception as e:
                    if self.debug_mode:
                        print(f"  -> Error deserializing '{key}': {e}")
                    # Skip problematic keys but continue
                    continue
            
            if self.debug_mode:
                print(f"Deserialization complete: {tensor_count} tensors restored")
            
            return restored_state
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error in deserialize_sam2_state: {e}")
                import traceback
                traceback.print_exc()
            raise
    
    def _serialize_tensor_with_bfloat16_fix(self, tensor, key="tensor"):
        """
        Serialize tensor with BFloat16 compatibility fix
        
        Args:
            tensor: PyTorch tensor to serialize
            key: Key name for debugging
        
        Returns:
            dict: Serialized tensor data with metadata
        """
        try:
            # Handle BFloat16 tensors by converting to Float32
            if tensor.dtype == torch.bfloat16:
                if self.debug_mode:
                    print(f"  -> Converting BFloat16 tensor '{key}' to Float32 for serialization")
                # Convert to float32 for serialization
                tensor_to_serialize = tensor.float()
                original_dtype = torch.bfloat16
            else:
                tensor_to_serialize = tensor
                original_dtype = tensor.dtype
            
            # Serialize the tensor
            serialized_data = {
                'data': tensor_to_serialize.cpu().numpy(),
                'shape': list(tensor.shape),
                'dtype': str(original_dtype),  # Store original dtype
                'device': str(tensor.device),
                'requires_grad': tensor.requires_grad if hasattr(tensor, 'requires_grad') else False
            }
            
            return serialized_data
            
        except Exception as e:
            if self.debug_mode:
                print(f"  -> Error serializing tensor '{key}': {e}")
            raise
    
    def _deserialize_tensor_with_bfloat16_fix(self, serialized_data, key="tensor", target_device=None):
        """
        Deserialize tensor with BFloat16 compatibility fix
        
        Args:
            serialized_data: Serialized tensor data
            key: Key name for debugging
            target_device: Target device for the tensor (optional)
        
        Returns:
            torch.Tensor: Restored tensor
        """
        try:
            # Extract data
            data = serialized_data['data']
            shape = serialized_data['shape']
            dtype_str = serialized_data.get('dtype', 'torch.float32')
            device_str = serialized_data.get('device', 'cpu')
            requires_grad = serialized_data.get('requires_grad', False)
            
            # Use target_device if provided, otherwise use stored device
            final_device = target_device if target_device else device_str
            
            # Convert dtype string back to torch dtype
            if dtype_str == 'torch.bfloat16':
                target_dtype = torch.bfloat16
            elif dtype_str == 'torch.float32':
                target_dtype = torch.float32
            elif dtype_str == 'torch.float16':
                target_dtype = torch.float16
            elif dtype_str == 'torch.int64':
                target_dtype = torch.int64
            elif dtype_str == 'torch.int32':
                target_dtype = torch.int32
            elif dtype_str == 'torch.bool':
                target_dtype = torch.bool
            else:
                # Default to float32 if unknown
                target_dtype = torch.float32
                if self.debug_mode:
                    print(f"  -> Unknown dtype '{dtype_str}', defaulting to float32")
            
            # Create tensor from numpy data
            tensor = torch.from_numpy(data).reshape(shape)
            
            # Convert to target dtype
            if tensor.dtype != target_dtype:
                tensor = tensor.to(target_dtype)
            
            # Set requires_grad if needed
            if requires_grad and target_dtype.is_floating_point:
                tensor.requires_grad_(requires_grad)
            
            # Move to target device
            if final_device != 'cpu':
                try:
                    tensor = tensor.to(final_device)
                except Exception as device_error:
                    if self.debug_mode:
                        print(f"  -> Could not move tensor to {final_device}, keeping on CPU: {device_error}")
            
            return tensor
            
        except Exception as e:
            if self.debug_mode:
                print(f"  -> Error deserializing tensor '{key}': {e}")
            raise
    
    def _serialize_nested_object_with_bfloat16_fix(self, obj, path=""):
        """
        Enhanced nested object serialization with BFloat16 handling
        
        Args:
            obj: Object to serialize (dict, list, tensor, etc.)
            path: Current path for debugging
        
        Returns:
            Serialized object
        """
        try:
            if isinstance(obj, torch.Tensor):
                return self._serialize_tensor_with_bfloat16_fix(obj, path)
            elif isinstance(obj, dict):
                serialized_dict = {}
                for key, value in obj.items():
                    try:
                        new_path = f"{path}.{key}" if path else key
                        serialized_dict[key] = self._serialize_nested_object_with_bfloat16_fix(value, new_path)
                    except Exception as e:
                        if self.debug_mode:
                            print(f"    -> Error serializing nested '{new_path}': {e}")
                        # Skip problematic nested objects
                        continue
                return serialized_dict
            elif isinstance(obj, (list, tuple)):
                serialized_list = []
                for i, item in enumerate(obj):
                    try:
                        new_path = f"{path}[{i}]" if path else f"[{i}]"
                        serialized_list.append(self._serialize_nested_object_with_bfloat16_fix(item, new_path))
                    except Exception as e:
                        if self.debug_mode:
                            print(f"    -> Error serializing nested '{new_path}': {e}")
                        # Skip problematic items
                        continue
                return serialized_list if isinstance(obj, list) else tuple(serialized_list)
            elif isinstance(obj, torch.device):
                return str(obj)
            else:
                # For non-tensor objects, return as-is
                return obj
                
        except Exception as e:
            if self.debug_mode:
                print(f"    -> Error in nested serialization at '{path}': {e}")
            return None  # Return None for problematic objects
    
    def _deserialize_nested_object_with_bfloat16_fix(self, obj, path="", target_device=None):
        """
        Enhanced nested object deserialization with BFloat16 handling
        
        Args:
            obj: Object to deserialize
            path: Current path for debugging
            target_device: Target device for tensors (optional)
        
        Returns:
            Deserialized object
        """
        try:
            if isinstance(obj, dict):
                # Check if this is a serialized tensor
                if 'data' in obj and 'shape' in obj and 'dtype' in obj:
                    return self._deserialize_tensor_with_bfloat16_fix(obj, path, target_device)
                else:
                    # Regular dictionary
                    deserialized_dict = {}
                    for key, value in obj.items():
                        try:
                            new_path = f"{path}.{key}" if path else key
                            
                            # Special handling for cached_features which contains image tensors
                            if key == 'cached_features' or 'cached_features' in path:
                                # This might contain image tensors that need special handling
                                deserialized_dict[key] = self._deserialize_cached_features(value, new_path, target_device)
                            else:
                                deserialized_dict[key] = self._deserialize_nested_object_with_bfloat16_fix(value, new_path, target_device)
                        except Exception as e:
                            if self.debug_mode:
                                print(f"    -> Error deserializing nested '{new_path}': {e}")
                            # Skip problematic items
                            continue
                    return deserialized_dict
            elif isinstance(obj, list):
                deserialized_list = []
                for i, item in enumerate(obj):
                    try:
                        new_path = f"{path}[{i}]" if path else f"[{i}]"
                        deserialized_list.append(self._deserialize_nested_object_with_bfloat16_fix(item, new_path, target_device))
                    except Exception as e:
                        if self.debug_mode:
                            print(f"    -> Error deserializing nested '{new_path}': {e}")
                        # Skip problematic items
                        continue
                return deserialized_list
            elif isinstance(obj, tuple):
                # Handle tuples
                deserialized_list = []
                for i, item in enumerate(obj):
                    try:
                        new_path = f"{path}[{i}]" if path else f"[{i}]"
                        deserialized_list.append(self._deserialize_nested_object_with_bfloat16_fix(item, new_path, target_device))
                    except Exception as e:
                        if self.debug_mode:
                            print(f"    -> Error deserializing nested tuple '{new_path}': {e}")
                        # Skip problematic items
                        continue
                return tuple(deserialized_list)
            elif isinstance(obj, str) and ('cpu' in obj or 'cuda' in obj or 'mps' in obj):
                # Device string - use target_device if provided
                if target_device:
                    return target_device
                else:
                    return torch.device(obj)
            else:
                # Return as-is for other types
                return obj
                
        except Exception as e:
            if self.debug_mode:
                print(f"    -> Error in nested deserialization at '{path}': {e}")
            return obj  # Return original object if deserialization fails
    
    def _deserialize_cached_features(self, cached_data, path="", target_device=None):
        """
        Special handling for cached_features which contains image tensors and backbone outputs
        
        Args:
            cached_data: Cached features data
            path: Current path for debugging
            target_device: Target device for tensors
        
        Returns:
            Properly deserialized cached features
        """
        try:
            if self.debug_mode:
                print(f"    -> Special cached_features deserialization at '{path}'")
            
            if isinstance(cached_data, dict):
                deserialized_cache = {}
                for frame_idx, frame_data in cached_data.items():
                    try:
                        if isinstance(frame_data, (list, tuple)) and len(frame_data) == 2:
                            # This should be (image, backbone_out) tuple
                            image_data, backbone_data = frame_data
                            
                            # Deserialize image tensor
                            if isinstance(image_data, dict) and 'data' in image_data:
                                image_tensor = self._deserialize_tensor_with_bfloat16_fix(image_data, f"{path}.{frame_idx}.image", target_device)
                            else:
                                image_tensor = self._deserialize_nested_object_with_bfloat16_fix(image_data, f"{path}.{frame_idx}.image", target_device)
                            
                            # Deserialize backbone data
                            backbone_out = self._deserialize_nested_object_with_bfloat16_fix(backbone_data, f"{path}.{frame_idx}.backbone", target_device)
                            
                            # Recreate the tuple
                            deserialized_cache[frame_idx] = (image_tensor, backbone_out)
                            
                            if self.debug_mode:
                                print(f"    -> Restored cached features for frame {frame_idx}: image shape {image_tensor.shape if hasattr(image_tensor, 'shape') else type(image_tensor)}")
                        else:
                            # Fallback for unexpected format
                            deserialized_cache[frame_idx] = self._deserialize_nested_object_with_bfloat16_fix(frame_data, f"{path}.{frame_idx}", target_device)
                    except Exception as e:
                        if self.debug_mode:
                            print(f"    -> Error deserializing cached features for frame {frame_idx}: {e}")
                        continue
                
                return deserialized_cache
            else:
                # Fallback for non-dict cached data
                return self._deserialize_nested_object_with_bfloat16_fix(cached_data, path, target_device)
                
        except Exception as e:
            if self.debug_mode:
                print(f"    -> Error in cached features deserialization: {e}")
            return cached_data
    
    def save_to_file(self, serialized_data, file_path):
        """
        Save serialized data to compressed file
        
        Args:
            serialized_data: Serialized state data
            file_path: Path to save file
        """
        try:
            with gzip.open(file_path, 'wb') as f:
                pickle.dump(serialized_data, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            if self.debug_mode:
                file_size = Path(file_path).stat().st_size / (1024 * 1024)  # MB
                print(f"Successfully saved to {file_path} ({file_size:.2f} MB)")
                
        except Exception as e:
            if self.debug_mode:
                print(f"Error saving to file: {e}")
            raise
    
    def load_from_file(self, file_path):
        """
        Load serialized data from compressed file
        
        Args:
            file_path: Path to load file
            
        Returns:
            dict: Loaded serialized data
        """
        try:
            with gzip.open(file_path, 'rb') as f:
                serialized_data = pickle.load(f)
            
            if self.debug_mode:
                file_size = Path(file_path).stat().st_size / (1024 * 1024)  # MB
                print(f"Successfully loaded from {file_path} ({file_size:.2f} MB)")
            
            return serialized_data
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error loading from file: {e}")
            raise