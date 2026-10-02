"""
Localization Manager
Handles application internationalization and text translations using external TSV files
"""

import os
import csv
from pathlib import Path

class LocalizationManager:
    """Manages application localization with external translation files"""
    
    def __init__(self, translations_dir=None, default_language=None):
        self.current_language = default_language or "en"  # Use provided default or fallback to English
        self.translations = {}
        self.language_names = {}  # Maps language codes to display names
        self.translations_dir = translations_dir or self._get_default_translations_dir()
        self.load_translations()
        
        # After loading, validate that the default language exists
        if self.current_language not in self.translations:
            print(f"Warning: Configured language '{self.current_language}' not found, falling back to English")
            self.current_language = "en"
    
    def _get_default_translations_dir(self):
        """Get default translations directory (same as this module)"""
        return Path(__file__).parent / "translations"
    
    def load_translations(self):
        """Load translations from TSV files"""
        self.translations = {}
        self.language_names = {}
        
        # Always load English as fallback (embedded)
        self.translations["en"] = self._get_english_fallback()
        self.language_names["en"] = "English"
        
        # Ensure translations directory exists
        translations_path = Path(self.translations_dir)
        if not translations_path.exists():
            print(f"Warning: Translations directory not found: {translations_path}")
            print("Only English will be available")
            return
        
        # Load each language file (silently)
        for tsv_file in translations_path.glob("*.tsv"):
            language_code = tsv_file.stem
            
            # Skip English and template
            if language_code in ["en", "template"]:
                continue
            
            try:
                language_name, translations = self._load_tsv_file(tsv_file)
                if language_name and translations:
                    self.translations[language_code] = translations
                    self.language_names[language_code] = language_name
            except Exception as e:
                print(f"Error loading translations for '{language_code}': {e}")
                print(f"File: {tsv_file}")
        
        # Display info about the ACTIVE language only
        if self.current_language in self.translations:
            lang_name = self.language_names.get(self.current_language, self.current_language)
            trans_count = len(self.translations[self.current_language])
            print(f"Loaded {trans_count} translations for '{lang_name}' ({self.current_language})")
        
        # Ensure current language exists
        if self.current_language not in self.translations:
            available_languages = list(self.translations.keys())
            if available_languages:
                self.current_language = "en"
                print(f"Warning: Configured language not found, using English")
    
    def _load_tsv_file(self, tsv_file):
        """Load translations from a single TSV file, returning (language_name, translations)"""
        translations = {}
        language_name = None
        
        with open(tsv_file, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file, delimiter='\t')
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 because header is row 1
                # Safely get values with fallback to empty string
                key = (row.get('key') or '').strip()
                # A TSV field holds no real newline: "\n" is written as an escape
                # and decoded here, so multi-line messages match the English fallback
                translation = (row.get('translation') or '').strip().replace('\\n', '\n')
                
                # Skip empty rows
                if not key and not translation:
                    continue
                
                # Skip comments (lines starting with #)
                if key.startswith('#'):
                    continue
                
                # Special handling for language name (must be first non-comment row)
                if key == "language_name" and language_name is None:
                    language_name = translation
                    continue
                
                # Regular translation entry
                if key and translation:
                    translations[key] = translation
                elif key:  # Key exists but translation is empty
                    print(f"Warning: Empty translation for key '{key}' in {tsv_file.name} (line {row_num})")
        
        # Validate that we found a language name
        if language_name is None:
            print(f"Error: No 'language_name' found in {tsv_file.name}")
            print("First non-comment line should be: language_name\\t[Language Display Name]\\t...")
            return None, None
        
        return language_name, translations
    
    def _get_english_fallback(self):
        """Get embedded English translations (fallback only)"""
        return {
            # Main window
            "window_title": "VOLUTE",
            "folder_selection": "Folder Selection",
            "select_folder": "Select image folder",
            "no_folder_selected": "No folder selected",
            
            # Status
            "status_loading_images": "Loading images: {0}",
            "status_initializing_sam2": "Initializing SAM2…",
            "sam2_init_failed": "SAM2 could not be initialized for the folder {0}.",
            
            # Navigation
            "navigation": "Navigation",
            "previous": "\u25c0 Previous",
            "next": "Next \u25b6",
            
            # Points configuration
            "points_config": "Points Configuration",
            "add_points": "Add points",
            "add_points_tooltip": "Left click: positive point | Right click or Ctrl+click: negative point",
            "remove_points": "Remove points",
            "remove_points_tooltip": "Click and drag to select area | All points in rectangle will be removed",
            "define_box": "Define box",
            "define_box_tooltip": "Click and drag to define a bounding box | One box per object and frame, combined with that frame's points",
            "remove_box_btn": "Remove box",
            "box_points_outside_title": "Points contradicting the box",
            "box_points_outside_msg": (
                "{0} positive and {1} negative point(s) of this object on this frame "
                "lie outside the box just drawn. SAM2 receives the box and the points "
                "together, so these points contradict the box rather than being ignored."
            ),
            "box_points_outside_delete_hint": "Delete the points outside the box?",
            "point_outside_box_confirm": (
                "This point lies outside the box defined for this object on this frame. "
                "SAM2 receives the box and the points together, so this point will "
                "contradict the box rather than being ignored. Add it anyway?"
            ),
            "box_mask_import_conflict": (
                "The mask of this object on this frame comes from an imported mask. "
                "A box and an imported mask are competing conditioning inputs: the next "
                "prediction will replace the imported mask. Define the box anyway?"
            ),
            "box_delete_imported_mask": "Delete the existing mask right away",
            "strict_box_clipping": "Masks strictly confined to box:",
            "strict_box_clipping_tooltip": (
                "Clears every predicted pixel outside the box. Applies to subsequent "
                "predictions and propagations only: a mask already clipped cannot be "
                "restored by turning this option back off."
            ),
            "box_clipping_mode": "Clipping applies to:",
            "box_clipping_mode_box_frames": "Frames with a box",
            "box_clipping_mode_reference": "All frames (reference box)",
            "box_clipping_reference_warning": (
                "The reference box is the box defined on the object's first frame. "
                "Applying it to every frame only makes sense for an object that does "
                "not move: as soon as it does, the box will cut through it."
            ),
            "box_mask_import_conflict_batch": (
                "{0} of the masks about to be imported target an object and frame that "
                "already has a box. A box and an imported mask are competing conditioning "
                "inputs: the next prediction will replace the imported mask on those "
                "frames. Import anyway?"
            ),
            "show_points_global": "Show points (current object):",
            "clear_all_points": "Clear all points",
            "multi_selection_add_points_blocked": "Adding points requires a single selected object.",
            
            # Point tracking (SAM2++)
            "export_tracked_points":       "Export tracked points",
            "export_closest_tracked_points":     "Export closest tracked point distances\u2026",
            "closest_tracked_points_exported":   "Tracked point distances exported ({0} rows).",
            "no_tracked_points_to_export": "No tracked points to export",
            "tracked_points_exported":     "{0} tracked points exported",
            "tab_prediction":                    "Prediction",
            "tab_points_definition":             "Points",
            "point_management":                  "Point Management",
            "points_list":                       "Points list:",
            "add_point_btn":                     "Add point",
            "remove_point_btn":                  "Remove point",
            "current_point_config":              "Current Point Configuration",
            "show_current_point":                "Show current point:",
            "point_color":                       "Point color:",
            "tracked_point_color":               "Tracked point color:",
            "tracked_point_display_config":      "Tracked Point Display",
            "tracked_point_size_label":          "Tracked point size:",
            "tracked_point_style_label":         "Tracked point style:",
            "clear_point":                       "Clear point",
            "predict_points":                    "Predict points on current frame",
            "propagate_points":                  "Propagate points through video",
            "export_images_with_tracked_points": "Export images with tracked points",
            "mode_mask":           "Mask mode",
            "mode_point_tracking": "Point tracking mode",
            "clear_points":        "Clear points",
            "edit":                "Edit",
            "undo":                "Undo",
            "redo":                "Redo",
            
            # Object management
            "object_management": "Object Management",
            "object_list": "Object list:",
            "add_object": "Add object",
            "remove_object": "Remove object",
            "current_object_config": "Current Object Configuration",
            "positive_points_color": "Positive points color:",
            "negative_points_color": "Negative points color:",
            "mask_color": "Mask color:",
            "marker_style": "Marker style:",
            "marker_size": "Marker size:",
            "marker_style_circle": "Circle",
            "marker_style_square": "Square",
            "marker_style_triangle": "Triangle",
            "marker_style_diamond": "Diamond",
            "marker_style_star": "Star",
            "marker_style_cross": "Cross",
            "marker_style_plus": "Plus",
            "marker_style_plus_filled": "Filled plus",
            "marker_style_cross_filled": "Filled cross",
            "mask_opacity": "Mask opacity:",
            "show_points": "Show points:",
            "object_name": "Object name:",
            "object": "Object",
            "point": "Point",
            "point_name": "Point name:",
            "confirm_remove_objects": "Are you sure you want to remove {0} objects?",
            
            # Prediction
            "prediction": "Prediction",
            "predict_current": "Predict masks on current image",
            "propagate_masks": "Propagate masks through video",
            
            # Display options
            "background_opacity": "Background opacity:",
            "show_labels": "Show labels:",
            "centroid_config": "Centroid Configuration",
            "show_centroids": "Show centroids:",
            "centroid_color": "Centroid color:",
            "centroid_size": "Centroid size:",
            
            # Export
            "export": "Export",
            "export_images": "Export images with masks",
            "export_coordinates": "Export mask coordinates",
            "export_centroids": "Export centroids",
            
            # Menu
            "language": "Language",
            "file": "File",
            "project_data": "Project Data", 
            "sam2_inference_state": "SAM2 Inference State (Experimental)",
            
            # About dialog
            "help":                "Help",
            "about_title":         "About",
            "about_subtitle":      "Video Object Labeling, User-guided Tracking and Extraction",

            # Model chooser and settings
            "model_dialog_title": "Model selection",
            "model_dialog_prompt": "Select the model to use:",
            "model_dialog_launch": "Open",
            "model_set_default": "Set as default",
            "model_set_default_tooltip": "Saves this model as the one preselected here, and used directly when this list is not shown.",
            "model_show_at_startup": "Show this list at startup",
            "model_show_at_startup_tooltip": "When unchecked, the application starts directly with the default model. This choice can be changed in the application settings.",
            "debug_mode_label": "Debug mode",
            "debug_mode_tooltip": "Prints detailed technical information about the application's operation to the console, or to the log file when started from an application bundle.",
            "model_desc_sam2_default": "Best accuracy",
            "model_desc_sam2_small": "Faster processing",
            "model_desc_medsam2_general": "General medical imaging",
            "model_desc_medsam2_ct": "CT lesions",
            "model_desc_medsam2_heart": "Cardiac ultrasound",
            "model_desc_medsam2_liver": "Liver lesions in MRI",
            "model_desc_sam2plus_mask": "Drop-in SAM2 replacement",
            "model_desc_sam2plus_point": "Point trajectories",
            "settings_menu": "Settings…",
            "settings_title": "Settings",
            "settings_tab_interface": "Interface",
            "settings_tab_export": "Export",
            "settings_tab_tools": "Performance and tools",
            "settings_tab_debug": "Debugging",
            "settings_language": "Interface language:",
            "settings_show_model_dialog": "Show the model list at startup:",
            "settings_show_image_filename": "Show the image filename:",
            "settings_default_model": "Default model:",
            "settings_native_dialogs": "System file dialogs:",
            "settings_import_confirmation": "Default answer to import dialogs:",
            "settings_progress_font": "Progress details font size:",
            "settings_animation_pacing": "Progress animation pace:",
            "settings_coordinates_format": "Mask coordinates format:",
            "settings_centroids_format": "Centroids format:",
            "settings_image_quality": "JPEG quality of exported images:",
            "settings_cache_size": "Frames kept in memory (0 = unlimited):",
            "settings_gimp_path": "GIMP executable:",
            "settings_ffmpeg_path": "ffmpeg executable:",
            "settings_debug_enabled": "Verbose debug output:",
            "settings_debug_filenames": "Detail filename matching:",
            "settings_debug_mask_sync": "Detail mask synchronization:",
            "settings_browse": "Browse…",
            "settings_save": "Save",
            "settings_restore_defaults": "Restore defaults",
            "settings_restore_confirm": "Restore every setting to its default value? Nothing is written until you save.",
            "settings_restart_note": "Most settings take effect the next time the application starts.",
            "settings_saved": "Settings saved.",
            "settings_save_failed": "The configuration file could not be written.",
            "about_version":       "Version {0}",
            "about_credits_title": "Credits",
            "about_credits_body":  "Developed by <a href='https://lpp.cnrs.fr/nicolas-audibert/'><b>Nicolas Audibert</b></a> "
                                   "with the assistance of "
                                   "<a href='https://claude.ai'>Claude</a> (Anthropic) as an AI "
                                   "pair-programming assistant.",
            "about_logo_credit":   "The logo was created by Solène Bodiou.",
            "about_repository_title": "Repository",
            "about_repository_body":  "Source code, releases and issue tracker: "
                                      "<a href='https://github.com/nicolasaudibert/VOLUTE'>"
                                      "github.com/nicolasaudibert/VOLUTE</a>.",
            "about_license_title": "License",
            "about_license_body":  "This software is distributed under the "
                                   "<a href='https://www.gnu.org/licenses/gpl-3.0.html'>"
                                   "GNU General Public License v3.0</a>.",
            "about_sam2_title":    "SAM2",
            "about_sam2_body":     "This application builds on "
                                   "<a href='https://github.com/facebookresearch/segment-anything-2'>"
                                   "SAM 2</a> by Meta AI Research. "
                                   "Please cite the following reference in academic work:",
            "about_medsam2_title": "MedSAM2 (optional backend)",
            "about_medsam2_body":  "If you use the MedSAM2 backend, please also cite:",
            "about_sam2plus_title": "SAM2++ (optional backend)",
            "about_sam2plus_body":  "If you use the SAM2++ backend, please also cite:",
            
            # Messages
            "warning": "Warning",
            "error": "Error",
            "success": "Success",
            "confirmation": "Confirmation",
            "no_images_found": "No images found in folder.",
            "no_image_loaded": "No image loaded.",
            "define_points_first": "Please define at least one point or box for at least one object on this image.",
            "no_inference_state": "Inference state not initialized. Please predict a mask first.",
            "no_masks_to_export": "No masks to export.",
            "no_centroids_to_export": "No centroids to export.",
            "prediction_in_progress": "Mask prediction in progress...",
            "initializing_inference_state": "Initializing inference state…",
            "predicting_object": "Prediction for {0}…",
            "forward_propagation": "Forward propagation: {0}",
            "backward_propagation": "Backward propagation: {0}",
            "repropagation_forward": "Re-propagation (forward): {0}",
            "repropagation_backward": "Re-propagation (backward): {0}",
            "propagation_interrupted": "Propagation Interrupted",
            "prediction_error": "Error during prediction: {0}",
            "propagation_error": "Error during propagation: {0}",
            "propagation_in_progress": "Mask propagation in progress...",
            "cancel": "Cancel",
            "yes": "Yes",
            "no": "No",
            "cannot_remove_all_objects": "You must keep at least one object.",
            "cannot_remove_all_points":  "You must keep at least one point.",
            "confirm_remove_object": "Are you sure you want to remove object {0}?",
            "prediction_successful": "Prediction successful for {0} object(s) on image {1}.",
            "no_masks_generated": "No masks could be generated.",
            "propagation_successful": "Bidirectional propagation successful: {0} masks generated for {1} objects.",
            "images_exported": "{0} images exported successfully in {1}",
            "coordinates_exported": "Mask coordinates exported successfully: {0} masks.",
            "centroids_exported": "Centroids exported successfully ({0} centroids).",
            "pandas_required": "pandas and openpyxl libraries are required for Excel export. Please install them with: pip install pandas openpyxl",
            "prediction_cancelled": "Prediction cancelled by user.",
            "propagation_cancelled": "Propagation interrupted after {0} operations.",
            "folder": "Folder",
            "image": "Image",
            
            # File dialog filters
            "filter_volute": "VOLUTE Project Data",
            "filter_voluteinf": "SAM2 Inference State Files",
            "filter_xlsx": "Excel Files",
            "filter_csv": "CSV Files",
            "filter_json": "JSON Files",
            "filter_pkl": "Pickle Files",
            "filter_tsv": "TSV Files",
            "filter_txt": "Text Files",
            "filter_yaml": "YAML Files",
            "filter_xcf": "GIMP Files",
            "filter_image": "Image Files",
            "filter_mask": "Mask Files",
            "filter_video": "Video Files",
            "filter_all": "All Files",

            # Project data management
            "export_project_data": "Export Project Data",
            "import_project_data": "Import Project Data",
            "project_data_exported": "Project data exported successfully to {0} ({1} KB).",
            "project_data_imported": "Project data imported successfully from {0}",
            "no_project_data": "No project data to export. Please create some objects and predict masks first.",
            "project_export_no_dimensions": "No image loaded. Cannot determine image dimensions.",
            "project_include_imported_masks_title": "Imported masks",
            "project_include_imported_masks_msg": (
                "This project contains {0} mask(s) that came from an import. Unlike predicted "
                "masks, they cannot be recomputed from the saved points and boxes.\n\n"
                "Include them in the project file (larger, self-contained), or leave them out "
                "and re-import them after loading?"
            ),
            "project_export_error": "Error exporting project data: {0}",
            "project_import_error": "Error importing project data: {0}",
            "project_import_failed": "Failed to import project data.",
            "project_version_mismatch": "This file may be from a different version. Import may not work correctly.",
            "project_minimal_export": "This file contains minimal data: {0}",
            "file_not_found": "File not found: {0}",
            "dimension_mismatch": (
                "Image dimensions mismatch!\n\nCurrent images: {0}x{1}\nSaved state: {2}x{3}\n\n"
                "This may cause issues with mask positions. Continue anyway?"
            ),
            "import_project_warning": "This will overwrite the current object data and points. Continue?",
            "partial_import": "Object data imported successfully, but SAM2 inference state could not be restored.",
            
            # SAM2 inference state management
            "export_sam2_state": "Export SAM2 Inference State",
            "import_sam2_state": "Import SAM2 Inference State",
            "import_sam2_state_warning": "This will overwrite the current SAM2 inference state. Continue?",
            "sam2_config_title": "SAM2 Configuration",
            "sam2_config_question": "Would you like to select the configuration and checkpoint files for SAM2?",
            "sam2_config_defaults": "Otherwise the default paths are used:\nConfig: {0}\nCheckpoint: {1}",
            "sam2_config_select_checkpoint": "Select SAM2 checkpoint file",
            "sam2_config_select_config": "Select SAM2 configuration file",
            "filter_pt": "PyTorch Checkpoint",
            "sam2_state_exported": "SAM2 inference state exported successfully to {0}",
            "sam2_state_imported": "SAM2 inference state imported successfully from {0}",
            "no_sam2_state": "No SAM2 inference state to export. Please predict masks first.",
            "sam2_device_mismatch": "Device mismatch detected! This may cause import to fail.",
            "sam2_experimental_warning": "SAM2 inference state export/import is experimental and may not work across different systems.",
            "sam2_export_successful": "SAM2 Export Successful",
            "sam2_import_successful": "SAM2 Import Successful",
            "sam2_export_failed": "SAM2 Export Failed",
            "sam2_import_failed": "SAM2 Import Failed",
            "device_mismatch": "Device Mismatch",
            "invalid_file": "Invalid File",
            "file_not_found": "File Not Found",
            
            # Export operations
            "select_export_folder": "Select export folder",
            "export_complete": "Export Complete",
            "export_failed": "Export Failed", 
            "export_error": "Export Error",
            "masked_images_exported": "Masked images exported successfully",
            "coordinates_exported_success": "Coordinates exported successfully",
            "centroids_exported_success": "Centroids exported successfully",
            
            # Progress dialogs
            "exporting_sam2_state": "Exporting SAM2 inference state...",
            "importing_sam2_state": "Importing SAM2 inference state...",
            "serializing_data": "Serializing SAM2 data...",
            "deserializing_data": "Deserializing SAM2 data...",
            "processing_masks": "Processing masks...",
            "validating_state": "Validating inference state...",
            "saving_file": "Saving file...",
            "loading_file": "Loading file...",
            "preparing_import": "Preparing for import...",
            "finalizing_import": "Finalizing import...",
            "progress_complete": "Operation completed successfully",
            "progress_cancelled": "Operation cancelled by user",
            
            # Batch processing
            "batch_processing": "Batch Processing",
            "batch_items": "Batch Items",
            "batch_options": "Processing Options",
            "batch_col_sam2": ".volute File",
            "batch_col_folder": "Image Folder",
            "batch_col_ref_frame": "Ref Frame",
            "batch_add_row": "Add Row",
            "batch_remove_row": "Remove Row",
            "batch_browse_sam2": "Browse .volute\u2026",
            "batch_browse_folder": "Browse Folder\u2026",
            "batch_browse_tracked_points": "Browse Tracked Points\u2026",
            "batch_col_tracked_points_file": "Tracked Points File",
            "batch_import_tsv": "Import TSV\u2026",
            "batch_export_tsv": "Export TSV\u2026",
            "batch_browse": "Browse\u2026",
            "batch_run": "Run Batch",
            "batch_close": "Close",
            "batch_output_folder": "Output folder:",
            "batch_output_placeholder": "Select output folder\u2026",
            "batch_ready": "Ready.",
            "batch_opt_propagate": "Propagate masks",
            "batch_opt_export_images": "Export masked images",
            "batch_opt_state_predict": "Export inference state (prediction)",
            "batch_opt_state_prop": "Export inference state (propagation)",
            "batch_no_selection": "No Selection",
            "batch_no_selection_msg": "Select a row first.",
            "batch_import_error": "Import Error",
            "batch_export_error": "Export Error",
            "batch_no_items": "No Items",
            "batch_no_items_msg": "Add at least one .volute / folder pair.",
            "batch_no_output": "No Output Folder",
            "batch_no_output_msg": "Select an output folder.",
            "batch_invalid_paths": "Invalid Paths",
            "batch_select_sam2": "Select .volute file",
            "batch_import_tsv_title": "Import TSV",
            "batch_export_tsv_title": "Export TSV",
            "batch_imported_rows": "Imported {0} row(s) from {1}.",
            "batch_exported_rows": "Exported {0} row(s) to {1}.",
            "batch_starting": "Starting batch: {0} item(s)",
            "batch_cancel_requested": "Cancellation requested\u2026",
            "batch_status_ok": "OK",
            "batch_status_errors": "ERRORS",
            "batch_complete": "Batch complete: {0}/{1} succeeded.",
            
            # Reference points
            "ref_points": "Reference Points",
            "ref_point_name": "Point name:",
            "add_ref_point_btn": "Add",
            "rename_ref_point_btn": "Rename",
            "remove_ref_point_btn": "Remove (all frames)",
            "remove_ref_point_frame_btn": "Remove (this frame)",
            "no_ref_point_selected": "No reference point selected.",
            "ref_point_name_empty": "Please enter a point name.",
            "ref_point_name_exists": "A point with this name already exists.",
            "current_ref_point_config": "Current Reference Point Configuration",
            "ref_point_color": "Reference point color:",
            "confirm_remove_ref_points": "Are you sure you want to remove {0} reference points?",
            "confirm_remove_ref_points_frame": "Are you sure you want to remove the current-frame position for {0} reference points?",
            "export_closest_points": "Export closest mask points\u2026",
            "closest_points_exported": "Closest mask points exported ({0} rows).",
            "no_masks_for_closest": "No masks available for closest point export.",
            "ref_point_extrapolation_warning": (
                "The following reference points require extrapolation for some frames:\n"
                "{0}\n\nProceed anyway?"
            ),
            "ref_advanced_mode": "Advanced mode (per-frame positions)",
            "ref_advanced_mode_blocked": (
                "Cannot disable advanced mode: the following points have positions "
                "defined on multiple frames:\n{0}\n\nRemove their extra positions first."
            ),
            "ref_point_reposition_confirm": (
                "This click will change the interpolated position of this point on "
                "this frame. Continue?"
            ),
            "dont_ask_again": "Don't ask again",
            "ref_point_prev_frame_btn": "\u25c0 Previous defined frame",
            "ref_point_next_frame_btn": "Next defined frame \u25b6",
            "ref_point_defined_frame_prev_btn": "\u25c0 Defined frame",
            "ref_point_defined_frame_next_btn": "Defined frame \u25b6",
            "ref_point_extrapolation_label": "Extrapolation:",
            "ref_point_extrapolation_extrapolate": "Extrapolate",
            "ref_point_extrapolation_undefined": "Undefined",
            "ref_point_extrapolation_clamp": "Clamp to boundary",
            "ref_point_interpolation_label": "Interpolation:",
            "ref_point_interpolation_cubic": "Cubic",
            "ref_point_interpolation_linear": "Linear",
            "batch_tab_items": "Items \u0026 Options",
            "batch_tab_ref_points": "Reference Points",
            "batch_all_pairs": "All combinations",
            "batch_selected_pairs": "Selected pairs",
            "batch_col_object": "Object",
            "batch_col_ref_point": "Reference Point",
            "batch_opt_closest_points": "Export closest mask points",
            "batch_ref_pairs_tsv_import": "Import pairs TSV\u2026",
            "batch_ref_pairs_tsv_export": "Export pairs TSV\u2026",
            "include_object_distances": "Include inter-object distances",
            "ref_point": "Ref. point",
            "objects": "objects",
            "import_names_btn": "Import from file\u2026",
            "import_names_overwrite_msg": (
                "Existing {0} found.\n\n"
                "Overwrite all existing entries (Yes) or append imported names (No)?"
            ),
            "import_names_duplicates_title": "Duplicate Names",
            "import_names_duplicates_msg": (
                "The following names already exist:\n{0}\n\n"
                "Rename duplicates with a suffix (Yes) or skip them (No)?"
            ),
            "import_cross_names_title": "Name Conflict",
            "import_cross_names_msg": (
                "The following names exist in both objects and reference points:\n{0}\n\n"
                "Objects and reference points are managed separately, but identical "
                "names may be confusing. Consider renaming one of them."
            ),
            "batch_col_target_type": "Target Type",
            "target_type_ref": "Ref. Point",
            "target_type_obj": "Object",
            
            # Tabs
            "tab_objects_definition": "Objects",
            "tab_ref_points": "Ref. Points",
            "tab_masks": "Masks",
            
            # Convex hull
            "show_hulls":           "Show convex hulls:",
            "hull_smoothing":       "Smoothing:",
            "hull_line_width":      "Line width:",
            "hull_outline":         "Show outer contour:",
            "hull_outline_color":   "Contour color:",
            "export_hull_coords":   "Export convex hull coordinates",
            "hull_coords_exported": "Hull coordinates exported ({0} rows).",
            "no_hulls_to_export":   "No convex hulls to export.",
            "batch_opt_export_hull":"Export hull coordinates",
            
            # Outer contour
            "mask_contours_config":    "Mask Contours",
            "tab_outer_contour":       "Outer Contour",
            "tab_convex_hull":         "Convex Hull",
            "show_contours":           "Show outer contours:",
            "contour_smoothing":       "Smoothing:",
            "contour_line_width":      "Line width:",
            "contour_outline":         "Show outer border:",
            "contour_outline_color":   "Border color:",
            "export_contour_coords":   "Export contour coordinates",
            "contour_coords_exported": "Contour coordinates exported ({0} rows).",
            "no_contours_to_export":   "No contours to export.",
            "batch_opt_export_contour":"Export contour coordinates",
            
            # Imported points (SAM2++ point mode export, mask mode import)
            "imported_points_config":        "Imported Points",
            "show_imported_points":          "Show imported points:",
            "remove_imported_point_btn":     "Remove",
            "current_imported_point_config": "Current Imported Point Configuration",
            "imported_point_color":          "Imported point color:",
            "no_imported_point_selected":    "No imported point selected.",
            "confirm_remove_imported_point": "Are you sure you want to remove imported point {0}?",
            "batch_col_imported_point":      "Imported Point",
            "batch_tab_imported_points":     "Imported Points",
            "batch_opt_export_point_mask_analysis": "Export point/mask analysis",
            
            # Imported points — file import
            "import_tracked_points":                 "Import Tracked Points\u2026",
            "imported_points_count_mismatch":         "The imported file references {0} frame(s), but the current folder has {1} image(s).\n\nContinue anyway?",
            "imported_points_filenames_unmatched":    "{0} imported filename(s) could not be matched to the current image folder and will be skipped:\n{1}",
            "imported_points_no_match":               "None of the imported filenames match the current image folder. Import cancelled.",
            "imported_points_out_of_bounds_warning":  "Some imported points fall outside the current image dimensions for the following names, which may indicate a mismatch with the source session:\n{0}",
            "imported_points_imported":               "{0} imported point(s) imported successfully.",
            
            # Imported points — point/mask analysis export
            "export_point_mask_analysis":      "Export Point/Mask Analysis\u2026",
            "point_mask_analysis_exported":    "Point/mask analysis exported ({0} rows).",
            "no_imported_points_for_analysis": "No imported points or no masks available for point/mask analysis.",
            
            # Mask-based initialization (import mask)
            "import_mask":                        "Import Masks\u2026",
            "imported_mask_filenames_unmatched":   "{0} imported mask filename(s) could not be matched to the current image folder and will be skipped:\n{1}",
            "imported_mask_imported":              "{0} mask(s) imported successfully.",
            "imported_mask_imported_multi_frame":  "{0} mask(s) imported successfully across {1} frame(s).",
            "repropagate_from_frame":              "Re-propagate from this frame\u2026",
            "repropagate_span_title":              "Re-propagate Span",
            "repropagate_forward_label":           "Forward (frames):",
            "repropagate_backward_label":          "Backward (frames):",
            "repropagate_unbounded":               "Unbounded",
            "mask_color_mapping_title":            "Map Colors to Objects",
            "mask_color_mapping_hint":              "Assign each detected color to an object:",
            "mask_color_mapping_new_object":       "Create new object",
            "no_mask_on_frame_to_repropagate":     "No mask on the current frame for this object.",
            
            # GIMP export (mask editing round-trip)
            "gimp_export_frame":            "Export Frame for Editing\u2026",
            "gimp_export_dialog_title":     "Export Frame for Editing",
            "gimp_export_dialog_hint":      "Choose how to export the current frame and object masks:",
            "gimp_export_mode_xcf":         "Single .xcf file (assembled by GIMP)",
            "gimp_export_mode_files":       "Separate image files",
            "gimp_export_all_mode_xcf":     "One .xcf file per frame (assembled by GIMP)",
            "gimp_export_all_mode_files":   "Separate image files (one subfolder per frame, then per object)",
            "gimp_not_detected_tooltip":    "GIMP command-line executable not found \u2014 see gimp.executable_path in the configuration file.",
            "gimp_export_successful":       "Frame exported successfully.",
            "gimp_export_in_progress":      "Exporting\u2026 this may take a moment while GIMP starts.",
            "gimp_import_in_progress":      "Importing\u2026 this may take a moment while GIMP starts.",
            "gimp_export_all_frames":       "Export All Frames for Editing\u2026",
            "gimp_export_all_frames_confirm":     "{0} frame(s) will be exported. Continue?",
            "gimp_export_all_frames_successful":  "{0} frame(s) exported successfully.",
            "gimp_export_all_dialog_title": "Export All Frames for Editing",
            "gimp_export_all_dialog_hint":  "Choose how to export the frames and object masks:",
            "imported_mask_no_xcf_layers":  "No mask layers found in the selected .xcf file(s).",
            "gimp_import_replace_default_object": (
                "The current object '{0}' has no points or masks yet. Replace it "
                "with the {1} imported object(s) instead of adding them?"
            ),
            "gimp_export_cancelled":         "Export cancelled.",
            "gimp_export_partial_cancelled": (
                "Export cancelled: {0} of {1} frame(s) exported before cancellation."
            ),
            "gimp_import_cancelled":         "Import cancelled. No mask was imported.",

            # Frame extraction from a video file (ffmpeg)
            "video_frames_menu": "Extract Frames from Video\u2026",
            "video_frames_title": "Extract Frames from Video",
            "video_frames_video": "Video file:",
            "video_frames_select_video": "Select a video file",
            "video_frames_destination": "Destination folder:",
            "video_frames_select_destination": "Select the destination folder",
            "video_frames_format": "Image format:",
            "video_frames_format_jpg": "JPEG (compact)",
            "video_frames_format_png": "PNG (lossless, much larger)",
            "video_frames_quality": "JPEG quality:",
            "video_frames_rate": "Frames:",
            "video_frames_rate_all": "Every frame",
            "video_frames_rate_fps": "Per second:",
            "video_frames_range": "Time range:",
            "video_frames_start": "From",
            "video_frames_end": "to",
            "video_frames_extract": "Extract",
            "video_frames_info": "Duration {0} s \u00b7 {1} frames per second \u00b7 {2} frames \u00b7 {3}",
            "video_frames_no_ffprobe": "ffprobe was not found beside ffmpeg: the video's duration and frame count are unknown, so progress cannot be measured.",
            "video_frames_probe_failed": "This file cannot be read as a video:\n{0}",
            "video_frames_preview": "About {0} frame(s), named {1}, {2}, \u2026",
            "video_frames_preview_unknown": "Frames named {0}, {1}, \u2026",
            "video_frames_no_video": "Choose a video file.",
            "video_frames_no_destination": "Choose a destination folder.",
            "video_frames_destination_not_folder": "The destination exists and is not a folder.",
            "video_frames_destination_has_images": "The destination folder already holds images. Choose an empty or new folder, so that the frames are not mixed with other images.",
            "video_frames_bad_range": "The end of the time range must come after its start.",
            "video_frames_start_past_end": "The start of the time range lies beyond the end of the video ({0} s).",
            "video_frames_progress": "Extracting frames from {0}\u2026\n{1} frame(s) written",
            "video_frames_cancelled": "Extraction cancelled. No frame was kept.",
            "video_frames_none": "No frame was extracted. Check that the time range lies within the video.",
            "video_frames_failed": "Frame extraction failed:\n{0}",
            "video_frames_done_load": "{0} frame(s) extracted into:\n{1}\n\nLoad them now?",
            "video_frames_ffmpeg_missing": "ffmpeg was not found. Install it (it is free, from ffmpeg.org or a package manager), or give the path to its executable in Settings \u203a Performance and tools.",
            "video_frames_ffmpeg_override_invalid": "The ffmpeg path given in Settings \u203a Performance and tools is not an executable file:\n{0}",
        }
    
    def get_text(self, key, *args):
        """Get translated text for the current language"""
        # Try current language first
        text = self.translations.get(self.current_language, {}).get(key)
        
        # Fallback to English if not found
        if text is None:
            text = self.translations.get("en", {}).get(key, key)
            if text == key:  # Key not found even in English
                print(f"Warning: Translation key '{key}' not found in any language")
        
        # Apply formatting if arguments provided
        if args:
            try:
                return text.format(*args)
            except (IndexError, KeyError, ValueError) as e:
                print(f"Warning: Error formatting translation '{key}': {e}")
                return text
        
        return text
    
    def set_language(self, language):
        """Set the current language"""
        if language in self.translations:
            self.current_language = language
            return True
        else:
            print(f"Warning: Language '{language}' not available")
            return False
    
    def get_available_languages(self):
        """Get list of available languages with their display names"""
        return [(code, name) for code, name in self.language_names.items()]
    
    def get_language_name(self, language_code):
        """Get display name for a language code"""
        return self.language_names.get(language_code, language_code)
    
    def reload_translations(self):
        """Reload translations from files (useful after adding new languages)"""
        self.load_translations()
    
    def validate_translation_file(self, tsv_file_path):
        """Validate a translation file without loading it"""
        try:
            language_name, translations = self._load_tsv_file(Path(tsv_file_path))
            if not language_name:
                return False, "No language_name found in file"
            
            # Check against English keys
            english_keys = set(self.translations["en"].keys())
            translation_keys = set(translations.keys())
            
            missing_keys = english_keys - translation_keys
            extra_keys = translation_keys - english_keys
            
            issues = []
            if missing_keys:
                issues.append(f"Missing keys: {', '.join(sorted(missing_keys))}")
            if extra_keys:
                issues.append(f"Extra keys: {', '.join(sorted(extra_keys))}")
            
            if issues:
                return False, "; ".join(issues)
            
            return True, f"Valid translation file for '{language_name}'"
            
        except Exception as e:
            return False, f"Error validating file: {e}"
    
    def get_translation_stats(self):
        """Get statistics about loaded translations"""
        stats = {}
        english_count = len(self.translations.get("en", {}))
        
        for lang_code, translations in self.translations.items():
            lang_name = self.language_names.get(lang_code, lang_code)
            translation_count = len(translations)
            
            stats[lang_code] = {
                'language_name': lang_name,
                'translation_count': translation_count,
                'completeness': (translation_count / english_count * 100) if english_count > 0 else 0
            }
        
        return stats
