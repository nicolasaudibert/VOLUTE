"""
Image Manager
Handles image loading, navigation, and folder management
"""

import os
import numpy as np
from collections import defaultdict
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtCore import QDir

class ImageManager:
    """Manages image loading and navigation"""
    
    def __init__(self, main_window):
        self.main_window = main_window
        
        # Application state
        self.images = []
        self.image_paths = []
        self.current_image_idx = 0
        self.current_folder = None
    
    def select_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self.main_window,
            self.main_window.localization.get_text("select_folder"),
            QDir.homePath()
        )
        if folder:
            self.current_folder = folder
            self.main_window.ui_manager.set_folder_label(folder)
            self.main_window.load_images_from_folder(folder)
    
    def load_images_from_folder(self, folder):
        """Load images from selected folder"""
        # Reset state
        # Pass incoming folder so reset_application_state can decide whether to preserve the SAM2 prep cache
        self.reset_application_state(incoming_folder=folder)
        
        # Get image files
        image_files = self.main_window.file_manager.get_image_files(folder)
        
        if not image_files:
            self.main_window.ui_manager.show_message("warning", 
                                       self.main_window.localization.get_text("warning"), 
                                       self.main_window.localization.get_text("no_images_found"))
            return False
        
        # Validate image sequence
        image_paths = [os.path.join(folder, f) for f in image_files]
        is_valid, message = self.main_window.file_manager.validate_image_sequence(image_paths)
        
        if not is_valid:
            self.main_window.ui_manager.show_message("warning", "Image Validation", message)
            return False
        
        # Store image paths
        self.image_paths = image_paths
        
        # Load first image
        self.load_image(0)
        
        # Enable navigation controls
        self.main_window.ui_manager.enable_navigation(True)
        self.main_window.ui_manager.update_navigation_controls(0, len(self.image_paths))
        
        if self.main_window.debug_mode:
            print(f"Loaded {len(self.image_paths)} images from {folder}")
        
        return True
    
    def reset_application_state(self, incoming_folder=None):
        """Reset application state for new video sequence"""
        self.images = []
        self.image_paths = []
        self.current_image_idx = 0

        self.main_window.object_manager.clear_all_data()

        if hasattr(self.main_window, 'positive_points'):
            self.main_window.positive_points = defaultdict(list)
        if hasattr(self.main_window, 'negative_points'):
            self.main_window.negative_points = defaultdict(list)
        if hasattr(self.main_window, 'masks'):
            self.main_window.masks = {}
        if hasattr(self.main_window, 'masks_scores'):
            self.main_window.masks_scores = {}

        if self.main_window.sam2_backend:
            # Preserve the prep cache when reloading the same folder
            preserve = (
                incoming_folder is not None
                and self.main_window.sam2_backend._is_prep_cache_valid(incoming_folder)
            )
            self.main_window.sam2_backend.reset_state(preserve_prep_cache=preserve)

        self.main_window.display_manager.reset_global_zoom()
        self.main_window.ui_manager.update_objects_list()
        self.main_window.ui_manager.update_object_ui()

        if self.main_window.debug_mode:
            print("Application state reset")
    
    def load_image(self, idx):
        """Load and display image at specified index"""
        if not (0 <= idx < len(self.image_paths)):
            return
        
        try:
            # Load image
            image_path = self.image_paths[idx]
            pil_image = self.main_window.file_manager.load_image(image_path)
            image = np.array(pil_image)
            
            # Store current image
            self.images = [image]
            self.current_image_idx = idx
            
            # Update display
            self.main_window.display_manager.update_display(maintain_global_zoom=True)
            
            # Update navigation controls
            self.main_window.ui_manager.update_navigation_controls(idx, len(self.image_paths))
            
            if self.main_window.debug_mode:
                print(f"Loaded image {idx}: {os.path.basename(image_path)}, shape: {image.shape}")
                
        except Exception as e:
            error_msg = f"Cannot load image: {e}"
            if self.main_window.debug_mode:
                print(f"Error loading image: {e}")
            self.main_window.ui_manager.show_message("error", self.main_window.localization.get_text("error"), error_msg)
    
    def prev_image(self):
        """Go to previous image"""
        if self.current_image_idx > 0:
            self.load_image(self.current_image_idx - 1)
    
    def next_image(self):
        """Go to next image"""
        if self.current_image_idx < len(self.image_paths) - 1:
            self.load_image(self.current_image_idx + 1)
    
    def slider_changed(self):
        """Handle slider value change"""
        slider = self.main_window.ui_manager.get_control('image_slider')
        if slider:
            idx = slider.value()
            if idx != self.current_image_idx:
                self.load_image(idx)
    
    def get_current_image(self):
        """Get current image as numpy array"""
        if self.images:
            return self.images[0]
        return None
    
    def get_current_image_path(self):
        """Get path of current image"""
        if 0 <= self.current_image_idx < len(self.image_paths):
            return self.image_paths[self.current_image_idx]
        return None
    
    def get_current_image_info(self):
        """Get information about current image"""
        if not self.images:
            return None
        
        image = self.images[0]
        h, w = image.shape[:2]
        
        return {
            'index': self.current_image_idx,
            'total_images': len(self.image_paths),
            'path': self.get_current_image_path(),
            'shape': image.shape,
            'height': h,
            'width': w
        }
    
    def has_images(self):
        """Check if images are loaded"""
        return len(self.images) > 0 and len(self.image_paths) > 0
    
    def get_all_image_paths(self):
        """Get all image paths"""
        return self.image_paths.copy()
    
    def get_folder_path(self):
        """Get current folder path"""
        return self.current_folder
