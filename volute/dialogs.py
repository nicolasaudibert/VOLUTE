"""
Dialogs
Standalone QDialog subclasses used by main_window, with no coupling to it
beyond the explicit arguments passed at construction time.
"""

from PyQt5.QtWidgets import (
    QDialog, QSpinBox, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QLabel,
    QRadioButton, QGridLayout, QComboBox, QMessageBox,
)

# Standard buttons whose English label differs from the localized one. Qt only
# translates them when a Qt translator matching the system locale is loaded,
# which this application does not install. Ok and Close keep Qt's label, which
# already reads correctly in the languages shipped here.
_STANDARD_BUTTON_TEXT_KEYS = {
    QMessageBox.Yes: "yes",
    QMessageBox.No: "no",
    QMessageBox.Cancel: "cancel",
}


def localize_standard_buttons(box, localization):
    """Give a QMessageBox's standard buttons their localized labels."""
    for standard_button, text_key in _STANDARD_BUTTON_TEXT_KEYS.items():
        button = box.button(standard_button)
        if button:
            button.setText(localization.get_text(text_key))


def localized_question(parent, localization, title, text,
                       buttons=QMessageBox.Yes | QMessageBox.No,
                       default=QMessageBox.No,
                       icon=QMessageBox.Question,
                       informative=None):
    """Modal question with localized button labels; returns the standard button
    clicked, like the QMessageBox.question()/warning() static helpers it replaces."""
    box = QMessageBox(parent)
    box.setIcon(icon)
    box.setWindowTitle(title)
    box.setText(text)
    if informative:
        box.setInformativeText(informative)
    box.setStandardButtons(buttons)
    box.setDefaultButton(default)
    localize_standard_buttons(box, localization)
    return box.exec_()


class RepropagationSpanDialog(QDialog):
    """Two optional integer fields (forward/backward span in frames).
    A value of 0 means unbounded in that direction (maps to
    max_frame_num_to_track=None)."""

    def __init__(self, localization, parent=None):
        super().__init__(parent)
        self.setWindowTitle(localization.get_text("repropagate_span_title"))
        layout = QVBoxLayout(self)

        fwd_row = QHBoxLayout()
        fwd_row.addWidget(QLabel(localization.get_text("repropagate_forward_label")))
        self.forward_spin = QSpinBox()
        self.forward_spin.setRange(0, 999999)
        self.forward_spin.setSpecialValueText(localization.get_text("repropagate_unbounded"))
        fwd_row.addWidget(self.forward_spin)
        layout.addLayout(fwd_row)

        bwd_row = QHBoxLayout()
        bwd_row.addWidget(QLabel(localization.get_text("repropagate_backward_label")))
        self.backward_spin = QSpinBox()
        self.backward_spin.setRange(0, 999999)
        self.backward_spin.setSpecialValueText(localization.get_text("repropagate_unbounded"))
        bwd_row.addWidget(self.backward_spin)
        layout.addLayout(bwd_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_spans(self):
        """Returns (forward_frames, backward_frames); None means unbounded."""
        return self.forward_spin.value() or None, self.backward_spin.value() or None


class ColorObjectMappingDialog(QDialog):
    """One-time color→object mapping for Format B (multi-object
    color-composite) mask imports — each detected significant color must
    be assigned to an existing object or a newly created one before the
    import can proceed."""

    _NEW_OBJECT = -1  # sentinel combo data value for "Create new object"

    def __init__(self, colors, object_manager, localization, parent=None):
        super().__init__(parent)
        self._combos = {}
        self.object_manager = object_manager

        self.setWindowTitle(localization.get_text("mask_color_mapping_title"))
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(localization.get_text("mask_color_mapping_hint")))

        grid = QGridLayout()
        for row, color in enumerate(colors):
            swatch = QLabel()
            swatch.setFixedSize(20, 20)
            swatch.setStyleSheet(
                f"background-color: rgb({color[0]},{color[1]},{color[2]}); border: 1px solid black;"
            )
            grid.addWidget(swatch, row, 0)

            combo = QComboBox()
            for obj_id in object_manager.get_object_ids():
                combo.addItem(object_manager.object_names.get(obj_id, f"Object {obj_id}"), obj_id)
            combo.addItem(localization.get_text("mask_color_mapping_new_object"), self._NEW_OBJECT)
            grid.addWidget(combo, row, 1)
            self._combos[color] = combo
        layout.addLayout(grid)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_mapping(self):
        """Returns {color: obj_id}, creating a new object for any color
        mapped to "Create new object"."""
        mapping = {}
        for color, combo in self._combos.items():
            obj_id = combo.currentData()
            if obj_id == self._NEW_OBJECT:
                obj_id = self.object_manager.add_new_object()
            mapping[color] = obj_id
        return mapping


class GimpExportDialog(QDialog):
    """Export-mode choice for "Export Frame for Editing…" and "Export All
    Frames for Editing…" (radio buttons, default selection driven by GIMP
    CLI auto-detection). title_key/hint_key let the multi-frame call site
    use distinct wording instead of the single-frame text."""

    def __init__(self, localization, gimp_available, parent=None,
                 title_key="gimp_export_dialog_title", hint_key="gimp_export_dialog_hint",
                 xcf_key="gimp_export_mode_xcf", files_key="gimp_export_mode_files"):
        super().__init__(parent)
        self.setWindowTitle(localization.get_text(title_key))
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(localization.get_text(hint_key)))

        self.xcf_radio = QRadioButton(localization.get_text(xcf_key))
        self.files_radio = QRadioButton(localization.get_text(files_key))
        self.xcf_radio.setEnabled(gimp_available)
        if not gimp_available:
            self.xcf_radio.setToolTip(localization.get_text("gimp_not_detected_tooltip"))
        (self.xcf_radio if gimp_available else self.files_radio).setChecked(True)
        layout.addWidget(self.xcf_radio)
        layout.addWidget(self.files_radio)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_mode(self):
        return 'xcf' if self.xcf_radio.isChecked() else 'files'
