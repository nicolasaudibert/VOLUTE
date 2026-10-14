"""
Model Selection Dialog
Startup chooser listing the available model configurations, plus the catalog
those entries come from.

The catalog is the single source of truth for the model configurations the
application offers: the startup dialog, the settings dialog and the launcher
all read it. This module deliberately imports nothing from the package, so the
launcher can load it before importing volute — whose own import pulls in
torch and SAM2, several seconds the dialog should not wait for.
"""

from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QCheckBox, QPushButton, QDialogButtonBox,
)
from PyQt5.QtCore import Qt

# Each entry carries what the launcher needs to build the backend: the model
# family, and the config/checkpoint/task overrides that distinguish it from the
# family default. Labels are model names, left untranslated; the one-line
# description beside them is localized.
MODEL_ENTRIES = [
    {
        'key': 'sam2_default',
        'label': 'SAM2 — Hiera Large',
        'description': 'model_desc_sam2_default',
        'model': 'sam2',
    },
    {
        'key': 'sam2_small',
        'label': 'SAM2 — Hiera Small',
        'description': 'model_desc_sam2_small',
        'model': 'sam2',
        'config': 'configs/sam2.1/sam2.1_hiera_s.yaml',
        'checkpoint': 'checkpoints/sam2.1_hiera_small.pt',
    },
    {
        'key': 'medsam2_general',
        'label': 'MedSAM2 — General',
        'description': 'model_desc_medsam2_general',
        'model': 'medsam2',
    },
    {
        'key': 'medsam2_ct',
        'label': 'MedSAM2 — CT Lesion',
        'description': 'model_desc_medsam2_ct',
        'model': 'medsam2',
        'config': 'configs/medsam2_configs/sam2.1_hiera_t512.yaml',
        'checkpoint': 'checkpoints/MedSAM2_CTLesion.pt',
    },
    {
        'key': 'medsam2_heart',
        'label': 'MedSAM2 — Heart Ultrasound',
        'description': 'model_desc_medsam2_heart',
        'model': 'medsam2',
        'config': 'configs/medsam2_configs/sam2.1_hiera_t512.yaml',
        'checkpoint': 'checkpoints/MedSAM2_US_Heart.pt',
    },
    {
        'key': 'medsam2_liver',
        'label': 'MedSAM2 — Liver MRI',
        'description': 'model_desc_medsam2_liver',
        'model': 'medsam2',
        'config': 'configs/medsam2_configs/sam2.1_hiera_t512.yaml',
        'checkpoint': 'checkpoints/MedSAM2_MRI_LiverLesion.pt',
    },
    {
        'key': 'sam2plus_mask',
        'label': 'SAM2++ — Mask mode',
        'description': 'model_desc_sam2plus_mask',
        'model': 'sam2plus',
        'task': 'mask',
    },
    {
        'key': 'sam2plus_point',
        'label': 'SAM2++ — Point tracking',
        'description': 'model_desc_sam2plus_point',
        'model': 'sam2plus',
        'task': 'point',
    },
]


# Config and checkpoint a family starts from when its entry names none. Paths
# are relative to the SAM2-Plus root, the launcher's working directory; configs
# resolve inside the package that builds the model.
FAMILY_DEFAULTS = {
    'sam2': ('configs/sam2.1/sam2.1_hiera_l.yaml',
             './checkpoints/sam2.1_hiera_large.pt'),
    'medsam2': ('configs/medsam2_configs/sam2.1_hiera_t512.yaml',
                './checkpoints/MedSAM2_latest.pt'),
    'sam2plus': ('configs/sam2.1/sam2.1_hiera_b+_predmasks_decoupled_MAME.yaml',
                 './checkpoints/SAM2-Plus/checkpoint_phase123.pt'),
}


def entry_paths(entry):
    """Return the (config, checkpoint) an entry starts from."""
    config, checkpoint = FAMILY_DEFAULTS[entry['model']]
    return entry.get('config', config), entry.get('checkpoint', checkpoint)


