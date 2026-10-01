"""
Object Controls
Object management and configuration controls
"""

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox,
    QSlider, QLineEdit, QCheckBox, QGroupBox, QListWidget,
    QFileDialog, QMessageBox, QStyleFactory, QTabWidget,
    QWidget, QAbstractItemView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QBrush
from ..dialogs import localized_question
from ..file_utils import build_file_filter

# Matplotlib marker codes offered by the style combos, with the translation key
# naming each shape. Items read "<symbol> — <name>" so the symbol stays visible,
# and carry the code itself as item data.
MARKER_STYLE_KEYS = {
    'o': 'marker_style_circle',
    's': 'marker_style_square',
    '^': 'marker_style_triangle',
    'D': 'marker_style_diamond',
    '*': 'marker_style_star',
    'x': 'marker_style_cross',
    '+': 'marker_style_plus',
    'P': 'marker_style_plus_filled',
    'X': 'marker_style_cross_filled',
}


def marker_style_label(localization, code):
    """Combo label for a marker code: the symbol, then its localized name."""
    return f"{code} — {localization.get_text(MARKER_STYLE_KEYS[code])}"


def fill_marker_combo(combo, localization, codes):
    """Populate a marker style combo, each item carrying its code as data."""
    combo.clear()
    for code in codes:
        combo.addItem(marker_style_label(localization, code), code)


def relabel_marker_combo(combo, localization):
    """Refresh an already populated marker combo after a language change."""
    combo.blockSignals(True)
    for index in range(combo.count()):
        combo.setItemText(index, marker_style_label(localization, combo.itemData(index)))
    combo.blockSignals(False)


