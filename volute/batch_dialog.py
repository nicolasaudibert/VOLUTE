"""
Batch Dialog
UI dialog for configuring and running batch SAM2 segmentation
"""

import os
import csv

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QCheckBox, QSlider, QLineEdit,
    QGroupBox, QProgressBar, QPlainTextEdit, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
    QFileDialog, QMessageBox, QWidget, QSizePolicy,
    QTabWidget, QRadioButton, QButtonGroup, QComboBox,
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal

from .ui_components.object_controls import _FusionSlider
from .batch_processor import BatchProcessor
from . import progress_animation
from .file_utils import build_file_filter

class BatchWorker(QThread):
    """Worker thread that runs BatchProcessor.process_batch"""

    progress      = pyqtSignal(str)            # step-level message
    mask_progress = pyqtSignal(int, int, str)  # current, total, label
    item_done     = pyqtSignal(int, int, object)  # idx, total, result dict
    finished      = pyqtSignal(object)         # list of all results

    def __init__(self, processor, items, options, output_dir, parent=None):
        super().__init__(parent)
        self.processor  = processor
        self.items      = items
        self.options    = options
        self.output_dir = output_dir

    def run(self):
        results = self.processor.process_batch(
            self.items, self.options, self.output_dir,
            item_callback=lambda i, total, r: self.item_done.emit(i, total, r),
            progress_callback=lambda msg: self.progress.emit(msg),
            mask_progress_callback=lambda c, t, l: self.mask_progress.emit(c, t, l)
        )
        self.finished.emit(results)

    def cancel(self):
        self.processor.cancel()


