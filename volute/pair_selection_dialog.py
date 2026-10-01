"""
Pair Selection Dialog
Choose (object, target) pairs before export; target can be a reference point
or another object (when inter-object distances are enabled).
"""
import csv

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QRadioButton, QButtonGroup,
    QTableWidget, QHeaderView, QPushButton, QAbstractItemView,
    QDialogButtonBox, QCheckBox, QFileDialog, QMessageBox, QComboBox,
)
from .file_utils import build_file_filter

# Target-type constants shared with reference_point_exporter
TARGET_REF = 'ref_point'
TARGET_OBJ = 'object'
TARGET_IMPORTED = 'imported_point'


class PairSelectionDialog(QDialog):
    """
    Opens before the file dialog when exporting closest mask points.

    After exec_() == Accepted, call get_pairs():
        pairs, include_object_distances = dlg.get_pairs()

    pairs:
        None  → all combinations (optionally including obj-vs-obj)
        list  → List[Tuple[obj_id, target_type, target_key]]
    """

    def __init__(self, object_manager, ref_point_manager=None, localization=None, parent=None,
                 imported_point_manager=None, allowed_target_types=None, window_title=None):
        super().__init__(parent)
        self.object_manager = object_manager
        self.rpm = ref_point_manager
        self.ipm = imported_point_manager
        self.loc = localization
        # Backward-compatible default: ref points + objects, as before this parameter existed
        self.allowed_target_types = allowed_target_types or (TARGET_REF, TARGET_OBJ)
        self.setWindowTitle(window_title or self.loc.get_text("export_closest_points"))
        self.resize(540, 420)
        self._setup_ui()

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _obj_entries(self):
        """Sorted list of (obj_id, display_name)."""
        return [
            (oid, self.object_manager.object_names.get(oid, f"Object {oid}"))
            for oid in sorted(self.object_manager.object_colors.keys())
        ]

    def _target_entries(self, exclude_obj_id=None):
        """
        [(target_type, target_key, display_label)] for the right column.
        Only target types present in self.allowed_target_types are included.
        Ref points first, then objects (when the inter-object option is
        enabled, excluding exclude_obj_id to prevent self-distance pairs),
        then imported points.
        """
        entries = []
        if TARGET_REF in self.allowed_target_types and self.rpm:
            entries += [(TARGET_REF, name, name) for name in self.rpm.get_names()]
        if TARGET_OBJ in self.allowed_target_types and self.obj_dist_cb.isChecked():
            for oid, oname in self._obj_entries():
                if oid != exclude_obj_id:
                    entries.append((TARGET_OBJ, oid, f"[Obj] {oname}"))
        if TARGET_IMPORTED in self.allowed_target_types and self.ipm:
            entries += [(TARGET_IMPORTED, name, name) for name in self.ipm.get_names()]
        return entries

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        v = QVBoxLayout(self)

        self.all_radio = QRadioButton(self.loc.get_text("batch_all_pairs"))
        self.sel_radio = QRadioButton(self.loc.get_text("batch_selected_pairs"))
        self.all_radio.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self.all_radio)
        grp.addButton(self.sel_radio)
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.all_radio)
        mode_row.addWidget(self.sel_radio)
        mode_row.addStretch()
        v.addLayout(mode_row)

        self.obj_dist_cb = QCheckBox(self.loc.get_text("include_object_distances"))
        self.obj_dist_cb.stateChanged.connect(self._on_obj_dist_changed)
        self.obj_dist_cb.setVisible(TARGET_OBJ in self.allowed_target_types)
        v.addWidget(self.obj_dist_cb)

        self.table = QTableWidget(0, 2)
        target_col_key = (
            "batch_col_imported_point"
            if self.allowed_target_types == (TARGET_IMPORTED,)
            else "batch_col_ref_point"
        )
        self.table.setHorizontalHeaderLabels([
            self.loc.get_text("batch_col_object"),
            self.loc.get_text(target_col_key),
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEnabled(False)
        v.addWidget(self.table)

        btn_row = QHBoxLayout()
        self.add_btn = QPushButton(self.loc.get_text("add_ref_point_btn"))
        self.add_btn.clicked.connect(self._add_pair)
        self.add_btn.setEnabled(False)
        self.rem_btn = QPushButton(self.loc.get_text("remove_ref_point_btn"))
        self.rem_btn.clicked.connect(self._remove_pair)
        self.rem_btn.setEnabled(False)
        self.import_btn = QPushButton(self.loc.get_text("batch_ref_pairs_tsv_import"))
        self.import_btn.clicked.connect(self._import_tsv)
        self.import_btn.setEnabled(False)
        self.export_btn = QPushButton(self.loc.get_text("batch_ref_pairs_tsv_export"))
        self.export_btn.clicked.connect(self._export_tsv)
        for w in (self.add_btn, self.rem_btn, self.import_btn):
            btn_row.addWidget(w)
        btn_row.addStretch()
        btn_row.addWidget(self.export_btn)
        v.addLayout(btn_row)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

        self.all_radio.toggled.connect(self._on_mode_changed)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_mode_changed(self, all_checked):
        enabled = not all_checked
        for w in (self.table, self.add_btn, self.rem_btn, self.import_btn):
            w.setEnabled(enabled)

    def _on_obj_dist_changed(self):
        """Rebuild right-column combos, excluding the object selected on the left."""
        for row in range(self.table.rowCount()):
            obj_cb = self.table.cellWidget(row, 0)
            tgt_cb = self.table.cellWidget(row, 1)
            if not isinstance(obj_cb, QComboBox) or not isinstance(tgt_cb, QComboBox):
                continue
            prev = tgt_cb.currentData()
            new_tgt = self._make_target_combo(obj_cb.currentData())
            for i in range(new_tgt.count()):
                if new_tgt.itemData(i) == prev:
                    new_tgt.setCurrentIndex(i)
                    break
            self.table.setCellWidget(row, 1, new_tgt)

    def _on_obj_combo_changed(self, obj_cb):
        """Update target combo to exclude the newly selected object."""
        for r in range(self.table.rowCount()):
            if self.table.cellWidget(r, 0) is not obj_cb:
                continue
            tgt_cb = self.table.cellWidget(r, 1)
            prev = tgt_cb.currentData() if isinstance(tgt_cb, QComboBox) else None
            new_tgt = self._make_target_combo(obj_cb.currentData())
            for i in range(new_tgt.count()):
                if new_tgt.itemData(i) == prev:
                    new_tgt.setCurrentIndex(i)
                    break
            self.table.setCellWidget(r, 1, new_tgt)
            break

    # ------------------------------------------------------------------
    # Combo factories
    # ------------------------------------------------------------------

    def _make_obj_combo(self):
        cb = QComboBox()
        for oid, oname in self._obj_entries():
            cb.addItem(oname, oid)
        return cb

    def _make_target_combo(self, exclude_obj_id=None):
        """Build target combo excluding the specified object (self-distance guard)."""
        cb = QComboBox()
        for t_type, t_key, label in self._target_entries(exclude_obj_id):
            cb.addItem(label, (t_type, t_key))
        return cb

    # ------------------------------------------------------------------
    # Row management
    # ------------------------------------------------------------------

    def _add_pair(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        obj_cb = self._make_obj_combo()
        tgt_cb = self._make_target_combo(obj_cb.currentData())
        # Update target list whenever the object selection changes
        obj_cb.currentIndexChanged.connect(
            lambda _, cb=obj_cb: self._on_obj_combo_changed(cb)
        )
        self.table.setCellWidget(row, 0, obj_cb)
        self.table.setCellWidget(row, 1, tgt_cb)

    def _remove_pair(self):
        for row in sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True):
            self.table.removeRow(row)

    # ------------------------------------------------------------------
    # TSV import / export
    # ------------------------------------------------------------------

    def _import_tsv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.loc.get_text("batch_ref_pairs_tsv_import"), "",
            build_file_filter(self.loc, 'tsv', 'all')
        )
        if not path:
            return
        name_to_id = {v: k for k, v in self.object_manager.object_names.items()}
        try:
            with open(path, 'r', encoding='utf-8', newline='') as f:
                for rd in csv.DictReader(f, delimiter='\t'):
                    obj_name = rd.get('object', '').strip()
                    target   = (rd.get('target') or rd.get('ref_point', '')).strip()
                    t_type   = rd.get('target_type', TARGET_REF).strip()
                    if not obj_name or not target:
                        continue
                    obj_id = name_to_id.get(obj_name)
                    if obj_id is None:
                        continue
                    tgt_key = name_to_id.get(target) if t_type == TARGET_OBJ else target
                    row = self.table.rowCount()
                    self.table.insertRow(row)
                    obj_cb = self._make_obj_combo()
                    for i in range(obj_cb.count()):
                        if obj_cb.itemData(i) == obj_id:
                            obj_cb.setCurrentIndex(i)
                            break
                    tgt_cb = self._make_target_combo(obj_cb.currentData())
                    for i in range(tgt_cb.count()):
                        d = tgt_cb.itemData(i)
                        if d and d[0] == t_type and d[1] == tgt_key:
                            tgt_cb.setCurrentIndex(i)
                            break
                    # Connect signal after initial value is set
                    obj_cb.currentIndexChanged.connect(
                        lambda _, cb=obj_cb: self._on_obj_combo_changed(cb)
                    )
                    self.table.setCellWidget(row, 0, obj_cb)
                    self.table.setCellWidget(row, 1, tgt_cb)
        except Exception as e:
            QMessageBox.critical(self, self.loc.get_text("batch_import_error"), str(e))

    def _export_tsv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self.loc.get_text("batch_ref_pairs_tsv_export"), "ref_pairs.tsv",
            build_file_filter(self.loc, 'tsv', 'all')
        )
        if not path:
            return
        try:
            rows_out = []
            if self.all_radio.isChecked():
                for oid, oname in self._obj_entries():
                    for t_type, t_key, _ in self._target_entries():
                        tgt_name = (
                            self.object_manager.object_names.get(t_key, str(t_key))
                            if t_type == TARGET_OBJ else t_key
                        )
                        rows_out.append({
                            'object': oname, 'target': tgt_name, 'target_type': t_type
                        })
            else:
                for row in range(self.table.rowCount()):
                    obj_cb = self.table.cellWidget(row, 0)
                    tgt_cb = self.table.cellWidget(row, 1)
                    if not isinstance(obj_cb, QComboBox) or not isinstance(tgt_cb, QComboBox):
                        continue
                    oid = obj_cb.currentData()
                    td  = tgt_cb.currentData()
                    if oid is None or td is None:
                        continue
                    oname    = self.object_manager.object_names.get(oid, str(oid))
                    t_type, t_key = td
                    tgt_name = (
                        self.object_manager.object_names.get(t_key, str(t_key))
                        if t_type == TARGET_OBJ else t_key
                    )
                    rows_out.append({
                        'object': oname, 'target': tgt_name, 'target_type': t_type
                    })
            with open(path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(
                    f, fieldnames=['object', 'target', 'target_type'], delimiter='\t'
                )
                writer.writeheader()
                writer.writerows(rows_out)
        except Exception as e:
            QMessageBox.critical(self, self.loc.get_text("batch_export_error"), str(e))

    # ------------------------------------------------------------------
    # Result accessor
    # ------------------------------------------------------------------

    def get_pairs(self):
        """
        Returns (pairs, include_object_distances).
        pairs: None (all) or List[(obj_id, target_type, target_key)].
        """
        inc_obj = self.obj_dist_cb.isChecked()
        if self.all_radio.isChecked():
            return None, inc_obj
        pairs = []
        for row in range(self.table.rowCount()):
            obj_cb = self.table.cellWidget(row, 0)
            tgt_cb = self.table.cellWidget(row, 1)
            if not isinstance(obj_cb, QComboBox) or not isinstance(tgt_cb, QComboBox):
                continue
            oid = obj_cb.currentData()
            td  = tgt_cb.currentData()
            if oid is not None and td is not None:
                pairs.append((oid, td[0], td[1]))
        return (pairs or None), inc_obj
