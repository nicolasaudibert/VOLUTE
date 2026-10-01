"""
SAM2 Object Synchronizer
Main coordinator for object synchronization operations
"""

from .sam2_mask_synchronizer import SAM2MaskSynchronizer
from .sam2_display_updater import SAM2DisplayUpdater
from .sam2_object_manager_cleaner import SAM2ObjectManagerCleaner

class SAM2ObjectSynchronizer:
    """Main coordinator for SAM2 object synchronization operations"""
    
    def __init__(self, main_window, debug_mode=False):
        self.main_window = main_window
        self.debug_mode = debug_mode
        
        # Initialize specialized components
        self.mask_synchronizer = SAM2MaskSynchronizer(main_window, debug_mode)
        self.display_updater = SAM2DisplayUpdater(main_window, debug_mode)
        self.cleaner = SAM2ObjectManagerCleaner(main_window, debug_mode)
    
    def clear_object_manager(self):
        """Clear all object data in Object Manager"""
        self.cleaner.clear_object_manager()
    
    def synchronize_masks_from_sam2_state(self):
        """Extract masks from SAM2 state and synchronize with Object Manager"""
        self.mask_synchronizer.synchronize_masks_from_sam2_state()
    
    def force_display_update(self):
        """Force display update after mask synchronization"""
        self.display_updater.force_display_update()