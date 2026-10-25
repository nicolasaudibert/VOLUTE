"""
FFmpeg Manager
Finds the ffmpeg and ffprobe executables, reads a video's properties,
extracts its frames as a numbered image sequence the application can load,
and encodes images back into a video. Holds no Qt code: the UI side runs
extract_frames() and encode_video() in a worker thread.
"""

import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

from .file_utils import FileManager
from .gimp_export_manager import STATUS_OK, STATUS_CANCELLED, STATUS_ERROR


# Output formats offered for extracted frames: extension written, keyed by
# the format name used in the dialog and in extract_frames().
FRAME_FORMATS = {'jpg': 'jpg', 'png': 'png'}

# Failure message of an extraction that produced no frame, typically a time
# range starting past the end of the video; the UI recognises it to show its
# own explanation instead.
NO_FRAMES_MESSAGE = "ffmpeg wrote no frame."

# Video codecs offered for an exported video: the ffmpeg program that writes
# each one and the options it is given, keyed by the name used in the export
# dialog. ProRes is sized by its profile rather than by a bit rate.
VIDEO_CODECS = {
    'h264':   {'encoder': 'libx264', 'pix_fmt': 'yuv420p', 'bitrate': True},
    'h265':   {'encoder': 'libx265', 'pix_fmt': 'yuv420p', 'bitrate': True,
               'extra': ['-tag:v', 'hvc1']},
    'prores': {'encoder': 'prores_ks', 'pix_fmt': 'yuv422p10le', 'bitrate': False,
               'extra': ['-profile:v', '2']},
}

# Audio formats an exported video can be given: ffmpeg encoder, the codec
# name ffprobe reports for it, and the default bit rate in kbit/s of the
# lossy ones (None for the lossless ones)
AUDIO_CODECS = {
    'aac':   {'encoder': 'aac',        'codec': 'aac',       'bitrate': 192},
    'mp3':   {'encoder': 'libmp3lame', 'codec': 'mp3',       'bitrate': 192},
    'opus':  {'encoder': 'libopus',    'codec': 'opus',      'bitrate': 128},
    'alac':  {'encoder': 'alac',       'codec': 'alac',      'bitrate': None},
    'flac':  {'encoder': 'flac',       'codec': 'flac',      'bitrate': None},
    'pcm16': {'encoder': 'pcm_s16le',  'codec': 'pcm_s16le', 'bitrate': None},
    'pcm24': {'encoder': 'pcm_s24le',  'codec': 'pcm_s24le', 'bitrate': None},
}

# Containers offered, with the video encodings and audio formats each one
# takes, and the audio codecs it can hold as they are, without re-encoding
CONTAINERS = {
    'mp4': {'codecs': ('h264', 'h265'), 'audio': ('aac', 'mp3', 'alac'),
            'audio_copy': {'aac', 'mp3', 'ac3', 'eac3', 'alac'}},
    'mov': {'codecs': ('h264', 'h265', 'prores'),
            'audio': ('aac', 'mp3', 'alac', 'pcm16', 'pcm24'),
            'audio_copy': {'aac', 'mp3', 'ac3', 'eac3', 'alac', 'pcm_s16le', 'pcm_s24le'}},
    'mkv': {'codecs': ('h264', 'h265', 'prores'),
            'audio': ('aac', 'mp3', 'opus', 'flac', 'pcm16', 'pcm24'),
            'audio_copy': None},   # None: any
}

# Encoding and container matching a source video, from ffprobe's codec name
# and the file's extension
SOURCE_CODECS = {'h264': 'h264', 'hevc': 'h265', 'prores': 'prores'}
SOURCE_CONTAINERS = {'.mp4': 'mp4', '.m4v': 'mp4', '.mov': 'mov', '.mkv': 'mkv'}


def default_encoding(source_path, info):
    """(container, codec) matching the source video when it has one this
    export can write, H.264 in MP4 otherwise."""
    container = SOURCE_CONTAINERS.get(os.path.splitext(source_path or '')[1].lower(), 'mp4')
    codec = SOURCE_CODECS.get((info or {}).get('codec'), 'h264')
    if codec not in CONTAINERS[container]['codecs']:
        container = 'mov'
    return container, codec


