"""
Optional animated indicator for progress dialogs.

The animation complements a progress bar, it never replaces one: when no
animation file sits in resources/, the helper returns None and the dialogs lay
out exactly as they do without it.
"""

import time
from pathlib import Path

from PyQt5.QtCore import QSize
from PyQt5.QtGui import QMovie
from PyQt5.QtWidgets import QHBoxLayout, QLabel

RESOURCES = Path(__file__).parent / "resources"
BASENAME = "progress"

# Animated WebP comes first: it carries a full alpha channel and 24-bit colour,
# where GIF is limited to 256 colours and a single transparent index, which
# shows as fringing against a themed dialog background. Qt reads both through
# QMovie; anything else it cannot animate.
EXTENSIONS = ("webp", "gif")

# Values of the ui.progress_animation_pacing setting. PACING_FILE plays the
# animation at the frame durations stored in the file. PACING_PROGRESS advances
# it one frame per progress update, which is how it behaved while those
# operations ran on the GUI thread.
PACING_FILE = "file"
PACING_PROGRESS = "progress"

# Side of the square the animation is drawn in, in logical pixels. The
# animation sits above the progress bar rather than beside it, so this can grow
# without crowding anything; change it here and every dialog follows. Author
# the file at twice this value, since a HiDPI display draws two device pixels
# per logical one and would otherwise upscale and blur it.
DISPLAY_SIZE = 96


def find_animation():
    """Path of the animation to play, or None when none is installed."""
    for extension in EXTENSIONS:
        candidate = RESOURCES / f"{BASENAME}.{extension}"
        if candidate.is_file():
            return candidate
    return None


def create_progress_animation(parent=None, size=DISPLAY_SIZE):
    """Return a QLabel playing the animation, or None when there is none.

    Callers place the widget above their progress bar and skip it when it is
    None, which is what makes the animation optional. The movie is returned
    stopped: drive it with start() and stop() below so it only runs while the
    operation does.
    """
    path = find_animation()
    if path is None:
        return None

    movie = QMovie(str(path))
    if not movie.isValid():
        return None

    # Decode every frame up front rather than during playback. The dialogs
    # hosting this share a thread with the operation they report on, so any
    # work deferred to playback competes with that operation.
    movie.setCacheMode(QMovie.CacheAll)
    movie.setScaledSize(QSize(size, size))

    label = QLabel(parent)
    label.setFixedSize(size, size)
    # QLabel.setMovie does not take ownership, so the movie needs a parent of
    # its own; without one Python collects it and nothing ever plays.
    movie.setParent(label)
    label.setMovie(movie)
    return label


def create_centred_row(parent=None, size=DISPLAY_SIZE):
    """Return (row, label) placing the animation centred on a row of its own,
    or (None, None) when no animation is installed.

    Dialogs add the row above their progress bar and keep the label to start()
    and stop() it. Going through one builder keeps every dialog consistent,
    and leaves them untouched when there is nothing to show.
    """
    label = create_progress_animation(parent, size)
    if label is None:
        return None, None

    row = QHBoxLayout()
    row.addStretch()
    row.addWidget(label)
    row.addStretch()
    return row, label


def start(label):
    """Start the animation of such a label. Accepts None, so callers that may
    have no animation need no test of their own."""
    if label is not None and label.movie() is not None:
        label.movie().start()


def stop(label):
    """Stop the animation of such a label. Accepts None, as start() does."""
    if label is not None and label.movie() is not None:
        label.movie().stop()


def configured_pacing(widget):
    """The pacing setting, reached through the widget's chain of parents;
    PACING_FILE when none of them carries a configuration manager."""
    while widget is not None:
        config_manager = getattr(widget, "config_manager", None)
        if config_manager is not None:
            return config_manager.get_progress_animation_pacing()
        widget = widget.parent()
    return PACING_FILE


def show_first_frame(label):
    """Show the first frame of such a label without playing it, for dialogs
    that step() it instead. Accepts None, as start() does."""
    if label is not None and label.movie() is not None:
        label.movie().jumpToFrame(0)
        label.frame_shown_at = time.monotonic()


def step(label):
    """Advance a label shown with show_first_frame() by one frame, provided
    the frame on show has lasted its full duration. Accepts None.

    This is how QMovie behaved when the operation held the GUI thread: at each
    return of control it showed the next frame, however late, but never
    before its time.
    """
    if label is None or label.movie() is None:
        return
    movie = label.movie()
    now = time.monotonic()
    shown_at = getattr(label, "frame_shown_at", None)
    if shown_at is not None and (now - shown_at) * 1000 < movie.nextFrameDelay():
        return
    if not movie.jumpToNextFrame():
        movie.jumpToFrame(0)
    label.frame_shown_at = now