def is_installed(entry, root='.'):
    """Whether the entry's checkpoint and config are both present under root.

    MedSAM2 also needs its config inside the sam2 package, which the installer
    downloads with its checkpoints.
    """
    config, checkpoint = entry_paths(entry)
    package = 'sam2_plus' if entry['model'] == 'sam2plus' else 'sam2'
    root = Path(root)
    return (root / checkpoint).is_file() and (root / package / config).is_file()


def find_entry(key):
    """Return the catalog entry with this key, or the first one when unknown."""
    for entry in MODEL_ENTRIES:
        if entry['key'] == key:
            return entry
    return MODEL_ENTRIES[0]


class ModelSelectionDialog(QDialog):
    """Startup model chooser.

    On acceptance the two persistent checkboxes are written back to the
    configuration file; the debug flag is read by the launcher and applies to
    the session only, its persistent counterpart being debug.enabled in the
    settings.
    """

    def __init__(self, localization, config_manager, parent=None):
        super().__init__(parent)
        self.localization = localization
        self.config_manager = config_manager
        self.chosen_entry = None
        self.debug_enabled = False

        self.setWindowTitle(localization.get_text("model_dialog_title"))
        self.setMinimumWidth(460)
        self._setup_ui()

    def _setup_ui(self):
        loc = self.localization
        v = QVBoxLayout(self)

        v.addWidget(QLabel(loc.get_text("model_dialog_prompt")))

        # A model whose files are missing stays listed, greyed out, with a
        # tooltip saying how to get it
        self.list_widget = QListWidget()
        for entry in MODEL_ENTRIES:
            text = f"{entry['label']} — {loc.get_text(entry['description'])}"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, entry['key'])
            if not is_installed(entry):
                item.setText(f"{text} ({loc.get_text('model_not_installed')})")
                item.setFlags(item.flags() & ~(Qt.ItemIsEnabled | Qt.ItemIsSelectable))
                item.setToolTip(loc.get_text('model_missing_tooltip'))
            self.list_widget.addItem(item)
        self.list_widget.itemDoubleClicked.connect(self.accept)
        v.addWidget(self.list_widget)

        # The default model when installed, else the first installed one
        default_key = self.config_manager.get_default_model()
        installed = [row for row in range(self.list_widget.count())
                     if self._is_enabled(self.list_widget.item(row))]
        for row in installed:
            if self.list_widget.item(row).data(Qt.UserRole) == default_key:
                self.list_widget.setCurrentRow(row)
                break
        else:
            if installed:
                self.list_widget.setCurrentRow(installed[0])

        self.set_default_checkbox = QCheckBox(loc.get_text("model_set_default"))
        self.set_default_checkbox.setToolTip(loc.get_text("model_set_default_tooltip"))
        v.addWidget(self.set_default_checkbox)

        self.show_startup_checkbox = QCheckBox(loc.get_text("model_show_at_startup"))
        self.show_startup_checkbox.setChecked(True)
        self.show_startup_checkbox.setToolTip(loc.get_text("model_show_at_startup_tooltip"))
        v.addWidget(self.show_startup_checkbox)

        self.debug_checkbox = QCheckBox(loc.get_text("debug_mode_label"))
        self.debug_checkbox.setToolTip(loc.get_text("debug_mode_tooltip"))
        v.addWidget(self.debug_checkbox)

        buttons = QDialogButtonBox()
        launch = buttons.addButton(loc.get_text("model_dialog_launch"),
                                   QDialogButtonBox.AcceptRole)
        launch.setDefault(True)
        launch.setEnabled(bool(installed))
        buttons.addButton(loc.get_text("cancel"), QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        v.addWidget(buttons)

    @staticmethod
    def _is_enabled(item):
        return bool(item.flags() & Qt.ItemIsEnabled)

    def accept(self):
        item = self.list_widget.currentItem()
        if item is None or not self._is_enabled(item):
            return
        self.chosen_entry = find_entry(item.data(Qt.UserRole))
        self.debug_enabled = self.debug_checkbox.isChecked()

        changed = False
        if self.set_default_checkbox.isChecked():
            self.config_manager.set('models.default_model', self.chosen_entry['key'])
            changed = True
        if not self.show_startup_checkbox.isChecked():
            self.config_manager.set('ui.show_model_dialog', False)
            changed = True
        if changed:
            self.config_manager.save_config()

        super().accept()
