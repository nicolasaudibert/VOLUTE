"""
Settings Dialog
Edits the settings held in volute_config.yaml and writes them back, comments
and layout preserved (see ConfigManager.save_config).

The field table below is the only place a setting has to be declared: it drives
the widgets, the tabs, and the reading and writing of values alike.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QCheckBox,
    QComboBox, QSpinBox, QLineEdit, QPushButton, QDialogButtonBox, QTabWidget,
    QWidget, QFileDialog, QMessageBox,
)
from PyQt5.QtCore import Qt

from .model_dialog import MODEL_ENTRIES
from .dialogs import localized_question

# (dotted key, tab key, label key, kind, options)
#   bool    — checkbox
#   int     — spin box, options = (minimum, maximum)
#   choice  — combo box over fixed values, options = (value, …)
#   language/model — combo box filled at runtime
#   path    — line edit with a Browse button
SETTINGS_FIELDS = [
    ('ui.default_language',            'interface', 'settings_language',            'language', None),
    ('ui.show_model_dialog',           'interface', 'settings_show_model_dialog',   'bool',     None),
    ('models.default_model',           'interface', 'settings_default_model',       'model',    None),
    ('ui.show_image_filename',         'interface', 'settings_show_image_filename', 'bool',     None),
    ('ui.native_file_dialogs',         'interface', 'settings_native_dialogs',      'bool',     None),
    ('ui.import_confirmation_default', 'interface', 'settings_import_confirmation', 'choice',   ('yes', 'no')),
    ('ui.progress_details_font_size',  'interface', 'settings_progress_font',       'int',      (6, 32)),
    ('ui.progress_animation_pacing',   'interface', 'settings_animation_pacing',    'choice',   ('file', 'progress')),

    ('export.coordinates_format',      'export',    'settings_coordinates_format',  'choice',   ('json', 'csv', 'pickle')),
    ('export.centroids_format',        'export',    'settings_centroids_format',    'choice',   ('excel', 'csv', 'json')),
    ('export.image_quality',           'export',    'settings_image_quality',       'int',      (1, 100)),

    ('performance.image_cache_size',   'tools',     'settings_cache_size',          'int',      (0, 100000)),
    ('gimp.executable_path',           'tools',     'settings_gimp_path',           'path',     None),
    ('ffmpeg.executable_path',         'tools',     'settings_ffmpeg_path',         'path',     None),

    ('debug.enabled',                  'debug',     'settings_debug_enabled',       'bool',     None),
    ('debug.show_filename_mappings',   'debug',     'settings_debug_filenames',     'bool',     None),
    ('debug.show_mask_sync_details',   'debug',     'settings_debug_mask_sync',     'bool',     None),
]

TABS = [
    ('interface', 'settings_tab_interface'),
    ('export',    'settings_tab_export'),
    ('tools',     'settings_tab_tools'),
    ('debug',     'settings_tab_debug'),
]


class SettingsDialog(QDialog):
    """Application settings, saved to the configuration file."""

    def __init__(self, localization, config_manager, parent=None):
        super().__init__(parent)
        self.localization = localization
        self.config_manager = config_manager
        self.widgets = {}

        self.setWindowTitle(localization.get_text("settings_title"))
        self.setMinimumWidth(560)
        self._setup_ui()
        self._load_values(self.config_manager.config)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        loc = self.localization
        v = QVBoxLayout(self)

        tabs = QTabWidget()
        grids = {}
        for tab_key, label_key in TABS:
            page = QWidget()
            grid = QGridLayout(page)
            grid.setColumnStretch(1, 1)
            grids[tab_key] = grid
            tabs.addTab(page, loc.get_text(label_key))
        v.addWidget(tabs)

        for dotted, tab_key, label_key, kind, options in SETTINGS_FIELDS:
            grid = grids[tab_key]
            row = grid.rowCount()
            grid.addWidget(QLabel(loc.get_text(label_key)), row, 0)
            widget, container = self._build_widget(kind, options, label_key)
            self.widgets[dotted] = widget
            grid.addWidget(container, row, 1)

        for grid in grids.values():
            grid.setRowStretch(grid.rowCount(), 1)

        note = QLabel(loc.get_text("settings_restart_note"))
        note.setWordWrap(True)
        note.setStyleSheet("color: gray;")
        v.addWidget(note)

        buttons = QDialogButtonBox()
        save = buttons.addButton(loc.get_text("settings_save"), QDialogButtonBox.AcceptRole)
        save.setDefault(True)
        buttons.addButton(loc.get_text("cancel"), QDialogButtonBox.RejectRole)
        restore = buttons.addButton(loc.get_text("settings_restore_defaults"),
                                    QDialogButtonBox.ResetRole)
        restore.clicked.connect(self._restore_defaults)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        v.addWidget(buttons)

    def _build_widget(self, kind, options, label_key):
        """Return (widget carrying the value, widget to place in the layout)."""
        if kind == 'bool':
            widget = QCheckBox()
            return widget, widget
        if kind == 'int':
            widget = QSpinBox()
            widget.setRange(*options)
            return widget, widget
        if kind == 'choice':
            widget = QComboBox()
            for value in options:
                widget.addItem(value, value)
            return widget, widget
        if kind == 'language':
            widget = QComboBox()
            for code, name in self.localization.get_available_languages():
                widget.addItem(name, code)
            return widget, widget
        if kind == 'model':
            widget = QComboBox()
            for entry in MODEL_ENTRIES:
                widget.addItem(entry['label'], entry['key'])
            return widget, widget

        # path
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        widget = QLineEdit()
        row.addWidget(widget)
        browse = QPushButton(self.localization.get_text("settings_browse"))
        browse.clicked.connect(lambda: self._browse_into(widget, label_key))
        row.addWidget(browse)
        return widget, container

    def _browse_into(self, line_edit, label_key):
        path, _ = QFileDialog.getOpenFileName(
            self, self.localization.get_text(label_key), line_edit.text())
        if path:
            line_edit.setText(path)

    # ------------------------------------------------------------------
    # Values
    # ------------------------------------------------------------------

    @staticmethod
    def _lookup(source, dotted, fallback=None):
        """Read a dotted key from a plain nested dictionary."""
        node = source
        for part in dotted.split('.'):
            if not isinstance(node, dict) or part not in node:
                return fallback
            node = node[part]
        return node

    def _load_values(self, source):
        """Fill every widget from a configuration dictionary."""
        for dotted, _, _, kind, _ in SETTINGS_FIELDS:
            widget = self.widgets[dotted]
            value = self._lookup(source, dotted,
                                 self._lookup(self.config_manager.default_config, dotted))
            if kind == 'bool':
                widget.setChecked(bool(value))
            elif kind == 'int':
                widget.setValue(int(value or 0))
            elif kind == 'path':
                widget.setText('' if value is None else str(value))
            else:
                index = widget.findData(value)
                widget.setCurrentIndex(index if index >= 0 else 0)

    def _collect_values(self):
        """Read every widget back into a {dotted key: value} mapping."""
        values = {}
        for dotted, _, _, kind, _ in SETTINGS_FIELDS:
            widget = self.widgets[dotted]
            if kind == 'bool':
                values[dotted] = widget.isChecked()
            elif kind == 'int':
                values[dotted] = widget.value()
            elif kind == 'path':
                text = widget.text().strip()
                values[dotted] = text or None
            else:
                values[dotted] = widget.currentData()
        return values

    def _restore_defaults(self):
        """Put the shipped defaults back in the widgets, leaving the file alone
        until the person saves."""
        if localized_question(
            self, self.localization,
            self.localization.get_text("settings_title"),
            self.localization.get_text("settings_restore_confirm"),
        ) != QMessageBox.Yes:
            return
        self._load_values(self.config_manager.default_config)

    def accept(self):
        for dotted, value in self._collect_values().items():
            self.config_manager.set(dotted, value)
        if not self.config_manager.save_config():
            QMessageBox.warning(self, self.localization.get_text("error"),
                                self.localization.get_text("settings_save_failed"))
            return
        super().accept()
