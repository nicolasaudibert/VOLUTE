"""
Reference Point Controls
UI panel for managing named reference points.
"""

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox, QSlider,
    QLineEdit, QGroupBox, QListWidget, QFileDialog, QMessageBox,
    QAbstractItemView, QCheckBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QBrush, QColor
from ..dialogs import localized_question
from ..file_utils import build_file_filter
from .object_controls import fill_marker_combo

# Extrapolation policies and interpolation modes offered for a reference point,
# as (stored value, translation key) pairs — shared with UIManager, which
# relabels the combos on a language change.
REF_POINT_EXTRAPOLATION_ITEMS = [
    ('extrapolate', 'ref_point_extrapolation_extrapolate'),
    ('undefined',   'ref_point_extrapolation_undefined'),
    ('clamp',       'ref_point_extrapolation_clamp'),
]
REF_POINT_INTERPOLATION_ITEMS = [
    ('cubic',  'ref_point_interpolation_cubic'),
    ('linear', 'ref_point_interpolation_linear'),
]

class _RefNameLineEdit(QLineEdit):
    """QLineEdit that remembers the text it had when it gained focus, for undo history."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.focus_in_text = ""

    def focusInEvent(self, event):
        self.focus_in_text = self.text()
        super().focusInEvent(event)

class ReferencePointControls:
    """Builds the Reference Points UI panel."""

    def __init__(self, main_window, localization):
        self.main_window = main_window
        self.localization = localization
        self.controls = {}

    # ------------------------------------------------------------------
    # Mixed-value display helpers
    #
    # Duplicated from ObjectControls rather than factored into a shared
    # module: keeping them separate lets the Ref. Points tab diverge from
    # the Objects/Points tab later (different mixed-value styling, extra
    # states, etc.) without touching shared code.
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

    def create_ref_points_panel(self):
        group = QGroupBox(self.localization.get_text("ref_points"))
        v = QVBoxLayout(group)

        # Global advanced-mode toggle
        adv_row = QHBoxLayout()
        self.controls['ref_advanced_mode_checkbox'] = QCheckBox(
            self.localization.get_text("ref_advanced_mode")
        )
        self.controls['ref_advanced_mode_checkbox'].setChecked(False)
        self.controls['ref_advanced_mode_checkbox'].stateChanged.connect(
            self.main_window.toggle_ref_advanced_mode
        )
        adv_row.addWidget(self.controls['ref_advanced_mode_checkbox'])
        v.addLayout(adv_row)

        # List of ref point names — extended selection, same as objects/points list
        self.controls['ref_points_list'] = QListWidget()
        self.controls['ref_points_list'].setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.controls['ref_points_list'].itemSelectionChanged.connect(
            self._on_ref_points_selection_changed
        )
        v.addWidget(self.controls['ref_points_list'])

        # Name input row
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel(self.localization.get_text("ref_point_name")))
        self.controls['ref_point_name_edit'] = _RefNameLineEdit()
        self.controls['ref_point_name_edit'].textChanged.connect(self._rename_point_live)
        self.controls['ref_point_name_edit'].editingFinished.connect(self._commit_rename_history)
        name_row.addWidget(self.controls['ref_point_name_edit'])
        v.addLayout(name_row)

        # Add / Remove (all frames)
        btn_row = QHBoxLayout()
        for key, attr, slot in [
            ("add_ref_point_btn",    'add_ref_point_btn',    self._add_point),
            ("remove_ref_point_btn", 'remove_ref_point_btn', self._remove_point),
        ]:
            btn = QPushButton(self.localization.get_text(key))
            btn.clicked.connect(slot)
            self.controls[attr] = btn
            btn_row.addWidget(btn)
        v.addLayout(btn_row)

        # Remove on current frame only
        self.controls['remove_ref_point_frame_btn'] = QPushButton(
            self.localization.get_text("remove_ref_point_frame_btn")
        )
        self.controls['remove_ref_point_frame_btn'].clicked.connect(self._remove_point_frame)
        self.controls['remove_ref_point_frame_btn'].setEnabled(False)
        v.addWidget(self.controls['remove_ref_point_frame_btn'])

        # Navigation to frames with an explicitly defined position (advanced mode)
        nav_row = QHBoxLayout()
        self.controls['ref_point_prev_frame_btn'] = QPushButton(
            self.localization.get_text("ref_point_defined_frame_prev_btn")
        )
        self.controls['ref_point_prev_frame_btn'].clicked.connect(
            self.main_window.goto_prev_ref_point_frame
        )
        self.controls['ref_point_prev_frame_btn'].setEnabled(False)
        nav_row.addWidget(self.controls['ref_point_prev_frame_btn'])
        self.controls['ref_point_next_frame_btn'] = QPushButton(
            self.localization.get_text("ref_point_defined_frame_next_btn")
        )
        self.controls['ref_point_next_frame_btn'].clicked.connect(
            self.main_window.goto_next_ref_point_frame
        )
        self.controls['ref_point_next_frame_btn'].setEnabled(False)
        nav_row.addWidget(self.controls['ref_point_next_frame_btn'])
        v.addLayout(nav_row)

        # Import names from .txt file
        self.controls['import_ref_points_btn'] = QPushButton(
            self.localization.get_text("import_names_btn")
        )
        self.controls['import_ref_points_btn'].clicked.connect(self._import_from_txt)
        v.addWidget(self.controls['import_ref_points_btn'])

        # Per-reference-point color/marker controls, mirroring the
        # Current Object/Point Configuration panel on the Objects/Points tab.
        v.addWidget(self._create_ref_point_config_panel())

        return group

    def _create_ref_point_config_panel(self):
        """Color / marker style / marker size controls for the selected reference point(s)."""
        config_group = QGroupBox(self.localization.get_text("current_ref_point_config"))
        config_layout = QVBoxLayout(config_group)

        # Color
        color_row = QHBoxLayout()
        color_row.addWidget(QLabel(self.localization.get_text("ref_point_color")))
        self.controls['ref_point_color_btn'] = QPushButton("")
        self.controls['ref_point_color_btn'].setStyleSheet("background-color: gold;")
        self.controls['ref_point_color_btn'].clicked.connect(
            self.main_window.choose_ref_point_color
        )
        color_row.addWidget(self.controls['ref_point_color_btn'])
        config_layout.addLayout(color_row)

        # Marker style
        style_row = QHBoxLayout()
        style_row.addWidget(QLabel(self.localization.get_text("marker_style")))
        self.controls['ref_point_marker_combo'] = QComboBox()
        fill_marker_combo(self.controls['ref_point_marker_combo'], self.localization,
                          ['o', 's', '^', 'D', '*', 'x', '+'])
        self.controls['ref_point_marker_combo'].currentIndexChanged.connect(
            self.main_window.update_ref_point_marker_style
        )
        style_row.addWidget(self.controls['ref_point_marker_combo'])
        config_layout.addLayout(style_row)

        # Marker size
        size_row = QHBoxLayout()
        size_row.addWidget(QLabel(self.localization.get_text("marker_size")))
        self.controls['ref_point_marker_size_slider'] = QSlider(Qt.Horizontal)
        self.controls['ref_point_marker_size_slider'].setRange(1, 50)
        self.controls['ref_point_marker_size_slider'].setValue(10)
        self.controls['ref_point_marker_size_value_label'] = QLabel("10")
        self.controls['ref_point_marker_size_slider'].valueChanged.connect(
            self.main_window.update_ref_point_marker_size
        )
        self.controls['ref_point_marker_size_slider'].valueChanged.connect(
            lambda v: self.controls['ref_point_marker_size_value_label'].setText(str(v))
        )
        size_row.addWidget(self.controls['ref_point_marker_size_slider'])
        size_row.addWidget(self.controls['ref_point_marker_size_value_label'])
        config_layout.addLayout(size_row)

        # Extrapolation policy (advanced mode, >=2 frames not spanning full range)
        extrap_row = QHBoxLayout()
        extrap_row.addWidget(QLabel(self.localization.get_text("ref_point_extrapolation_label")))
        self.controls['ref_point_extrapolation_combo'] = QComboBox()
        for value, key in REF_POINT_EXTRAPOLATION_ITEMS:
            self.controls['ref_point_extrapolation_combo'].addItem(
                self.localization.get_text(key), value
            )
        self.controls['ref_point_extrapolation_combo'].currentIndexChanged.connect(
            self.main_window.update_ref_point_extrapolation_policy
        )
        self.controls['ref_point_extrapolation_combo'].setEnabled(False)
        extrap_row.addWidget(self.controls['ref_point_extrapolation_combo'])
        config_layout.addLayout(extrap_row)

        # Interpolation mode (advanced mode, >2 frames)
        interp_row = QHBoxLayout()
        interp_row.addWidget(QLabel(self.localization.get_text("ref_point_interpolation_label")))
        self.controls['ref_point_interpolation_combo'] = QComboBox()
        for value, key in REF_POINT_INTERPOLATION_ITEMS:
            self.controls['ref_point_interpolation_combo'].addItem(
                self.localization.get_text(key), value
            )
        self.controls['ref_point_interpolation_combo'].currentIndexChanged.connect(
            self.main_window.update_ref_point_interpolation_mode
        )
        self.controls['ref_point_interpolation_combo'].setEnabled(False)
        interp_row.addWidget(self.controls['ref_point_interpolation_combo'])
        config_layout.addLayout(interp_row)

        return config_group

    # ------------------------------------------------------------------
    # Default name generation
    # ------------------------------------------------------------------

    def _next_default_name(self):
        """Return the next available default ref point name (localized prefix + counter)."""
        rpm = getattr(self.main_window, 'ref_point_manager', None)
        base = self.localization.get_text('ref_point')
        existing = set(rpm.reference_points.keys()) if rpm else set()
        n = len(existing) + 1
        name = f"{base} {n}"
        while name in existing:
            n += 1
            name = f"{base} {n}"
        return name

    # ------------------------------------------------------------------
    # Cross-name helpers
    # ------------------------------------------------------------------

    def _cross_name_conflicts(self, names):
        """Return names that also appear in object_manager (for non-blocking warnings)."""
        om = getattr(self.main_window, 'object_manager', None)
        if not om:
            return []
        obj_names = set(om.object_names.values())
        return [n for n in names if n in obj_names]

    def _warn_cross_names(self, conflicts):
        """Show non-blocking warning about names shared with objects."""
        txt = "\n".join(conflicts[:10])
        if len(conflicts) > 10:
            txt += f"\n({len(conflicts) - 10} more\u2026)"
        self.main_window.ui_manager.show_message(
            "warning",
            self.localization.get_text("import_cross_names_title"),
            self.localization.get_text("import_cross_names_msg", txt),
        )

    # ------------------------------------------------------------------
    # Selection handling (multi-selection)
    # ------------------------------------------------------------------

    def _on_ref_points_selection_changed(self):
        rpm = getattr(self.main_window, 'ref_point_manager', None)
        if not rpm:
            return
        lst = self.controls['ref_points_list']
        names_all = rpm.get_names()
        rows = sorted(idx.row() for idx in lst.selectedIndexes())
        names = [names_all[r] for r in rows if 0 <= r < len(names_all)]
        if not names:
            return
        rpm.selected_ref_point_names = set(names)
        rpm.current_ref_point_name = names[-1]
        multi = len(names) > 1
        self.controls['ref_point_name_edit'].setEnabled(not multi)
        self.controls['ref_point_name_edit'].setText("" if multi else names[-1])
        self.update_ref_point_ui()

    def update_ref_point_ui(self):
        """Refresh color/marker/advanced-mode controls for the current selection,
        showing a mixed-value indicator when selected reference points differ on
        a property. Advanced-mode-only controls are kept in sync with the global
        mode toggle even when no reference point is currently selected."""
        rpm = getattr(self.main_window, 'ref_point_manager', None)
        if not rpm:
            return

        advanced = rpm.advanced_mode
        if 'remove_ref_point_frame_btn' in self.controls:
            self.controls['remove_ref_point_frame_btn'].setEnabled(advanced)

        if not rpm.current_ref_point_name:
            for key in ('ref_point_extrapolation_combo', 'ref_point_interpolation_combo',
                        'ref_point_prev_frame_btn', 'ref_point_next_frame_btn'):
                if key in self.controls:
                    self.controls[key].setEnabled(False)
            if 'ref_point_prev_frame_btn' in self.controls:
                self.controls['ref_point_prev_frame_btn'].setText(self.localization.get_text(
                    "ref_point_prev_frame_btn" if advanced else "ref_point_defined_frame_prev_btn"))
            if 'ref_point_next_frame_btn' in self.controls:
                self.controls['ref_point_next_frame_btn'].setText(self.localization.get_text(
                    "ref_point_next_frame_btn" if advanced else "ref_point_defined_frame_next_btn"))
            return

        current = rpm.current_ref_point_name
        selected = sorted(rpm.selected_ref_point_names) or [current]

        if 'ref_point_color_btn' in self.controls:
            btn = self.controls['ref_point_color_btn']
            colors = {rpm.ref_point_colors[n].name()
                      for n in selected if n in rpm.ref_point_colors}
            if len(colors) > 1:
                self._set_color_button_mixed(btn)
            elif current in rpm.ref_point_colors:
                self._set_color_button(btn, rpm.ref_point_colors[current])

        if 'ref_point_marker_combo' in self.controls:
            combo = self.controls['ref_point_marker_combo']
            styles = {rpm.ref_point_markers[n]['style']
                      for n in selected if n in rpm.ref_point_markers}
            combo.blockSignals(True)
            if len(styles) > 1:
                combo.setCurrentIndex(-1)
            elif current in rpm.ref_point_markers:
                idx = combo.findData(rpm.ref_point_markers[current]['style'])
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(False)

        if 'ref_point_marker_size_slider' in self.controls:
            sizes = {rpm.ref_point_markers[n]['size']
                     for n in selected if n in rpm.ref_point_markers}
            mixed = len(sizes) > 1
            slider = self.controls['ref_point_marker_size_slider']
            if current in rpm.ref_point_markers:
                slider.blockSignals(True)
                slider.setValue(rpm.ref_point_markers[current]['size'])
                slider.blockSignals(False)
            self._set_slider_mixed(slider, mixed)
            if 'ref_point_marker_size_value_label' in self.controls:
                label_txt = "\u2014" if mixed else str(rpm.ref_point_markers[current]['size'])
                self.controls['ref_point_marker_size_value_label'].setText(label_txt)

        n_frames_current = len(rpm.get_frames(current))
        multi_selection = len(selected) > 1

        if 'ref_point_extrapolation_combo' in self.controls:
            combo = self.controls['ref_point_extrapolation_combo']
            frames = rpm.get_frames(current)
            total = len(self.main_window.image_manager.image_paths)
            relevant = advanced and len(frames) >= 2 and any(
                f not in (0, total - 1) for f in frames
            )
            combo.setEnabled(relevant)
            policies = {rpm.ref_point_extrapolation_policy.get(n, rpm.default_extrapolation_policy)
                        for n in selected}
            combo.blockSignals(True)
            if len(policies) > 1:
                combo.setCurrentIndex(-1)
            else:
                idx = combo.findData(rpm.ref_point_extrapolation_policy.get(
                    current, rpm.default_extrapolation_policy))
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(False)

        if 'ref_point_interpolation_combo' in self.controls:
            combo = self.controls['ref_point_interpolation_combo']
            frames = rpm.get_frames(current)
            relevant = advanced and len(frames) > 2
            combo.setEnabled(relevant)
            modes = {rpm.ref_point_interpolation_mode.get(n, rpm.default_interpolation_mode)
                     for n in selected}
            combo.blockSignals(True)
            if len(modes) > 1:
                combo.setCurrentIndex(-1)
            else:
                idx = combo.findData(rpm.ref_point_interpolation_mode.get(
                    current, rpm.default_interpolation_mode))
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            combo.blockSignals(False)

        if 'ref_point_prev_frame_btn' in self.controls and 'ref_point_next_frame_btn' in self.controls:
            prev_btn, next_btn = self.controls['ref_point_prev_frame_btn'], self.controls['ref_point_next_frame_btn']
            prev_btn.setText(self.localization.get_text(
                "ref_point_prev_frame_btn" if advanced else "ref_point_defined_frame_prev_btn"))
            next_btn.setText(self.localization.get_text(
                "ref_point_next_frame_btn" if advanced else "ref_point_defined_frame_next_btn"))
            if multi_selection:
                prev_btn.setEnabled(False)
                next_btn.setEnabled(False)
            else:
                current_frame = self.main_window.image_manager.current_image_idx
                prev_btn.setEnabled(
                    rpm.get_adjacent_defined_frame(current, current_frame, forward=False) is not None)
                next_btn.setEnabled(
                    rpm.get_adjacent_defined_frame(current, current_frame, forward=True) is not None)

    # ------------------------------------------------------------------
    # Internal slots
    # ------------------------------------------------------------------

    def _add_point(self):
        """Add a new reference point with an auto-generated default name, selecting
        it exclusively — mirroring "Add object"/"Add point" on the Objects/Points tab.
        The name field is only used to rename an existing point, never to name a new one."""
        rpm = getattr(self.main_window, 'ref_point_manager', None)
        if not rpm:
            return
        name = self._next_default_name()

        conflicts = self._cross_name_conflicts([name])
        if conflicts:
            self._warn_cross_names(conflicts)

        from ..history_manager import Command
        prev_current = rpm.current_ref_point_name
        prev_selected = set(rpm.selected_ref_point_names)

        rpm.reference_points[name] = {}
        rpm.ref_point_colors[name] = QColor(rpm.default_color)
        rpm.ref_point_markers[name] = {
            'style': rpm.default_marker, 'size': rpm.default_marker_size
        }
        rpm.current_ref_point_name = name
        rpm.selected_ref_point_names = {name}
        self._refresh_list()
        self.controls['ref_point_name_edit'].setText(name)
        self.update_ref_point_ui()

        def _undo():
            rpm.reference_points.pop(name, None)
            rpm.ref_point_colors.pop(name, None)
            rpm.ref_point_markers.pop(name, None)
            rpm.current_ref_point_name = prev_current
            rpm.selected_ref_point_names = set(prev_selected)
            self._refresh_list()
            if rpm.current_ref_point_name:
                self.controls['ref_point_name_edit'].setText(rpm.current_ref_point_name)
            self.update_ref_point_ui()
            self.main_window.display_manager.update_display(maintain_global_zoom=True)

        def _redo():
            rpm.reference_points[name] = {}
            rpm.ref_point_colors[name] = QColor(rpm.default_color)
            rpm.ref_point_markers[name] = {
                'style': rpm.default_marker, 'size': rpm.default_marker_size
            }
            rpm.current_ref_point_name = name
            rpm.selected_ref_point_names = {name}
            self._refresh_list()
            self.controls['ref_point_name_edit'].setText(name)
            self.update_ref_point_ui()
            self.main_window.display_manager.update_display(maintain_global_zoom=True)

        self.main_window.history_manager.push(
            Command(undo_fn=_undo, redo_fn=_redo, label="Add ref point"))

    def _rename_point_live(self, new_name):
        """Rename current ref point immediately as the user types (single selection only)."""
        rpm = getattr(self.main_window, 'ref_point_manager', None)
        if not rpm or not rpm.current_ref_point_name:
            return
        if len(rpm.selected_ref_point_names) > 1:
            return
        new_name = new_name.strip()
        if not new_name or new_name == rpm.current_ref_point_name:
            return
        if new_name in rpm.reference_points:
            return  # Silent no-op: duplicate names not allowed
        old_name = rpm.current_ref_point_name
        rpm.rename_point(old_name, new_name)
        rpm.selected_ref_point_names = {new_name}
        self._refresh_list()

    def _remove_point(self):
        """Remove all selected reference points (all frames), with a single grouped
        undo command and a grouped confirmation message when more than one is selected."""
        rpm = getattr(self.main_window, 'ref_point_manager', None)
        if not rpm or not rpm.selected_ref_point_names:
            self.main_window.ui_manager.show_message(
                "warning", "", self.localization.get_text("no_ref_point_selected")
            )
            return
        import copy
        from ..history_manager import Command

        names = sorted(rpm.selected_ref_point_names)

        if len(names) > 1:
            confirm_msg = self.localization.get_text("confirm_remove_ref_points", len(names))
            reply = self.main_window.ui_manager.show_message(
                "question", self.localization.get_text("confirmation"), confirm_msg
            )
            if reply != QMessageBox.Yes:
                return

        snapshots = {
            n: {
                'frames': copy.deepcopy(rpm.reference_points.get(n, {})),
                'color': QColor(rpm.ref_point_colors[n]) if n in rpm.ref_point_colors else None,
                'marker': dict(rpm.ref_point_markers[n]) if n in rpm.ref_point_markers else None,
            }
            for n in names
        }
        prev_current = rpm.current_ref_point_name
        prev_selected = set(rpm.selected_ref_point_names)

        for n in names:
            rpm.remove_all_points(n)

        remaining = rpm.get_names()
        new_current = remaining[0] if remaining else None
        rpm.current_ref_point_name = new_current
        rpm.selected_ref_point_names = {new_current} if new_current else set()

        self._refresh_list()
        if rpm.current_ref_point_name:
            self.controls['ref_point_name_edit'].setText(rpm.current_ref_point_name)
        self.update_ref_point_ui()
        self.main_window.display_manager.update_display(maintain_global_zoom=True)

        def _undo():
            for n in names:
                snap = snapshots[n]
                rpm.reference_points[n] = copy.deepcopy(snap['frames'])
                if snap['color'] is not None:
                    rpm.ref_point_colors[n] = QColor(snap['color'])
                if snap['marker'] is not None:
                    rpm.ref_point_markers[n] = dict(snap['marker'])
            rpm.current_ref_point_name = prev_current
            rpm.selected_ref_point_names = set(prev_selected)
            self._refresh_list()
            if rpm.current_ref_point_name:
                self.controls['ref_point_name_edit'].setText(rpm.current_ref_point_name)
            self.update_ref_point_ui()
            self.main_window.display_manager.update_display(maintain_global_zoom=True)

        def _redo():
            for n in names:
                rpm.remove_all_points(n)
            rpm.current_ref_point_name = new_current
            rpm.selected_ref_point_names = {new_current} if new_current else set()
            self._refresh_list()
            self.update_ref_point_ui()
            self.main_window.display_manager.update_display(maintain_global_zoom=True)

        self.main_window.history_manager.push(
            Command(undo_fn=_undo, redo_fn=_redo, label="Remove ref points"))

    def _remove_point_frame(self):
        """Remove the current frame's position for all selected reference points
        (extended to the full selection, for consistency with "Remove all frames")."""
        rpm = getattr(self.main_window, 'ref_point_manager', None)
        if not rpm or not rpm.selected_ref_point_names:
            self.main_window.ui_manager.show_message(
                "warning", "", self.localization.get_text("no_ref_point_selected")
            )
            return
        from ..history_manager import Command

        names = sorted(rpm.selected_ref_point_names)
        frame_idx = self.main_window.image_manager.current_image_idx

        # Only prompt for points that actually have a position on this frame
        names_with_point = [n for n in names if rpm.has_point(n, frame_idx)]
        if not names_with_point:
            return  # nothing to remove on this frame — no history entry needed

        if len(names_with_point) > 1:
            confirm_msg = self.localization.get_text(
                "confirm_remove_ref_points_frame", len(names_with_point)
            )
            reply = self.main_window.ui_manager.show_message(
                "question", self.localization.get_text("confirmation"), confirm_msg
            )
            if reply != QMessageBox.Yes:
                return

        before = {
            n: rpm.reference_points.get(n, {}).get(frame_idx)
            for n in names_with_point
        }

        for n in before:
            rpm.remove_point(n, frame_idx)
        self._refresh_list()
        self.main_window.display_manager.update_display(maintain_global_zoom=True)

        def _undo():
            for n, coords in before.items():
                rpm.reference_points.setdefault(n, {})[frame_idx] = coords
            self._refresh_list()
            self.main_window.display_manager.update_display(maintain_global_zoom=True)

        def _redo():
            for n in before:
                rpm.remove_point(n, frame_idx)
            self._refresh_list()
            self.main_window.display_manager.update_display(maintain_global_zoom=True)

        self.main_window.history_manager.push(
            Command(undo_fn=_undo, redo_fn=_redo, label="Remove ref point frame"))

    def _commit_rename_history(self):
        """Push an undo command for the ref point rename once editing finishes.
        The live rename (_rename_point_live) has already applied the final name;
        this only records the transition for undo/redo."""
        rpm = getattr(self.main_window, 'ref_point_manager', None)
        edit = self.controls.get('ref_point_name_edit')
        if not rpm or not edit:
            return
        before = getattr(edit, 'focus_in_text', '')
        after = rpm.current_ref_point_name
        if not before or not after or before == after:
            edit.focus_in_text = after
            return

        from ..history_manager import Command

        def _apply(old_name, new_name):
            if old_name in rpm.reference_points:
                rpm.rename_point(old_name, new_name)
            self._refresh_list()
            if rpm.current_ref_point_name:
                edit.blockSignals(True)
                edit.setText(rpm.current_ref_point_name)
                edit.blockSignals(False)

        self.main_window.history_manager.push(Command(
            undo_fn=lambda: _apply(after, before),
            redo_fn=lambda: _apply(before, after),
            label="Rename ref point",
        ))
        edit.focus_in_text = after

    # ------------------------------------------------------------------
    # Import from .txt
    # ------------------------------------------------------------------

    def _import_from_txt(self):
        rpm = getattr(self.main_window, 'ref_point_manager', None)
        if not rpm:
            return

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

        existing = list(rpm.reference_points.keys())
        overwrite = False

        # Ask overwrite vs append when ref points already exist
        if existing:
            reply = localized_question(
                self.main_window,
                self.localization,
                self.localization.get_text("import_names_btn"),
                self.localization.get_text(
                    "import_names_overwrite_msg",
                    self.localization.get_text("ref_points").lower()
                ),
            )
            overwrite = (reply == QMessageBox.Yes)

        if overwrite:
            final = list(imported)
        else:
            # Append mode: identify duplicates
            duplicates = [n for n in imported if n in existing]
            non_dup    = [n for n in imported if n not in existing]

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
                if reply == QMessageBox.Yes:  # Rename with suffix
                    all_names = set(existing) | set(non_dup)
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
                else:  # Skip duplicates
                    final = non_dup
            else:
                final = non_dup

        if not final:
            return

        # Non-blocking cross-name warning (objects vs ref points)
        conflicts = self._cross_name_conflicts(final)
        if conflicts:
            self._warn_cross_names(conflicts)

        # Apply
        if overwrite:
            rpm.clear()

        for name in final:
            rpm.reference_points.setdefault(name, {})
            rpm.ref_point_colors.setdefault(name, QColor(rpm.default_color))
            rpm.ref_point_markers.setdefault(
                name, {'style': rpm.default_marker, 'size': rpm.default_marker_size}
            )

        if not rpm.current_ref_point_name and rpm.reference_points:
            rpm.current_ref_point_name = next(iter(rpm.reference_points))
        if rpm.current_ref_point_name:
            rpm.selected_ref_point_names = {rpm.current_ref_point_name}

        self._refresh_list()
        if rpm.current_ref_point_name:
            self.controls['ref_point_name_edit'].setText(rpm.current_ref_point_name)
        self.update_ref_point_ui()

    # ------------------------------------------------------------------
    # List refresh
    # ------------------------------------------------------------------

    def _refresh_list(self):
        rpm = getattr(self.main_window, 'ref_point_manager', None)
        if not rpm:
            return
        lst = self.controls['ref_points_list']
        lst.blockSignals(True)
        lst.clear()
        names = rpm.get_names()
        for name in names:
            n_frames = len(rpm.get_frames(name))
            lst.addItem(f"{name} ({n_frames})" if n_frames else name)
        for row, name in enumerate(names):
            if name in rpm.selected_ref_point_names:
                lst.item(row).setSelected(True)
        lst.blockSignals(False)

    def get_controls(self):
        return self.controls
