# Application icon

Drop an icon file here and the application picks it up at startup — no code
change needed. `VOLUTE.py::find_app_icon()` looks for, in this order:

1. `icon_<size>.png` — several files combined into one multi-resolution icon,
   e.g. `icon_16.png`, `icon_32.png`, `icon_128.png`, `icon_512.png`. Preferred:
   each size can be tuned rather than downscaled automatically.
2. `icon.png` — a single square image; 512×512 downscales acceptably.
3. `icon.svg` — needs Qt's SVG image plugin, shipped with PyQt5.
4. `icon.ico` — a Windows icon container.

When none is present, the platform's default Python application icon is used.

`about_logo.png` is optional and separate: a lockup showing the icon with the
name below it, ideally on a transparent background, displayed at 320 px wide in
the About dialog in place of the text title. Without it, the dialog shows
`icon_128.png` above the title.

`icon.icns` (macOS bundle) and `icon.ico` (Windows) also live here; the bundle
script copies the `.icns` into the application and declares it as its icon.

# Progress animation

`progress.webp` or `progress.gif` is optional: drop one here and the progress
dialogs show it centred **above** their progress bar, never instead of it. With
no such file the dialogs lay out exactly as they do now, down to their height.
`progress_animation.py` looks for, in this order:

1. `progress.webp` — an animated WebP. Preferred: a full alpha channel and
   24-bit colour, so the edges stay clean over the dialog background.
2. `progress.gif` — 256 colours and a single transparent index, which shows as
   fringing unless the animation was authored over the dialog's own background.

Qt animates these two formats and no other; an APNG is read as a still image.
A file Qt cannot decode is ignored as if it were absent.

Authoring notes:

- The animation is drawn in a square of `progress_animation.DISPLAY_SIZE`
  logical pixels, **96** by default. Change that one constant and every dialog
  follows. Author the file at **twice** that, 192×192, since a HiDPI display
  draws two device pixels per logical one and would otherwise upscale and blur
  it.
- Every frame is decoded when the dialog opens, which costs about
  `width × height × 4 bytes × frames` of memory — a 192×192 animation of 16
  frames is under 2.5 MB. Keep the frame count modest all the same.
- The animation loops for as long as the operation runs, so give it a seamless
  cycle and set its loop count to infinite.
- A square is assumed. A non-square file is squashed into one, so crop it
  before dropping it here.

Where it appears:

- **Batch dialog** — above the progress area, running only while a batch runs.
- **SAM2 state export and import** — at the top of the dialog, whose fixed
  height grows by the animation's.
- **Every other progress dialog** — prediction, propagation and
  re-propagation, point tracking, folder loading and GIMP export — above the
  text and the bar. These are `AnimatedProgressDialog`, a `QProgressDialog`
  that frees a row at the top for the animation; with no animation file they
  are plain `QProgressDialog`s, down to their size.

Every one of these operations runs its work in a worker thread, so the
animation plays at the frame durations stored in the file. Two exceptions
remain in the SAM2 state import: synchronizing the masks and refreshing the
display update the interface, so they run on the GUI thread and the animation
pauses while they do.

`ui.progress_animation_pacing` in `volute_config.yaml`, also in the settings
dialog, can set it to `"progress"` instead: in prediction, propagation and the
SAM2 state export and import, the animation then advances one frame per
progress update, never faster than the file allows. Folder loading, GIMP export
and batch processing always follow the file.

## Per-platform notes

- **Windows / Linux**: this icon is used for the windows and the taskbar.
- **macOS**: an application bundle's own `.icns` wins for the Dock icon. Put the
  `.icns` at `<bundle>.app/Contents/Resources/` and declare it with
  `CFBundleIconFile` — `install_app_bundle_macos.sh` does not do so, since the
  icon is a design choice rather than something to generate. The icon here still
  applies to windows, and to the Dock when the GUI runs outside a bundle.
