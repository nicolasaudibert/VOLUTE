"""
Inference State Manager - Main Module
Handles saving and loading of SAM2 inference states

The work is split across separate files in the volute/ directory:
- inference_state_manager.py: Main coordinator (this file)
- project_state_manager.py: Handles .volute files (project data)
- sam2_state_manager.py: Handles .voluteinf files (SAM2 inference state)
"""

import os
import pickle
import gzip
import numpy as np
from PyQt5.QtWidgets import QMessageBox

from .project_state_manager import ProjectStateManager
from .sam2_state_manager import SAM2StateManager

class InferenceStateManager:
    """Main manager that coordinates project data and SAM2 state operations"""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.debug_mode = main_window.debug_mode
        
        # Initialize sub-managers
        self.project_manager = ProjectStateManager(main_window)
        self.sam2_manager = SAM2StateManager(main_window)
    
    # Project Data (.volute files) - Delegate to ProjectStateManager
    def export_inference_state_dialog(self):
        """Show dialog to export project data"""
        return self.project_manager.export_project_data_dialog()
    
    def import_inference_state_dialog(self):
        """Show dialog to import project data"""
        return self.project_manager.import_project_data_dialog()
    
    def export_inference_state(self, file_path):
        """Export project data to file"""
        return self.project_manager.export_project_data(file_path)
    
    def import_inference_state(self, file_path):
        """Import project data from file"""
        return self.project_manager.import_project_data(file_path)
    
    # SAM2 Inference State (.voluteinf files) - Delegate to SAM2StateManager
    def export_sam2_inference_state_dialog(self):
        """Show dialog to export SAM2 inference state"""
        return self.sam2_manager.export_sam2_inference_state_dialog()
    
    def import_sam2_inference_state_dialog(self):
        """Show dialog to import SAM2 inference state"""
        return self.sam2_manager.import_sam2_inference_state_dialog()
    
    def export_sam2_inference_state(self, file_path):
        """Export SAM2 inference state to file"""
        return self.sam2_manager.export_sam2_inference_state(file_path)
    
    def import_sam2_inference_state(self, file_path):
        """Import SAM2 inference state from file"""
        return self.sam2_manager.import_sam2_inference_state(file_path)
    
    # Utility methods
    def inspect_sam2_inference_state(self):
        """Inspect SAM2 inference state for debugging"""
        return self.sam2_manager.inspect_sam2_inference_state()