class BatchDialog(QDialog):
    """Dialog for configuring and running batch SAM2 processing"""

    COL_SAM2      = 0
    COL_FOLDER    = 1
    COL_REF_FRAME = 2
    COL_TRACKED_POINTS = 3

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.loc = main_window.localization
        self.worker = None
        self.processor = BatchProcessor(
            main_window.sam2_backend,
            main_window.localization,
            main_window.debug_mode
        )

        self.setWindowTitle(self.loc.get_text("batch_processing"))
        self.resize(950, 740)
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Tab widget wrapping existing content (Tab 1) and new ref points tab (Tab 2)
        self.tab_widget = QTabWidget()
        layout.addWidget(self.tab_widget)

        # Tab 1 — Items & Options (existing content)
        tab1 = QWidget()
        t1 = QVBoxLayout(tab1)
        t1.addWidget(self._build_table_group())
        t1.addWidget(self._build_options_group())
        t1.addLayout(self._build_output_row())
        self.tab_widget.addTab(tab1, self.loc.get_text("batch_tab_items"))

        # Tab 2 — Reference Points
        tab2 = QWidget()
        t2 = QVBoxLayout(tab2)
        t2.addWidget(self._build_ref_points_group())
        t2.addStretch()
        self.tab_widget.addTab(tab2, self.loc.get_text("batch_tab_ref_points"))

        # Tab 3 — Imported Points
        tab3 = QWidget()
        t3 = QVBoxLayout(tab3)
        t3.addWidget(self._build_imported_points_group())
        t3.addStretch()
        self.tab_widget.addTab(tab3, self.loc.get_text("batch_tab_imported_points"))

        # Progress area and action buttons are always visible (outside tabs)
        layout.addLayout(self._build_progress_area())
        layout.addLayout(self._build_action_buttons())

    def _build_table_group(self):
        group = QGroupBox(self.loc.get_text("batch_items"))
        v = QVBoxLayout(group)

        # Table
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([
            self.loc.get_text("batch_col_sam2"),
            self.loc.get_text("batch_col_folder"),
            self.loc.get_text("batch_col_ref_frame"),
            self.loc.get_text("batch_col_tracked_points_file"),
        ])
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(self.COL_SAM2,      QHeaderView.Stretch)
        hh.setSectionResizeMode(self.COL_FOLDER,    QHeaderView.Stretch)
        hh.setSectionResizeMode(self.COL_REF_FRAME, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(self.COL_TRACKED_POINTS, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setToolTip(
            "Double-click a cell to edit directly.\n"
            "Leave 'Ref Frame' empty to use the first frame with points."
        )
        v.addWidget(self.table)

        # Row-management buttons
        btn_row = QHBoxLayout()
        for key, slot in [
            ("batch_add_row",       self.add_empty_row),
            ("batch_remove_row",    self.remove_selected_rows),
            ("batch_browse_sam2",   self.browse_sam2),
            ("batch_browse_folder", self.browse_folder),
            ("batch_browse_tracked_points", self.browse_tracked_points),
        ]:
            btn = QPushButton(self.loc.get_text(key))
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)

        btn_row.addStretch()

        for key, slot in [
            ("batch_import_tsv", self.import_tsv),
            ("batch_export_tsv", self.export_tsv),
        ]:
            btn = QPushButton(self.loc.get_text(key))
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)

        v.addLayout(btn_row)
        return group

    def _build_options_group(self):
        group = QGroupBox(self.loc.get_text("batch_options"))
        grid = QGridLayout(group)

        # Checkboxes  (label, attribute, default, row, col)
        checks = [
            (self.loc.get_text("batch_opt_propagate"),        'opt_propagate',            True,  0, 0),
            (self.loc.get_text("batch_opt_export_images"),    'opt_export_images',        True,  0, 1),
            (self.loc.get_text("export_centroids"),           'opt_export_centroids',     True,  1, 0),
            (self.loc.get_text("export_coordinates"),         'opt_export_coords',        True,  1, 1),
            (self.loc.get_text("batch_opt_state_predict"),    'opt_export_state_predict', False, 2, 0),
            (self.loc.get_text("batch_opt_state_prop"),       'opt_export_state_prop',    False, 2, 1),
            (self.loc.get_text("batch_opt_export_hull"),      'opt_export_hull_coords',   False, 3, 0),
            (self.loc.get_text("batch_opt_export_contour"),   'opt_export_contour_coords', False, 3, 1),
        ]
        for label, attr, default, row, col in checks:
            cb = QCheckBox(label)
            cb.setChecked(default)
            setattr(self, attr, cb)
            grid.addWidget(cb, row, col)


        # Hull smoothing (enabled only when export hull coords is checked)
        hull_smooth_widget = QWidget()
        hs_layout = QHBoxLayout(hull_smooth_widget)
        hs_layout.setContentsMargins(0, 0, 0, 0)
        hs_layout.addWidget(QLabel(self.loc.get_text("hull_smoothing")))
        self.hull_smoothing_slider = _FusionSlider(Qt.Horizontal)
        self.hull_smoothing_slider.setRange(0, 100)
        self.hull_smoothing_slider.setValue(0)
        self.hull_smoothing_label = QLabel("0")
        self.hull_smoothing_slider.valueChanged.connect(
            lambda v: self.hull_smoothing_label.setText(str(v))
        )
        hs_layout.addWidget(self.hull_smoothing_slider)
        hs_layout.addWidget(self.hull_smoothing_label)
        hull_smooth_widget.setEnabled(False)
        grid.addWidget(hull_smooth_widget, 4, 0, 1, 2)

        self.opt_export_hull_coords.toggled.connect(hull_smooth_widget.setEnabled)

        # Contour smoothing (enabled only when export contour coords is checked)
        contour_smooth_widget = QWidget()
        cs_layout = QHBoxLayout(contour_smooth_widget)
        cs_layout.setContentsMargins(0, 0, 0, 0)
        cs_layout.addWidget(QLabel(self.loc.get_text("contour_smoothing")))
        self.contour_smoothing_slider = _FusionSlider(Qt.Horizontal)
        self.contour_smoothing_slider.setRange(0, 100)
        self.contour_smoothing_slider.setValue(0)
        self.contour_smoothing_label = QLabel("0")
        self.contour_smoothing_slider.valueChanged.connect(
            lambda v: self.contour_smoothing_label.setText(str(v))
        )
        cs_layout.addWidget(self.contour_smoothing_slider)
        cs_layout.addWidget(self.contour_smoothing_label)
        contour_smooth_widget.setEnabled(False)
        grid.addWidget(contour_smooth_widget, 5, 0, 1, 2)

        self.opt_export_contour_coords.toggled.connect(contour_smooth_widget.setEnabled)

        # Background opacity (enabled only when export images is checked)
        bg_widget = QWidget()
        bg_layout = QHBoxLayout(bg_widget)
        bg_layout.setContentsMargins(0, 0, 0, 0)
        bg_layout.addWidget(QLabel(self.loc.get_text("background_opacity")))
        self.bg_opacity_slider = _FusionSlider(Qt.Horizontal)
        self.bg_opacity_slider.setRange(0, 100)
        self.bg_opacity_slider.setValue(100)
        self.bg_opacity_label = QLabel("100%")
        self.bg_opacity_slider.valueChanged.connect(
            lambda v: self.bg_opacity_label.setText(f"{v}%")
        )
        bg_layout.addWidget(self.bg_opacity_slider)
        bg_layout.addWidget(self.bg_opacity_label)
        grid.addWidget(bg_widget, 6, 0, 1, 2)  # row 6

        self.opt_export_images.toggled.connect(bg_widget.setEnabled)

        return group

    def _build_output_row(self):
        row = QHBoxLayout()
        row.addWidget(QLabel(self.loc.get_text("batch_output_folder")))
        self.output_path_edit = QLineEdit()
        self.output_path_edit.setPlaceholderText(self.loc.get_text("batch_output_placeholder"))
        self.output_path_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        browse_out = QPushButton(self.loc.get_text("batch_browse"))
        browse_out.clicked.connect(self.browse_output_folder)
        row.addWidget(self.output_path_edit)
        row.addWidget(browse_out)
        return row

    def _build_ref_points_group(self):
        """Tab 2 content: reference point pair selection and closest-points export checkbox."""
        group = QGroupBox(self.loc.get_text("batch_tab_ref_points"))
        v = QVBoxLayout(group)

        # Export checkbox — always enabled, controls the rest
        self.opt_export_closest_points = QCheckBox(
            self.loc.get_text("batch_opt_closest_points")
        )
        self.opt_export_closest_points.setChecked(False)
        v.addWidget(self.opt_export_closest_points)
    
        # Container for everything else — toggled by the checkbox above
        self._ref_options_widget = QWidget()
        rv = QVBoxLayout(self._ref_options_widget)
        rv.setContentsMargins(0, 0, 0, 0)
        self._ref_options_widget.setEnabled(False)

        # Mode selection
        mode_row = QHBoxLayout()
        self.ref_all_pairs_radio = QRadioButton(self.loc.get_text("batch_all_pairs"))
        self.ref_sel_pairs_radio = QRadioButton(self.loc.get_text("batch_selected_pairs"))
        self.ref_all_pairs_radio.setChecked(True)
        ref_mode_grp = QButtonGroup(self)
        ref_mode_grp.addButton(self.ref_all_pairs_radio)
        ref_mode_grp.addButton(self.ref_sel_pairs_radio)
        mode_row.addWidget(self.ref_all_pairs_radio)
        mode_row.addWidget(self.ref_sel_pairs_radio)
        mode_row.addStretch()
        rv.addLayout(mode_row)

        # Pairs table (Object | Target | Target Type) — enabled only when "Selected pairs"
        self.ref_pairs_table = QTableWidget(0, 3)
        self.ref_pairs_table.setHorizontalHeaderLabels([
            self.loc.get_text("batch_col_object"),
            self.loc.get_text("batch_col_ref_point"),
            self.loc.get_text("batch_col_target_type"),
        ])
        hh = self.ref_pairs_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.ref_pairs_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.ref_pairs_table.setEnabled(False)
        rv.addWidget(self.ref_pairs_table)

        # Table management + TSV import/export buttons
        btn_row = QHBoxLayout()
        self._add_pair_btn = QPushButton(self.loc.get_text("add_ref_point_btn"))
        self._add_pair_btn.clicked.connect(self._add_ref_pair)
        self._add_pair_btn.setEnabled(False)
        self._rem_pair_btn = QPushButton(self.loc.get_text("remove_ref_point_btn"))
        self._rem_pair_btn.clicked.connect(self._remove_ref_pair)
        self._rem_pair_btn.setEnabled(False)
        self._import_pairs_btn = QPushButton(self.loc.get_text("batch_ref_pairs_tsv_import"))
        self._import_pairs_btn.clicked.connect(self._import_ref_pairs_tsv)
        self._import_pairs_btn.setEnabled(False)
        self._export_pairs_btn = QPushButton(self.loc.get_text("batch_ref_pairs_tsv_export"))
        self._export_pairs_btn.clicked.connect(self._export_ref_pairs_tsv)
        for w in (self._add_pair_btn, self._rem_pair_btn):
            btn_row.addWidget(w)
        btn_row.addStretch()
        for w in (self._import_pairs_btn, self._export_pairs_btn):
            btn_row.addWidget(w)
        rv.addLayout(btn_row)

        # Include inter-object distances
        self.opt_include_obj_dist = QCheckBox(self.loc.get_text("include_object_distances"))
        self.opt_include_obj_dist.setChecked(False)
        rv.addWidget(self.opt_include_obj_dist)

        v.addWidget(self._ref_options_widget)

        # Wire mode toggle
        self.ref_all_pairs_radio.toggled.connect(self._on_ref_mode_changed)
        self.opt_export_closest_points.toggled.connect(self._ref_options_widget.setEnabled)
        return group

    def _on_ref_mode_changed(self, all_checked):
        """Enable/disable pair table controls based on selected mode."""
        for w in (self.ref_pairs_table, self._add_pair_btn,
                  self._rem_pair_btn, self._import_pairs_btn):
            w.setEnabled(not all_checked)

    def _add_ref_pair(self):
        row = self.ref_pairs_table.rowCount()
        self.ref_pairs_table.insertRow(row)
        self.ref_pairs_table.setItem(row, 0, QTableWidgetItem(""))
        self.ref_pairs_table.setItem(row, 1, QTableWidgetItem(""))
        combo = QComboBox()
        combo.addItem(self.loc.get_text("target_type_ref"), 'ref_point')
        combo.addItem(self.loc.get_text("target_type_obj"), 'object')
        self.ref_pairs_table.setCellWidget(row, 2, combo)

    def _remove_ref_pair(self):
        for row in sorted(
            {i.row() for i in self.ref_pairs_table.selectedIndexes()}, reverse=True
        ):
            self.ref_pairs_table.removeRow(row)

    def _import_ref_pairs_tsv(self):
        """Import (object, ref_point) pairs from a TSV file."""
        path, _ = QFileDialog.getOpenFileName(
            self, self.loc.get_text("batch_ref_pairs_tsv_import"), "",
            build_file_filter(self.loc, 'tsv', 'all')
        )
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8',newline='') as f:
                for rd in csv.DictReader(f, delimiter='\t'):
                    obj    = rd.get('object', '').strip()
                    target = (rd.get('target') or rd.get('ref_point', '')).strip()
                    t_type = rd.get('target_type', 'ref_point').strip()
                    if obj or target:
                        r = self.ref_pairs_table.rowCount()
                        self.ref_pairs_table.insertRow(r)
                        self.ref_pairs_table.setItem(r, 0, QTableWidgetItem(obj))
                        self.ref_pairs_table.setItem(r, 1, QTableWidgetItem(target))
                        combo = QComboBox()
                        combo.addItem(self.loc.get_text("target_type_ref"), 'ref_point')
                        combo.addItem(self.loc.get_text("target_type_obj"), 'object')
                        if t_type == 'object':
                            combo.setCurrentIndex(1)
                        self.ref_pairs_table.setCellWidget(r, 2, combo)
        except Exception as e:
            QMessageBox.critical(self, self.loc.get_text("batch_import_error"), str(e))

    def _export_ref_pairs_tsv(self):
        """Export (object, ref_point) pairs to a TSV file."""
        path, _ = QFileDialog.getSaveFileName(
            self, self.loc.get_text("batch_ref_pairs_tsv_export"), "ref_pairs.tsv",
            build_file_filter(self.loc, 'tsv', 'all')
        )
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(
                    f, fieldnames=['object', 'target', 'target_type'], delimiter='\t'
                )
                writer.writeheader()
                for row in range(self.ref_pairs_table.rowCount()):
                    oi    = self.ref_pairs_table.item(row, 0)
                    ri    = self.ref_pairs_table.item(row, 1)
                    combo = self.ref_pairs_table.cellWidget(row, 2)
                    writer.writerow({
                        'object':      oi.text().strip() if oi else '',
                        'target':      ri.text().strip() if ri else '',
                        'target_type': combo.currentData() if combo else 'ref_point',
                    })
        except Exception as e:
            QMessageBox.critical(self, self.loc.get_text("batch_export_error"), str(e))

    def _build_imported_points_group(self):
        """Tab 3 content: imported point pair selection and point/mask analysis export checkbox."""
        group = QGroupBox(self.loc.get_text("batch_tab_imported_points"))
        v = QVBoxLayout(group)
    
        self.opt_export_point_mask_analysis = QCheckBox(
            self.loc.get_text("batch_opt_export_point_mask_analysis")
        )
        self.opt_export_point_mask_analysis.setChecked(False)
        v.addWidget(self.opt_export_point_mask_analysis)
    
        self._imported_options_widget = QWidget()
        iv = QVBoxLayout(self._imported_options_widget)
        iv.setContentsMargins(0, 0, 0, 0)
        self._imported_options_widget.setEnabled(False)
    
        mode_row = QHBoxLayout()
        self.imported_all_pairs_radio = QRadioButton(self.loc.get_text("batch_all_pairs"))
        self.imported_sel_pairs_radio = QRadioButton(self.loc.get_text("batch_selected_pairs"))
        self.imported_all_pairs_radio.setChecked(True)
        imported_mode_grp = QButtonGroup(self)
        imported_mode_grp.addButton(self.imported_all_pairs_radio)
        imported_mode_grp.addButton(self.imported_sel_pairs_radio)
        mode_row.addWidget(self.imported_all_pairs_radio)
        mode_row.addWidget(self.imported_sel_pairs_radio)
        mode_row.addStretch()
        iv.addLayout(mode_row)
    
        # Pairs table (Object | Imported Point) — no target-type combo needed,
        # the target type is always TARGET_IMPORTED for this export
        self.imported_pairs_table = QTableWidget(0, 2)
        self.imported_pairs_table.setHorizontalHeaderLabels([
            self.loc.get_text("batch_col_object"),
            self.loc.get_text("batch_col_imported_point"),
        ])
        hh = self.imported_pairs_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        self.imported_pairs_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.imported_pairs_table.setEnabled(False)
        iv.addWidget(self.imported_pairs_table)
    
        btn_row = QHBoxLayout()
        self._add_imported_pair_btn = QPushButton(self.loc.get_text("add_ref_point_btn"))
        self._add_imported_pair_btn.clicked.connect(self._add_imported_pair)
        self._add_imported_pair_btn.setEnabled(False)
        self._rem_imported_pair_btn = QPushButton(self.loc.get_text("remove_ref_point_btn"))
        self._rem_imported_pair_btn.clicked.connect(self._remove_imported_pair)
        self._rem_imported_pair_btn.setEnabled(False)
        self._import_imported_pairs_btn = QPushButton(self.loc.get_text("batch_ref_pairs_tsv_import"))
        self._import_imported_pairs_btn.clicked.connect(self._import_imported_pairs_tsv)
        self._import_imported_pairs_btn.setEnabled(False)
        self._export_imported_pairs_btn = QPushButton(self.loc.get_text("batch_ref_pairs_tsv_export"))
        self._export_imported_pairs_btn.clicked.connect(self._export_imported_pairs_tsv)
        for w in (self._add_imported_pair_btn, self._rem_imported_pair_btn):
            btn_row.addWidget(w)
        btn_row.addStretch()
        for w in (self._import_imported_pairs_btn, self._export_imported_pairs_btn):
            btn_row.addWidget(w)
        iv.addLayout(btn_row)
    
        v.addWidget(self._imported_options_widget)
    
        self.imported_all_pairs_radio.toggled.connect(self._on_imported_mode_changed)
        self.opt_export_point_mask_analysis.toggled.connect(self._imported_options_widget.setEnabled)
        return group

    def _on_imported_mode_changed(self, all_checked):
        """Enable/disable pair table controls based on selected mode."""
        for w in (self.imported_pairs_table, self._add_imported_pair_btn,
                  self._rem_imported_pair_btn, self._import_imported_pairs_btn):
            w.setEnabled(not all_checked)

    def _add_imported_pair(self):
        row = self.imported_pairs_table.rowCount()
        self.imported_pairs_table.insertRow(row)
        self.imported_pairs_table.setItem(row, 0, QTableWidgetItem(""))
        self.imported_pairs_table.setItem(row, 1, QTableWidgetItem(""))

    def _remove_imported_pair(self):
        for row in sorted(
            {i.row() for i in self.imported_pairs_table.selectedIndexes()}, reverse=True
        ):
            self.imported_pairs_table.removeRow(row)

    def _import_imported_pairs_tsv(self):
        """Import (object, imported_point) pairs from a TSV file."""
        path, _ = QFileDialog.getOpenFileName(
            self, self.loc.get_text("batch_ref_pairs_tsv_import"), "",
            build_file_filter(self.loc, 'tsv', 'all')
        )
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8', newline='') as f:
                for rd in csv.DictReader(f, delimiter='\t'):
                    obj    = rd.get('object', '').strip()
                    target = (rd.get('target') or rd.get('imported_point', '')).strip()
                    if obj or target:
                        r = self.imported_pairs_table.rowCount()
                        self.imported_pairs_table.insertRow(r)
                        self.imported_pairs_table.setItem(r, 0, QTableWidgetItem(obj))
                        self.imported_pairs_table.setItem(r, 1, QTableWidgetItem(target))
        except Exception as e:
            QMessageBox.critical(self, self.loc.get_text("batch_import_error"), str(e))

    def _export_imported_pairs_tsv(self):
        """Export (object, imported_point) pairs to a TSV file."""
        path, _ = QFileDialog.getSaveFileName(
            self, self.loc.get_text("batch_ref_pairs_tsv_export"), "imported_pairs.tsv",
            build_file_filter(self.loc, 'tsv', 'all')
        )
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=['object', 'target'], delimiter='\t')
                writer.writeheader()
                for row in range(self.imported_pairs_table.rowCount()):
                    oi = self.imported_pairs_table.item(row, 0)
                    ri = self.imported_pairs_table.item(row, 1)
                    writer.writerow({
                        'object': oi.text().strip() if oi else '',
                        'target': ri.text().strip() if ri else '',
                    })
        except Exception as e:
            QMessageBox.critical(self, self.loc.get_text("batch_export_error"), str(e))

    def _build_progress_area(self):
        v = QVBoxLayout()

        # Optional animation, centred above everything else rather than in
        # place of any of it. Absent, the area lays out as it does without.
        animation_row, self.progress_animation = progress_animation.create_centred_row(self)
        if animation_row is not None:
            v.addLayout(animation_row)

        self.progress_label = QLabel(self.loc.get_text("batch_ready"))
        v.addWidget(self.progress_label)

        # Item-level progress (one step per batch item)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        v.addWidget(self.progress_bar)

        # Mask-level progress (per frame / per object during SAM2 tasks)
        self.mask_progress_label = QLabel("")
        self.mask_progress_bar = QProgressBar()
        self.mask_progress_bar.setValue(0)
        self.mask_progress_bar.setTextVisible(False)
        self.mask_progress_bar.setMaximumHeight(10)
        v.addWidget(self.mask_progress_label)
        v.addWidget(self.mask_progress_bar)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(120)
        v.addWidget(self.log_text)
        return v

    def _build_action_buttons(self):
        row = QHBoxLayout()
        row.addStretch()

        self.run_btn = QPushButton(self.loc.get_text("batch_run"))
        self.run_btn.setDefault(True)
        self.run_btn.clicked.connect(self.run_batch)

        self.cancel_btn = QPushButton(self.loc.get_text("cancel"))
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self.cancel_batch)

        close_btn = QPushButton(self.loc.get_text("batch_close"))
        close_btn.clicked.connect(self.close)

        for btn in (self.run_btn, self.cancel_btn, close_btn):
            row.addWidget(btn)

        return row

    # ------------------------------------------------------------------
    # Table helpers (items table — Tab 1)
    # ------------------------------------------------------------------

    def add_empty_row(self):
        self._add_row("", "", "", "")

    def _add_row(self, sam2_file, image_folder, ref_frame, tracked_points_file=""):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, self.COL_SAM2,      QTableWidgetItem(sam2_file))
        self.table.setItem(row, self.COL_FOLDER,    QTableWidgetItem(image_folder))
        self.table.setItem(row, self.COL_REF_FRAME, QTableWidgetItem(str(ref_frame)))
        self.table.setItem(row, self.COL_TRACKED_POINTS, QTableWidgetItem(tracked_points_file))

    def remove_selected_rows(self):
        rows = sorted(
            {idx.row() for idx in self.table.selectedIndexes()},
            reverse=True
        )
        for row in rows:
            self.table.removeRow(row)

    def _selected_row(self):
        """Return the index of the first selected row, or -1"""
        rows = {idx.row() for idx in self.table.selectedIndexes()}
        return min(rows) if rows else -1

    def browse_sam2(self):
        row = self._selected_row()
        if row < 0:
            QMessageBox.warning(self,
                self.loc.get_text("batch_no_selection"),
                self.loc.get_text("batch_no_selection_msg"))
            return
        path, _ = QFileDialog.getOpenFileName(
            self, self.loc.get_text("batch_select_sam2"), "",
            build_file_filter(self.loc, 'volute', 'all')
        )
        if path:
            self.table.setItem(row, self.COL_SAM2, QTableWidgetItem(path))

    def browse_folder(self):
        row = self._selected_row()
        if row < 0:
            QMessageBox.warning(self,
                self.loc.get_text("batch_no_selection"),
                self.loc.get_text("batch_no_selection_msg"))
            return
        folder = QFileDialog.getExistingDirectory(
            self, self.loc.get_text("select_folder")
        )
        if folder:
            self.table.setItem(row, self.COL_FOLDER, QTableWidgetItem(folder))

    def browse_tracked_points(self):
        row = self._selected_row()
        if row < 0:
            QMessageBox.warning(self,
                self.loc.get_text("batch_no_selection"),
                self.loc.get_text("batch_no_selection_msg"))
            return
        path, _ = QFileDialog.getOpenFileName(
            self, self.loc.get_text("batch_browse_tracked_points"), "",
            build_file_filter(self.loc, 'xlsx', 'csv', 'json', 'all')
        )
        if path:
            self.table.setItem(row, self.COL_TRACKED_POINTS, QTableWidgetItem(path))

    def browse_output_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, self.loc.get_text("select_export_folder")
        )
        if folder:
            self.output_path_edit.setText(folder)

    def _cell_text(self, row, col):
        item = self.table.item(row, col)
        return item.text().strip() if item else ""

    # ------------------------------------------------------------------
    # TSV import / export (items table)
    # ------------------------------------------------------------------

    def import_tsv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, self.loc.get_text("batch_import_tsv_title"), "",
            build_file_filter(self.loc, 'tsv', 'all')
        )
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f, delimiter='\t')
                count = 0
                for row in reader:
                    sam2   = row.get('sam2_file',    '').strip()
                    folder = row.get('image_folder', '').strip()
                    ref    = row.get('ref_frame',    '').strip()
                    tp     = row.get('tracked_points_file', '').strip()
                    if sam2 or folder:
                        self._add_row(sam2, folder, ref, tp)
                        count += 1
            self._log(self.loc.get_text("batch_imported_rows", count, os.path.basename(path)))
        except Exception as e:
            QMessageBox.critical(self, self.loc.get_text("batch_import_error"), str(e))

    def export_tsv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, self.loc.get_text("batch_export_tsv_title"), "batch_config.tsv",
            build_file_filter(self.loc, 'tsv', 'all')
        )
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8', newline='') as f:
                writer = csv.DictWriter(
                    f,
                    fieldnames=['sam2_file', 'image_folder', 'ref_frame', 'tracked_points_file'],
                    delimiter='\t'
                )
                writer.writeheader()
                for row in range(self.table.rowCount()):
                    writer.writerow({
                        'sam2_file':            self._cell_text(row, self.COL_SAM2),
                        'image_folder':         self._cell_text(row, self.COL_FOLDER),
                        'ref_frame':            self._cell_text(row, self.COL_REF_FRAME),
                        'tracked_points_file':  self._cell_text(row, self.COL_TRACKED_POINTS),
                    })
            self._log(self.loc.get_text("batch_exported_rows",
                                        self.table.rowCount(), os.path.basename(path)))
        except Exception as e:
            QMessageBox.critical(self, self.loc.get_text("batch_export_error"), str(e))

    # ------------------------------------------------------------------
    # Batch execution
    # ------------------------------------------------------------------

    def _collect_items(self):
        """Return list of (sam2_file, image_folder, ref_frame_or_None, tracked_points_file_or_None)"""
        items = []
        for row in range(self.table.rowCount()):
            sam2   = self._cell_text(row, self.COL_SAM2)
            folder = self._cell_text(row, self.COL_FOLDER)
            ref    = self._cell_text(row, self.COL_REF_FRAME)
            tp     = self._cell_text(row, self.COL_TRACKED_POINTS)
            if sam2 and folder:
                ref_frame = int(ref) if ref.isdigit() else None
                items.append((sam2, folder, ref_frame, tp or None))
        return items

    def _collect_options(self):
        opts = {
            'propagate':              self.opt_propagate.isChecked(),
            'export_images':          self.opt_export_images.isChecked(),
            'export_centroids':       self.opt_export_centroids.isChecked(),
            'export_coordinates':     self.opt_export_coords.isChecked(),
            'export_state_predict':   self.opt_export_state_predict.isChecked(),
            'export_state_propagate': self.opt_export_state_prop.isChecked(),
            'bg_opacity':             self.bg_opacity_slider.value() / 100.0,
            'export_closest_points':  self.opt_export_closest_points.isChecked(),
            'export_hull_coords':     self.opt_export_hull_coords.isChecked(),
            'hull_smoothing':         self.hull_smoothing_slider.value() / 100.0,
            'export_contour_coords':  self.opt_export_contour_coords.isChecked(),
            'contour_smoothing':      self.contour_smoothing_slider.value() / 100.0,
        }
        # Ref point pairs: None = all combinations; list = selected (object_name, ref_name)
        if self.ref_all_pairs_radio.isChecked():
            opts['ref_point_pairs'] = None
        else:
            pairs = []
            for row in range(self.ref_pairs_table.rowCount()):
                oi    = self.ref_pairs_table.item(row, 0)
                ri    = self.ref_pairs_table.item(row, 1)
                combo = self.ref_pairs_table.cellWidget(row, 2)
                if oi and ri:
                    obj_name = oi.text().strip()
                    tgt_name = ri.text().strip()
                    t_type   = combo.currentData() if combo else 'ref_point'
                    if obj_name and tgt_name:
                        pairs.append((obj_name, tgt_name, t_type))
            opts['ref_point_pairs'] = pairs or None
            opts['include_object_distances'] = self.opt_include_obj_dist.isChecked()
            
            opts['export_point_mask_analysis'] = self.opt_export_point_mask_analysis.isChecked()
            if self.imported_all_pairs_radio.isChecked():
                opts['imported_point_pairs'] = None
            else:
                pairs = []
                for row in range(self.imported_pairs_table.rowCount()):
                    oi = self.imported_pairs_table.item(row, 0)
                    ri = self.imported_pairs_table.item(row, 1)
                    if oi and ri:
                        obj_name = oi.text().strip()
                        tgt_name = ri.text().strip()
                        if obj_name and tgt_name:
                            pairs.append((obj_name, tgt_name))
                opts['imported_point_pairs'] = pairs or None
            
            return opts

    def run_batch(self):
        items = self._collect_items()
        if not items:
            QMessageBox.warning(self,
                self.loc.get_text("batch_no_items"),
                self.loc.get_text("batch_no_items_msg"))
            return

        output_dir = self.output_path_edit.text().strip()
        if not output_dir:
            QMessageBox.warning(self,
                self.loc.get_text("batch_no_output"),
                self.loc.get_text("batch_no_output_msg"))
            return

        # Validate paths
        bad = []
        for sam2, folder, _, _ in items:
            if not os.path.isfile(sam2):
                bad.append(f"File not found: {sam2}")
            if not os.path.isdir(folder):
                bad.append(f"Folder not found: {folder}")
        if bad:
            QMessageBox.critical(self,
                self.loc.get_text("batch_invalid_paths"),
                "\n".join(bad[:5]))
            return

        os.makedirs(output_dir, exist_ok=True)

        self.run_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.log_text.clear()
        self.progress_bar.setRange(0, len(items))
        self.progress_bar.setValue(0)
        self._log(self.loc.get_text("batch_starting", len(items)))

        self.worker = BatchWorker(
            self.processor, items, self._collect_options(), output_dir, self
        )
        self.worker.progress.connect(self._log)
        self.worker.mask_progress.connect(self._on_mask_progress)
        self.worker.item_done.connect(self._on_item_done)
        self.worker.finished.connect(self._on_batch_finished)
        self.worker.start()
        progress_animation.start(self.progress_animation)

    def cancel_batch(self):
        if self.worker:
            self.worker.cancel()
            self._log(self.loc.get_text("batch_cancel_requested"))

    def _on_mask_progress(self, current, total, label):
        if total > 0:
            self.mask_progress_bar.setRange(0, total)
            self.mask_progress_bar.setValue(current)
        self.mask_progress_label.setText(label)

    def _on_item_done(self, idx, total, result):
        self.progress_bar.setValue(idx + 1)
        folder = os.path.basename(result.get('output_folder', ''))
        status = (self.loc.get_text("batch_status_ok")
                  if result['success']
                  else self.loc.get_text("batch_status_errors"))
        stats  = ", ".join(f"{k}={v}" for k, v in result.get('stats', {}).items())
        msg    = f"[{idx + 1}/{total}] {folder}: {status}"
        if stats:
            msg += f"  ({stats})"
        if result['errors']:
            msg += f"\n  ! {'; '.join(result['errors'][:3])}"
        if result.get('warnings'):
            msg += f"\n  ⚠ {'; '.join(result['warnings'][:3])}"
        self._log(msg)

    def _on_batch_finished(self, results):
        progress_animation.stop(self.progress_animation)
        self.run_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        success = sum(1 for r in results if r['success'])
        self._log(self.loc.get_text("batch_complete", success, len(results)))
        self.progress_bar.setValue(self.progress_bar.maximum())

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _log(self, msg):
        self.log_text.appendPlainText(msg)
        self.progress_label.setText(msg.split('\n')[0])

    def closeEvent(self, event):
        progress_animation.stop(self.progress_animation)
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(3000)
        event.accept()
