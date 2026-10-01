"""
SAM2 State Coordinator
Main coordinator for SAM2 state operations, delegates to specialized handlers
"""

from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtCore import QDir

from .sam2_state_exporter import SAM2StateExporter
from .sam2_state_importer import SAM2StateImporter
from .sam2_compatibility_checker import SAM2CompatibilityChecker
from .file_utils import build_file_filter

class SAM2StateCoordinator:
    """Coordinates SAM2 state operations through specialized handlers"""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.debug_mode = main_window.debug_mode
        
        # Initialize specialized handlers
        self.exporter = SAM2StateExporter(main_window, debug_mode=self.debug_mode)
        self.importer = SAM2StateImporter(main_window, debug_mode=self.debug_mode)
        self.compatibility_checker = SAM2CompatibilityChecker(main_window, debug_mode=self.debug_mode)
    
    def export_sam2_inference_state_dialog(self):
        """Show dialog to export SAM2 inference state"""
        # Delegate directly to SAM2StateExporter, which handles the whole dialog flow
        return self.exporter.export_sam2_inference_state_dialog()
    
    def import_sam2_inference_state_dialog(self):
        """Show dialog to import SAM2 inference state"""
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Import SAM2 Inference State",
            QDir.homePath(),
            build_file_filter(self.main_window.localization, 'voluteinf', 'all')
        )
        
        if file_path:
            return self.importer.import_sam2_inference_state(file_path)
        return False
    
    def export_sam2_inference_state(self, file_path):
        """Export SAM2 inference state to an explicit path, without a file dialog"""
        return self.exporter.export_to_path(file_path)
    
    def import_sam2_inference_state(self, file_path):
        """Import SAM2 inference state from file"""
        return self.importer.import_sam2_inference_state(file_path)
    
    def inspect_sam2_inference_state(self):
        """Inspect SAM2 inference state for debugging"""
        self.importer.inspect_sam2_inference_state()
