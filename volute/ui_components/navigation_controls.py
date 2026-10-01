"""
Navigation Controls
Image navigation bar placed below the canvas
"""

from PyQt5.QtWidgets import (
    QHBoxLayout, QPushButton, QLabel, QSlider, QSpinBox, QWidget, QSizePolicy,
)
from PyQt5.QtCore import Qt


class NavigationControls:
    """Creates the navigation bar (Prev | Slider | SpinBox | Next) for placement below the canvas"""

    def __init__(self, main_window, localization):
        self.main_window  = main_window
        self.localization = localization
        self.controls     = {}

    def create_navigation_bar(self):
        """Return a QWidget containing [Prev] [====slider (≥60%)====] [spinbox] [Next]."""
        widget = QWidget()
        h = QHBoxLayout(widget)
        h.setContentsMargins(4, 2, 4, 2)
        h.setSpacing(6)

        self.controls['prev_btn'] = QPushButton(self.localization.get_text("previous"))
        self.controls['prev_btn'].clicked.connect(self.main_window.prev_image)
        self.controls['prev_btn'].setEnabled(False)
        self.controls['prev_btn'].setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        self.controls['image_slider'] = QSlider(Qt.Horizontal)
        self.controls['image_slider'].setEnabled(False)
        self.controls['image_slider'].valueChanged.connect(self.main_window.slider_changed)
        self.controls['image_slider'].setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.controls['frame_spinbox'] = QSpinBox()
        self.controls['frame_spinbox'].setEnabled(False)
        self.controls['frame_spinbox'].setMinimum(1)
        self.controls['frame_spinbox'].setMaximum(1)
        self.controls['frame_spinbox'].setFixedWidth(72)
        self.controls['frame_spinbox'].valueChanged.connect(self._spinbox_changed)

        self.controls['next_btn'] = QPushButton(self.localization.get_text("next"))
        self.controls['next_btn'].clicked.connect(self.main_window.next_image)
        self.controls['next_btn'].setEnabled(False)
        self.controls['next_btn'].setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        # Keep label in controls for backward compat with callers of
        # update_navigation_controls, but don't show it (title_label handles display)
        self.controls['image_counter_label'] = QLabel("0/0")

        # stretch=0 for buttons/spinbox, stretch=6 for slider → slider gets ≥60% of width
        h.addWidget(self.controls['prev_btn'], 0)
        h.addWidget(self.controls['image_slider'], 6)
        h.addWidget(self.controls['frame_spinbox'], 0)
        h.addWidget(self.controls['next_btn'], 0)

        return widget

    def _spinbox_changed(self, value):
        """Handle spinbox value change — shared navigation path with the slider."""
        idx = value - 1  # spinbox is 1-based, frame index is 0-based
        if idx != self.main_window.image_manager.current_image_idx:
            self.main_window.image_manager.load_image(idx)

    def update_navigation_controls(self, current_idx, total_images):
        if 'image_counter_label' in self.controls:
            self.controls['image_counter_label'].setText(
                f"{current_idx + 1}/{total_images}")

        if 'prev_btn' in self.controls:
            self.controls['prev_btn'].setEnabled(current_idx > 0)

        if 'next_btn' in self.controls:
            self.controls['next_btn'].setEnabled(current_idx < total_images - 1)

        if 'image_slider' in self.controls:
            self.controls['image_slider'].blockSignals(True)
            self.controls['image_slider'].setMinimum(0)
            self.controls['image_slider'].setMaximum(max(0, total_images - 1))
            self.controls['image_slider'].setValue(current_idx)
            self.controls['image_slider'].setEnabled(total_images > 0)
            self.controls['image_slider'].blockSignals(False)

        if 'frame_spinbox' in self.controls:
            self.controls['frame_spinbox'].blockSignals(True)
            self.controls['frame_spinbox'].setMinimum(1)
            self.controls['frame_spinbox'].setMaximum(max(1, total_images))
            self.controls['frame_spinbox'].setValue(current_idx + 1)
            self.controls['frame_spinbox'].setEnabled(total_images > 0)
            self.controls['frame_spinbox'].blockSignals(False)

    def enable_navigation(self, enabled=True):
        for name in ('prev_btn', 'next_btn', 'image_slider', 'frame_spinbox'):
            if name in self.controls:
                self.controls[name].setEnabled(enabled)

    def get_controls(self):
        return self.controls
