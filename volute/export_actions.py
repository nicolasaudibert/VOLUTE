"""
Export Actions
Menu-triggered export actions: masked images, coordinates, centroids,
hull/contour coordinates, closest-point exports, tracked points, and
point/mask analysis. Each method only orchestrates a file dialog, a call
into an exporter, and a result message.
"""

import os
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from PyQt5.QtCore import QDir
from .dialogs import localized_question
from .file_utils import build_file_filter


class ExportActions:
    """Export menu actions, delegated to from main_window. Accesses
    main_window's managers via self.main_window.<attr> rather than caching
    references, so it keeps working if a manager is ever re-instantiated."""

    def __init__(self, main_window):
        self.main_window = main_window

    def export_masked_images(self):
        """Export masked images with original filenames"""
        mw = self.main_window
        try:
            if mw.debug_mode:
                print("=== EXPORTING MASKED IMAGES (ORIGINAL FILENAMES) ===")

            from .exporters import DataExporter

            data_exporter = DataExporter(mw, debug_mode=mw.debug_mode)

            export_folder = QFileDialog.getExistingDirectory(
                mw,
                mw.localization.get_text("select_export_folder"),
                QDir.homePath()
            )

            if export_folder:
                quality = mw.config_manager.get_image_quality()

                success = data_exporter.export_masked_images(export_folder, quality=quality)

                if success:
                    mw.ui_manager.show_message(
                        "info",
                        mw.localization.get_text("export_complete"),
                        mw.localization.get_text("masked_images_exported")
                    )
                else:
                    mw.ui_manager.show_message(
                        "warning",
                        mw.localization.get_text("export_failed"),
                        mw.localization.get_text("export_error")
                    )

        except Exception as e:
            if mw.debug_mode:
                print(f"Error in export_masked_images: {e}")
                import traceback
                traceback.print_exc()
            mw.ui_manager.show_message(
                "error",
                mw.localization.get_text("export_error"),
                str(e)
            )

    def export_mask_coordinates(self):
        """Export coordinates to single file with configurable format"""
        mw = self.main_window
        try:
            if mw.debug_mode:
                print("=== EXPORTING COORDINATES TO SINGLE FILE ===")

            from .exporters import DataExporter

            data_exporter = DataExporter(mw, debug_mode=mw.debug_mode)

            default_format = mw.config_manager.get_coordinates_format()

            if default_format == 'json':
                file_filter = build_file_filter(mw.localization, 'json', 'csv', 'pkl', 'all')
                default_ext = ".json"
            elif default_format == 'csv':
                file_filter = build_file_filter(mw.localization, 'csv', 'json', 'pkl', 'all')
                default_ext = ".csv"
            elif default_format == 'pickle':
                file_filter = build_file_filter(mw.localization, 'pkl', 'json', 'csv', 'all')
                default_ext = ".pkl"
            else:
                file_filter = build_file_filter(mw.localization, 'json', 'csv', 'pkl', 'all')
                default_ext = ".json"

            default_filename = "mask_coordinates" + default_ext
            if mw.image_manager.current_folder:
                folder_name = os.path.basename(mw.image_manager.current_folder.rstrip(os.sep))
                default_filename = f"{folder_name}_coordinates{default_ext}"

            export_file, selected_filter = QFileDialog.getSaveFileName(
                mw,
                mw.localization.get_text("export_coordinates"),
                default_filename,
                file_filter
            )

            if export_file:
                file_extension = os.path.splitext(export_file)[1].lower()
                if file_extension == '.json':
                    file_format = 'json'
                elif file_extension == '.csv':
                    file_format = 'csv'
                elif file_extension == '.pkl':
                    file_format = 'pickle'
                else:
                    file_format = default_format
                    if not file_extension:
                        export_file += default_ext

                success = data_exporter.export_coordinates_to_file(export_file, file_format)

                if success:
                    mw.ui_manager.show_message(
                        "info",
                        mw.localization.get_text("export_complete"),
                        f"Coordinates exported to {os.path.basename(export_file)}"
                    )
                else:
                    mw.ui_manager.show_message(
                        "warning",
                        mw.localization.get_text("export_failed"),
                        mw.localization.get_text("export_error")
                    )

        except Exception as e:
            if mw.debug_mode:
                print(f"Error in export_coordinates: {e}")
                import traceback
                traceback.print_exc()
            mw.ui_manager.show_message(
                "error",
                mw.localization.get_text("export_error"),
                str(e)
            )

    def export_centroids(self):
        """Export centroids with configurable format"""
        mw = self.main_window
        try:
            if mw.debug_mode:
                print("=== EXPORTING CENTROIDS (ORIGINAL FILENAMES) ===")

            from .exporters import DataExporter

            data_exporter = DataExporter(mw, debug_mode=mw.debug_mode)

            default_format = mw.config_manager.get_centroids_format()

            if default_format == 'excel':
                file_filter = build_file_filter(mw.localization, 'xlsx', 'csv', 'json', 'all')
                default_ext = ".xlsx"
            elif default_format == 'csv':
                file_filter = build_file_filter(mw.localization, 'csv', 'xlsx', 'json', 'all')
                default_ext = ".csv"
            elif default_format == 'json':
                file_filter = build_file_filter(mw.localization, 'json', 'xlsx', 'csv', 'all')
                default_ext = ".json"
            else:
                file_filter = build_file_filter(mw.localization, 'xlsx', 'csv', 'json', 'all')
                default_ext = ".xlsx"

            default_filename = "centroids" + default_ext
            if mw.image_manager.current_folder:
                folder_name = os.path.basename(mw.image_manager.current_folder.rstrip(os.sep))
                default_filename = f"{folder_name}_centroids{default_ext}"

            export_file, selected_filter = QFileDialog.getSaveFileName(
                mw,
                mw.localization.get_text("export_centroids"),
                default_filename,
                file_filter
            )

            if export_file:
                file_extension = os.path.splitext(export_file)[1].lower()
                if file_extension in ['.xlsx', '.xls']:
                    file_format = 'excel'
                elif file_extension == '.csv':
                    file_format = 'csv'
                elif file_extension == '.json':
                    file_format = 'json'
                else:
                    file_format = default_format
                    if not file_extension:
                        export_file += default_ext

                success = data_exporter.export_centroids_to_file(export_file, file_format)

                if success:
                    mw.ui_manager.show_message(
                        "info",
                        mw.localization.get_text("export_complete"),
                        f"Centroids exported to {os.path.basename(export_file)}"
                    )
                else:
                    mw.ui_manager.show_message(
                        "warning",
                        mw.localization.get_text("export_failed"),
                        mw.localization.get_text("export_error")
                    )

        except Exception as e:
            if mw.debug_mode:
                print(f"Error in export_centroids: {e}")
                import traceback
                traceback.print_exc()
            mw.ui_manager.show_message(
                "error",
                mw.localization.get_text("export_error"),
                str(e)
            )

    def export_hull_coordinates(self):
        """Export convex hull vertex coordinates for all objects and frames."""
        mw = self.main_window
        has_hulls = any(
            bool(frames) for frames in mw.object_manager.object_hulls.values()
        )
        if not has_hulls:
            mw.ui_manager.show_message(
                "warning",
                mw.localization.get_text("warning"),
                mw.localization.get_text("no_hulls_to_export"),
            )
            return

        default_filename = "hull_coordinates.xlsx"
        if mw.image_manager.current_folder:
            folder_name = os.path.basename(mw.image_manager.current_folder.rstrip(os.sep))
            default_filename = f"{folder_name}_hull_coordinates.xlsx"

        export_file, _ = QFileDialog.getSaveFileName(
            mw,
            mw.localization.get_text("export_hull_coords"),
            default_filename,
            build_file_filter(mw.localization, 'xlsx', 'csv', 'json', 'all'),
        )
        if not export_file:
            return

        try:
            n = mw.export_manager.export_hull_coordinates(export_file)
            mw.ui_manager.show_message(
                "info",
                mw.localization.get_text("success"),
                mw.localization.get_text("hull_coords_exported", n),
            )
        except Exception as e:
            if mw.debug_mode:
                import traceback
                traceback.print_exc()
            mw.ui_manager.show_message(
                "error", mw.localization.get_text("export_error"), str(e)
            )

    def export_contour_coordinates(self):
        """Export outer contour vertex coordinates for all objects and frames."""
        mw = self.main_window
        has_contours = any(
            bool(frames) for frames in mw.object_manager.object_contours.values()
        )
        if not has_contours:
            mw.ui_manager.show_message(
                "warning",
                mw.localization.get_text("warning"),
                mw.localization.get_text("no_contours_to_export"),
            )
            return

        default_filename = "contour_coordinates.xlsx"
        if mw.image_manager.current_folder:
            folder_name = os.path.basename(mw.image_manager.current_folder.rstrip(os.sep))
            default_filename = f"{folder_name}_contour_coordinates.xlsx"

        export_file, _ = QFileDialog.getSaveFileName(
            mw,
            mw.localization.get_text("export_contour_coords"),
            default_filename,
            build_file_filter(mw.localization, 'xlsx', 'csv', 'json', 'all'),
        )
        if not export_file:
            return

        try:
            n = mw.export_manager.export_contour_coordinates(export_file)
            mw.ui_manager.show_message(
                "info",
                mw.localization.get_text("success"),
                mw.localization.get_text("contour_coords_exported", n),
            )
        except Exception as e:
            if mw.debug_mode:
                import traceback
                traceback.print_exc()
            mw.ui_manager.show_message(
                "error", mw.localization.get_text("export_error"), str(e)
            )

    def export_closest_mask_points(self):
        """Export closest mask points for (object, reference point) pairs."""
        mw = self.main_window
        from PyQt5.QtWidgets import QMessageBox
        from .pair_selection_dialog import PairSelectionDialog
        from .reference_point_exporter import ClosestMaskPointExporter

        if not mw.ref_point_manager.reference_points:
            mw.ui_manager.show_message(
                "warning",
                mw.localization.get_text("warning"),
                mw.localization.get_text("no_masks_for_closest"),
            )
            return
        if not mw.object_manager.object_masks:
            mw.ui_manager.show_message(
                "warning",
                mw.localization.get_text("warning"),
                mw.localization.get_text("no_masks_for_closest"),
            )
            return

        total_frames = len(mw.image_manager.image_paths)

        names_extrap = mw.ref_point_manager.any_extrapolation_needed(total_frames)
        if names_extrap:
            names_str = '\n'.join(f"  • {n}" for n in names_extrap)
            reply = localized_question(
                mw,
                mw.localization,
                mw.localization.get_text("warning"),
                mw.localization.get_text("ref_point_extrapolation_warning").format(names_str),
                buttons=QMessageBox.Ok | QMessageBox.Cancel,
                default=QMessageBox.Ok,
                icon=QMessageBox.Warning,
            )
            if reply != QMessageBox.Ok:
                return

        dlg = PairSelectionDialog(
            mw.object_manager, mw.ref_point_manager, mw.localization, mw
        )
        if dlg.exec_() != PairSelectionDialog.Accepted:
            return
        pairs, include_obj_dist = dlg.get_pairs()

        default_filename = "closest_mask_points.xlsx"
        if mw.image_manager.current_folder:
            folder_name = os.path.basename(mw.image_manager.current_folder.rstrip(os.sep))
            default_filename = f"{folder_name}_closest_mask_points.xlsx"
        export_file, _ = QFileDialog.getSaveFileName(
            mw,
            mw.localization.get_text("export_closest_points"),
            default_filename,
            build_file_filter(mw.localization, 'xlsx', 'csv', 'json', 'all'),
        )
        if not export_file:
            return

        try:
            exporter = ClosestMaskPointExporter(mw, debug_mode=mw.debug_mode)
            n = exporter.export_closest_mask_points(
                object_masks=mw.object_manager.object_masks,
                object_names=mw.object_manager.object_names,
                reference_point_manager=mw.ref_point_manager,
                image_paths=mw.image_manager.image_paths,
                export_file=export_file,
                pairs=pairs,
                total_frames=total_frames,
                include_object_distances=include_obj_dist,
            )
            mw.ui_manager.show_message(
                "info",
                mw.localization.get_text("success"),
                mw.localization.get_text("closest_points_exported").format(n),
            )
        except Exception as e:
            if mw.debug_mode:
                import traceback; traceback.print_exc()
            mw.ui_manager.show_message(
                "error", mw.localization.get_text("export_error"), str(e)
            )

    def export_tracked_points(self):
        """Export SAM2++ tracked point coordinates."""
        mw = self.main_window
        om = mw.object_manager
        if not om.object_tracked_points or not any(om.object_tracked_points.values()):
            mw.ui_manager.show_message(
                "warning",
                mw.localization.get_text("warning"),
                mw.localization.get_text("no_tracked_points_to_export"),
            )
            return

        default_filename = "tracked_points.xlsx"
        if mw.image_manager.current_folder:
            folder_name = os.path.basename(mw.image_manager.current_folder.rstrip(os.sep))
            default_filename = f"{folder_name}_tracked_points.xlsx"

        export_file, _ = QFileDialog.getSaveFileName(
            mw, mw.localization.get_text("export_tracked_points"),
            default_filename,
            build_file_filter(mw.localization, 'xlsx', 'csv', 'json', 'all'),
        )
        if not export_file:
            return

        try:
            n = mw.export_manager.export_tracked_points(export_file)
            mw.ui_manager.show_message(
                "info",
                mw.localization.get_text("success"),
                mw.localization.get_text("tracked_points_exported", n),
            )
        except Exception as e:
            if mw.debug_mode:
                import traceback; traceback.print_exc()
            mw.ui_manager.show_message(
                "error", mw.localization.get_text("export_error"), str(e)
            )

    def export_closest_tracked_points(self):
        """Export distances between tracked points and reference points (SAM2++ point mode)."""
        mw = self.main_window
        from .pair_selection_dialog import PairSelectionDialog
        from .reference_point_exporter import TrackedPointDistanceExporter

        om = mw.object_manager
        if not om.object_tracked_points or not any(om.object_tracked_points.values()):
            mw.ui_manager.show_message(
                "warning", mw.localization.get_text("warning"),
                mw.localization.get_text("no_tracked_points_to_export"),
            )
            return
        if not mw.ref_point_manager.reference_points:
            mw.ui_manager.show_message(
                "warning", mw.localization.get_text("warning"),
                mw.localization.get_text("no_masks_for_closest"),
            )
            return

        total_frames = len(mw.image_manager.image_paths)

        names_extrap = mw.ref_point_manager.any_extrapolation_needed(total_frames)
        if names_extrap:
            names_str = '\n'.join(f"  • {n}" for n in names_extrap)
            reply = localized_question(
                mw, mw.localization,
                mw.localization.get_text("warning"),
                mw.localization.get_text("ref_point_extrapolation_warning").format(names_str),
                buttons=QMessageBox.Ok | QMessageBox.Cancel,
                default=QMessageBox.Ok,
                icon=QMessageBox.Warning,
            )
            if reply != QMessageBox.Ok:
                return

        dlg = PairSelectionDialog(mw.object_manager, mw.ref_point_manager, mw.localization, mw)
        if dlg.exec_() != PairSelectionDialog.Accepted:
            return
        pairs, include_obj_dist = dlg.get_pairs()

        default_filename = "tracked_point_distances.xlsx"
        if mw.image_manager.current_folder:
            folder_name = os.path.basename(mw.image_manager.current_folder.rstrip(os.sep))
            default_filename = f"{folder_name}_tracked_point_distances.xlsx"
        export_file, _ = QFileDialog.getSaveFileName(
            mw, mw.localization.get_text("export_closest_tracked_points"),
            default_filename,
            build_file_filter(mw.localization, 'xlsx', 'csv', 'json', 'all'),
        )
        if not export_file:
            return

        image_info = mw.image_manager.get_current_image_info()

        try:
            exporter = TrackedPointDistanceExporter(mw, debug_mode=mw.debug_mode)
            n = exporter.export_tracked_point_distances(
                object_tracked_points=om.object_tracked_points,
                object_names=om.object_names,
                reference_point_manager=mw.ref_point_manager,
                image_paths=mw.image_manager.get_all_image_paths(),
                export_file=export_file,
                image_width=image_info['width'],
                image_height=image_info['height'],
                pairs=pairs,
                total_frames=total_frames,
                include_object_distances=include_obj_dist,
            )
            mw.ui_manager.show_message(
                "info", mw.localization.get_text("success"),
                mw.localization.get_text("closest_tracked_points_exported").format(n),
            )
        except Exception as e:
            if mw.debug_mode:
                import traceback; traceback.print_exc()
            mw.ui_manager.show_message(
                "error", mw.localization.get_text("export_error"), str(e)
            )

    def export_point_mask_analysis(self):
        """Export containment/distance metrics between imported points and mask-mode objects."""
        mw = self.main_window
        from .pair_selection_dialog import PairSelectionDialog, TARGET_IMPORTED
        from .imported_point_mask_analysis_exporter import ImportedPointMaskAnalysisExporter

        if not mw.imported_point_manager.imported_points or not mw.object_manager.object_masks:
            mw.ui_manager.show_message(
                "warning",
                mw.localization.get_text("warning"),
                mw.localization.get_text("no_imported_points_for_analysis"),
            )
            return

        dlg = PairSelectionDialog(
            mw.object_manager, localization=mw.localization, parent=mw,
            imported_point_manager=mw.imported_point_manager,
            allowed_target_types=(TARGET_IMPORTED,),
            window_title=mw.localization.get_text("export_point_mask_analysis"),
        )
        if dlg.exec_() != PairSelectionDialog.Accepted:
            return
        pairs, _ = dlg.get_pairs()

        total_frames = len(mw.image_manager.image_paths)

        default_filename = "point_mask_analysis.xlsx"
        if mw.image_manager.current_folder:
            folder_name = os.path.basename(mw.image_manager.current_folder.rstrip(os.sep))
            default_filename = f"{folder_name}_point_mask_analysis.xlsx"
        export_file, _ = QFileDialog.getSaveFileName(
            mw,
            mw.localization.get_text("export_point_mask_analysis"),
            default_filename,
            build_file_filter(mw.localization, 'xlsx', 'csv', 'json', 'all'),
        )
        if not export_file:
            return

        try:
            exporter = ImportedPointMaskAnalysisExporter(mw, debug_mode=mw.debug_mode)
            n = exporter.export_point_mask_analysis(
                object_masks=mw.object_manager.object_masks,
                object_names=mw.object_manager.object_names,
                object_centroids=mw.object_manager.object_centroids,
                object_hulls=mw.object_manager.object_hulls,
                object_contours=mw.object_manager.object_contours,
                imported_point_manager=mw.imported_point_manager,
                image_paths=mw.image_manager.image_paths,
                export_file=export_file,
                pairs=pairs,
                total_frames=total_frames,
            )
            mw.ui_manager.show_message(
                "info",
                mw.localization.get_text("success"),
                mw.localization.get_text("point_mask_analysis_exported", n),
            )
        except Exception as e:
            if mw.debug_mode:
                import traceback; traceback.print_exc()
            mw.ui_manager.show_message(
                "error", mw.localization.get_text("export_error"), str(e)
            )

    def export_images_with_tracked_points(self):
        """Export images with tracked point markers (SAM2++ point mode)."""
        mw = self.main_window
        om = mw.object_manager
        if not om.object_tracked_points or not any(om.object_tracked_points.values()):
            mw.ui_manager.show_message(
                "warning",
                mw.localization.get_text("warning"),
                mw.localization.get_text("no_tracked_points_to_export"),
            )
            return
        export_folder = QFileDialog.getExistingDirectory(
            mw, mw.localization.get_text("select_export_folder"), QDir.homePath()
        )
        if not export_folder:
            return
        try:
            from .exporters import ImageExporter
            exporter = ImageExporter(mw, debug_mode=mw.debug_mode)
            n = exporter.export_images_with_tracked_points(
                mw.image_manager.get_all_image_paths(),
                om.object_tracked_points,
                om.object_colors,
                om.object_names,
                om.tracked_point_style,
                om.tracked_point_size,
                export_folder,
                quality=mw.config_manager.get_image_quality(),
            )
            mw.ui_manager.show_message(
                "info",
                mw.localization.get_text("export_complete"),
                mw.localization.get_text("images_exported", n,
                    os.path.join(export_folder, "images_with_tracked_points")),
            )
        except Exception as e:
            if mw.debug_mode:
                import traceback; traceback.print_exc()
            mw.ui_manager.show_message(
                "error", mw.localization.get_text("export_error"), str(e)
            )
