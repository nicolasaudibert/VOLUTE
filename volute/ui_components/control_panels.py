"""
Control Panels
Points configuration, prediction, and display options panels
"""

from PyQt5.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QRadioButton, QButtonGroup, QGroupBox, QSlider, QCheckBox, QComboBox,
)
from PyQt5.QtCore import Qt
from .object_controls import _FusionSlider, fill_marker_combo

# Clipping variants offered by the "Masks strictly confined to box" option,
# as (stored value, translation key) pairs — shared with UIManager, which
# relabels the combo on a language change.
BOX_CLIPPING_MODE_ITEMS = [
    ('box_frames',   'box_clipping_mode_box_frames'),
    ('reference_box', 'box_clipping_mode_reference'),
]


class ControlPanels:
    """Creates points, prediction, and display option panels"""

    def __init__(self, main_window, localization):
        self.main_window  = main_window
        self.localization = localization
        self.controls     = {}

    def create_points_panel(self):
        """Points mode: Add (left=positive, right/Ctrl=negative) or Remove (drag rect).
        Reference points are placed with Alt+click — no radio button needed.

        Returns None in SAM2++ point tracking mode: this panel has no meaning there
        (a single seed point per object, replaced on click — see EventManager).
        The clear button for that mode lives in the Object Management panel instead.
        """
        if self.main_window.is_point_mode():
            return None

        group = QGroupBox(self.localization.get_text("points_config"))
        v = QVBoxLayout(group)

        self.controls['point_mode_group'] = QButtonGroup(self.main_window)

        self.controls['add_points_radio'] = QRadioButton(
            self.localization.get_text("add_points"))
        self.controls['add_points_radio'].setChecked(True)
        self.controls['add_points_radio'].setToolTip(
            self.localization.get_text("add_points_tooltip"))
        self.controls['point_mode_group'].addButton(
            self.controls['add_points_radio'], 1)
        v.addWidget(self.controls['add_points_radio'])

        self.controls['remove_points_radio'] = QRadioButton(
            self.localization.get_text("remove_points"))
        self.controls['remove_points_radio'].setToolTip(
            self.localization.get_text("remove_points_tooltip"))
        self.controls['point_mode_group'].addButton(
            self.controls['remove_points_radio'], 2)
        v.addWidget(self.controls['remove_points_radio'])

        self.controls['define_box_radio'] = QRadioButton(
            self.localization.get_text("define_box"))
        self.controls['define_box_radio'].setToolTip(
            self.localization.get_text("define_box_tooltip"))
        self.controls['point_mode_group'].addButton(
            self.controls['define_box_radio'], 3)
        v.addWidget(self.controls['define_box_radio'])

        self.controls['remove_box_btn'] = QPushButton(
            self.localization.get_text("remove_box_btn"))
        self.controls['remove_box_btn'].clicked.connect(self.main_window.remove_box)
        self.controls['remove_box_btn'].setEnabled(False)
        v.addWidget(self.controls['remove_box_btn'])

        self.controls['clear_points_btn'] = QPushButton(
            self.localization.get_text("clear_all_points"))
        self.controls['clear_points_btn'].clicked.connect(self.main_window.clear_points)
        v.addWidget(self.controls['clear_points_btn'])

        return group

    def create_prediction_panel(self):
        is_pt = self.main_window.is_point_mode()
        group = QGroupBox(self.localization.get_text("prediction"))
        v = QVBoxLayout(group)

        self.controls['predict_current_btn'] = QPushButton(
            self.localization.get_text("predict_points" if is_pt else "predict_current"))
        self.controls['predict_current_btn'].clicked.connect(
            self.main_window.predict_current_image)
        v.addWidget(self.controls['predict_current_btn'])

        self.controls['propagate_btn'] = QPushButton(
            self.localization.get_text("propagate_points" if is_pt else "propagate_masks"))
        self.controls['propagate_btn'].clicked.connect(self.main_window.propagate_masks)
        v.addWidget(self.controls['propagate_btn'])

        if not is_pt:
            self.controls['repropagate_btn'] = QPushButton(
                self.localization.get_text("repropagate_from_frame"))
            self.controls['repropagate_btn'].clicked.connect(
                self.main_window.repropagate_from_current_frame)
            v.addWidget(self.controls['repropagate_btn'])

            clip_row = QHBoxLayout()
            clip_row.addWidget(QLabel(self.localization.get_text("strict_box_clipping")))
            self.controls['strict_box_clipping_checkbox'] = QCheckBox()
            self.controls['strict_box_clipping_checkbox'].setChecked(False)
            self.controls['strict_box_clipping_checkbox'].setToolTip(
                self.localization.get_text("strict_box_clipping_tooltip"))
            self.controls['strict_box_clipping_checkbox'].stateChanged.connect(
                self.main_window.toggle_strict_box_clipping)
            clip_row.addWidget(self.controls['strict_box_clipping_checkbox'])
            v.addLayout(clip_row)

            mode_row = QHBoxLayout()
            mode_row.addWidget(QLabel(self.localization.get_text("box_clipping_mode")))
            self.controls['box_clipping_mode_combo'] = QComboBox()
            for value, key in BOX_CLIPPING_MODE_ITEMS:
                self.controls['box_clipping_mode_combo'].addItem(
                    self.localization.get_text(key), value)
            self.controls['box_clipping_mode_combo'].setEnabled(False)
            self.controls['box_clipping_mode_combo'].currentIndexChanged.connect(
                self.main_window.update_box_clipping_mode)
            mode_row.addWidget(self.controls['box_clipping_mode_combo'])
            v.addLayout(mode_row)

        return group

    def create_tracked_point_display_panel(self):
        """Tracked point style/size controls (SAM2++ point mode).
        Shown in the Prediction tab in place of the Centroid and Mask Contours panels."""
        group = QGroupBox(self.localization.get_text("tracked_point_display_config"))
        v = QVBoxLayout(group)

        style_row = QHBoxLayout()
        style_row.addWidget(QLabel(self.localization.get_text("tracked_point_style_label")))
        self.controls['tracked_point_style_combo'] = QComboBox()
        fill_marker_combo(self.controls['tracked_point_style_combo'], self.localization,
                          ['P', 'o', 's', '^', 'D', '*', 'X'])
        self.controls['tracked_point_style_combo'].setCurrentIndex(
            self.controls['tracked_point_style_combo'].findData(
                self.main_window.object_manager.tracked_point_style))
        self.controls['tracked_point_style_combo'].currentIndexChanged.connect(
            self.main_window.update_tracked_point_style)
        style_row.addWidget(self.controls['tracked_point_style_combo'])
        v.addLayout(style_row)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel(self.localization.get_text("tracked_point_size_label")))
        self.controls['tracked_point_size_slider'] = _FusionSlider(Qt.Horizontal)
        self.controls['tracked_point_size_slider'].setRange(3, 30)
        self.controls['tracked_point_size_slider'].setValue(
            self.main_window.object_manager.tracked_point_size)
        self.controls['tracked_point_size_value_label'] = QLabel(
            str(self.main_window.object_manager.tracked_point_size))
        self.controls['tracked_point_size_slider'].valueChanged.connect(
            self.main_window.update_tracked_point_size)
        self.controls['tracked_point_size_slider'].valueChanged.connect(
            lambda v: self.controls['tracked_point_size_value_label'].setText(str(v))
        )
        size_row.addWidget(self.controls['tracked_point_size_slider'])
        size_row.addWidget(self.controls['tracked_point_size_value_label'])
        v.addLayout(size_row)

        return group

    def create_display_options(self):
        """Returns a list of QHBoxLayouts for display option controls."""
        layouts = []

        # Background opacity
        bg_row = QHBoxLayout()
        bg_row.addWidget(QLabel(self.localization.get_text("background_opacity")))
        self.controls['background_opacity_slider'] = _FusionSlider(Qt.Horizontal)
        self.controls['background_opacity_slider'].setRange(0, 100)
        self.controls['background_opacity_slider'].setValue(100)
        self.controls['background_opacity_slider'].valueChanged.connect(
            self.main_window.update_display)
        bg_row.addWidget(self.controls['background_opacity_slider'])
        layouts.append(bg_row)

        # Show object labels
        labels_row = QHBoxLayout()
        labels_row.addWidget(QLabel(self.localization.get_text("show_labels")))
        self.controls['show_object_labels_checkbox'] = QCheckBox()
        self.controls['show_object_labels_checkbox'].setChecked(True)
        self.controls['show_object_labels_checkbox'].stateChanged.connect(
            self.main_window.update_display)
        labels_row.addWidget(self.controls['show_object_labels_checkbox'])
        layouts.append(labels_row)

        return layouts

    def get_controls(self):
        return self.controls
