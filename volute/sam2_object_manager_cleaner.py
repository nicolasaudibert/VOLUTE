"""
SAM2 Object Manager Cleaner
Handles clearing and cleaning operations for Object Manager
"""

class SAM2ObjectManagerCleaner:
    """Handles Object Manager cleaning operations"""
    
    def __init__(self, main_window, debug_mode=False):
        self.main_window = main_window
        self.debug_mode = debug_mode
    
    def clear_object_manager(self):
        """Clear all object data in Object Manager"""
        try:
            object_manager = self.main_window.object_manager
            
            # Clear all object data structures
            object_manager.object_masks.clear()
            object_manager.object_points.clear()
            object_manager.object_colors.clear()
            object_manager.object_names.clear()
            object_manager.object_markers.clear()
            object_manager.object_centroids.clear()
            
            if hasattr(object_manager, 'object_show_points'):
                object_manager.object_show_points.clear()
            
            if self.debug_mode:
                print("Cleared all object data from Object Manager")
                
        except Exception as e:
            if self.debug_mode:
                print(f"Error clearing Object Manager: {e}")