"""
Filename Manager
Manages mapping between original filenames and SAM2 temporary filenames
"""

import os
from pathlib import Path
import re

class FilenameManager:
    """Manages filename mapping between original and SAM2 temporary names"""
    
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
        
        # Mapping: frame_index -> original_filename
        self.frame_to_original = {}
        
        # Mapping: original_filename -> frame_index
        self.original_to_frame = {}
        
        # Mapping: sam2_temp_filename -> original_filename
        self.temp_to_original = {}
        
        # Mapping: original_filename -> sam2_temp_filename
        self.original_to_temp = {}
        
        # Current folder path for validation
        self.current_folder = None
    
    def initialize_mappings(self, image_paths, sam2_temp_folder=None):
        """
        Initialize filename mappings from image paths
        
        Args:
            image_paths: List of original image file paths
            sam2_temp_folder: Path to SAM2 temporary folder (optional)
        """
        try:
            if self.debug_mode:
                print(f"=== FILENAME MANAGER: Initializing mappings ===")
                print(f"Original image paths count: {len(image_paths)}")
            
            # Clear existing mappings
            self.clear_mappings()
            
            # Store current folder
            if image_paths:
                self.current_folder = os.path.dirname(image_paths[0])
            
            # Create mappings
            for frame_idx, image_path in enumerate(image_paths):
                original_filename = os.path.basename(image_path)
                
                # Create SAM2 temporary filename (5-digit padding)
                temp_filename = f"{frame_idx:05d}.jpg"
                
                # Store all mappings
                self.frame_to_original[frame_idx] = original_filename
                self.original_to_frame[original_filename] = frame_idx
                self.temp_to_original[temp_filename] = original_filename
                self.original_to_temp[original_filename] = temp_filename
                
                if self.debug_mode and frame_idx < 5:  # Show first 5 for debug
                    print(f"  Frame {frame_idx}: {temp_filename} -> {original_filename}")
            
            # If SAM2 temp folder is provided, validate mappings
            if sam2_temp_folder and os.path.exists(sam2_temp_folder):
                self._validate_temp_folder_mappings(sam2_temp_folder)
            
            if self.debug_mode:
                print(f"=== FILENAME MANAGER: Initialization complete ===")
                print(f"Total mappings created: {len(self.frame_to_original)}")
        
        except Exception as e:
            if self.debug_mode:
                print(f"Error initializing filename mappings: {e}")
                import traceback
                traceback.print_exc()
    
    def _validate_temp_folder_mappings(self, sam2_temp_folder):
        """Validate that temp folder contains expected files"""
        try:
            temp_files = [f for f in os.listdir(sam2_temp_folder) 
                         if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            
            expected_count = len(self.frame_to_original)
            actual_count = len(temp_files)
            
            if self.debug_mode:
                print(f"VALIDATION: Expected {expected_count} temp files, found {actual_count}")
            
            # Check for missing files
            missing_files = []
            for frame_idx in range(expected_count):
                temp_filename = f"{frame_idx:05d}.jpg"
                temp_path = os.path.join(sam2_temp_folder, temp_filename)
                if not os.path.exists(temp_path):
                    missing_files.append(temp_filename)
            
            if missing_files and self.debug_mode:
                print(f"WARNING: Missing temp files: {missing_files[:10]}...")  # Show first 10
        
        except Exception as e:
            if self.debug_mode:
                print(f"Error validating temp folder: {e}")
    
    def get_original_filename(self, frame_index):
        """
        Get original filename from frame index
        
        Args:
            frame_index: Frame index (int)
            
        Returns:
            str: Original filename or None if not found
        """
        return self.frame_to_original.get(frame_index)
    
    def get_original_filename_from_temp(self, temp_filename):
        """
        Get original filename from SAM2 temporary filename
        
        Args:
            temp_filename: SAM2 temporary filename (e.g., "00042.jpg")
            
        Returns:
            str: Original filename or None if not found
        """
        return self.temp_to_original.get(temp_filename)
    
    def get_temp_filename(self, original_filename):
        """
        Get SAM2 temporary filename from original filename
        
        Args:
            original_filename: Original filename
            
        Returns:
            str: SAM2 temporary filename or None if not found
        """
        return self.original_to_temp.get(original_filename)
    
    def get_frame_index(self, original_filename):
        """
        Get frame index from original filename
        
        Args:
            original_filename: Original filename
            
        Returns:
            int: Frame index or None if not found
        """
        return self.original_to_frame.get(original_filename)
    
    def extract_frame_index_from_temp(self, temp_filename):
        """
        Extract frame index from SAM2 temporary filename
        
        Args:
            temp_filename: SAM2 temporary filename (e.g., "00042.jpg")
            
        Returns:
            int: Frame index or None if not valid temp filename
        """
        try:
            # Match pattern like "00042.jpg"
            match = re.match(r'^(\d{5})\.(jpg|jpeg|png)$', temp_filename.lower())
            if match:
                return int(match.group(1))
            return None
        except:
            return None
    
    def get_export_filename_mapping(self, export_type="mask"):
        """
        Get complete filename mapping for exports
        
        Args:
            export_type: Type of export ("mask", "coords", "centroids")
            
        Returns:
            dict: {frame_index: export_filename} mapping
        """
        try:
            export_mapping = {}
            
            for frame_idx, original_filename in self.frame_to_original.items():
                # Create export filename based on original filename
                name_without_ext = os.path.splitext(original_filename)[0]
                
                if export_type == "mask":
                    export_filename = f"{name_without_ext}_masked.png"
                elif export_type == "coords":
                    export_filename = f"{name_without_ext}_coords.json"
                elif export_type == "centroids":
                    export_filename = f"{name_without_ext}_centroid.json"
                else:
                    export_filename = f"{name_without_ext}_{export_type}.png"
                
                export_mapping[frame_idx] = export_filename
            
            if self.debug_mode:
                print(f"Created export mapping for {export_type}: {len(export_mapping)} files")
            
            return export_mapping
        
        except Exception as e:
            if self.debug_mode:
                print(f"Error creating export mapping: {e}")
            return {}
    
    def get_all_original_filenames(self):
        """
        Get all original filenames in frame order
        
        Returns:
            list: List of original filenames in frame order
        """
        filenames = []
        for frame_idx in sorted(self.frame_to_original.keys()):
            filenames.append(self.frame_to_original[frame_idx])
        return filenames
    
    def get_all_temp_filenames(self):
        """
        Get all temporary filenames in frame order
        
        Returns:
            list: List of temporary filenames in frame order
        """
        filenames = []
        for frame_idx in sorted(self.frame_to_original.keys()):
            temp_filename = f"{frame_idx:05d}.jpg"
            filenames.append(temp_filename)
        return filenames
    
    def clear_mappings(self):
        """Clear all filename mappings"""
        self.frame_to_original.clear()
        self.original_to_frame.clear()
        self.temp_to_original.clear()
        self.original_to_temp.clear()
        self.current_folder = None
        
        if self.debug_mode:
            print("FILENAME MANAGER: All mappings cleared")
    
    def get_statistics(self):
        """
        Get mapping statistics for debugging
        
        Returns:
            dict: Statistics about current mappings
        """
        return {
            'total_files': len(self.frame_to_original),
            'current_folder': self.current_folder,
            'sample_mappings': {
                frame_idx: self.frame_to_original[frame_idx] 
                for frame_idx in sorted(self.frame_to_original.keys())[:5]
            }
        }
    
    def validate_consistency(self):
        """
        Validate internal consistency of mappings
        
        Returns:
            bool: True if consistent, False otherwise
        """
        try:
            # Check that all mappings have same length
            lengths = [
                len(self.frame_to_original),
                len(self.original_to_frame),
                len(self.temp_to_original),
                len(self.original_to_temp)
            ]
            
            if len(set(lengths)) != 1:
                if self.debug_mode:
                    print(f"VALIDATION ERROR: Inconsistent mapping lengths: {lengths}")
                return False
            
            # Check bidirectional consistency
            for frame_idx, original in self.frame_to_original.items():
                if self.original_to_frame.get(original) != frame_idx:
                    if self.debug_mode:
                        print(f"VALIDATION ERROR: Bidirectional inconsistency for frame {frame_idx}")
                    return False
            
            if self.debug_mode:
                print("VALIDATION: All mappings are consistent")
            
            return True
        
        except Exception as e:
            if self.debug_mode:
                print(f"VALIDATION ERROR: {e}")
            return False