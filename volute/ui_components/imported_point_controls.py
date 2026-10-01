"""
Imported Point Controls
UI panel for displaying and configuring points imported from a SAM2++
point-mode "Export tracked points" file (mask mode only).

Unlike reference points, imported points are never placed via canvas click
and have no advanced/interpolation mode — they are read-only positions set
at import time. This panel only covers display (show/hide, color, marker)
and whole-name removal.
"""

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox, QSlider,
    QGroupBox, QListWidget, QMessageBox, QCheckBox,
)
from PyQt5.QtCore import Qt
from .object_controls import fill_marker_combo


class ImportedPointControls:
    """Builds the Imported Points display/configuration UI panel."""

    def __init__(self, main_window, localization):
        self.main_window = main_window
        self.localization = localization
        self.controls = {}

    # ------------------------------------------------------------------
    # Panel construction
    # ------------------------------------------------------------------

    def create_imported_points_panel(self):
        group = QGroupBox(self.localization.get_text("imported_points_config"))
        v = QVBoxLayout(group)

        # Global show/hide toggle
        show_row = QHBoxLayout()
        show_row.addWidget(QLabel(self.localization.get_text("show_imported_points")))
        self.controls['show_imported_points_checkbox'] = QCheckBox()
        self.controls['show_imported_points_checkbox'].setChecked(True)
        self.controls['show_imported_points_checkbox'].stateChanged.connect(
            self.main_window.toggle_imported_points_display
        )
        show_row.addWidget(self.controls['show_imported_points_checkbox'])
        v.addLayout(show_row)

        # List of imported point names (single selection — set once at import time)
        self.controls['imported_points_list'] = QListWidget()
        self.controls['imported_points_list'].itemSelectionChanged.connect(
            self._on_selection_changed
        )
        v.addWidget(self.controls['imported_points_list'])

        # Remove (whole name, all frames)
        self.controls['remove_imported_point_btn'] = QPushButton(
            self.localization.get_text("remove_imported_point_btn")
        )
        self.controls['remove_imported_point_btn'].clicked.connect(self._remove_point)
        v.addWidget(self.controls['remove_imported_point_btn'])

        v.addWidget(self._create_config_panel())

        return group

    def _create_config_panel(self):
        config_group = QGroupBox(self.localization.get_text("current_imported_point_config"))
        config_layout = QVBoxLayout(config_group)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel(self.localization.get_text("imported_point_color")))
        self.controls['imported_point_color_btn'] = QPushButton("")
        self.controls['imported_point_color_btn'].setStyleSheet("background-color: #00b4ff;")
        self.controls['imported_point_color_btn'].clicked.connect(
            self.main_window.choose_imported_point_color
        )
        color_row.addWidget(self.controls['imported_point_color_btn'])
        config_layout.addLayout(color_row)

        style_row = QHBoxLayout()
        style_row.addWidget(QLabel(self.localization.get_text("marker_style")))
        self.controls['imported_point_marker_combo'] = QComboBox()
        fill_marker_combo(self.controls['imported_point_marker_combo'], self.localization,
                          ['o', 's', '^', 'D', '*', 'x', '+', 'X'])
        self.controls['imported_point_marker_combo'].currentIndexChanged.connect(
            self.main_window.update_imported_point_marker_style
        )
        style_row.addWidget(self.controls['imported_point_marker_combo'])
        config_layout.addLayout(style_row)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel(self.localization.get_text("marker_size")))
        self.controls['imported_point_marker_size_slider'] = QSlider(Qt.Horizontal)
        self.controls['imported_point_marker_size_slider'].setRange(1, 50)
        self.controls['imported_point_marker_size_slider'].setValue(10)
        self.controls['imported_point_marker_size_value_label'] = QLabel("10")
        self.controls['imported_point_marker_size_slider'].valueChanged.connect(
            self.main_window.update_imported_point_marker_size
        )
        self.controls['imported_point_marker_size_slider'].valueChanged.connect(
            lambda v: self.controls['imported_point_marker_size_value_label'].setText(str(v))
        )
        size_row.addWidget(self.controls['imported_point_marker_size_slider'])
        size_row.addWidget(self.controls['imported_point_marker_size_value_label'])
        config_layout.addLayout(size_row)

        return config_group

    # ------------------------------------------------------------------
    # Selection handling (single selection)
    # ------------------------------------------------------------------

    def _on_selection_changed(self):
        ipm = getattr(self.main_window, 'imported_point_manager', None)
        if not ipm:
            return
        lst = self.controls['imported_points_list']
        names_all = ipm.get_names()
        rows = sorted(idx.row() for idx in lst.selectedIndexes())
        names = [names_all[r] for r in rows if 0 <= r < len(names_all)]
        if not names:
            return
        ipm.selected_imported_point_names = {names[-1]}
        ipm.current_imported_point_name = names[-1]
        self.update_imported_point_ui()

    def update_imported_point_ui(self):
        """Refresh color/marker controls for the currently selected imported point."""
        ipm = getattr(self.main_window, 'imported_point_manager', None)
        if not ipm:
            return

        enabled = ipm.current_imported_point_name is not None
        for key in ('remove_imported_point_btn', 'imported_point_color_btn',
                    'imported_point_marker_combo', 'imported_point_marker_size_slider'):
            if key in self.controls:
                self.controls[key].setEnabled(enabled)
        if not enabled:
            return

        current = ipm.current_imported_point_name

        if 'imported_point_color_btn' in self.controls and current in ipm.imported_point_colors:
            color = ipm.imported_point_colors[current]
            self.controls['imported_point_color_btn'].setStyleSheet(
                f"background-color: {color.name()};"
            )

        if 'imported_point_marker_combo' in self.controls and current in ipm.imported_point_markers:
            combo = self.controls['imported_point_marker_combo']
            combo.blockSignals(True)
            idx = combo.findData(ipm.imported_point_markers[current]['style'])
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.blockSignals(False)

        if 'imported_point_marker_size_slider' in self.controls and current in ipm.imported_point_markers:
            slider = self.controls['imported_point_marker_size_slider']
            slider.blockSignals(True)
            slider.setValue(ipm.imported_point_markers[current]['size'])
            slider.blockSignals(False)
            if 'imported_point_marker_size_value_label' in self.controls:
                self.controls['imported_point_marker_size_value_label'].setText(
                    str(ipm.imported_point_markers[current]['size'])
                )

    # ------------------------------------------------------------------
    # Removal
    # ------------------------------------------------------------------

    def _remove_point(self):
        """Remove the selected imported point (all frames), delegating the
        confirmation dialog and undo command to main_window."""
        ipm = getattr(self.main_window, 'imported_point_manager', None)
        if not ipm or not ipm.current_imported_point_name:
            self.main_window.ui_manager.show_message(
                "warning", "", self.localization.get_text("no_imported_point_selected")
            )
            return
        self.main_window.remove_imported_point(ipm.current_imported_point_name)

    # ------------------------------------------------------------------
    # List refresh
    # ------------------------------------------------------------------

    def _refresh_list(self):
        ipm = getattr(self.main_window, 'imported_point_manager', None)
        if not ipm:
            return
        lst = self.controls['imported_points_list']
        lst.blockSignals(True)
        lst.clear()
        names = ipm.get_names()
        for name in names:
            n_frames = ipm.frame_count(name)
            lst.addItem(f"{name} ({n_frames})" if n_frames else name)
        for row, name in enumerate(names):
            if name in ipm.selected_imported_point_names:
                lst.item(row).setSelected(True)
        lst.blockSignals(False)

    def get_controls(self):
        return self.controls
