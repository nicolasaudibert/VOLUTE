"""
Video Frames UI
UI-facing half of frame extraction: the dialog gathering the extraction
options, and the controller that runs FFmpegManager.extract_frames() behind a
progress dialog, records beside the frames the video they came from, then
offers to load them.
"""

import json
import os

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSpinBox, QDoubleSpinBox, QRadioButton,
    QCheckBox, QDialogButtonBox, QFileDialog, QMessageBox, QWidget,
)
from PyQt5.QtCore import Qt, QDir, QLocale

from .dialogs import localized_question
from .ffmpeg_manager import (
    NO_FRAMES_MESSAGE, folder_has_images, frame_number_width,
)
from .file_utils import build_file_filter
from .gimp_export_manager import STATUS_OK, STATUS_CANCELLED, STATUS_ERROR
from .progress_dialog import AnimatedProgressDialog
from .progress_worker import run_with_progress


# Stem given to the frames when the video's own name leaves nothing usable
DEFAULT_STEM = "frame"

# Suffix of the destination folder suggested beside the video
DESTINATION_SUFFIX = "_frames"

# Upper bound of the time fields when the video's duration is unknown
MAX_SECONDS = 24 * 3600.0

# Written into a folder of extracted frames: the video they came from, the
# frame rate they were extracted at (None: every frame) and the time of the
# first one, in seconds
SOURCE_FILE = "volute_source.json"


def read_video_source(folder):
    """The source record of a folder of extracted frames, or None."""
    try:
        with open(os.path.join(folder, SOURCE_FILE), encoding='utf-8') as f:
            source = json.load(f)
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(source, dict) or not source.get('video'):
        return None
    return {'video': source['video'], 'fps': source.get('fps'),
            'start': float(source.get('start') or 0.0)}


def write_video_source(folder, video, fps=None, start=None):
    """Record in folder the video its frames were extracted from. A failure
    to write it is silent: only the video export's defaults depend on it."""
    try:
        with open(os.path.join(folder, SOURCE_FILE), 'w', encoding='utf-8') as f:
            json.dump({'video': os.path.abspath(video), 'fps': fps,
                       'start': float(start or 0.0)}, f, indent=2)
    except OSError:
        pass


def frame_stem(video_path):
    """Stem of the extracted frames' names: the video's name without its
    extension."""
    stem = os.path.splitext(os.path.basename(video_path))[0].strip()
    return stem or DEFAULT_STEM


class DecimalSpinBox(QDoubleSpinBox):
    """QDoubleSpinBox taking a point or a comma as decimal separator,
    whatever its locale, and turning either into the locale's as it is typed.
    Its text carries no group separator for the comma to be mistaken for."""

    def validate(self, text, pos):
        point = self.locale().decimalPoint()
        for separator in '.,':
            text = text.replace(separator, point)
        return super().validate(text, pos)


