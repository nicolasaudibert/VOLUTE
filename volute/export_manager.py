"""
Export Manager
Coordinates export operations using the exporter classes
"""

import os
from PyQt5.QtWidgets import QFileDialog
from PyQt5.QtCore import QDir
from .exporters import (ImageExporter, CoordinateExporter, CentroidExporter,
                        ConvexHullExporter, MaskContourExporter, TrackedPointExporter)
from .file_utils import build_file_filter

class ExportManager:
    """Manages export operations"""
    
    def __init__(self, main_window):
        self.main_window = main_window
        
        # Initialize exporters
        self.image_exporter = ImageExporter(main_window.debug_mode)
        self.coordinate_exporter = CoordinateExporter(main_window.debug_mode)
        self.centroid_exporter = CentroidExporter(main_window.debug_mode)
    
    def export_masked_images(self):
        """Export images with masks"""
        if not any(self.main_window.object_manager.object_masks.values()):
            self.main_window.ui_manager.show_message("warning", 
                                       self.main_window.localization.get_text("warning"), 
                                       self.main_window.localization.get_text("no_masks_to_export"))
            return
        
        try:
            export_folder = QFileDialog.getExistingDirectory(
                self.main_window, "Select export folder", QDir.homePath()
            )
            if not export_folder:
                return
            
            count = self.image_exporter.export_masked_images(
                self.main_window.image_manager.get_all_image_paths(), 
                self.main_window.object_manager.object_masks, 
                self.main_window.object_manager.object_colors, 
                export_folder
            )
            
            if count > 0:
                masked_folder = os.path.join(export_folder, "masked_images")
                message = self.main_window.localization.get_text("images_exported", count, masked_folder)
                self.main_window.ui_manager.show_message("info", self.main_window.localization.get_text("success"), message)
            else:
                self.main_window.ui_manager.show_message("warning", 
                                           self.main_window.localization.get_text("warning"), 
                                           "No images were exported")
        
        except Exception as e:
            error_msg = f"Error during image export: {e}"
            if self.main_window.debug_mode:
                print(error_msg)
                import traceback
                traceback.print_exc()
            self.main_window.ui_manager.show_message("error", self.main_window.localization.get_text("error"), error_msg)
    
    def export_mask_coordinates(self):
        """Export mask coordinates"""
        masks = getattr(self.main_window, 'masks', {})
        if not masks:
            self.main_window.ui_manager.show_message("warning", 
                                       self.main_window.localization.get_text("warning"), 
                                       self.main_window.localization.get_text("no_masks_to_export"))
            return
        
        try:
            export_file, _ = QFileDialog.getSaveFileName(
                self.main_window, 
                "Save mask coordinates", 
                QDir.homePath() + "/mask_coordinates.json",
                build_file_filter(self.main_window.localization, 'json', 'pkl')
            )
            
            if not export_file:
                return
            
            masks_scores = getattr(self.main_window, 'masks_scores', {})
            count = self.coordinate_exporter.export_mask_coordinates(
                masks, 
                self.main_window.image_manager.get_all_image_paths(), 
                masks_scores, 
                export_file
            )
            
            message = self.main_window.localization.get_text("coordinates_exported", count)
            self.main_window.ui_manager.show_message("info", self.main_window.localization.get_text("success"), message)
        
        except Exception as e:
            error_msg = f"Error during coordinate export: {e}"
            if self.main_window.debug_mode:
                print(error_msg)
            self.main_window.ui_manager.show_message("error", self.main_window.localization.get_text("error"), error_msg)
    
    def export_centroids(self):
        """Export centroids"""
        if not self.main_window.object_manager.object_centroids:
            self.main_window.ui_manager.show_message("warning", 
                                       self.main_window.localization.get_text("warning"), 
                                       self.main_window.localization.get_text("no_centroids_to_export"))
            return
        
        try:
            folder_name = "video"
            if self.main_window.image_manager.current_folder:
                folder_name = os.path.basename(self.main_window.image_manager.current_folder)
            
            default_filename = f"{folder_name}_centroids.xlsx"
            default_path = os.path.join(QDir.homePath(), default_filename)
            
            export_file, _ = QFileDialog.getSaveFileName(
                self.main_window, 
                "Save centroids", 
                default_path,
                build_file_filter(self.main_window.localization, 'xlsx', 'json', 'csv')
            )
            
            if not export_file:
                return
            
            count = self.centroid_exporter.export_centroids(
                self.main_window.object_manager.object_centroids,
                self.main_window.object_manager.object_names,
                self.main_window.image_manager.get_all_image_paths(),
                export_file
            )
            
            message = self.main_window.localization.get_text("centroids_exported", count)
            self.main_window.ui_manager.show_message("info", self.main_window.localization.get_text("success"), message)
        
        except Exception as e:
            error_msg = f"Error during centroid export: {e}"
            if self.main_window.debug_mode:
                print(error_msg)
                import traceback
                traceback.print_exc()
            
            if "pandas" in str(e).lower():
                self.main_window.ui_manager.show_message("warning", 
                                           self.main_window.localization.get_text("warning"), 
                                           self.main_window.localization.get_text("pandas_required"))
            else:
                self.main_window.ui_manager.show_message("error", self.main_window.localization.get_text("error"), error_msg)

    def export_hull_coordinates(self, export_file):
        """
        Export convex hull vertex coordinates via ConvexHullExporter.

        Args:
            export_file: Output path (.xlsx / .csv / .json).

        Returns:
            Total number of vertex rows exported.
        """
        exporter = ConvexHullExporter(debug_mode=self.main_window.debug_mode)
        return exporter.export_hull_coordinates(
            self.main_window.object_manager.object_hulls,
            self.main_window.object_manager.object_names,
            self.main_window.image_manager.get_all_image_paths(),
            export_file,
            object_hull_coverage=self.main_window.object_manager.object_hull_coverage,
        )

    def export_contour_coordinates(self, export_file):
        """
        Export outer contour vertex coordinates via MaskContourExporter.

        Args:
            export_file: Output path (.xlsx / .csv / .json).

        Returns:
            Total number of vertex rows exported.
        """
        exporter = MaskContourExporter(debug_mode=self.main_window.debug_mode)
        return exporter.export_contour_coordinates(
            self.main_window.object_manager.object_contours,
            self.main_window.object_manager.object_names,
            self.main_window.image_manager.get_all_image_paths(),
            export_file,
            object_contour_coverage=self.main_window.object_manager.object_contour_coverage,
        )

    def export_tracked_points(self, export_file):
        """Export SAM2++ tracked point coordinates via TrackedPointExporter."""
        exporter = TrackedPointExporter(debug_mode=self.main_window.debug_mode)
        return exporter.export_tracked_points(
            self.main_window.object_manager.object_tracked_points,
            self.main_window.object_manager.object_names,
            self.main_window.image_manager.get_all_image_paths(),
            export_file,
        )
