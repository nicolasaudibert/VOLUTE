"""
SAM2 Compatibility Checker
Handles compatibility checking for SAM2 state imports
"""

from PyQt5.QtWidgets import QMessageBox

class SAM2CompatibilityChecker:
    """Checks compatibility for SAM2 state imports"""
    
    def __init__(self, main_window, debug_mode=False):
        self.main_window = main_window
        self.debug_mode = debug_mode
    
    def check_compatibility(self, sam2_state_data):
        """Check device and dimension compatibility"""
        if not self._check_device_compatibility(sam2_state_data):
            return False
        
        if not self._check_dimension_compatibility(sam2_state_data):
            return False
        
        return True
    
    def _check_device_compatibility(self, sam2_state_data):
        """Check device compatibility"""
        saved_device = sam2_state_data.get('sam2_config', {}).get('device', 'unknown')
        current_device = str(self.main_window.sam2_backend.device)
        
        if saved_device != current_device:
            reply = self.main_window.ui_manager.show_message(
                "question",
                "Device Mismatch",
                f"Device mismatch detected!\n\n"
                f"Saved on: {saved_device}\n"
                f"Current: {current_device}\n\n"
                f"This may cause the import to fail. Continue anyway?"
            )
            
            if reply != QMessageBox.Yes:
                return False
        
        return True
    
    def _check_dimension_compatibility(self, sam2_state_data):
        """Check image dimension compatibility"""
        if not self.main_window.image_manager.has_images():
            return True  # No images loaded, skip check
        
        current_image_info = self.main_window.image_manager.get_current_image_info()
        saved_dimensions = sam2_state_data.get('image_dimensions', {})
        
        current_height = current_image_info['height']
        current_width = current_image_info['width']
        saved_height = saved_dimensions.get('height')
        saved_width = saved_dimensions.get('width')
        
        if saved_height and saved_width:
            if current_height != saved_height or current_width != saved_width:
                reply = self.main_window.ui_manager.show_message(
                    "question",
                    "Dimension Mismatch",
                    f"Image dimensions mismatch!\n\n"
                    f"Current images: {current_width}x{current_height}\n"
                    f"Saved state: {saved_width}x{saved_height}\n\n"
                    f"This may cause issues with SAM2 inference. Continue anyway?"
                )
                
                if reply != QMessageBox.Yes:
                    return False
        
        return True