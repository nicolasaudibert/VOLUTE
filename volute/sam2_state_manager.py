"""
SAM2 State Manager
Main entry point for SAM2 state management operations
Delegates all operations to specialized components
"""

from .sam2_state_coordinator import SAM2StateCoordinator

class SAM2StateManager:
    """
    Main SAM2 state manager that delegates to specialized components
    This class serves as the primary interface for SAM2 state operations
    """
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.debug_mode = main_window.debug_mode
        
        # Initialize the main coordinator
        self.coordinator = SAM2StateCoordinator(main_window)
    
    # Export operations
    def export_sam2_inference_state_dialog(self):
        """Show dialog to export SAM2 inference state"""
        return self.coordinator.export_sam2_inference_state_dialog()
    
    def export_sam2_inference_state(self, file_path):
        """Export SAM2 inference state to file"""
        return self.coordinator.export_sam2_inference_state(file_path)
    
    # Import operations
    def import_sam2_inference_state_dialog(self):
        """Show dialog to import SAM2 inference state"""
        return self.coordinator.import_sam2_inference_state_dialog()
    
    def import_sam2_inference_state(self, file_path):
        """Import SAM2 inference state from file"""
        return self.coordinator.import_sam2_inference_state(file_path)
    
    # Debug operations
    def inspect_sam2_inference_state(self):
        """Inspect SAM2 inference state for debugging"""
        return self.coordinator.inspect_sam2_inference_state()