class _NameLineEdit(QLineEdit):
    """QLineEdit that remembers the text it had when it gained focus, for undo history."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.focus_in_text = ""

    def focusInEvent(self, event):
        self.focus_in_text = self.text()
        super().focusInEvent(event)

class _FusionSlider(QSlider):
    """QSlider using the cross-platform Fusion style.

    On macOS, QMacStyle repaints all sliders in a window whenever any one
    of them is interacted with (global "active control" tracking), causing
    spurious visual thumb displacement on uninvolved sliders.  Forcing the
    Fusion style on each slider makes Qt render it independently, which
    eliminates the artefact without affecting the rest of the UI.

    Wheel events are also suppressed unless the slider explicitly owns focus,
    preventing accidental value changes when scrolling the parent QScrollArea.
    """

    _fusion_style = None  # Shared instance — created once

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if _FusionSlider._fusion_style is None:
            _FusionSlider._fusion_style = QStyleFactory.create("Fusion")
        if _FusionSlider._fusion_style is not None:
            self.setStyle(_FusionSlider._fusion_style)

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class ObjectControls:
    """Creates object management and configuration controls"""

    def __init__(self, main_window, localization, object_manager):
        self.main_window    = main_window
        self.localization   = localization
        self.object_manager = object_manager
        self.controls       = {}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _mixed_pixmap(self, size=20):
        """Diagonal-hatch pattern used to indicate a mixed value across a multi-selection."""
        pix = QPixmap(size, size)
        pix.fill(Qt.white)
        painter = QPainter(pix)
        painter.setBrush(QBrush(Qt.darkGray, Qt.BDiagPattern))
        painter.setPen(Qt.NoPen)
        painter.drawRect(0, 0, size, size)
        painter.end()
        return pix

    def _set_color_button(self, btn, color):
        """Show a single actual color on a color-picker button."""
        btn.setIcon(QIcon())
        btn.setStyleSheet(f"background-color: {color.name()};")

    def _set_color_button_mixed(self, btn):
        """Show the mixed-value hatch pattern on a color-picker button."""
        btn.setStyleSheet("background-color: white;")
        pix = self._mixed_pixmap()
        btn.setIcon(QIcon(pix))
        btn.setIconSize(pix.size())

    _MIXED_SLIDER_STYLESHEET = (
        "QSlider::sub-page:horizontal { background: #999999; }"
        "QSlider::handle:horizontal { background: #999999; border: 1px solid #666666;"
        " width: 12px; margin: -4px 0; border-radius: 6px; }"
    )

    def _set_slider_mixed(self, slider, mixed):
        """Recolor the slider's filled track and handle to grey when the underlying
        selection has mixed values, reverting to the default style otherwise."""
        slider.setStyleSheet(self._MIXED_SLIDER_STYLESHEET if mixed else "")

    # ------------------------------------------------------------------
    # Panel construction
    # ------------------------------------------------------------------

    def create_objects_panel(self):
        """Create objects management panel"""
        is_pt = self.main_window.is_point_mode()
        objects_group = QGroupBox(self.localization.get_text(
            "point_management" if is_pt else "object_management"))
        objects_layout = QVBoxLayout()
        objects_group.setLayout(objects_layout)

        objects_layout.addWidget(QLabel(self.localization.get_text(
            "points_list" if is_pt else "object_list")))

        self.controls['objects_list'] = QListWidget()
        self.controls['objects_list'].setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.controls['objects_list'].addItem(self.localization.get_text(
            "point" if is_pt else "object") + " 1")
        self.controls['objects_list'].setCurrentRow(0)
        self.controls['objects_list'].itemSelectionChanged.connect(
            self.main_window.on_objects_selection_changed
        )
        objects_layout.addWidget(self.controls['objects_list'])

        btn_row = QHBoxLayout()
        self.controls['add_object_btn'] = QPushButton(self.localization.get_text(
            "add_point_btn" if is_pt else "add_object"))
        self.controls['add_object_btn'].clicked.connect(self.main_window.add_new_object)
        btn_row.addWidget(self.controls['add_object_btn'])

        self.controls['remove_object_btn'] = QPushButton(self.localization.get_text(
            "remove_point_btn" if is_pt else "remove_object"))
        self.controls['remove_object_btn'].clicked.connect(self.main_window.remove_current_object)
        btn_row.addWidget(self.controls['remove_object_btn'])
        objects_layout.addLayout(btn_row)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel(self.localization.get_text(
            "point_name" if is_pt else "object_name")))
        self.controls['obj_name_edit'] = _NameLineEdit()
        self.controls['obj_name_edit'].textChanged.connect(self.main_window.update_object_name)
        self.controls['obj_name_edit'].editingFinished.connect(
            self.main_window.commit_object_name_history)
        name_row.addWidget(self.controls['obj_name_edit'])
        objects_layout.addLayout(name_row)

        self.controls['import_objects_btn'] = QPushButton(
            self.localization.get_text("import_names_btn")
        )
        self.controls['import_objects_btn'].clicked.connect(self._import_from_txt)
        objects_layout.addWidget(self.controls['import_objects_btn'])

        # Global show points toggle
        pts_row = QHBoxLayout()
        pts_row.addWidget(QLabel(self.localization.get_text(
            "show_current_point" if is_pt else "show_points_global")))
        self.controls['show_points_global_checkbox'] = QCheckBox()
        self.controls['show_points_global_checkbox'].setChecked(True)
        self.controls['show_points_global_checkbox'].stateChanged.connect(
            self.main_window.toggle_global_points_visibility
        )
        pts_row.addWidget(self.controls['show_points_global_checkbox'])
        objects_layout.addLayout(pts_row)

        if is_pt:
            multi = len(self.object_manager.selected_object_ids) > 1
            self.controls['clear_points_btn'] = QPushButton(
                self.localization.get_text("clear_points" if multi else "clear_point"))
            self.controls['clear_points_btn'].clicked.connect(self.main_window.clear_points)
            objects_layout.addWidget(self.controls['clear_points_btn'])

        return objects_group

    def create_object_config_panel(self):
        """Create current object configuration panel"""
        is_pt = self.main_window.is_point_mode()
        object_config_group = QGroupBox(self.localization.get_text(
            "current_point_config" if is_pt else "current_object_config"))
        object_config_layout = QVBoxLayout()
        object_config_group.setLayout(object_config_layout)

        self.setup_color_controls(object_config_layout)
        self.setup_marker_controls(object_config_layout)
        self.setup_opacity_controls(object_config_layout)

        return object_config_group

    def setup_color_controls(self, parent_layout):
        """Setup color selection controls"""
        is_pt = self.main_window.is_point_mode()
        rows = [
            ("point_color" if is_pt else "positive_points_color",
             'obj_pos_color_btn', "green", "positive"),
            ("tracked_point_color" if is_pt else "mask_color",
             'obj_mask_color_btn', "blue", "mask"),
        ]
        if not is_pt:
            rows.insert(1, ("negative_points_color", 'obj_neg_color_btn', "red", "negative"))

        for label_key, btn_key, default_color, color_type in rows:
            row = QHBoxLayout()
            row.addWidget(QLabel(self.localization.get_text(label_key)))
            btn = QPushButton("")
            btn.setStyleSheet(f"background-color: {default_color};")
            btn.clicked.connect(
                lambda checked, ct=color_type: self.main_window.choose_object_color(ct)
            )
            self.controls[btn_key] = btn
            row.addWidget(btn)
            parent_layout.addLayout(row)

    def setup_marker_controls(self, parent_layout):
        """Setup marker style and size controls"""
        row = QHBoxLayout()
        row.addWidget(QLabel(self.localization.get_text("marker_style")))
        self.controls['obj_marker_combo'] = QComboBox()
        fill_marker_combo(self.controls['obj_marker_combo'], self.localization,
                          ['o', 's', '^', 'D', '*', 'x', '+'])
        self.controls['obj_marker_combo'].currentIndexChanged.connect(
            self.main_window.update_object_marker_style
        )
        row.addWidget(self.controls['obj_marker_combo'])
        parent_layout.addLayout(row)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel(self.localization.get_text("marker_size")))
        self.controls['obj_marker_size_slider'] = _FusionSlider(Qt.Horizontal)
        self.controls['obj_marker_size_slider'].setRange(1, 50)
        self.controls['obj_marker_size_slider'].setValue(5)
        self.controls['obj_marker_size_value_label'] = QLabel("5")
        self.controls['obj_marker_size_slider'].valueChanged.connect(
            self.main_window.update_object_marker_size
        )
        self.controls['obj_marker_size_slider'].valueChanged.connect(
            lambda v: self.controls['obj_marker_size_value_label'].setText(str(v))
        )
        size_row.addWidget(self.controls['obj_marker_size_slider'])
        size_row.addWidget(self.controls['obj_marker_size_value_label'])
        parent_layout.addLayout(size_row)

    def setup_opacity_controls(self, parent_layout):
        """Setup opacity controls"""
        if self.main_window.is_point_mode():
            return
        row = QHBoxLayout()
        row.addWidget(QLabel(self.localization.get_text("mask_opacity")))
        self.controls['obj_mask_opacity_slider'] = _FusionSlider(Qt.Horizontal)
        self.controls['obj_mask_opacity_slider'].setRange(0, 100)
        self.controls['obj_mask_opacity_slider'].setValue(50)
        self.controls['obj_mask_opacity_value_label'] = QLabel("50")
        self.controls['obj_mask_opacity_slider'].valueChanged.connect(
            self.main_window.update_object_mask_opacity
        )
        self.controls['obj_mask_opacity_slider'].valueChanged.connect(
            lambda v: self.controls['obj_mask_opacity_value_label'].setText(str(v))
        )
        row.addWidget(self.controls['obj_mask_opacity_slider'])
        row.addWidget(self.controls['obj_mask_opacity_value_label'])
        parent_layout.addLayout(row)

    def create_centroid_panel(self):
        """Create centroid configuration panel"""
        centroid_group = QGroupBox(self.localization.get_text("centroid_config"))
        centroid_layout = QVBoxLayout()
        centroid_group.setLayout(centroid_layout)

        row = QHBoxLayout()
        row.addWidget(QLabel(self.localization.get_text("show_centroids")))
        self.controls['show_centroids_checkbox'] = QCheckBox()
        self.controls['show_centroids_checkbox'].setChecked(False)
        self.controls['show_centroids_checkbox'].stateChanged.connect(
            self.main_window.toggle_centroids_display
        )
        row.addWidget(self.controls['show_centroids_checkbox'])
        centroid_layout.addLayout(row)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel(self.localization.get_text("centroid_color")))
        self.controls['centroid_color_btn'] = QPushButton("")
        self.controls['centroid_color_btn'].setStyleSheet("background-color: white;")
        self.controls['centroid_color_btn'].clicked.connect(self.main_window.choose_centroid_color)
        color_row.addWidget(self.controls['centroid_color_btn'])
        centroid_layout.addLayout(color_row)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel(self.localization.get_text("centroid_size")))
        self.controls['centroid_size_slider'] = _FusionSlider(Qt.Horizontal)
        self.controls['centroid_size_slider'].setRange(3, 30)
        self.controls['centroid_size_slider'].setValue(10)
        self.controls['centroid_size_slider'].valueChanged.connect(
            self.main_window.update_centroid_size
        )
        self.controls['centroid_size_value_label'] = QLabel("10")
        self.controls['centroid_size_slider'].valueChanged.connect(
            lambda v: self.controls['centroid_size_value_label'].setText(str(v))
        )
        size_row.addWidget(self.controls['centroid_size_slider'])
        size_row.addWidget(self.controls['centroid_size_value_label'])
        centroid_layout.addLayout(size_row)

        return centroid_group

    def create_contours_panel(self):
        """Create unified Mask Contours panel with Outer Contour and Convex Hull sub-tabs."""
        outer_group = QGroupBox(self.localization.get_text("mask_contours_config"))
        outer_layout = QVBoxLayout(outer_group)

        inner_tab = QTabWidget()
        self.controls['contours_subtab'] = inner_tab

        # ------ Sub-tab A: Outer Contour --------------------------------
        tab_a = QWidget()
        ta = QVBoxLayout(tab_a)

        row = QHBoxLayout()
        row.addWidget(QLabel(self.localization.get_text("show_contours")))
        self.controls['show_contours_checkbox'] = QCheckBox()
        self.controls['show_contours_checkbox'].setChecked(False)
        self.controls['show_contours_checkbox'].stateChanged.connect(
            self.main_window.toggle_contours_display
        )
        row.addWidget(self.controls['show_contours_checkbox'])
        ta.addLayout(row)

        smooth_row = QHBoxLayout()
        smooth_row.addWidget(QLabel(self.localization.get_text("contour_smoothing")))
        self.controls['contour_smoothing_slider'] = _FusionSlider(Qt.Horizontal)
        self.controls['contour_smoothing_slider'].setRange(0, 100)
        self.controls['contour_smoothing_slider'].setValue(0)
        self.controls['contour_smoothing_value_label'] = QLabel("0")
        self.controls['contour_smoothing_slider'].valueChanged.connect(
            lambda v: self.controls['contour_smoothing_value_label'].setText(str(v))
        )
        self.controls['contour_smoothing_slider'].sliderReleased.connect(
            self.main_window.update_contour_smoothing
        )
        smooth_row.addWidget(self.controls['contour_smoothing_slider'])
        smooth_row.addWidget(self.controls['contour_smoothing_value_label'])
        ta.addLayout(smooth_row)

        lw_row = QHBoxLayout()
        lw_row.addWidget(QLabel(self.localization.get_text("contour_line_width")))
        self.controls['contour_line_width_slider'] = _FusionSlider(Qt.Horizontal)
        self.controls['contour_line_width_slider'].setRange(1, 10)
        self.controls['contour_line_width_slider'].setValue(2)
        self.controls['contour_line_width_slider'].valueChanged.connect(
            self.main_window.update_contour_line_width
        )
        self.controls['contour_line_width_value_label'] = QLabel("2")
        self.controls['contour_line_width_slider'].valueChanged.connect(
            lambda v: self.controls['contour_line_width_value_label'].setText(str(v))
        )
        lw_row.addWidget(self.controls['contour_line_width_slider'])
        lw_row.addWidget(self.controls['contour_line_width_value_label'])
        ta.addLayout(lw_row)

        outline_row = QHBoxLayout()
        outline_row.addWidget(QLabel(self.localization.get_text("contour_outline")))
        self.controls['contour_outline_checkbox'] = QCheckBox()
        self.controls['contour_outline_checkbox'].setChecked(False)
        self.controls['contour_outline_checkbox'].stateChanged.connect(
            self.main_window.toggle_contour_outline
        )
        outline_row.addWidget(self.controls['contour_outline_checkbox'])
        ta.addLayout(outline_row)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel(self.localization.get_text("contour_outline_color")))
        self.controls['contour_outline_color_btn'] = QPushButton("")
        self.controls['contour_outline_color_btn'].setStyleSheet("background-color: white;")
        self.controls['contour_outline_color_btn'].clicked.connect(
            self.main_window.choose_contour_outline_color
        )
        color_row.addWidget(self.controls['contour_outline_color_btn'])
        ta.addLayout(color_row)

        ta.addStretch()
        inner_tab.addTab(tab_a, self.localization.get_text("tab_outer_contour"))

        # ------ Sub-tab B: Convex Hull (moved from create_hull_panel) ---
        tab_b = QWidget()
        tb = QVBoxLayout(tab_b)

        row = QHBoxLayout()
        row.addWidget(QLabel(self.localization.get_text("show_hulls")))
        self.controls['show_hulls_checkbox'] = QCheckBox()
        self.controls['show_hulls_checkbox'].setChecked(False)
        self.controls['show_hulls_checkbox'].stateChanged.connect(
            self.main_window.toggle_hulls_display
        )
        row.addWidget(self.controls['show_hulls_checkbox'])
        tb.addLayout(row)

        smooth_row = QHBoxLayout()
        smooth_row.addWidget(QLabel(self.localization.get_text("hull_smoothing")))
        self.controls['hull_smoothing_slider'] = _FusionSlider(Qt.Horizontal)
        self.controls['hull_smoothing_slider'].setRange(0, 100)
        self.controls['hull_smoothing_slider'].setValue(0)
        self.controls['hull_smoothing_value_label'] = QLabel("0")
        self.controls['hull_smoothing_slider'].valueChanged.connect(
            lambda v: self.controls['hull_smoothing_value_label'].setText(str(v))
        )
        self.controls['hull_smoothing_slider'].sliderReleased.connect(
            self.main_window.update_hull_smoothing
        )
        smooth_row.addWidget(self.controls['hull_smoothing_slider'])
        smooth_row.addWidget(self.controls['hull_smoothing_value_label'])
        tb.addLayout(smooth_row)

        lw_row = QHBoxLayout()
        lw_row.addWidget(QLabel(self.localization.get_text("hull_line_width")))
        self.controls['hull_line_width_slider'] = _FusionSlider(Qt.Horizontal)
        self.controls['hull_line_width_slider'].setRange(1, 10)
        self.controls['hull_line_width_slider'].setValue(2)
        self.controls['hull_line_width_slider'].valueChanged.connect(
            self.main_window.update_hull_line_width
        )
        self.controls['hull_line_width_value_label'] = QLabel("2")
        self.controls['hull_line_width_slider'].valueChanged.connect(
            lambda v: self.controls['hull_line_width_value_label'].setText(str(v))
        )
        lw_row.addWidget(self.controls['hull_line_width_slider'])
        lw_row.addWidget(self.controls['hull_line_width_value_label'])
        tb.addLayout(lw_row)

        outline_row = QHBoxLayout()
        outline_row.addWidget(QLabel(self.localization.get_text("hull_outline")))
        self.controls['hull_outline_checkbox'] = QCheckBox()
        self.controls['hull_outline_checkbox'].setChecked(False)
        self.controls['hull_outline_checkbox'].stateChanged.connect(
            self.main_window.toggle_hull_outline
        )
        outline_row.addWidget(self.controls['hull_outline_checkbox'])
        tb.addLayout(outline_row)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel(self.localization.get_text("hull_outline_color")))
        self.controls['hull_outline_color_btn'] = QPushButton("")
        self.controls['hull_outline_color_btn'].setStyleSheet("background-color: white;")
        self.controls['hull_outline_color_btn'].clicked.connect(
            self.main_window.choose_hull_outline_color
        )
        color_row.addWidget(self.controls['hull_outline_color_btn'])
        tb.addLayout(color_row)

        tb.addStretch()
        inner_tab.addTab(tab_b, self.localization.get_text("tab_convex_hull"))

        outer_layout.addWidget(inner_tab)
        return outer_group

    # ------------------------------------------------------------------
    # Import from .txt
    # ------------------------------------------------------------------

    def _is_default_state(self):
        """
        Return True when only the default empty Object 1 exists
        (no user-added objects and no points defined on any frame).
        """
        om = self.object_manager
        ids = list(om.object_colors.keys())
        if ids != [1]:
            return False
        frames = om.object_points.get(1, {})
        return not any(
            pts.get('positive') or pts.get('negative')
            for pts in frames.values()
        )

    def _cross_name_conflicts(self, names):
        """Return names that also appear among reference point names."""
        rpm = getattr(self.main_window, 'ref_point_manager', None)
        if not rpm:
            return []
        ref_names = set(rpm.reference_points.keys())
        return [n for n in names if n in ref_names]

    def _warn_cross_names(self, conflicts):
        """Show non-blocking warning about names shared with reference points."""
        txt = "\n".join(conflicts[:10])
        if len(conflicts) > 10:
            txt += f"\n({len(conflicts) - 10} more\u2026)"
        self.main_window.ui_manager.show_message(
            "warning",
            self.localization.get_text("import_cross_names_title"),
            self.localization.get_text("import_cross_names_msg", txt),
        )

    def _import_from_txt(self):
        path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            self.localization.get_text("import_names_btn"),
            "",
            build_file_filter(self.localization, 'txt', 'all')
        )
        if not path:
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                imported = [ln.strip() for ln in f if ln.strip()]
        except Exception as e:
            self.main_window.ui_manager.show_message("error", "", str(e))
            return

        if not imported:
            return

        om = self.object_manager
        overwrite = False

        if self._is_default_state():
            overwrite = True
        else:
            reply = localized_question(
                self.main_window,
                self.localization,
                self.localization.get_text("import_names_btn"),
                self.localization.get_text(
                    "import_names_overwrite_msg",
                    self.localization.get_text("objects")
                ),
            )
            overwrite = (reply == QMessageBox.Yes)

        if overwrite:
            final = list(imported)
        else:
            existing_names = set(om.object_names.values())
            duplicates = [n for n in imported if n in existing_names]
            non_dup    = [n for n in imported if n not in existing_names]

            if duplicates:
                dup_txt = "\n".join(duplicates[:10])
                if len(duplicates) > 10:
                    dup_txt += f"\n({len(duplicates) - 10} more\u2026)"
                reply = localized_question(
                    self.main_window,
                    self.localization,
                    self.localization.get_text("import_names_duplicates_title"),
                    self.localization.get_text("import_names_duplicates_msg", dup_txt),
                )
                if reply == QMessageBox.Yes:
                    all_names = existing_names | set(non_dup)
                    renamed = []
                    for n in duplicates:
                        sfx = 2
                        cand = f"{n} ({sfx})"
                        while cand in all_names:
                            sfx += 1
                            cand = f"{n} ({sfx})"
                        renamed.append(cand)
                        all_names.add(cand)
                    final = non_dup + renamed
                else:
                    final = non_dup
            else:
                final = non_dup

        if not final:
            return

        conflicts = self._cross_name_conflicts(final)
        if conflicts:
            self._warn_cross_names(conflicts)

        if overwrite:
            om.clear_all_data()
            om.object_names[1] = final[0]
            om.current_object_id = 1
            for name in final[1:]:
                new_id = om.add_new_object()
                om.object_names[new_id] = name
        else:
            for name in final:
                new_id = om.add_new_object()
                om.object_names[new_id] = name

        self.update_objects_list()
        self.main_window.ui_manager.update_object_ui()

    # ------------------------------------------------------------------
    # UI updates
    # ------------------------------------------------------------------

    def update_object_ui(self):
        """Update UI based on selected object(s) properties, showing a mixed-value
        indicator when a property differs across the current multi-selection."""
        om = self.object_manager
        obj_id = om.current_object_id
        if obj_id not in om.object_colors:
            return

        is_pt = self.main_window.is_point_mode()
        selected = sorted(om.selected_object_ids)
        multi = len(selected) > 1

        color_btns = [('obj_pos_color_btn', 'positive'), ('obj_mask_color_btn', 'mask')]
        if not is_pt:
            color_btns.insert(1, ('obj_neg_color_btn', 'negative'))
        for btn_key, color_type in color_btns:
            if btn_key not in self.controls:
                continue
            btn = self.controls[btn_key]
            colors = {om.object_colors[oid][color_type].name()
                      for oid in selected if oid in om.object_colors}
            if len(colors) > 1:
                self._set_color_button_mixed(btn)
            else:
                self._set_color_button(btn, om.object_colors[obj_id][color_type])

        if 'obj_marker_combo' in self.controls:
            combo = self.controls['obj_marker_combo']
            styles = {om.object_markers[oid]['style']
                      for oid in selected if oid in om.object_markers}
            combo.blockSignals(True)
            if len(styles) > 1:
                combo.setCurrentIndex(-1)
            else:
                idx = combo.findData(om.object_markers[obj_id]['style'])
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(False)

        if 'obj_marker_size_slider' in self.controls:
            sizes = {om.object_markers[oid]['size']
                     for oid in selected if oid in om.object_markers}
            mixed = len(sizes) > 1
            slider = self.controls['obj_marker_size_slider']
            slider.blockSignals(True)
            slider.setValue(om.object_markers[obj_id]['size'])
            slider.blockSignals(False)
            self._set_slider_mixed(slider, mixed)
            if 'obj_marker_size_value_label' in self.controls:
                label_txt = "\u2014" if mixed else str(om.object_markers[obj_id]['size'])
                self.controls['obj_marker_size_value_label'].setText(label_txt)

        if not is_pt and 'obj_mask_opacity_slider' in self.controls:
            opacities = {int(om.object_colors[oid]['mask'].alphaF() * 100)
                         for oid in selected if oid in om.object_colors}
            mixed = len(opacities) > 1
            opacity = int(om.object_colors[obj_id]['mask'].alphaF() * 100)
            slider = self.controls['obj_mask_opacity_slider']
            slider.blockSignals(True)
            slider.setValue(opacity)
            slider.blockSignals(False)
            self._set_slider_mixed(slider, mixed)
            if 'obj_mask_opacity_value_label' in self.controls:
                self.controls['obj_mask_opacity_value_label'].setText(
                    "\u2014" if mixed else str(opacity)
                )

        name = om.object_names.get(obj_id, f"Object {obj_id}")
        if 'obj_name_edit' in self.controls:
            self.controls['obj_name_edit'].setEnabled(not multi)
            self.controls['obj_name_edit'].setText("" if multi else name)

        if 'clear_points_btn' in self.controls:
            self.controls['clear_points_btn'].setText(
                self.localization.get_text("clear_points" if multi else "clear_point")
            )

    def update_objects_list(self):
        """Update the objects list widget"""
        if 'objects_list' not in self.controls:
            return
        list_widget = self.controls['objects_list']
        list_widget.blockSignals(True)
        list_widget.clear()
        key = "point" if self.object_manager.point_mode else "object"
        obj_ids = sorted(self.object_manager.object_colors.keys())
        for obj_id in obj_ids:
            obj_name = self.object_manager.object_names.get(
                obj_id, f"{self.localization.get_text(key)} {obj_id}")
            list_widget.addItem(obj_name)
        for row, obj_id in enumerate(obj_ids):
            if obj_id in self.object_manager.selected_object_ids:
                list_widget.item(row).setSelected(True)
        list_widget.blockSignals(False)

    def get_controls(self):
        """Get all controls dictionary"""
        return self.controls
