"""
File Utilities
Handles file operations, image loading, and file management
"""

import os
import re
import numpy as np
from PIL import Image

# Glob patterns behind each file-dialog filter kind. The type names themselves
# are localized ("filter_<kind>" keys), the patterns are not.
FILE_FILTER_PATTERNS = {
    'volute':  '*.volute',
    'voluteinf': '*.voluteinf',
    'xlsx':    '*.xlsx',
    'csv':     '*.csv',
    'json':    '*.json',
    'pkl':     '*.pkl',
    'tsv':     '*.tsv',
    'txt':     '*.txt',
    'yaml':    '*.yaml',
    'pt':      '*.pt',
    'xcf':     '*.xcf',
    'image':   '*.png *.jpg *.jpeg *.bmp *.tif *.tiff',
    'mask':    '*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.xcf',
    'all':     '*',
}


def build_file_filter(localization, *kinds):
    """Build a QFileDialog filter string with localized type names, e.g.
    build_file_filter(loc, 'csv', 'all') -> "Fichiers CSV (*.csv);;Tous les fichiers (*)"."""
    return ";;".join(
        f"{localization.get_text('filter_' + kind)} ({FILE_FILTER_PATTERNS[kind]})"
        for kind in kinds
    )


class FileManager:
    """Manages file operations and image loading"""
    
    SUPPORTED_EXTENSIONS = [
        '.jpg', '.jpeg',  # JPEG
        '.png',           # PNG
        '.bmp',           # BMP
        '.tif', '.tiff'   # TIFF
    ]
    
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
    
    @staticmethod
    def is_supported_image_format(filename):
        """Check if file is a supported image format"""
        return any(filename.lower().endswith(ext) for ext in FileManager.SUPPORTED_EXTENSIONS)
    
    @staticmethod
    def natural_sort_key(filename):
        """
        Generate a sort key for natural sorting of filenames.
        This handles numeric parts correctly (e.g., file2.jpg comes before file10.jpg)
        """
        # Split filename into text and numeric parts
        parts = re.split(r'(\d+)', filename)
        # Convert numeric parts to integers for proper sorting
        result = []
        for part in parts:
            if part.isdigit():
                result.append(int(part))
            else:
                result.append(part.lower())
        return result
    
    def get_image_files(self, folder):
        """Get sorted list of supported image files from folder"""
        if not os.path.exists(folder):
            if self.debug_mode:
                print(f"Folder does not exist: {folder}")
            return []
        
        all_files = os.listdir(folder)
        image_files = [f for f in all_files if self.is_supported_image_format(f)]
        
        if not image_files:
            if self.debug_mode:
                print(f"No supported image files found in: {folder}")
            return []
        
        # Sort files using natural sorting to handle numeric sequences correctly
        image_files.sort(key=self.natural_sort_key)
        
        if self.debug_mode:
            print(f"Found {len(image_files)} supported image files")
            print(f"First few files: {image_files[:5]}")
        
        # Find image ending with 00000 (any supported extension)
        first_image = None
        for file in image_files:
            # Extract filename without extension
            name_without_ext = os.path.splitext(file)[0]
            if name_without_ext.endswith('00000'):
                first_image = file
                break
        
        # If no image ends with 00000, take first by default
        if first_image is None:
            first_image = image_files[0]
            if self.debug_mode:
                print(f"No image ending with 00000 found. Using {first_image} as first image.")
        else:
            if self.debug_mode:
                print(f"Found reference image: {first_image}")
        
        # Reorganize list so first_image is first
        if first_image in image_files:
            image_files.remove(first_image)
            image_files.insert(0, first_image)
        
        return image_files
    
    def load_image(self, image_path):
        """Load image and convert to RGB if necessary"""
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        try:
            pil_image = Image.open(image_path)
            
            # Convert to RGB if necessary (for TIFF, BMP, etc.)
            if pil_image.mode != 'RGB':
                if self.debug_mode:
                    print(f"Converting image from {pil_image.mode} to RGB: {os.path.basename(image_path)}")
                pil_image = pil_image.convert('RGB')
            
            return pil_image
        
        except Exception as e:
            if self.debug_mode:
                print(f"Error loading image {image_path}: {e}")
            raise
    
    def load_image_as_array(self, image_path):
        """Load image as numpy array"""
        pil_image = self.load_image(image_path)
        return np.array(pil_image)
    
    def get_image_info(self, image_path):
        """Get image information (size, format, etc.)"""
        try:
            with Image.open(image_path) as img:
                return {
                    'size': img.size,
                    'mode': img.mode,
                    'format': img.format,
                    'filename': os.path.basename(image_path)
                }
        except Exception as e:
            if self.debug_mode:
                print(f"Error getting image info for {image_path}: {e}")
            return None
    
    def validate_image_sequence(self, image_paths):
        """Validate that all images in sequence have same dimensions"""
        if not image_paths:
            return True, "No images to validate"
        
        try:
            # Check first image
            with Image.open(image_paths[0]) as first_img:
                reference_size = first_img.size
                reference_mode = first_img.mode
            
            # Check all other images
            for i, path in enumerate(image_paths[1:], 1):
                with Image.open(path) as img:
                    if img.size != reference_size:
                        return False, f"Image {i+1} has different size: {img.size} vs {reference_size}"
                    # Note: We don't check mode as we convert to RGB anyway
            
            return True, f"All {len(image_paths)} images are valid"
        
        except Exception as e:
            return False, f"Error validating images: {e}"
    
    @staticmethod
    def get_output_format_from_extension(filename):
        """Get appropriate PIL format from file extension"""
        _, ext = os.path.splitext(filename)
        ext = ext.lower()
        
        if ext in ['.jpg', '.jpeg']:
            return 'JPEG'
        elif ext == '.png':
            return 'PNG'
        elif ext == '.bmp':
            return 'BMP'
        elif ext in ['.tif', '.tiff']:
            return 'TIFF'
        else:
            return 'PNG'  # Default fallback

    @staticmethod
    def ensure_directory_exists(directory):
        """Create directory if it doesn't exist"""
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            return True
        return False

    @staticmethod
    def read_tracked_points_file(path):
        """
        Parse a tracked-point file previously produced by TrackedPointExporter
        (SAM2++ point mode "Export tracked points"), reversing its logic.

        Expects columns: Object_Name, Frame_Index, Original_Filename, X_px, Y_px.
        Object_ID, if present, is ignored — points are re-matched by name string,
        not by the source session's numeric object id.

        Returns a list of dicts:
            [{'name': str, 'frame_index': int, 'original_filename': str,
              'x_px': float, 'y_px': float}, ...]

        Raises ValueError on missing required columns or unsupported extension,
        ImportError if reading .xlsx without pandas/openpyxl installed.
        """
        ext = os.path.splitext(path)[1].lower()
        required = {'Object_Name', 'Frame_Index', 'Original_Filename', 'X_px', 'Y_px'}

        if ext == '.xlsx':
            try:
                import pandas as pd
            except ImportError:
                raise ImportError("pandas and openpyxl are required to read .xlsx files")
            df = pd.read_excel(path, engine='openpyxl')
            missing = required - set(df.columns)
            if missing:
                raise ValueError(f"Missing required columns: {sorted(missing)}")
            records = df.to_dict('records')
        elif ext == '.csv':
            import csv
            with open(path, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                missing = required - set(reader.fieldnames or [])
                if missing:
                    raise ValueError(f"Missing required columns: {sorted(missing)}")
                records = list(reader)
        elif ext == '.json':
            import json
            with open(path, 'r', encoding='utf-8') as f:
                records = json.load(f)
            if records:
                missing = required - set(records[0].keys())
                if missing:
                    raise ValueError(f"Missing required columns: {sorted(missing)}")
        else:
            raise ValueError(f"Unsupported file extension: {ext}")

        rows = []
        for r in records:
            rows.append({
                'name':              str(r['Object_Name']),
                'frame_index':       int(r['Frame_Index']),
                'original_filename': str(r['Original_Filename']),
                'x_px':              float(r['X_px']),
                'y_px':              float(r['Y_px']),
            })
        return rows