def default_bitrate_kbps(info, width, height, fps):
    """Video bit rate of the source in kbit/s; when unknown, 0.1 bit per pixel
    and frame, about what H.264 needs for a clean result."""
    bitrate = (info or {}).get('bit_rate')
    if bitrate:
        return max(1, int(round(bitrate / 1000)))
    return max(100, int(round(width * height * (fps or 25) * 0.1 / 1000)))


# ffmpeg's name of each container, for the output format given explicitly:
# the file being written carries a temporary name ffmpeg cannot read it from
CONTAINER_FORMATS = {'mp4': 'mp4', 'mov': 'mov', 'mkv': 'matroska'}


def default_audio_codec(container, video_codec):
    """Audio format an export re-encodes to when it cannot copy the audio:
    24-bit PCM beside ProRes in MOV, as editing software expects, FLAC in
    MKV, AAC otherwise."""
    if container == 'mov' and video_codec == 'prores':
        return 'pcm24'
    return 'flac' if container == 'mkv' else 'aac'


def resolve_audio_codec(choice, container, video_codec, source_audio_codec, can_copy=True):
    """The audio format to write, 'copy' included: choice itself, unless it
    is 'auto', which copies the audio when the container holds its codec and
    nothing has to change it (can_copy), and falls back to
    default_audio_codec() otherwise."""
    if choice != 'auto':
        return choice
    allowed = CONTAINERS[container]['audio_copy']
    if can_copy and source_audio_codec and (allowed is None or source_audio_codec in allowed):
        return 'copy'
    return default_audio_codec(container, video_codec)


# Smallest zero-padding width of frame numbers. Frame 0 is then always
# named <stem>_00000, which FileManager.get_image_files() takes as the
# reference image of the sequence.
MIN_NUMBER_WIDTH = 5


def frame_number_width(frame_count):
    """Zero-padding width for frames numbered 0 to frame_count - 1."""
    return max(MIN_NUMBER_WIDTH, len(str(max(frame_count - 1, 0))))


def jpeg_quality_to_qscale(quality):
    """Map a 1-100 JPEG quality (higher is better) onto ffmpeg's -q:v scale
    for mjpeg, which runs from 2 (best) to 31 (worst)."""
    quality = min(max(int(quality), 1), 100)
    return round(2 + (100 - quality) * 29 / 99)


def folder_has_images(folder):
    """True when folder exists and holds at least one loadable image file."""
    if not os.path.isdir(folder):
        return False
    return any(FileManager.is_supported_image_format(f) for f in os.listdir(folder))


def _parse_rate(text):
    """Frames per second from an ffprobe rate such as '30000/1001', or None
    when the rate is missing or reported as 0/0."""
    try:
        num, _, den = str(text).partition('/')
        value = float(num) / float(den or 1)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return value if value > 0 else None


def _parse_float(text):
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0 else None


