"""
Video Export
File › Export › Export Video with Masks… (with tracked points, in point mode):
the frames, with what the image export draws on them, encoded into a video by
ffmpeg, with the frame rate of the video they came from, and its audio track
or that of another file.

The video a frame folder was extracted from is remembered in the small file
video_frames_ui writes into that folder at extraction, in the project file,
and for the session once the export dialog has been given it; the audio
chosen at an export, in the session and the project file.
"""

import os

import numpy as np
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QSpinBox, QCheckBox, QDialogButtonBox, QFileDialog,
    QMessageBox, QWidget, QRadioButton, QButtonGroup,
)
from PyQt5.QtCore import Qt, QDir, QLocale

from .dialogs import localized_question
from .ffmpeg_manager import (
    AUDIO_CODECS, CONTAINERS, SOURCE_CODECS, VIDEO_CODECS, default_bitrate_kbps,
    default_encoding, resolve_audio_codec,
)
from .file_utils import build_file_filter
from .gimp_export_manager import STATUS_OK, STATUS_CANCELLED, STATUS_ERROR
from .progress_dialog import AnimatedProgressDialog
from .progress_worker import run_with_progress
from .video_frames_ui import DecimalSpinBox


# Labels of the containers and encodings the dialog offers
CONTAINER_LABEL_KEYS = {'mp4': 'video_export_container_mp4',
                        'mov': 'video_export_container_mov',
                        'mkv': 'video_export_container_mkv'}
CODEC_LABEL_KEYS = {'h264': 'video_export_codec_h264',
                    'h265': 'video_export_codec_h265',
                    'prores': 'video_export_codec_prores'}

AUDIO_LABEL_KEYS = {'aac': 'video_export_audio_aac', 'mp3': 'video_export_audio_mp3',
                    'opus': 'video_export_audio_opus', 'alac': 'video_export_audio_alac',
                    'flac': 'video_export_audio_flac', 'pcm16': 'video_export_audio_pcm16',
                    'pcm24': 'video_export_audio_pcm24'}

# Where an audio file is placed against the video when their durations
# differ, with their labels
PLACEMENTS = (('start', 'video_export_place_start'), ('middle', 'video_export_place_middle'),
              ('end', 'video_export_place_end'), ('offset', 'video_export_place_offset'))

# Sample rates offered, None keeping the audio's own
SAMPLE_RATES = ((None, 'video_export_rate_original'), (44100, 'video_export_rate_44100'),
                (48000, 'video_export_rate_48000'))

# Frame rate offered when nothing says what the frames were taken at
DEFAULT_FPS = 25.0

# Durations closer than this, in seconds, count as equal
DURATION_TOLERANCE = 0.0005


