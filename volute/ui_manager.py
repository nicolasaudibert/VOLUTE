"""
UI Manager
Handles the creation and management of the user interface components
"""

import os
from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWidget, QScrollArea,
    QMessageBox, QAction, QFileDialog, QGroupBox, QLabel,
    QTabWidget, QSizePolicy, QSplitter
)
from PyQt5.QtCore import QDir, Qt
from PyQt5.QtGui import QKeySequence
from .about_dialog import AboutDialog
from .canvas import Canvas, CustomNavigationToolbar
from .ui_components import (
    ControlPanels, NavigationControls, ObjectControls, ReferencePointControls,
    ImportedPointControls
)

class UIManager:
    """Manages the user interface components and layout"""

    def __init__(self, main_window, localization, object_manager):
        self.main_window   = main_window
        self.localization  = localization
        self.object_manager = object_manager

        self.canvas  = None
        self.toolbar = None

        # Qt's own translation catalog, reloaded on every language change
        self._qt_translator = None

        # Component managers
        self.control_panels    = ControlPanels(main_window, localization)
        self.navigation_controls = NavigationControls(main_window, localization)
        self.object_controls   = ObjectControls(main_window, localization, object_manager)
        self.ref_point_controls = ReferencePointControls(main_window, localization)
        self.imported_point_controls = ImportedPointControls(main_window, localization)

        # Menu export actions (disabled until masks exist)
        self._export_actions = []
        # Point/mask analysis export — separate list: enabled only when both
        # masks AND imported points exist (stricter condition than the others)
        self._imported_analysis_actions = []

        # Tab widget reference (for language updates)
        self._tab_widget = None

        # Consolidated controls dict
        self.controls = {}

    # ------------------------------------------------------------------
    # Setup entry point
    # ------------------------------------------------------------------

    def setup_ui(self):
        self.install_qt_translator()
        self.main_window.setWindowTitle(self.localization.get_text("window_title"))
        self.main_window.setGeometry(100, 100, 1200, 800)

        self.create_menu_bar()
        self.create_main_layout()
        self.setup_control_panels()

        if hasattr(self.main_window, 'event_manager'):
            self.main_window.event_manager.connect_to_ui(self)

        self.main_window.setFocusPolicy(Qt.StrongFocus)
        self.consolidate_controls()

    # ------------------------------------------------------------------
    # Helper methods
    # ------------------------------------------------------------------

    def _no_folder_hint(self):
        """Compose the 'no folder selected' hint using existing localization keys."""
        return (
            self.localization.get_text("no_folder_selected")
            + "  \u2014  "
            + self.localization.get_text("file")
            + " \u203a "
            + self.localization.get_text("select_folder")
        )

    def update_undo_redo_actions(self):
        hm = self.main_window.history_manager
        if hasattr(self, '_undo_action'):
            self._undo_action.setEnabled(hm.can_undo())
        if hasattr(self, '_redo_action'):
            self._redo_action.setEnabled(hm.can_redo())

    def _clear_points_label_key(self, is_pt):
        multi = len(self.object_manager.selected_object_ids) > 1
        if multi:
            return "clear_points"
        return "clear_point" if is_pt else "clear_all_points"

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------

    def create_menu_bar(self):
        menubar = self.main_window.menuBar()

        # ── File menu ────────────────────────────────────────────────
        file_menu = menubar.addMenu(self.localization.get_text("file"))

        select_folder_action = QAction(
            self.localization.get_text("select_folder"), self.main_window
        )
        select_folder_action.triggered.connect(self.main_window.select_folder)
        select_folder_action.setShortcut(QKeySequence(Qt.CTRL | Qt.Key_D))
        file_menu.addAction(select_folder_action)

        extract_frames_action = QAction(
            self.localization.get_text("video_frames_menu"), self.main_window
        )
        extract_frames_action.triggered.connect(self.main_window.extract_video_frames)
        file_menu.addAction(extract_frames_action)
        file_menu.addSeparator()

        # Export submenu — actions disabled until masks are available
        self._export_actions = []
        export_menu = file_menu.addMenu(self.localization.get_text("export"))

        is_pt = self.main_window.is_point_mode()
        if is_pt:
            export_items = [
                ("export_images_with_tracked_points",
                 self.main_window.export_images_with_tracked_points,
                 Qt.CTRL | Qt.SHIFT | Qt.Key_I),
                ("export_tracked_points",
                 self.main_window.export_tracked_points,
                 Qt.CTRL | Qt.SHIFT | Qt.Key_P),
                ("export_closest_tracked_points",
                 self.main_window.export_closest_tracked_points,
                 Qt.CTRL | Qt.SHIFT | Qt.Key_K),
            ]
        else:
            export_items = [
                ("export_images",       self.main_window.export_masked_images,      Qt.CTRL | Qt.SHIFT | Qt.Key_I),
                ("export_coordinates",  self.main_window.export_mask_coordinates,   Qt.CTRL | Qt.SHIFT | Qt.Key_M),
                ("export_centroids",    self.main_window.export_centroids,          Qt.CTRL | Qt.SHIFT | Qt.Key_T),
                ("export_closest_points", self.main_window.export_closest_mask_points, Qt.CTRL | Qt.SHIFT | Qt.Key_K),
                ("export_hull_coords",    self.main_window.export_hull_coordinates,      Qt.CTRL | Qt.SHIFT | Qt.Key_H),
                ("export_contour_coords", self.main_window.export_contour_coordinates,   Qt.CTRL | Qt.SHIFT | Qt.Key_U),
            ]
        for key, slot, shortcut in export_items:
            action = QAction(self.localization.get_text(key), self.main_window)
            action.triggered.connect(slot)
            action.setEnabled(False)
            action.setShortcut(QKeySequence(shortcut))
            export_menu.addAction(action)
            self._export_actions.append(action)

        if not is_pt:
            analysis_action = QAction(
                self.localization.get_text("export_point_mask_analysis"), self.main_window
            )
            analysis_action.triggered.connect(self.main_window.export_point_mask_analysis)
            analysis_action.setEnabled(False)
            analysis_action.setShortcut(QKeySequence(Qt.CTRL | Qt.SHIFT | Qt.Key_A))
            export_menu.addAction(analysis_action)
            self._imported_analysis_actions.append(analysis_action)

        file_menu.addSeparator()

        # Project data submenu
        project_menu = file_menu.addMenu(self.localization.get_text("project_data"))
        for key, slot, tip, shortcut in [
            ("export_project_data", self.main_window.export_inference_state,
             "Export points, masks, and object data to file",
             Qt.CTRL | Qt.Key_S),
            ("import_project_data", self.main_window.import_inference_state,
             "Import points, masks, and object data from file",
             Qt.CTRL | Qt.Key_O),
        ]:
            a = QAction(self.localization.get_text(key), self.main_window)
            a.triggered.connect(slot)
            a.setStatusTip(tip)
            a.setShortcut(QKeySequence(shortcut))
            project_menu.addAction(a)

        # Import tracked points (SAM2++ point mode export → mask mode session)
        import_tracked_points_action = QAction(
            self.localization.get_text("import_tracked_points"), self.main_window
        )
        import_tracked_points_action.triggered.connect(self.main_window.import_tracked_points)
        import_tracked_points_action.setEnabled(not self.main_window.is_point_mode())
        import_tracked_points_action.setShortcut(QKeySequence(Qt.CTRL | Qt.SHIFT | Qt.Key_J))
        file_menu.addAction(import_tracked_points_action)

        import_mask_action = QAction(
            self.localization.get_text("import_mask"), self.main_window
        )
        import_mask_action.triggered.connect(self.main_window.import_mask)
        import_mask_action.setEnabled(not self.main_window.is_point_mode())
        import_mask_action.setShortcut(QKeySequence(Qt.CTRL | Qt.SHIFT | Qt.Key_G))
        file_menu.addAction(import_mask_action)

        gimp_export_action = QAction(
            self.localization.get_text("gimp_export_frame"), self.main_window
        )
        gimp_export_action.triggered.connect(self.main_window.export_frame_for_gimp)
        gimp_export_action.setEnabled(not self.main_window.is_point_mode())
        gimp_export_action.setShortcut(QKeySequence(Qt.CTRL | Qt.SHIFT | Qt.Key_B))
        file_menu.addAction(gimp_export_action)

        gimp_export_all_action = QAction(
            self.localization.get_text("gimp_export_all_frames"), self.main_window
        )
        gimp_export_all_action.triggered.connect(self.main_window.export_all_frames_for_gimp)
        gimp_export_all_action.setEnabled(not self.main_window.is_point_mode())
        gimp_export_all_action.setShortcut(QKeySequence(Qt.CTRL | Qt.SHIFT | Qt.Key_F))
        file_menu.addAction(gimp_export_all_action)

        # SAM2 inference state submenu
        sam2_menu = file_menu.addMenu(self.localization.get_text("sam2_inference_state"))
        for key, slot, tip in [
            ("export_sam2_state", self.main_window.export_sam2_inference_state,
             "Export SAM2 internal inference state (experimental)"),
            ("import_sam2_state", self.main_window.import_sam2_inference_state,
             "Import SAM2 internal inference state (experimental)"),
        ]:
            a = QAction(self.localization.get_text(key), self.main_window)
            a.triggered.connect(slot)
            a.setStatusTip(tip)
            sam2_menu.addAction(a)

        # Batch processing
        batch_action = QAction(
            self.localization.get_text("batch_processing") + "\u2026", self.main_window
        )
        batch_action.triggered.connect(self.main_window.open_batch_dialog)
        batch_action.setStatusTip("Run SAM2 segmentation on multiple folders")
        file_menu.addAction(batch_action)
        file_menu.addSeparator()

        settings_action = QAction(
            self.localization.get_text("settings_menu"), self.main_window
        )
        settings_action.triggered.connect(self.main_window.open_settings_dialog)
        # NoRole keeps the item in the File menu: macOS would otherwise move an
        # entry it recognizes as preferences into the application menu
        settings_action.setMenuRole(QAction.NoRole)
        file_menu.addAction(settings_action)
        file_menu.addSeparator()

        # ── Edit menu ─────────────────────────────────────────────────
        edit_menu = menubar.addMenu(self.localization.get_text("edit"))

        self._undo_action = QAction(self.localization.get_text("undo"), self.main_window)
        self._undo_action.triggered.connect(self.main_window.history_manager.undo)
        self._undo_action.setShortcut(QKeySequence(Qt.CTRL | Qt.Key_Z))
        self._undo_action.setEnabled(False)
        edit_menu.addAction(self._undo_action)

        self._redo_action = QAction(self.localization.get_text("redo"), self.main_window)
        self._redo_action.triggered.connect(self.main_window.history_manager.redo)
        self._redo_action.setShortcut(QKeySequence(Qt.CTRL | Qt.SHIFT | Qt.Key_Z))
        self._redo_action.setEnabled(False)
        edit_menu.addAction(self._redo_action)

        # ── Language menu ─────────────────────────────────────────────
        language_menu = menubar.addMenu(self.localization.get_text("language"))
        for code, name in self.localization.get_available_languages():
            a = QAction(name, self.main_window)
            a.triggered.connect(lambda checked, lang=code: self.change_language(lang))
            language_menu.addAction(a)

        # ── Help menu ─────────────────────────────────────────────
        help_menu = menubar.addMenu(self.localization.get_text("help"))
        about_action = QAction(self.localization.get_text("about_title"), self.main_window)
        about_action.triggered.connect(
            lambda: AboutDialog(self.localization, self.main_window).exec_()
        )
        about_action.setMenuRole(QAction.NoRole)
        help_menu.addAction(about_action)

    # ------------------------------------------------------------------
    # Main layout
    # ------------------------------------------------------------------

    def create_main_layout(self):
        central_widget = QWidget()
        self.main_window.setCentralWidget(central_widget)
        outer_layout = QHBoxLayout(central_widget)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)
        outer_layout.addWidget(splitter)

        # ── Left: visualization column ────────────────────────────────
        viz_widget = QWidget()
        viz_layout = QVBoxLayout(viz_widget)

        self.title_label = QLabel(self._no_folder_hint())
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet(
            "font-size: 14px; font-weight: bold; padding: 5px;"
            "background-color: rgba(240,240,240,200);"
            "border-radius: 3px; margin: 2px;"
        )
        viz_layout.addWidget(self.title_label)

        self.canvas = Canvas(central_widget)
        viz_layout.addWidget(self.canvas, 9)

        self.toolbar = CustomNavigationToolbar(
            self.canvas, self.main_window,
            debug_mode=self.main_window.debug_mode
        )
        viz_layout.addWidget(self.toolbar)

        nav_widget = self.navigation_controls.create_navigation_bar()
        viz_layout.addWidget(nav_widget)

        splitter.addWidget(viz_widget)

        # ── Right: tabbed control panel ───────────────────────────────
        control_panel = QWidget()
        self.control_layout = QVBoxLayout(control_panel)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(control_panel)
        splitter.addWidget(scroll_area)

        # Only the left (visualization) pane absorbs window-resize deltas; the right
        # (control panel) pane keeps a fixed width until the user drags the handle.
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)

        self.main_layout  = outer_layout
        self.viz_layout   = viz_layout
        self.scroll_area  = scroll_area
        self.splitter     = splitter

    def apply_initial_splitter_sizes(self):
        """Set the initial left/right splitter proportions once the window has been
        shown (widget size hints are unreliable before that). The right pane is sized
        to fit its content without horizontal scrolling; the left pane takes the rest.
        Must be called once, after main_window.show()."""
        if not hasattr(self, 'splitter'):
            return
        control_panel = self.scroll_area.widget()
        right_width = control_panel.sizeHint().width() + self.scroll_area.verticalScrollBar().sizeHint().width() + 20
        total_width = self.main_window.width()
        left_width = max(total_width - right_width, 200)
        self.splitter.setSizes([left_width, right_width])

    # ------------------------------------------------------------------
    # Control panels (tabbed)
    # ------------------------------------------------------------------

    def setup_control_panels(self):
        tab = QTabWidget()
        self._tab_widget = tab
        is_pt = self.main_window.is_point_mode()

        # ── Tab 1: Objects / Points Definition ────────────────────────
        tab1 = QWidget()
        t1 = QVBoxLayout(tab1)
        points_panel = self.control_panels.create_points_panel()  # None in point mode
        if points_panel is not None:
            t1.addWidget(points_panel)
        t1.addWidget(self.object_controls.create_objects_panel())
        t1.addWidget(self.object_controls.create_object_config_panel())
        t1.addStretch()
        tab.addTab(tab1, self.localization.get_text(
            "tab_points_definition" if is_pt else "tab_objects_definition"))

        # ── Tab 2: Reference Points ───────────────────────────────────
        tab2 = QWidget()
        t2 = QVBoxLayout(tab2)
        t2.addWidget(self.ref_point_controls.create_ref_points_panel())
        t2.addStretch()
        tab.addTab(tab2, self.localization.get_text("tab_ref_points"))

        # ── Tab 3: Prediction ─────────────────────────────────────────
        tab3 = QWidget()
        t3 = QVBoxLayout(tab3)
        t3.addWidget(self.control_panels.create_prediction_panel())
        for opt_layout in self.control_panels.create_display_options():
            t3.addLayout(opt_layout)
        if is_pt:
            t3.addWidget(self.control_panels.create_tracked_point_display_panel())
        else:
            t3.addWidget(self.object_controls.create_centroid_panel())
            t3.addWidget(self.object_controls.create_contours_panel())
            t3.addWidget(self.imported_point_controls.create_imported_points_panel())
        t3.addStretch()
        tab.addTab(tab3, self.localization.get_text("tab_prediction"))

        # Track the active tab so canvas click behavior can be gated accordingly
        tab.currentChanged.connect(self.main_window.on_active_tab_changed)

        self.control_layout.addWidget(tab)

    # ------------------------------------------------------------------
    # Controls consolidation
    # ------------------------------------------------------------------

    def consolidate_controls(self):
        self.controls.update(self.control_panels.get_controls())
        self.controls.update(self.navigation_controls.get_controls())
        self.controls.update(self.object_controls.get_controls())
        self.controls.update(self.ref_point_controls.get_controls())
        self.controls.update(self.imported_point_controls.get_controls())

    # ------------------------------------------------------------------
    # Export enable / disable
    # ------------------------------------------------------------------

    def set_export_enabled(self, enabled: bool):
        """Enable or disable all export menu actions."""
        for action in self._export_actions:
            action.setEnabled(enabled)

    def set_imported_analysis_enabled(self, enabled: bool):
        """Enable or disable the point/mask analysis export action."""
        for action in self._imported_analysis_actions:
            action.setEnabled(enabled)

    def refresh_export_state(self):
        """Enable exports if any masks or tracked points exist."""
        try:
            om = self.main_window.object_manager
            has_masks = bool(om.object_masks and any(om.object_masks.values()))
            has_tracks = bool(
                om.object_tracked_points and any(om.object_tracked_points.values())
            )
        except Exception:
            has_masks = has_tracks = False
        self.set_export_enabled(has_masks or has_tracks)

        ipm = getattr(self.main_window, 'imported_point_manager', None)
        has_imported = bool(ipm and ipm.imported_points and any(ipm.imported_points.values()))
        self.set_imported_analysis_enabled(has_masks and has_imported)

    # ------------------------------------------------------------------
    # Language / text updates
    # ------------------------------------------------------------------

    def update_ref_points_list(self):
        self.ref_point_controls._refresh_list()

    def update_imported_points_list(self):
        self.imported_point_controls._refresh_list()

    def change_language(self, language):
        self.localization.set_language(language)
        self.install_qt_translator()
        self.update_ui_texts()

    def install_qt_translator(self):
        """Load Qt's own translations for the current language, so the widgets Qt
        provides itself — non-native file dialogs, standard buttons — follow the
        application language instead of staying in English.

        On macOS the *native* file dialog is drawn by the system and follows the
        system language, not this one."""
        from PyQt5.QtCore import QTranslator, QLibraryInfo, QCoreApplication
        app = QCoreApplication.instance()
        if app is None:
            return
        if self._qt_translator is not None:
            app.removeTranslator(self._qt_translator)
            self._qt_translator = None
        translator = QTranslator()
        if translator.load(f"qt_{self.localization.current_language}",
                           QLibraryInfo.location(QLibraryInfo.TranslationsPath)):
            app.installTranslator(translator)
            self._qt_translator = translator

    def update_ui_texts(self):
        checkpoint_path = getattr(self.main_window, '_last_checkpoint_path', None)
        if checkpoint_path:
            self.main_window.update_window_title(checkpoint_path)
        else:
            self.main_window.setWindowTitle(self.localization.get_text("window_title"))

        is_pt = self.main_window.is_point_mode()
        control_updates = {
            'clear_points_btn':             self._clear_points_label_key(is_pt),
            'add_object_btn':               'add_point_btn' if is_pt else 'add_object',
            'remove_object_btn':            'remove_point_btn' if is_pt else 'remove_object',
            'import_objects_btn':           'import_names_btn',
            'remove_box_btn':               'remove_box_btn',
            'predict_current_btn':          'predict_points' if is_pt else 'predict_current',
            'propagate_btn':                'propagate_points' if is_pt else 'propagate_masks',
            'repropagate_btn':              'repropagate_from_frame',
            'prev_btn':                     'previous',
            'next_btn':                     'next',
            'add_ref_point_btn':            'add_ref_point_btn',
            'remove_ref_point_btn':         'remove_ref_point_btn',
            'remove_ref_point_frame_btn':   'remove_ref_point_frame_btn',
            'import_ref_points_btn':        'import_names_btn',
        }
        for ctrl_name, text_key in control_updates.items():
            if ctrl_name in self.controls:
                self.controls[ctrl_name].setText(self.localization.get_text(text_key))

        if 'add_points_radio' in self.controls:
            self.controls['add_points_radio'].setText(
                self.localization.get_text("add_points"))
            self.controls['add_points_radio'].setToolTip(
                self.localization.get_text("add_points_tooltip"))
        if 'remove_points_radio' in self.controls:
            self.controls['remove_points_radio'].setText(
                self.localization.get_text("remove_points"))
            self.controls['remove_points_radio'].setToolTip(
                self.localization.get_text("remove_points_tooltip"))
        if 'define_box_radio' in self.controls:
            self.controls['define_box_radio'].setText(
                self.localization.get_text("define_box"))
            self.controls['define_box_radio'].setToolTip(
                self.localization.get_text("define_box_tooltip"))

        if self._tab_widget:
            self._tab_widget.setTabText(
                0, self.localization.get_text(
                    "tab_points_definition" if is_pt else "tab_objects_definition"))
            self._tab_widget.setTabText(
                1, self.localization.get_text("tab_ref_points"))
            self._tab_widget.setTabText(
                2, self.localization.get_text("tab_prediction"))

        # Combo items are not covered by the QLabel/QGroupBox reverse mapping
        # below, so they are relabeled explicitly
        from .ui_components.control_panels import BOX_CLIPPING_MODE_ITEMS
        from .ui_components.reference_point_controls import (
            REF_POINT_EXTRAPOLATION_ITEMS, REF_POINT_INTERPOLATION_ITEMS,
        )
        for ctrl_name, items in (
            ('box_clipping_mode_combo',        BOX_CLIPPING_MODE_ITEMS),
            ('ref_point_extrapolation_combo',  REF_POINT_EXTRAPOLATION_ITEMS),
            ('ref_point_interpolation_combo',  REF_POINT_INTERPOLATION_ITEMS),
        ):
            combo = self.controls.get(ctrl_name)
            if not combo:
                continue
            combo.blockSignals(True)
            for index, (_, text_key) in enumerate(items):
                combo.setItemText(index, self.localization.get_text(text_key))
            combo.blockSignals(False)

        from .ui_components.object_controls import relabel_marker_combo
        for ctrl_name in ('obj_marker_combo', 'ref_point_marker_combo',
                          'imported_point_marker_combo', 'tracked_point_style_combo'):
            combo = self.controls.get(ctrl_name)
            if combo:
                relabel_marker_combo(combo, self.localization)

        if 'contours_subtab' in self.controls:
            self.controls['contours_subtab'].setTabText(
                0, self.localization.get_text("tab_outer_contour"))
            self.controls['contours_subtab'].setTabText(
                1, self.localization.get_text("tab_convex_hull"))

        self._update_translatable_elements()
        self._update_default_object_names()

        if 'objects_list' in self.controls:
            self.controls['objects_list'].clear()
            key = "point" if self.object_manager.point_mode else "object"
            for obj_id in sorted(self.object_manager.object_colors.keys()):
                obj_name = self.object_manager.object_names.get(
                    obj_id, f"{self.localization.get_text(key)} {obj_id}")
                self.controls['objects_list'].addItem(obj_name)
            obj_ids = sorted(self.object_manager.object_colors.keys())
            if self.object_manager.current_object_id in obj_ids:
                idx = obj_ids.index(self.object_manager.current_object_id)
                self.controls['objects_list'].setCurrentRow(idx)

        if 'obj_name_edit' in self.controls:
            obj_id = self.object_manager.current_object_id
            name = self.object_manager.object_names.get(
                obj_id, f"{self.localization.get_text(key)} {obj_id}")
            self.controls['obj_name_edit'].setText(name)

        if hasattr(self, 'ref_point_controls'):
            self.ref_point_controls.update_ref_point_ui()

        self.main_window.menuBar().clear()
        self.create_menu_bar()
        self.update_undo_redo_actions()
        self.main_window.update()
        
        im = getattr(self.main_window, 'image_manager', None)
        if im and not im.has_images():
            self.title_label.setText(self._no_folder_hint())

    def _update_translatable_elements(self):
        from PyQt5.QtWidgets import QGroupBox
        reverse = self._create_reverse_translation_mapping()
        for gb in self.main_window.findChildren(QGroupBox):
            key = reverse.get(gb.title())
            if key:
                gb.setTitle(self.localization.get_text(key))
        for lbl in self.main_window.findChildren(QLabel):
            key = reverse.get(lbl.text())
            if key:
                lbl.setText(self.localization.get_text(key))

    def _create_reverse_translation_mapping(self):
        rev = {}
        for translations in self.localization.translations.values():
            for key, text in translations.items():
                rev[text] = key
        return rev

    def _update_default_object_names(self):
        key = "point" if self.object_manager.point_mode else "object"
        current_word = self.localization.get_text(key)
        obj_words = {t.get(key, current_word)
                     for t in self.localization.translations.values()}
        for obj_id, name in self.object_manager.object_names.items():
            if any(name == f"{w} {obj_id}" for w in obj_words):
                self.object_manager.object_names[obj_id] = f"{current_word} {obj_id}"

    # ------------------------------------------------------------------
    # Delegated UI helpers
    # ------------------------------------------------------------------

    def update_object_ui(self):
        self.object_controls.update_object_ui()

    def update_navigation_controls(self, current_idx, total_images):
        self.navigation_controls.update_navigation_controls(current_idx, total_images)

    def enable_navigation(self, enabled=True):
        self.navigation_controls.enable_navigation(enabled)

    def update_objects_list(self):
        self.object_controls.update_objects_list()

    def get_control(self, name):
        return self.controls.get(name)

    def set_folder_label(self, folder_path):
        """No-op: folder info is shown in the title label by DisplayManager."""
        pass

    def show_message(self, message_type, title, message):
        if message_type == "warning":
            QMessageBox.warning(self.main_window, title, message)
        elif message_type == "error":
            QMessageBox.critical(self.main_window, title, message)
        elif message_type == "info":
            QMessageBox.information(self.main_window, title, message)
        elif message_type == "question":
            from .dialogs import localized_question
            return localized_question(self.main_window, self.localization, title, message)
        return None

    def show_file_dialog(self, dialog_type, title, default_path="", file_filter=""):
        if dialog_type == "save":
            return QFileDialog.getSaveFileName(
                self.main_window, title, default_path, file_filter)
        elif dialog_type == "open":
            return QFileDialog.getOpenFileName(
                self.main_window, title, default_path, file_filter)
        elif dialog_type == "folder":
            return QFileDialog.getExistingDirectory(
                self.main_window, title, default_path)
        return None, None

    def show_status(self, message, timeout=0):
        """Show a message in the main window status bar (timeout ms; 0 = permanent)."""
        self.main_window.statusBar().showMessage(message, timeout)

    def clear_status(self):
        """Clear the status bar message."""
        self.main_window.statusBar().clearMessage()

    def cleanup(self):
        try:
            if self.canvas:
                self.canvas.clear_display()
            self.controls.clear()
            if self.main_window.debug_mode:
                print("UI Manager cleanup completed")
        except Exception as e:
            if self.main_window.debug_mode:
                print(f"Error during UI cleanup: {e}")