class VideoFramesDialog(QDialog):
    """Options of a frame extraction: video, destination, image format and
    JPEG quality, frame rate, and an optional time range. Probes the video
    as soon as it is chosen, to show its properties, bound the time range
    and preview the frame names."""

    def __init__(self, localization, ffmpeg_manager, parent=None):
        super().__init__(parent)
        self.loc = localization
        self.ffmpeg_manager = ffmpeg_manager
        self.info = None
        self._suggested_destination = None
        # Numbers follow the interface language's conventions, decimal
        # separator included; values themselves stay plain floats
        self.number_locale = QLocale(localization.current_language)
        self.number_locale.setNumberOptions(QLocale.OmitGroupSeparator)
        self.setWindowTitle(localization.get_text("video_frames_title"))
        self.setMinimumWidth(680)
        self._build()
        self._update_enabled()
        self._update_preview()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _path_row(self, browse_slot):
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        line_edit = QLineEdit()
        row.addWidget(line_edit)
        browse = QPushButton(self.loc.get_text("settings_browse"))
        # Otherwise it becomes the default button whenever its field has the
        # focus, and Return browses instead of confirming the dialog
        browse.setAutoDefault(False)
        browse.clicked.connect(browse_slot)
        row.addWidget(browse)
        return line_edit, container

    def _build(self):
        loc = self.loc
        layout = QVBoxLayout(self)
        grid = QGridLayout()
        layout.addLayout(grid)

        self.video_edit, video_row = self._path_row(self._browse_video)
        self.video_edit.editingFinished.connect(self._video_changed)
        grid.addWidget(QLabel(loc.get_text("video_frames_video")), 0, 0)
        grid.addWidget(video_row, 0, 1)

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: gray;")
        grid.addWidget(self.info_label, 1, 1)

        self.destination_edit, destination_row = self._path_row(self._browse_destination)
        grid.addWidget(QLabel(loc.get_text("video_frames_destination")), 2, 0)
        grid.addWidget(destination_row, 2, 1)

        self.format_combo = QComboBox()
        self.format_combo.addItem(loc.get_text("video_frames_format_jpg"), 'jpg')
        self.format_combo.addItem(loc.get_text("video_frames_format_png"), 'png')
        self.format_combo.currentIndexChanged.connect(self._update_enabled)
        self.format_combo.currentIndexChanged.connect(self._update_preview)
        grid.addWidget(QLabel(loc.get_text("video_frames_format")), 3, 0)
        grid.addWidget(self.format_combo, 3, 1)

        self.quality_spin = QSpinBox()
        self.quality_spin.setRange(1, 100)
        self.quality_spin.setValue(95)
        self.quality_label = QLabel(loc.get_text("video_frames_quality"))
        grid.addWidget(self.quality_label, 4, 0)
        grid.addWidget(self.quality_spin, 4, 1, Qt.AlignLeft)

        rate_row = QHBoxLayout()
        self.rate_all = QRadioButton(loc.get_text("video_frames_rate_all"))
        self.rate_all.setChecked(True)
        self.rate_fps = QRadioButton(loc.get_text("video_frames_rate_fps"))
        self.fps_spin = DecimalSpinBox()
        self.fps_spin.setLocale(self.number_locale)
        self.fps_spin.setDecimals(2)
        self.fps_spin.setRange(0.01, 1000.0)
        self.fps_spin.setValue(5.0)
        for widget in (self.rate_all, self.rate_fps, self.fps_spin):
            rate_row.addWidget(widget)
        rate_row.addStretch(1)
        for signal in (self.rate_all.toggled, self.fps_spin.valueChanged):
            signal.connect(self._update_enabled)
            signal.connect(self._update_preview)
        grid.addWidget(QLabel(loc.get_text("video_frames_rate")), 5, 0)
        grid.addLayout(rate_row, 5, 1)

        self.start_check, self.start_spin = self._time_field()
        self.end_check, self.end_spin = self._time_field()
        range_row = QHBoxLayout()
        self.start_check.setText(loc.get_text("video_frames_start"))
        self.end_check.setText(loc.get_text("video_frames_end"))
        for widget in (self.start_check, self.start_spin, self.end_check, self.end_spin):
            range_row.addWidget(widget)
        range_row.addStretch(1)
        grid.addWidget(QLabel(loc.get_text("video_frames_range")), 6, 0)
        grid.addLayout(range_row, 6, 1)

        self.preview_label = QLabel()
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("color: gray;")
        grid.addWidget(self.preview_label, 7, 1)

        buttons = QDialogButtonBox()
        extract = buttons.addButton(loc.get_text("video_frames_extract"),
                                    QDialogButtonBox.AcceptRole)
        extract.setDefault(True)
        buttons.addButton(loc.get_text("cancel"), QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _time_field(self):
        """Checkbox enabling a time in seconds, and the spin box holding it"""
        check = QCheckBox()
        spin = DecimalSpinBox()
        spin.setLocale(self.number_locale)
        spin.setDecimals(3)
        spin.setRange(0.0, MAX_SECONDS)
        spin.setSuffix(" s")
        for signal in (check.toggled, spin.valueChanged):
            signal.connect(self._update_enabled)
            signal.connect(self._update_preview)
        return check, spin

    def _update_enabled(self):
        is_jpeg = self.format_combo.currentData() == 'jpg'
        self.quality_label.setEnabled(is_jpeg)
        self.quality_spin.setEnabled(is_jpeg)
        self.fps_spin.setEnabled(self.rate_fps.isChecked())
        self.start_spin.setEnabled(self.start_check.isChecked())
        self.end_spin.setEnabled(self.end_check.isChecked())

    # ------------------------------------------------------------------
    # Video and destination
    # ------------------------------------------------------------------

    def _browse_video(self):
        start = os.path.dirname(self.video_edit.text()) or QDir.homePath()
        path, _ = QFileDialog.getOpenFileName(
            self, self.loc.get_text("video_frames_select_video"), start,
            build_file_filter(self.loc, 'video', 'all'))
        if path:
            self.video_edit.setText(path)
            self._video_changed()

    def _browse_destination(self):
        start = self.destination_edit.text() or os.path.dirname(self.video_edit.text())
        folder = QFileDialog.getExistingDirectory(
            self, self.loc.get_text("video_frames_select_destination"),
            start or QDir.homePath())
        if folder:
            self.destination_edit.setText(folder)

    def _video_changed(self):
        path = self.video_edit.text().strip()
        self.info = None
        if not path or not os.path.isfile(path):
            self.info_label.setText("")
            self._update_preview()
            return

        # A destination the person typed or picked is left alone; one this
        # dialog suggested follows the video
        destination = self.destination_edit.text().strip()
        if not destination or destination == self._suggested_destination:
            self._suggested_destination = os.path.join(
                os.path.dirname(path), frame_stem(path) + DESTINATION_SUFFIX)
            self.destination_edit.setText(self._suggested_destination)

        try:
            self.info = self.ffmpeg_manager.probe_video(path)
        except RuntimeError as e:
            self.info_label.setText(self.loc.get_text("video_frames_probe_failed", str(e)))
            self._update_preview()
            return
        if self.info is None:
            self.info_label.setText(self.loc.get_text("video_frames_no_ffprobe"))
        else:
            self.info_label.setText(self._describe(self.info))
            duration = self.info.get('duration')
            for spin in (self.start_spin, self.end_spin):
                spin.setMaximum(duration or MAX_SECONDS)
            if duration and not self.end_check.isChecked():
                self.end_spin.setValue(duration)
        self._update_preview()

    def _number(self, value, fmt, precision):
        """value formatted as QLocale.toString() does, in the interface
        language"""
        return self.number_locale.toString(float(value), fmt, precision)

    def _describe(self, info):
        def shown(value, fmt):
            return fmt(value) if value else "?"
        size = (f"{info['width']}×{info['height']}"
                if info.get('width') and info.get('height') else "?")
        return self.loc.get_text(
            "video_frames_info",
            shown(info.get('duration'), lambda v: self._number(v, 'f', 2)),
            shown(info.get('fps'), lambda v: self._number(v, 'g', 3)),
            shown(info.get('frame_count'), str),
            size,
        )

    # ------------------------------------------------------------------
    # Options
    # ------------------------------------------------------------------

    def _fps(self):
        return self.fps_spin.value() if self.rate_fps.isChecked() else None

    def _start(self):
        return self.start_spin.value() if self.start_check.isChecked() else None

    def _end(self):
        return self.end_spin.value() if self.end_check.isChecked() else None

    def _expected_frames(self):
        return self.ffmpeg_manager.estimate_frame_count(
            self.info, fps=self._fps(), start=self._start(), end=self._end())

    def _update_preview(self):
        """Show the names the first frames will get, and how many frames to
        expect when the video could be probed."""
        path = self.video_edit.text().strip()
        if not path:
            self.preview_label.setText("")
            return
        expected = self._expected_frames()
        width = frame_number_width(expected or 1)
        ext = self.format_combo.currentData()
        stem = frame_stem(path)
        first, second = (f"{stem}_{i:0{width}d}.{ext}" for i in (0, 1))
        if expected:
            self.preview_label.setText(
                self.loc.get_text("video_frames_preview", expected, first, second))
        else:
            self.preview_label.setText(
                self.loc.get_text("video_frames_preview_unknown", first, second))

    def _validation_error(self):
        """Localized reason the options cannot be used, or None."""
        video = self.video_edit.text().strip()
        if not video or not os.path.isfile(video):
            return self.loc.get_text("video_frames_no_video")
        destination = self.destination_edit.text().strip()
        if not destination:
            return self.loc.get_text("video_frames_no_destination")
        if os.path.exists(destination) and not os.path.isdir(destination):
            return self.loc.get_text("video_frames_destination_not_folder")
        if folder_has_images(destination):
            return self.loc.get_text("video_frames_destination_has_images")
        start, end = self._start(), self._end()
        if start is not None and end is not None and end <= start:
            return self.loc.get_text("video_frames_bad_range")
        duration = self.info.get('duration') if self.info else None
        if start is not None and duration and start >= duration:
            return self.loc.get_text("video_frames_start_past_end",
                                     self._number(duration, 'f', 2))
        return None

    def accept(self):
        error = self._validation_error()
        if error:
            QMessageBox.warning(self, self.loc.get_text("warning"), error)
            return
        super().accept()

    def get_options(self):
        """Keyword arguments for FFmpegManager.extract_frames()."""
        video = self.video_edit.text().strip()
        return {
            'video_path': video,
            'output_folder': os.path.abspath(self.destination_edit.text().strip()),
            'stem': frame_stem(video),
            'fmt': self.format_combo.currentData(),
            'quality': self.quality_spin.value(),
            'fps': self._fps(),
            'start': self._start(),
            'end': self._end(),
            'expected_frames': self._expected_frames(),
        }


class VideoFramesController:
    """File › Extract Frames from Video…: checks that ffmpeg is there, asks
    for the options, extracts behind a progress dialog, and offers to load
    the result."""

    def __init__(self, main_window):
        self.main_window = main_window

    def extract_video_frames(self):
        mw = self.main_window
        loc = mw.localization
        manager = mw.ffmpeg_manager

        # Detected afresh each time, so that installing ffmpeg or setting its
        # path in the settings takes effect without restarting
        if not manager.is_available(force=True):
            override = mw.config_manager.get_ffmpeg_path()
            message = (loc.get_text("video_frames_ffmpeg_override_invalid", override)
                       if override else loc.get_text("video_frames_ffmpeg_missing"))
            mw.ui_manager.show_message("warning", loc.get_text("warning"), message)
            return

        dialog = VideoFramesDialog(loc, manager, mw)
        if dialog.exec_() != QDialog.Accepted:
            return
        options = dialog.get_options()

        status, message, count = self._run(options)

        if status == STATUS_CANCELLED:
            mw.ui_manager.show_message("info", loc.get_text("video_frames_title"),
                                       loc.get_text("video_frames_cancelled"))
            return
        if status != STATUS_OK:
            if message == NO_FRAMES_MESSAGE:
                text = loc.get_text("video_frames_none")
            else:
                text = loc.get_text("video_frames_failed", message)
            mw.ui_manager.show_message("error", loc.get_text("error"), text)
            return

        folder = options['output_folder']
        # For the video export to start from this video's frame rate, format
        # and audio when these frames are loaded
        write_video_source(folder, options['video_path'], fps=options['fps'],
                           start=options['start'])
        answer = localized_question(
            mw, loc, loc.get_text("video_frames_title"),
            loc.get_text("video_frames_done_load", count, folder),
            default=QMessageBox.Yes, icon=QMessageBox.Information,
        )
        if answer == QMessageBox.Yes:
            mw.image_manager.current_folder = folder
            mw.ui_manager.set_folder_label(folder)
            mw.load_images_from_folder(folder)

    def _run(self, options):
        """Run the extraction in a worker thread behind a modal progress
        dialog; returns extract_frames()'s (status, message, count)."""
        mw = self.main_window
        loc = mw.localization
        video_name = os.path.basename(options['video_path'])
        total = options['expected_frames'] or 0

        progress = AnimatedProgressDialog(
            loc.get_text("video_frames_progress", video_name, 0),
            loc.get_text("cancel"), 0, total, mw,
        )
        progress.setWindowTitle(loc.get_text("video_frames_title"))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        # Reaching the maximum would otherwise reset and hide the dialog while
        # the frames are still being renamed; it is closed explicitly instead
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setValue(0)
        progress.show()

        finished = [False]

        def on_report(done, expected):
            # Reports still queued when cancel was clicked would hide the
            # cancellation notice
            if progress.wasCanceled():
                return
            progress.setLabelText(loc.get_text("video_frames_progress", video_name, done))
            if expected:
                if expected != progress.maximum():
                    progress.setMaximum(expected)
                progress.setValue(min(done, expected))

        def on_cancel():
            # close() also emits canceled(): ignore it once the task is done
            if finished[0]:
                return
            # cancel() hides the dialog at once; keep it up, and modal, until
            # ffmpeg has actually stopped and its frames are removed
            progress.setLabelText(loc.get_text("progress_cancelled"))
            progress.show()

        def task(report, is_cancelled):
            return mw.ffmpeg_manager.extract_frames(
                report=report, is_cancelled=is_cancelled, **options)

        progress.canceled.connect(on_cancel)
        try:
            result = run_with_progress(progress, task, on_report)
        except Exception as e:
            result = (STATUS_ERROR, str(e), 0)
        finally:
            finished[0] = True
            progress.close()
        return result