class VideoExportDialog(QDialog):
    """Options of a video export: the source video, whose frame rate,
    format and audio track it starts from, the frame rate, the audio — the
    source's track, another file placed against the video, or none — and its
    format, the output file, its container, encoding and bit rate."""

    def __init__(self, localization, ffmpeg_manager, source, frames_folder, frame_count,
                 frame_size, point_mode, audio_choice=None, parent=None):
        """source: the source video record (see video_frames_ui); audio_choice:
        the audio chosen at the previous export, as get_audio_choice()
        returns it, or None."""
        super().__init__(parent)
        self.loc = localization
        self.ffmpeg_manager = ffmpeg_manager
        self.frames_folder = frames_folder
        self.frame_count = frame_count
        self.frame_size = frame_size
        self.point_mode = point_mode
        self.info = None
        self.audio_info = None
        self._audio_error = None
        # Container the audio format list was last filled for
        self._audio_formats_for = None
        self._suggested_output = None
        self.number_locale = QLocale(localization.current_language)
        self.number_locale.setNumberOptions(QLocale.OmitGroupSeparator)
        self.setWindowTitle(localization.get_text(
            "video_export_title_points" if point_mode else "video_export_title"))
        self.setMinimumWidth(760)
        self._build()

        source = source or {}
        self._source_fps = source.get('fps')
        self.audio_start_spin.setValue(source.get('start') or 0.0)
        if source.get('video'):
            self.source_edit.setText(source['video'])
        self._source_changed()
        self._restore_audio_choice(audio_choice)

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
        row = 0

        self.source_edit, source_row = self._path_row(self._browse_source)
        self.source_edit.editingFinished.connect(self._source_changed)
        grid.addWidget(QLabel(loc.get_text("video_export_source")), row, 0)
        grid.addWidget(source_row, row, 1)
        row += 1

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: gray;")
        # Room for the longest description, so that the dialog keeps its size
        self.info_label.setMinimumHeight(2 * self.info_label.fontMetrics().lineSpacing())
        self.info_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        grid.addWidget(self.info_label, row, 1)
        row += 1

        self.fps_spin = DecimalSpinBox()
        self.fps_spin.setLocale(self.number_locale)
        self.fps_spin.setDecimals(3)
        self.fps_spin.setRange(0.01, 1000.0)
        self.fps_spin.setValue(DEFAULT_FPS)
        # The video's duration, and so the audio placement, follow the rate
        self.fps_spin.valueChanged.connect(lambda *_: self._update_enabled())
        grid.addWidget(QLabel(loc.get_text("video_export_fps")), row, 0)
        grid.addWidget(self.fps_spin, row, 1, Qt.AlignLeft)
        row += 1

        # Audio: the original video's track, another file, or none
        mode_row = QHBoxLayout()
        self.audio_mode_group = QButtonGroup(self)
        self.audio_radios = {}
        for mode, key in (('source', 'video_export_audio_source'),
                          ('file', 'video_export_audio_file'),
                          ('none', 'video_export_audio_none')):
            radio = QRadioButton(loc.get_text(key))
            self.audio_mode_group.addButton(radio)
            self.audio_radios[mode] = radio
            mode_row.addWidget(radio)
        mode_row.addStretch(1)
        self.audio_radios['none'].setChecked(True)
        self.audio_mode_group.buttonToggled.connect(lambda *_: self._update_enabled())
        grid.addWidget(QLabel(loc.get_text("video_export_audio_label")), row, 0)
        grid.addLayout(mode_row, row, 1)
        row += 1

        self.audio_start_label = QLabel(loc.get_text("video_export_audio_start"))
        self.audio_start_spin = DecimalSpinBox()
        self.audio_start_spin.setLocale(self.number_locale)
        self.audio_start_spin.setDecimals(3)
        self.audio_start_spin.setRange(0.0, 24 * 3600.0)
        grid.addWidget(self.audio_start_label, row, 0)
        grid.addWidget(self.audio_start_spin, row, 1, Qt.AlignLeft)
        row += 1

        self.audio_file_label = QLabel(loc.get_text("video_export_audio_file_label"))
        self.audio_file_edit, audio_file_row = self._path_row(self._browse_audio_file)
        self.audio_file_edit.editingFinished.connect(self._audio_file_changed)
        grid.addWidget(self.audio_file_label, row, 0)
        grid.addWidget(audio_file_row, row, 1)
        row += 1

        self.audio_info_label = QLabel()
        self.audio_info_label.setWordWrap(True)
        self.audio_info_label.setStyleSheet("color: gray;")
        self.audio_info_label.setMinimumHeight(self.audio_info_label.fontMetrics().lineSpacing())
        grid.addWidget(self.audio_info_label, row, 1)
        row += 1

        placement_row = QHBoxLayout()
        self.placement_label = QLabel(loc.get_text("video_export_placement"))
        self.placement_combo = QComboBox()
        for value, key in PLACEMENTS:
            self.placement_combo.addItem(loc.get_text(key), value)
        self.offset_label = QLabel(loc.get_text("video_export_offset"))
        self.offset_spin = DecimalSpinBox()
        self.offset_spin.setLocale(self.number_locale)
        self.offset_spin.setDecimals(3)
        self.offset_spin.setRange(-24 * 3600.0, 24 * 3600.0)
        self.offset_spin.setToolTip(loc.get_text("video_export_offset_tooltip"))
        self.placement_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        for widget in (self.placement_combo, self.offset_label, self.offset_spin):
            placement_row.addWidget(widget)
        placement_row.addStretch(1)
        grid.addWidget(self.placement_label, row, 0)
        grid.addLayout(placement_row, row, 1)
        row += 1

        self.loop_check = QCheckBox(loc.get_text("video_export_loop"))
        grid.addWidget(self.loop_check, row, 1)
        row += 1
        for signal in (self.placement_combo.currentIndexChanged, self.offset_spin.valueChanged,
                       self.loop_check.toggled):
            signal.connect(lambda *_: self._update_enabled())

        audio_format_row = QHBoxLayout()
        self.audio_format_label = QLabel(loc.get_text("video_export_audio_format"))
        self.audio_format_combo = QComboBox()
        self.audio_format_combo.setSizeAdjustPolicy(QComboBox.AdjustToContents)
        self.audio_format_combo.currentIndexChanged.connect(self._audio_format_changed)
        self.audio_bitrate_label = QLabel(loc.get_text("video_export_audio_bitrate"))
        self.audio_bitrate_spin = QSpinBox()
        self.audio_bitrate_spin.setRange(32, 640)
        self.audio_bitrate_spin.setSingleStep(32)
        self.audio_bitrate_spin.setSuffix(" kbit/s")
        self.audio_bitrate_spin.setValue(AUDIO_CODECS['aac']['bitrate'])
        self.sample_rate_label = QLabel(loc.get_text("video_export_sample_rate"))
        self.sample_rate_combo = QComboBox()
        for value, key in SAMPLE_RATES:
            self.sample_rate_combo.addItem(loc.get_text(key), value)
        self.sample_rate_combo.currentIndexChanged.connect(lambda *_: self._update_enabled())
        for widget in (self.audio_format_combo, self.audio_bitrate_label,
                       self.audio_bitrate_spin):
            audio_format_row.addWidget(widget)
        audio_format_row.addStretch(1)
        grid.addWidget(self.audio_format_label, row, 0)
        grid.addLayout(audio_format_row, row, 1)
        row += 1

        grid.addWidget(self.sample_rate_label, row, 0)
        grid.addWidget(self.sample_rate_combo, row, 1, Qt.AlignLeft)
        row += 1

        self.output_edit, output_row = self._path_row(self._browse_output)
        grid.addWidget(QLabel(loc.get_text("video_export_output")), row, 0)
        grid.addWidget(output_row, row, 1)
        row += 1

        format_row = QHBoxLayout()
        self.container_combo = QComboBox()
        for container in CONTAINERS:
            self.container_combo.addItem(loc.get_text(CONTAINER_LABEL_KEYS[container]), container)
        self.container_combo.currentIndexChanged.connect(self._container_changed)
        self.codec_combo = QComboBox()
        self.codec_combo.currentIndexChanged.connect(self._update_enabled)
        format_row.addWidget(self.container_combo)
        format_row.addWidget(QLabel(loc.get_text("video_export_codec")))
        format_row.addWidget(self.codec_combo)
        format_row.addStretch(1)
        grid.addWidget(QLabel(loc.get_text("video_export_container")), row, 0)
        grid.addLayout(format_row, row, 1)
        row += 1

        self.bitrate_label = QLabel(loc.get_text("video_export_bitrate"))
        self.bitrate_spin = QSpinBox()
        self.bitrate_spin.setRange(50, 500000)
        self.bitrate_spin.setSingleStep(100)
        self.bitrate_spin.setSuffix(" kbit/s")
        grid.addWidget(self.bitrate_label, row, 0)
        grid.addWidget(self.bitrate_spin, row, 1, Qt.AlignLeft)
        row += 1

        self.preview_label = QLabel()
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet("color: gray;")
        grid.addWidget(self.preview_label, row, 1)

        buttons = QDialogButtonBox()
        export = buttons.addButton(loc.get_text("video_export_export"),
                                   QDialogButtonBox.AcceptRole)
        export.setDefault(True)
        buttons.addButton(loc.get_text("cancel"), QDialogButtonBox.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._fill_codecs('h264')

    def _number(self, value, fmt, precision):
        return self.number_locale.toString(float(value), fmt, precision)

    # ------------------------------------------------------------------
    # Source, format and output
    # ------------------------------------------------------------------

    def _browse_source(self):
        start = (os.path.dirname(self.source_edit.text())
                 or os.path.dirname(self.frames_folder or '') or QDir.homePath())
        path, _ = QFileDialog.getOpenFileName(
            self, self.loc.get_text("video_frames_select_video"), start,
            build_file_filter(self.loc, 'video', 'all'))
        if path:
            self.source_edit.setText(path)
            self._source_changed()

    def _browse_output(self):
        container = self.container_combo.currentData()
        path, _ = QFileDialog.getSaveFileName(
            self, self.loc.get_text("video_export_select_output"),
            self.output_edit.text() or QDir.homePath(),
            f"{self.container_combo.currentText()} (*.{container})")
        if path:
            if not os.path.splitext(path)[1]:
                path += f".{container}"
            self.output_edit.setText(path)

    def _source_changed(self):
        """Probe the source video, then start the frame rate, audio and
        format from it; without one, leave them to the person."""
        path = self.source_edit.text().strip()
        self.info = None
        if path and os.path.isfile(path):
            try:
                self.info = self.ffmpeg_manager.probe_video(path)
            except RuntimeError as e:
                self.info_label.setText(self.loc.get_text("video_frames_probe_failed", str(e)))
        if self.info:
            self.info_label.setText(self._describe(self.info))
            fps = self._source_fps or self.info.get('fps')
            if fps:
                self.fps_spin.setValue(fps)
            container, codec = default_encoding(path, self.info)
            self.container_combo.setCurrentIndex(self.container_combo.findData(container))
            self._fill_codecs(codec)
        elif not path:
            self.info_label.setText(self.loc.get_text("video_export_no_source"))
        elif not os.path.isfile(path):
            self.info_label.setText(self.loc.get_text("video_export_source_missing"))
        if self._source_fps and not self.info:
            self.fps_spin.setValue(self._source_fps)
        # The original video's track by default when there is one; another
        # file chosen is left alone
        has_audio = bool(self.info and self.info.get('audio'))
        if has_audio and not self.audio_radios['file'].isChecked():
            self.audio_radios['source'].setChecked(True)
        elif not has_audio and self.audio_radios['source'].isChecked():
            self.audio_radios['none'].setChecked(True)
        width, height = self.frame_size
        self.bitrate_spin.setValue(default_bitrate_kbps(
            self.info, width, height, self.fps_spin.value()))
        self._suggest_output()
        self._update_enabled()

    def _describe(self, info):
        def shown(value, fmt):
            return fmt(value) if value else "?"
        audio = info.get('audio')
        if audio:
            audio_text = self.loc.get_text(
                "video_export_info_audio", (audio.get('codec') or "?").upper(),
                shown(audio.get('sample_rate'), lambda v: self._number(v, 'g', 6)))
        else:
            audio_text = self.loc.get_text("video_export_info_no_audio")
        codec = SOURCE_CODECS.get(info.get('codec'))
        return self.loc.get_text(
            "video_export_info",
            shown(info.get('duration'), lambda v: self._number(v, 'f', 2)),
            shown(info.get('fps'), lambda v: self._number(v, 'g', 4)),
            f"{info['width']}×{info['height']}" if info.get('width') else "?",
            self.loc.get_text(CODEC_LABEL_KEYS[codec]) if codec
            else (info.get('codec') or "?").upper(),
            audio_text)

    def _fill_codecs(self, preferred):
        """List the encodings the chosen container takes, keeping the
        current one, or else `preferred`, when it is among them."""
        current = self.codec_combo.currentData() or preferred
        codecs = CONTAINERS[self.container_combo.currentData()]['codecs']
        self.codec_combo.blockSignals(True)
        self.codec_combo.clear()
        for codec in codecs:
            self.codec_combo.addItem(self.loc.get_text(CODEC_LABEL_KEYS[codec]), codec)
        chosen = preferred if preferred in codecs else (current if current in codecs else codecs[0])
        self.codec_combo.setCurrentIndex(self.codec_combo.findData(chosen))
        self.codec_combo.blockSignals(False)
        self._update_enabled()

    def _container_changed(self):
        self._fill_codecs(self.codec_combo.currentData())
        # The output's extension follows the container
        path = self.output_edit.text().strip()
        if path:
            renamed = os.path.splitext(path)[0] + f".{self.container_combo.currentData()}"
            if path == self._suggested_output:
                self._suggested_output = renamed
            self.output_edit.setText(renamed)

    def _suggest_output(self):
        """Beside the frame folder, named after it; a file the person chose
        is left alone."""
        current = self.output_edit.text().strip()
        if current and current != self._suggested_output:
            return
        folder = (self.frames_folder or QDir.homePath()).rstrip(os.sep)
        suffix = "_tracked_points" if self.point_mode else "_masks"
        self._suggested_output = os.path.join(
            os.path.dirname(folder),
            os.path.basename(folder) + suffix + f".{self.container_combo.currentData()}")
        self.output_edit.setText(self._suggested_output)

    # ------------------------------------------------------------------
    # Audio
    # ------------------------------------------------------------------

    def _audio_mode(self):
        return next(mode for mode, radio in self.audio_radios.items() if radio.isChecked())

    def _browse_audio_file(self):
        start = (os.path.dirname(self.audio_file_edit.text())
                 or os.path.dirname(self.source_edit.text()) or QDir.homePath())
        path, _ = QFileDialog.getOpenFileName(
            self, self.loc.get_text("video_export_select_audio"), start,
            build_file_filter(self.loc, 'audio', 'video', 'all'))
        if path:
            self.audio_file_edit.setText(path)
            self.audio_radios['file'].setChecked(True)
            self._audio_file_changed()

    def _audio_file_changed(self):
        path = self.audio_file_edit.text().strip()
        self.audio_info = None
        self._audio_error = None
        if path and os.path.isfile(path):
            try:
                self.audio_info = self.ffmpeg_manager.probe_audio(path)
            except RuntimeError as e:
                self._audio_error = self.loc.get_text("video_export_audio_unreadable", str(e))
        elif path:
            self._audio_error = self.loc.get_text("video_export_audio_missing")
        self._update_enabled()

    def _restore_audio_choice(self, choice):
        """Start from the audio chosen at the previous export; a file that
        can no longer be read leaves the default."""
        if not choice:
            return
        self.placement_combo.setCurrentIndex(
            max(self.placement_combo.findData(choice.get('placement')), 0))
        self.offset_spin.setValue(choice.get('offset') or 0.0)
        self.loop_check.setChecked(bool(choice.get('loop')))
        if choice.get('path'):
            self.audio_file_edit.setText(choice['path'])
            self._audio_file_changed()
        mode = choice.get('mode')
        if mode == 'file' and self.audio_info:
            self.audio_radios['file'].setChecked(True)
        elif mode == 'none':
            self.audio_radios['none'].setChecked(True)

    def _video_duration(self):
        fps = self.fps_spin.value()
        return self.frame_count / fps if fps else 0.0

    def _audio_offset(self):
        """Time of the video at which the audio file starts, negative when
        its beginning is skipped."""
        video = self._video_duration()
        audio = (self.audio_info or {}).get('duration') or video
        placement = self.placement_combo.currentData()
        if placement == 'middle':
            return (video - audio) / 2
        if placement == 'end':
            return video - audio
        if placement == 'offset':
            return self.offset_spin.value()
        return 0.0

    def _loops(self):
        audio = (self.audio_info or {}).get('duration')
        return bool(self.loop_check.isChecked() and audio
                    and audio < self._video_duration() - DURATION_TOLERANCE)

    def _file_is_exact(self):
        """Whether the file is taken as it is, from its start and cut at the
        video's end only, so that its audio can be copied."""
        audio = (self.audio_info or {}).get('duration')
        return (abs(self._audio_offset()) < DURATION_TOLERANCE and not self._loops()
                and audio is not None and audio >= self._video_duration() - DURATION_TOLERANCE)

    def _audio_summary(self):
        """Durations of the audio file and the video, and what placing the
        one against the other cuts off or leaves silent."""
        if self._audio_error:
            return self._audio_error
        if not self.audio_info:
            return ""
        video = self._video_duration()
        audio = self.audio_info.get('duration')
        if audio is None:
            return self.loc.get_text("video_export_audio_duration_unknown")
        text = self.loc.get_text("video_export_audio_durations",
                                 self._number(audio, 'f', 2), self._number(video, 'f', 2))
        if self._loops():
            return text + " " + self.loc.get_text("video_export_audio_looped")
        offset = self._audio_offset()
        heard = max(0.0, min(video, offset + audio) - max(0.0, offset))
        consequences = []
        if audio - heard > DURATION_TOLERANCE:
            consequences.append(self.loc.get_text(
                "video_export_audio_cut", self._number(audio - heard, 'f', 2)))
        if video - heard > DURATION_TOLERANCE:
            consequences.append(self.loc.get_text(
                "video_export_audio_silence", self._number(video - heard, 'f', 2)))
        if not consequences:
            return text
        return text + " " + self.loc.get_text("video_export_audio_then", ", ".join(consequences))

    def _fill_audio_formats(self):
        """List the audio formats the container takes and this ffmpeg can
        write, after the automatic choice, keeping the current one when it
        is among them."""
        current = self.audio_format_combo.currentData() or 'auto'
        available = self.ffmpeg_manager.available_audio_encoders()
        container = self.container_combo.currentData()
        self.audio_format_combo.blockSignals(True)
        self.audio_format_combo.clear()
        self.audio_format_combo.addItem("", 'auto')
        for fmt in CONTAINERS[container]['audio']:
            if fmt in available:
                self.audio_format_combo.addItem(self.loc.get_text(AUDIO_LABEL_KEYS[fmt]), fmt)
        self.audio_format_combo.setCurrentIndex(
            max(self.audio_format_combo.findData(current), 0))
        self.audio_format_combo.blockSignals(False)
        self._audio_formats_for = container

    def _audio_format_changed(self):
        fmt = self.audio_format_combo.currentData()
        if fmt in AUDIO_CODECS and AUDIO_CODECS[fmt]['bitrate']:
            self.audio_bitrate_spin.setValue(AUDIO_CODECS[fmt]['bitrate'])
        self._update_enabled()

    def _audio_source_codec(self):
        if self._audio_mode() == 'source':
            return ((self.info or {}).get('audio') or {}).get('codec')
        return (self.audio_info or {}).get('codec')

    def _resolved_audio_codec(self):
        """What the audio format choice comes to: 'copy', or a key of
        AUDIO_CODECS."""
        can_copy = ((self._audio_mode() == 'source' or self._file_is_exact())
                    and self.sample_rate_combo.currentData() is None)
        return resolve_audio_codec(
            self.audio_format_combo.currentData() or 'auto', self.container_combo.currentData(),
            self.codec_combo.currentData(), self._audio_source_codec(), can_copy)

    def _has_audio(self):
        mode = self._audio_mode()
        return ((mode == 'source' and bool(self.info and self.info.get('audio')))
                or (mode == 'file' and self.audio_info is not None))

    def _update_audio_enabled(self):
        if self._audio_formats_for != self.container_combo.currentData():
            self._fill_audio_formats()
        self.audio_radios['source'].setEnabled(bool(self.info and self.info.get('audio')))
        mode = self._audio_mode()
        for widget in (self.audio_start_label, self.audio_start_spin):
            widget.setEnabled(mode == 'source')
        for widget in (self.audio_file_label, self.audio_file_edit, self.audio_info_label):
            widget.setEnabled(mode == 'file')
        placing = mode == 'file' and self.audio_info is not None
        for widget in (self.placement_label, self.placement_combo):
            widget.setEnabled(placing)
        offset = placing and self.placement_combo.currentData() == 'offset'
        self.offset_label.setEnabled(offset)
        self.offset_spin.setEnabled(offset)
        audio = (self.audio_info or {}).get('duration')
        self.loop_check.setEnabled(placing and bool(audio)
                                   and audio < self._video_duration() - DURATION_TOLERANCE)
        self.audio_info_label.setText(self._audio_summary() if mode == 'file' else "")

        with_audio = self._has_audio()
        resolved = self._resolved_audio_codec() if with_audio else None
        if resolved == 'copy':
            auto = self.loc.get_text("video_export_audio_auto_copy")
        elif resolved:
            auto = self.loc.get_text("video_export_audio_auto",
                                     self.loc.get_text(AUDIO_LABEL_KEYS[resolved]))
        else:
            auto = self.loc.get_text("video_export_audio_auto_plain")
        self.audio_format_combo.setItemText(0, auto)
        for widget in (self.audio_format_label, self.audio_format_combo,
                       self.sample_rate_label, self.sample_rate_combo):
            widget.setEnabled(with_audio)
        lossy = bool(resolved in AUDIO_CODECS and AUDIO_CODECS[resolved]['bitrate'])
        self.audio_bitrate_label.setEnabled(with_audio and lossy)
        self.audio_bitrate_spin.setEnabled(with_audio and lossy)

    def _update_enabled(self):
        self._update_audio_enabled()
        codec = self.codec_combo.currentData()
        uses_bitrate = bool(codec and VIDEO_CODECS[codec]['bitrate'])
        self.bitrate_label.setEnabled(uses_bitrate)
        self.bitrate_spin.setEnabled(uses_bitrate)
        self._update_preview()

    def _update_preview(self):
        fps = self.fps_spin.value()
        self.preview_label.setText(self.loc.get_text(
            "video_export_preview", self.frame_count,
            self._number(self.frame_count / fps if fps else 0, 'f', 2)))

    # ------------------------------------------------------------------
    # Result
    # ------------------------------------------------------------------

    def accept(self):
        output = self.output_edit.text().strip()
        if not output:
            QMessageBox.warning(self, self.loc.get_text("warning"),
                                self.loc.get_text("video_export_no_output"))
            return
        folder = os.path.dirname(os.path.abspath(output))
        if not os.path.isdir(folder):
            QMessageBox.warning(self, self.loc.get_text("warning"),
                                self.loc.get_text("video_export_output_folder_missing", folder))
            return
        if os.path.exists(output) and localized_question(
                self, self.loc, self.loc.get_text("warning"),
                self.loc.get_text("video_export_overwrite", os.path.basename(output)),
                icon=QMessageBox.Warning) != QMessageBox.Yes:
            return
        super().accept()

    def get_options(self):
        """Keyword arguments for FFmpegManager.encode_video(), past the
        frames and the frame size."""
        return {
            'output_path': os.path.abspath(self.output_edit.text().strip()),
            'container': self.container_combo.currentData(),
            'codec': self.codec_combo.currentData(),
            'fps': self.fps_spin.value(),
            'bitrate_kbps': self.bitrate_spin.value(),
            'audio': self._audio_options(),
        }

    def _audio_options(self):
        """The audio track as FFmpegManager.build_encoding_command() takes
        it, or None for a silent video."""
        if not self._has_audio():
            return None
        video = self._video_duration()
        common = {'codec': self._resolved_audio_codec(),
                  'bitrate_kbps': self.audio_bitrate_spin.value(),
                  'sample_rate': self.sample_rate_combo.currentData()}
        if self._audio_mode() == 'source':
            return dict(common, path=self.source_edit.text().strip(),
                        skip=self.audio_start_spin.value(), duration=video)
        path = self.audio_file_edit.text().strip()
        if self._file_is_exact():
            return dict(common, path=path, duration=video)
        offset = self._audio_offset()
        return dict(common, path=path, skip=max(0.0, -offset), delay=max(0.0, offset),
                    loop=self._loops(), pad_to=video)

    def get_audio_choice(self):
        """The audio chosen, to start the next export from: the mode, the
        file and its placement."""
        return {'mode': self._audio_mode(),
                'path': self.audio_file_edit.text().strip() or None,
                'placement': self.placement_combo.currentData(),
                'offset': self.offset_spin.value(),
                'loop': self.loop_check.isChecked()}

    def get_source(self):
        """The source record to keep for the session and the project: the
        video given, the frame rate when it differs from the video's own, and
        the audio start. None without a source video."""
        path = self.source_edit.text().strip()
        if not path:
            return None
        fps = self.fps_spin.value()
        own_fps = self.info.get('fps') if self.info else None
        return {'video': os.path.abspath(path),
                'fps': None if own_fps and abs(fps - own_fps) < 1e-3 else fps,
                'start': self.audio_start_spin.value()}


class VideoExportController:
    """File › Export › Export Video…: checks that ffmpeg is there, asks for
    the options, renders and encodes the frames behind a progress dialog."""

    def __init__(self, main_window):
        self.main_window = main_window

    def export_video(self):
        mw = self.main_window
        loc = mw.localization
        manager = mw.ffmpeg_manager
        if not mw.image_manager.has_images():
            mw.ui_manager.show_message("warning", loc.get_text("warning"),
                                       loc.get_text("no_image_loaded"))
            return
        if not manager.is_available(force=True):
            override = mw.config_manager.get_ffmpeg_path()
            message = (loc.get_text("video_frames_ffmpeg_override_invalid", override)
                       if override else loc.get_text("video_frames_ffmpeg_missing"))
            mw.ui_manager.show_message("warning", loc.get_text("warning"), message)
            return

        image_paths = list(mw.image_manager.image_paths)
        info = mw.image_manager.get_current_image_info()
        frame_size = (info['width'], info['height'])
        point_mode = mw.is_point_mode()
        dialog = VideoExportDialog(loc, manager, mw.video_source,
                                   mw.image_manager.current_folder, len(image_paths),
                                   frame_size, point_mode, mw.export_audio, mw)
        if dialog.exec_() != QDialog.Accepted:
            return
        mw.video_source = dialog.get_source()
        mw.export_audio = dialog.get_audio_choice()
        options = dialog.get_options()

        status, message = self._run(image_paths, frame_size, point_mode, options)
        title = loc.get_text("video_export_title_points" if point_mode else "video_export_title")
        if status == STATUS_CANCELLED:
            mw.ui_manager.show_message("info", title, loc.get_text("video_export_cancelled"))
        elif status != STATUS_OK:
            mw.ui_manager.show_message("error", loc.get_text("error"),
                                       loc.get_text("video_export_failed", message))
        else:
            mw.ui_manager.show_message("info", loc.get_text("export_complete"),
                                       loc.get_text("video_export_done", options['output_path']))

    def _frames(self, image_paths, frame_size, point_mode):
        """Every frame, in order, as the image export draws it: frames
        without a mask or a tracked point come as they are, so that the
        video keeps the timing of the original."""
        from .exporters import ImageExporter
        mw = self.main_window
        om = mw.object_manager
        bg_opacity = 1.0
        slider = mw.ui_manager.get_control('background_opacity_slider')
        if slider is not None and not point_mode:
            bg_opacity = slider.value() / 100.0
        for idx, path in enumerate(image_paths):
            if point_mode:
                image = ImageExporter.compose_tracked_point_frame(
                    path, idx, om.object_tracked_points, om.object_colors, om.object_names,
                    om.tracked_point_style, om.tracked_point_size)
            else:
                image = ImageExporter.compose_masked_frame(
                    path, idx, om.object_masks, om.object_colors, bg_opacity)
            if image.size != frame_size:
                image = image.resize(frame_size)
            yield np.asarray(image, dtype=np.uint8)

    def _run(self, image_paths, frame_size, point_mode, options):
        """Encode in a worker thread behind a modal progress dialog; returns
        encode_video()'s (status, message)."""
        mw = self.main_window
        loc = mw.localization
        total = len(image_paths)
        progress = AnimatedProgressDialog(
            loc.get_text("video_export_progress", 0, total),
            loc.get_text("cancel"), 0, total, mw)
        progress.setWindowTitle(loc.get_text(
            "video_export_title_points" if point_mode else "video_export_title"))
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        # Reaching the maximum would otherwise reset and hide the dialog while
        # ffmpeg is still finishing the file; it is closed explicitly instead
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.setValue(0)
        progress.show()

        finished = [False]

        def on_report(done, expected):
            if progress.wasCanceled():
                return
            progress.setLabelText(loc.get_text("video_export_progress", done, expected))
            progress.setValue(min(done, expected))

        def on_cancel():
            if finished[0]:
                return
            progress.setLabelText(loc.get_text("progress_cancelled"))
            progress.show()

        width, height = frame_size

        def task(report, is_cancelled):
            status, message, _ = mw.ffmpeg_manager.encode_video(
                self._frames(image_paths, frame_size, point_mode), total,
                width=width, height=height, report=report, is_cancelled=is_cancelled,
                **options)
            return status, message

        progress.canceled.connect(on_cancel)
        try:
            return run_with_progress(progress, task, on_report)
        except Exception as e:
            return STATUS_ERROR, str(e)
        finally:
            finished[0] = True
            progress.close()
