"""
Dialogs
Standalone QDialog subclasses used by main_window, with no coupling to it
beyond the explicit arguments passed at construction time.
"""

from PyQt5.QtWidgets import (
    QDialog, QSpinBox, QDialogButtonBox, QVBoxLayout, QHBoxLayout, QLabel,
    QRadioButton, QGridLayout, QComboBox, QMessageBox, QCheckBox, QPushButton,
    QScrollArea, QWidget, QButtonGroup,
)

# Junction modes of prediction_manager.plan_object_spans, with their labels
JUNCTION_MODE_LABEL_KEYS = (
    ('midpoint', 'junction_mode_midpoint'),
    ('forward',  'junction_mode_forward'),
    ('backward', 'junction_mode_backward'),
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


# Beyond this many passes, the resume dialog gives the totals alone
MAX_PASSES_LISTED = 6


def ask_resume_propagation(parent, localization, obj_name, frame_number, reverse,
                           passes, modified):
    """Offer to resume an interrupted propagation or start it over, stating how
    many frames it processed and how many remain — pass by pass when objects
    annotated on different frames needed several. passes lists (label, frames
    done, frame total) per pass. Resuming is the default unless prompts changed
    since the interruption, which the dialog then says. Returns 'resume',
    'restart', or None for Cancel."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Question)
    box.setWindowTitle(localization.get_text("resume_propagation_title"))
    box.setText(localization.get_text(
        "resume_propagation_text", frame_number, obj_name,
        localization.get_text("direction_backward" if reverse else "direction_forward")))
    done = sum(d for _, d, _ in passes)
    left = sum(t - d for _, d, t in passes)
    if len(passes) == 1:
        progress = localization.get_text("resume_propagation_progress", done, left)
    elif len(passes) > MAX_PASSES_LISTED:
        progress = localization.get_text("resume_propagation_passes_many", done, left, len(passes))
    else:
        lines = [localization.get_text("resume_propagation_passes", done, left, len(passes))]
        for label, pass_done, pass_total in passes:
            key = ("resume_pass_done" if pass_done == pass_total
                   else "resume_pass_pending" if pass_done == 0 else "resume_pass_running")
            lines.append(localization.get_text(key, label, pass_done, pass_total))
        progress = "\n".join(lines)
    box.setInformativeText("{0}\n\n{1}".format(
        progress,
        localization.get_text(
            "resume_propagation_modified" if modified else "resume_propagation_unchanged")))
    resume = box.addButton(localization.get_text("resume_propagation_resume"), QMessageBox.AcceptRole)
    restart = box.addButton(localization.get_text("resume_propagation_restart"), QMessageBox.DestructiveRole)
    cancel = box.addButton(localization.get_text("cancel"), QMessageBox.RejectRole)
    box.setDefaultButton(restart if modified else resume)
    box.setEscapeButton(cancel)
    box.exec_()
    clicked = box.clickedButton()
    if clicked is resume:
        return 'resume'
    if clicked is restart:
        return 'restart'
    return None


class JunctionModeDialog(QDialog):
    """How to share out the frames between two consecutive conditioning frames
    of an object: one choice for every segment, which the advanced settings can
    override segment by segment."""

    def __init__(self, cond_frames, object_names, mode, point_mode, localization, parent=None):
        """cond_frames: {obj_id: sorted conditioning frames}, for the objects
        that have more than one; point_mode names them points."""
        super().__init__(parent)
        self.localization = localization
        self.cond_frames = cond_frames
        self.object_names = object_names
        self.point_mode = point_mode
        self.overrides = {}

        self.setWindowTitle(localization.get_text("junction_mode_title"))
        layout = QVBoxLayout(self)

        listing = "\n".join(
            "\u2022 {0} ({1})".format(object_names.get(obj_id, f"Object {obj_id}"),
                                     ", ".join(str(f + 1) for f in frames))
            for obj_id, frames in cond_frames.items())
        hint = QLabel(localization.get_text(
            "junction_mode_hint_points" if point_mode else "junction_mode_hint", listing))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.mode_group = QButtonGroup(self)
        for value, label_key in JUNCTION_MODE_LABEL_KEYS:
            radio = QRadioButton(localization.get_text(label_key))
            radio.setProperty("mode", value)
            radio.setChecked(value == mode)
            self.mode_group.addButton(radio)
            layout.addWidget(radio)

        advanced_row = QHBoxLayout()
        advanced = QPushButton(localization.get_text("junction_mode_advanced"))
        advanced.clicked.connect(self._open_advanced)
        advanced_row.addWidget(advanced)
        self.overrides_label = QLabel()
        self.overrides_label.setStyleSheet("color: gray;")
        advanced_row.addWidget(self.overrides_label, 1)
        layout.addLayout(advanced_row)

        self.dont_ask = QCheckBox(localization.get_text("junction_mode_dont_ask"))
        layout.addWidget(self.dont_ask)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Cancel).setText(localization.get_text("cancel"))
        layout.addWidget(buttons)

    def _mode(self):
        return self.mode_group.checkedButton().property("mode")

    def _open_advanced(self):
        dialog = SegmentJunctionDialog(self.cond_frames, self.object_names, self.overrides,
                                       self.point_mode, self.localization, self)
        if dialog.exec_():
            self.overrides = dialog.get_overrides()
            self.overrides_label.setText(
                self.localization.get_text("junction_mode_overrides", len(self.overrides))
                if self.overrides else "")

    def get_choice(self):
        """Returns (mode, overrides, dont_ask); overrides maps
        (obj_id, start, end) to the mode of that segment."""
        return self._mode(), dict(self.overrides), self.dont_ask.isChecked()


class SegmentJunctionDialog(QDialog):
    """One row per segment between consecutive conditioning frames, each
    following the global choice unless given its own junction mode."""

    _GLOBAL = ''   # combo data of "As the global choice"

    def __init__(self, cond_frames, object_names, overrides, point_mode, localization,
                 parent=None):
        super().__init__(parent)
        self._combos = {}
        self.setWindowTitle(localization.get_text("junction_advanced_title"))
        layout = QVBoxLayout(self)

        hint = QLabel(localization.get_text("junction_advanced_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        first_column = "junction_column_point" if point_mode else "junction_column_object"
        for col, key in enumerate((first_column, "junction_column_frames",
                                   "junction_column_mode")):
            grid.addWidget(QLabel("<b>{0}</b>".format(localization.get_text(key))), 0, col)
        row = 1
        for obj_id, frames in cond_frames.items():
            name = object_names.get(obj_id, f"Object {obj_id}")
            for start, end in zip(frames, frames[1:]):
                grid.addWidget(QLabel(name), row, 0)
                grid.addWidget(QLabel(f"{start + 1} \u2192 {end + 1}"), row, 1)
                combo = QComboBox()
                combo.addItem(localization.get_text("junction_mode_global"), self._GLOBAL)
                for value, label_key in JUNCTION_MODE_LABEL_KEYS:
                    combo.addItem(localization.get_text(label_key), value)
                current = overrides.get((obj_id, start, end), self._GLOBAL)
                combo.setCurrentIndex(max(combo.findData(current), 0))
                grid.addWidget(combo, row, 2)
                self._combos[(obj_id, start, end)] = combo
                row += 1
        grid.setRowStretch(row, 1)

        # Wide enough for the table, tall enough for a dozen rows before scrolling
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(grid_widget)
        hint_size = grid_widget.sizeHint()
        scroll.setMinimumWidth(hint_size.width() + scroll.verticalScrollBar().sizeHint().width() + 4)
        scroll.setMinimumHeight(min(hint_size.height() + 4, 400))
        layout.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.Cancel).setText(localization.get_text("cancel"))
        layout.addWidget(buttons)

    def get_overrides(self):
        """{(obj_id, start, end): mode} for the segments not following the
        global choice."""
        return {key: combo.currentData() for key, combo in self._combos.items()
                if combo.currentData() != self._GLOBAL}


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