class FFmpegManager:
    """
    Detects usable ffmpeg/ffprobe executables and runs frame extraction as a
    subprocess, with progress reports and cancellation.
    """

    # Poll interval of the subprocess wait loop, and grace period left to
    # ffmpeg after terminate() before falling back to kill().
    POLL_INTERVAL = 0.2
    TERMINATE_GRACE = 3.0

    # Looked into when ffmpeg is not on PATH. An application started from
    # the macOS Finder inherits a minimal PATH that leaves out Homebrew and
    # MacPorts, and a conda environment used without being activated keeps
    # its own executables off PATH too.
    WELL_KNOWN_CANDIDATES = (
        os.path.join(sys.prefix, 'bin', 'ffmpeg'),
        os.path.join(sys.prefix, 'Library', 'bin', 'ffmpeg.exe'),
        '/opt/homebrew/bin/ffmpeg',
        '/usr/local/bin/ffmpeg',
        '/opt/local/bin/ffmpeg',
        '/usr/bin/ffmpeg',
        '/snap/bin/ffmpeg',
    )

    # Prefix of the hidden folder that receives frames while ffmpeg writes
    # them, inside the destination folder so the final renames stay on one
    # filesystem.
    STAGING_PREFIX = '.volute_extracting_'

    # Lines of ffmpeg's error output kept for the failure message.
    ERROR_TAIL_LINES = 20

    # Prefix of the file an exported video is written to, beside its final
    # name, until ffmpeg has finished: a failed or cancelled export then
    # leaves no partial file, and does not touch a video it would replace
    ENCODING_PREFIX = '.volute_encoding_'

    def __init__(self, main_window, debug_mode=False):
        self.main_window = main_window
        self.debug_mode = debug_mode
        self._ffmpeg_executable = None
        self._ffprobe_executable = None
        self._detected = False
        # Keys of AUDIO_CODECS this ffmpeg can write, once asked
        self._audio_encoders = None

    # ------------------------------------------------------------------
    # Executable detection
    # ------------------------------------------------------------------

    def detect_ffmpeg_executable(self, force=False):
        """
        Resolve a usable ffmpeg executable path: an explicit override from
        configuration takes precedence and is NOT silently ignored if
        invalid (an invalid override is reported as "not detected" rather
        than falling back to a search); otherwise 'ffmpeg' is looked up on
        PATH, and failing that in WELL_KNOWN_CANDIDATES.

        ffprobe is resolved alongside: next to the chosen ffmpeg first, the
        two being shipped together, then on PATH.
        """
        if self._detected and not force:
            return self._ffmpeg_executable

        override = self.main_window.config_manager.get_ffmpeg_path()
        if override:
            found = override if self._is_executable(override) else None
        else:
            found = shutil.which('ffmpeg')
            if found is None:
                found = next(
                    (p for p in self.WELL_KNOWN_CANDIDATES if self._is_executable(p)),
                    None,
                )

        self._ffmpeg_executable = found
        self._ffprobe_executable = self._find_ffprobe(found) if found else None
        self._detected = True
        return found

    def detect_ffprobe_executable(self, force=False):
        """ffprobe path resolved by detect_ffmpeg_executable(), or None."""
        self.detect_ffmpeg_executable(force=force)
        return self._ffprobe_executable

    def _find_ffprobe(self, ffmpeg_path):
        folder, name = os.path.split(ffmpeg_path)
        sibling = os.path.join(folder, name.replace('ffmpeg', 'ffprobe', 1))
        if sibling != ffmpeg_path and self._is_executable(sibling):
            return sibling
        return shutil.which('ffprobe')

    @staticmethod
    def _is_executable(path):
        return os.path.isfile(path) and os.access(path, os.X_OK)

    def is_available(self, force=False):
        return self.detect_ffmpeg_executable(force=force) is not None

    # ------------------------------------------------------------------
    # Video properties
    # ------------------------------------------------------------------

    def probe_video(self, video_path, timeout=30):
        """
        Read the first video stream's properties with ffprobe. Returns a
        dict with 'duration' (seconds), 'fps', 'frame_count', 'width',
        'height', 'codec' (ffprobe's name) and 'bit_rate' (bit/s), any of them
        None when the container does not say, and 'audio', the first audio
        stream's 'codec', 'sample_rate' and 'channels', or None without one;
        returns None when no ffprobe is available. Raises RuntimeError when the file
        cannot be read or holds no video stream.
        """
        ffprobe = self.detect_ffprobe_executable()
        if not ffprobe:
            return None

        cmd = [ffprobe, '-v', 'error',
               '-show_entries',
               'stream=codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate,'
               'nb_frames,duration,bit_rate,sample_rate,channels'
               ':format=duration',
               '-of', 'json', video_path]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                stdin=subprocess.DEVNULL, creationflags=self._creation_flags(),
            )
        except (OSError, subprocess.SubprocessError) as e:
            raise RuntimeError(str(e)) from e
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "ffprobe failed.")

        try:
            data = json.loads(result.stdout or '{}')
        except ValueError as e:
            raise RuntimeError(f"Unreadable ffprobe output: {e}") from e
        streams = data.get('streams') or []
        videos = [s for s in streams if s.get('codec_type') == 'video']
        if not videos:
            raise RuntimeError("No video stream found.")
        stream = videos[0]
        audios = [s for s in streams if s.get('codec_type') == 'audio']

        duration = (_parse_float(stream.get('duration'))
                    or _parse_float((data.get('format') or {}).get('duration')))
        fps = (_parse_rate(stream.get('avg_frame_rate'))
               or _parse_rate(stream.get('r_frame_rate')))
        try:
            frame_count = int(stream.get('nb_frames')) or None
        except (TypeError, ValueError):
            frame_count = None
        if frame_count is None and duration and fps:
            frame_count = int(round(duration * fps))

        audio = None
        if audios:
            audio = {'codec': audios[0].get('codec_name'),
                     'sample_rate': _parse_float(audios[0].get('sample_rate')),
                     'channels': audios[0].get('channels')}
        return {
            'duration': duration,
            'fps': fps,
            'frame_count': frame_count,
            'width': stream.get('width'),
            'height': stream.get('height'),
            'codec': stream.get('codec_name'),
            'bit_rate': _parse_float(stream.get('bit_rate')),
            'audio': audio,
        }

    @staticmethod
    def estimate_frame_count(info, fps=None, start=None, end=None):
        """
        Number of frames an extraction is expected to write, from
        probe_video()'s info, or None when it cannot be told. Only sizes the
        progress bar: the final names are padded from the actual count.
        """
        if not info:
            return None
        duration = info.get('duration')
        if duration:
            span_end = min(end, duration) if end is not None else duration
            span = span_end - (start or 0)
        elif start is None and end is None:
            span = None
        else:
            return None

        if fps:
            return max(int(math.ceil(span * fps)), 0) if span is not None else None
        if start is None and end is None and info.get('frame_count'):
            return info['frame_count']
        if span is not None and info.get('fps'):
            return max(int(round(span * info['fps'])), 0)
        return None

    # ------------------------------------------------------------------
    # Frame extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _creation_flags():
        """Keep a console window from opening on Windows when the
        application runs without one."""
        return getattr(subprocess, 'CREATE_NO_WINDOW', 0)

    @staticmethod
    def _image2_pattern(folder, extension):
        """Output pattern for ffmpeg's image sequence writer. It reads '%'
        anywhere in the path as a format directive, so a literal one in the
        folder name has to be doubled."""
        return os.path.join(folder.replace('%', '%%'), f'%09d.{extension}')

    def build_extraction_command(self, video_path, staging_folder, fmt='jpg',
                                 quality=95, fps=None, start=None, end=None):
        """ffmpeg command line writing frames 0, 1, 2… into staging_folder."""
        extension = FRAME_FORMATS[fmt]
        cmd = [self.detect_ffmpeg_executable(), '-hide_banner', '-nostdin',
               '-v', 'error', '-progress', 'pipe:1', '-nostats']
        # Seeking before -i is both fast and frame-accurate when decoding
        if start:
            cmd += ['-ss', f'{start:.3f}']
        cmd += ['-i', video_path]
        if end is not None:
            cmd += ['-t', f'{end - (start or 0):.3f}']
        cmd += ['-map', '0:v:0', '-an', '-sn', '-dn']
        if fps:
            cmd += ['-vf', f'fps={fps:g}']
        if fmt == 'jpg':
            cmd += ['-q:v', str(jpeg_quality_to_qscale(quality))]
        else:
            # 8 bits per channel, the depth the rest of the application reads
            cmd += ['-pix_fmt', 'rgb24']
        cmd += ['-start_number', '0', self._image2_pattern(staging_folder, extension)]
        return cmd

    @staticmethod
    def _read_progress(stream, state):
        """Drain ffmpeg's -progress output, keeping the last frame count."""
        for line in stream:
            key, _, value = line.strip().partition('=')
            if key == 'frame':
                try:
                    state['frame'] = int(value)
                except ValueError:
                    pass

    @staticmethod
    def _read_errors(stream, lines, limit):
        for line in stream:
            lines.append(line.rstrip())
            if len(lines) > limit:
                del lines[0]

    def _terminate_process(self, proc):
        """Stop a live ffmpeg process: terminate(), then kill() if it hasn't
        exited within the grace period."""
        try:
            proc.terminate()
            proc.wait(timeout=self.TERMINATE_GRACE)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
                proc.wait()
            except Exception:
                pass
        except Exception:
            pass

    @staticmethod
    def _discard(staging_folder, output_folder, created_output):
        """Remove every frame of an extraction that did not complete, and the
        destination folder too when the extraction created it."""
        shutil.rmtree(staging_folder, ignore_errors=True)
        if created_output:
            try:
                os.rmdir(output_folder)
            except OSError:
                pass

    def extract_frames(self, video_path, output_folder, stem, fmt='jpg',
                       quality=95, fps=None, start=None, end=None,
                       expected_frames=None, report=None, is_cancelled=None):
        """
        Extract the video's frames into output_folder as
        <stem>_<number>.<ext>, numbered from 0 and zero-padded to
        frame_number_width() of the number written, so that every tool
        sorts them in playback order.

        ffmpeg writes into a hidden staging folder inside output_folder; the
        frames are renamed into place only once it has succeeded. A
        cancelled or failed extraction therefore leaves no frame behind, and
        removes output_folder as well when it did not exist beforehand.

        report(done, total) is called as frames are written, total being
        expected_frames (0 when unknown); is_cancelled() is polled to stop
        ffmpeg. Returns (status, message, frame_count), message holding
        ffmpeg's error output on failure.
        """
        if self.detect_ffmpeg_executable() is None:
            return STATUS_ERROR, "ffmpeg executable not found.", 0
        if fmt not in FRAME_FORMATS:
            return STATUS_ERROR, f"Unsupported frame format: {fmt}", 0
        report = report or (lambda done, total: None)
        is_cancelled = is_cancelled or (lambda: False)
        total = expected_frames or 0

        created_output = not os.path.isdir(output_folder)
        try:
            os.makedirs(output_folder, exist_ok=True)
            staging = tempfile.mkdtemp(prefix=self.STAGING_PREFIX, dir=output_folder)
        except OSError as e:
            return STATUS_ERROR, str(e), 0

        cmd = self.build_extraction_command(video_path, staging, fmt=fmt, quality=quality,
                                            fps=fps, start=start, end=end)
        if self.debug_mode:
            print(f"[ffmpeg] {subprocess.list2cmdline(cmd)}")
        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL, text=True, errors='replace',
                creationflags=self._creation_flags(),
            )
        except OSError as e:
            self._discard(staging, output_folder, created_output)
            return STATUS_ERROR, str(e), 0

        # Both pipes are drained in threads so neither can fill up and stall
        # ffmpeg while this loop only polls for completion and cancellation.
        state = {'frame': 0}
        error_lines = []
        readers = [
            threading.Thread(target=self._read_progress, args=(proc.stdout, state), daemon=True),
            threading.Thread(target=self._read_errors,
                             args=(proc.stderr, error_lines, self.ERROR_TAIL_LINES), daemon=True),
        ]
        for reader in readers:
            reader.start()

        cancelled = False
        reported = -1
        while proc.poll() is None:
            if is_cancelled():
                cancelled = True
                self._terminate_process(proc)
                break
            if state['frame'] != reported:
                reported = state['frame']
                report(reported, total)
            time.sleep(self.POLL_INTERVAL)
        for reader in readers:
            reader.join(timeout=self.TERMINATE_GRACE)

        if cancelled or is_cancelled():
            self._discard(staging, output_folder, created_output)
            return STATUS_CANCELLED, "", 0
        if proc.returncode != 0:
            self._discard(staging, output_folder, created_output)
            message = "\n".join(error_lines).strip()
            # When no frame reaches the encoder, ffmpeg fails while opening it
            # and buries the actual cause under encoder errors.
            if "Nothing was written" in message:
                return STATUS_ERROR, NO_FRAMES_MESSAGE, 0
            return STATUS_ERROR, message or f"ffmpeg exited with code {proc.returncode}.", 0

        return self._rename_frames(staging, output_folder, stem, fmt, report,
                                   created_output)

    def _rename_frames(self, staging, output_folder, stem, fmt, report, created_output):
        """Move the staged frames into output_folder under their final,
        padded names, then remove the staging folder."""
        extension = FRAME_FORMATS[fmt]
        staged = []
        for name in os.listdir(staging):
            number, ext = os.path.splitext(name)
            if ext == f'.{extension}' and number.isdigit():
                staged.append((int(number), name))
        staged.sort()
        count = len(staged)
        if count == 0:
            self._discard(staging, output_folder, created_output)
            return STATUS_ERROR, NO_FRAMES_MESSAGE, 0

        width = frame_number_width(count)
        moved = []
        try:
            for index, (_, name) in enumerate(staged):
                target = os.path.join(output_folder, f"{stem}_{index:0{width}d}.{extension}")
                if os.path.exists(target):
                    raise FileExistsError(f"{target} already exists.")
                os.rename(os.path.join(staging, name), target)
                moved.append(target)
        except OSError as e:
            for path in moved:
                try:
                    os.remove(path)
                except OSError:
                    pass
            self._discard(staging, output_folder, created_output)
            return STATUS_ERROR, str(e), 0

        shutil.rmtree(staging, ignore_errors=True)
        report(count, count)
        return STATUS_OK, "", count

    # ------------------------------------------------------------------
    # Video encoding
    # ------------------------------------------------------------------

    def available_audio_encoders(self):
        """Keys of AUDIO_CODECS this ffmpeg can write: a build can lack the
        MP3 or the Opus one. Asked once, then kept."""
        if self._audio_encoders is None:
            names = set()
            ffmpeg = self.detect_ffmpeg_executable()
            if ffmpeg:
                try:
                    result = subprocess.run(
                        [ffmpeg, '-hide_banner', '-encoders'], capture_output=True, text=True,
                        timeout=30, stdin=subprocess.DEVNULL,
                        creationflags=self._creation_flags())
                    for line in result.stdout.splitlines():
                        parts = line.split()
                        if len(parts) >= 2 and parts[0].startswith('A'):
                            names.add(parts[1])
                except (OSError, subprocess.SubprocessError):
                    pass
            self._audio_encoders = {key for key, spec in AUDIO_CODECS.items()
                                    if spec['encoder'] in names}
        return self._audio_encoders

    def probe_audio(self, path, timeout=30):
        """Read the first audio stream of a file — an audio file, or a video
        with sound — with ffprobe. Returns a dict with 'duration' (seconds),
        'codec', 'sample_rate' and 'channels', any of them None when the file
        does not say; returns None when no ffprobe is available. Raises
        RuntimeError when the file cannot be read or holds no audio."""
        ffprobe = self.detect_ffprobe_executable()
        if not ffprobe:
            return None
        cmd = [ffprobe, '-v', 'error', '-select_streams', 'a:0', '-show_entries',
               'stream=codec_name,sample_rate,channels,duration:format=duration',
               '-of', 'json', path]
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
                stdin=subprocess.DEVNULL, creationflags=self._creation_flags(),
            )
        except (OSError, subprocess.SubprocessError) as e:
            raise RuntimeError(str(e)) from e
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "ffprobe failed.")
        try:
            data = json.loads(result.stdout or '{}')
        except ValueError as e:
            raise RuntimeError(f"Unreadable ffprobe output: {e}") from e
        streams = data.get('streams') or []
        if not streams:
            raise RuntimeError("No audio stream found.")
        stream = streams[0]
        return {
            'duration': (_parse_float(stream.get('duration'))
                         or _parse_float((data.get('format') or {}).get('duration'))),
            'codec': stream.get('codec_name'),
            'sample_rate': _parse_float(stream.get('sample_rate')),
            'channels': stream.get('channels'),
        }

    def build_encoding_command(self, output_path, container, width, height, fps,
                               codec='h264', bitrate_kbps=None, audio=None):
        """ffmpeg command line encoding raw RGB frames read from its standard
        input into output_path, with an audio track when audio is given: a
        dict with
          'path'         the file whose first audio stream is taken,
          'skip'         seconds skipped at its start,
          'duration'     seconds read from there, or None for all of it,
          'loop'         repeat it,
          'delay'        seconds of silence before it starts,
          'pad_to'       seconds the track is padded with silence and cut to,
                         or None,
          'codec'        'copy', or a key of AUDIO_CODECS,
          'bitrate_kbps' for the lossy formats,
          'sample_rate'  Hz to resample to, or None.
        Delay and padding go through audio filters, which 'copy' excludes."""
        spec = VIDEO_CODECS[codec]
        cmd = [self.detect_ffmpeg_executable(), '-hide_banner', '-v', 'error', '-y',
               '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{width}x{height}',
               '-framerate', f'{fps:g}', '-i', 'pipe:0']
        if audio:
            if audio.get('loop'):
                cmd += ['-stream_loop', '-1']
            if audio.get('skip'):
                cmd += ['-ss', f"{audio['skip']:.3f}"]
            if audio.get('duration'):
                cmd += ['-t', f"{audio['duration']:.3f}"]
            cmd += ['-i', audio['path']]
        cmd += ['-map', '0:v:0']
        if audio:
            cmd += ['-map', '1:a:0?']
        if spec['pix_fmt'] == 'yuv420p':
            # 4:2:0 chroma needs even dimensions
            cmd += ['-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2']
        cmd += ['-c:v', spec['encoder'], '-pix_fmt', spec['pix_fmt']]
        if spec['bitrate'] and bitrate_kbps:
            cmd += ['-b:v', f'{int(bitrate_kbps)}k']
        cmd += spec.get('extra', [])
        if audio:
            filters = []
            if audio.get('delay'):
                filters.append(f"adelay={int(round(audio['delay'] * 1000))}:all=1")
            if audio.get('pad_to'):
                filters += ['apad', f"atrim=0:{audio['pad_to']:.3f}"]
            if filters:
                cmd += ['-af', ','.join(filters)]
            if audio['codec'] == 'copy':
                cmd += ['-c:a', 'copy']
            else:
                audio_spec = AUDIO_CODECS[audio['codec']]
                cmd += ['-c:a', audio_spec['encoder']]
                if audio_spec['bitrate'] and audio.get('bitrate_kbps'):
                    cmd += ['-b:a', f"{int(audio['bitrate_kbps'])}k"]
                if audio.get('sample_rate'):
                    cmd += ['-ar', str(int(audio['sample_rate']))]
        if container in ('mp4', 'mov'):
            cmd += ['-movflags', '+faststart']
        cmd += ['-f', CONTAINER_FORMATS[container], output_path]
        return cmd

    def encode_video(self, frames, frame_count, output_path, container, width, height,
                     fps, codec='h264', bitrate_kbps=None, audio=None,
                     report=None, is_cancelled=None):
        """
        Encode frames, an iterable of height×width×3 uint8 RGB arrays, into
        output_path, with the audio track build_encoding_command() describes
        when audio is given.

        The video is written beside output_path under a temporary name and
        moved into place once ffmpeg has succeeded. report(done, total) is
        called after each frame, total being frame_count; is_cancelled() is
        polled between frames. Returns (status, message, frames_written),
        message holding ffmpeg's error output on failure.
        """
        if self.detect_ffmpeg_executable() is None:
            return STATUS_ERROR, "ffmpeg executable not found.", 0
        report = report or (lambda done, total: None)
        is_cancelled = is_cancelled or (lambda: False)
        partial = os.path.join(os.path.dirname(output_path) or '.',
                               self.ENCODING_PREFIX + os.path.basename(output_path))
        cmd = self.build_encoding_command(
            partial, container, width, height, fps, codec=codec,
            bitrate_kbps=bitrate_kbps, audio=audio)
        if self.debug_mode:
            print(f"[ffmpeg] {subprocess.list2cmdline(cmd)}")
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.PIPE,
                                    creationflags=self._creation_flags())
        except OSError as e:
            return STATUS_ERROR, str(e), 0

        error_lines = []
        reader = threading.Thread(
            target=self._read_errors,
            args=(io.TextIOWrapper(proc.stderr, errors='replace'), error_lines,
                  self.ERROR_TAIL_LINES),
            daemon=True)
        reader.start()

        def discard():
            try:
                os.remove(partial)
            except OSError:
                pass

        written = 0
        cancelled = False
        try:
            for frame in frames:
                if is_cancelled():
                    cancelled = True
                    break
                proc.stdin.write(frame.tobytes())
                written += 1
                report(written, frame_count)
            proc.stdin.close()
        except (BrokenPipeError, OSError):
            # ffmpeg stopped reading: its error output says why
            pass
        if cancelled:
            self._terminate_process(proc)
            reader.join(timeout=self.TERMINATE_GRACE)
            discard()
            return STATUS_CANCELLED, "", written
        proc.wait()
        reader.join(timeout=self.TERMINATE_GRACE)
        if proc.returncode != 0:
            discard()
            message = "\n".join(error_lines).strip()
            return STATUS_ERROR, message or f"ffmpeg exited with code {proc.returncode}.", written
        try:
            os.replace(partial, output_path)
        except OSError as e:
            discard()
            return STATUS_ERROR, str(e), written
        return STATUS_OK, "", written
