# Changelog

Notable changes to VOLUTE. Versions are those reported by **Help › About** and
by the macOS application bundle; `volute/__init__.py` holds the number everything
else reads.

## 0.9.3 — 2026-10-14

### Added

- One-command installation on macOS and Windows: a line pasted into the
  Terminal or PowerShell installs Miniforge, a Python environment, the PyTorch
  build the hardware calls for (Apple Silicon, Intel Mac, NVIDIA GPU by the
  CUDA version its driver supports, or CPU), SAM2-Plus, the models chosen,
  ffmpeg and VOLUTE into a folder of its own, applies the SAM2 post-processing
  patch and creates the launcher. Nothing outside the folder is changed but
  the launcher. Run again, it updates VOLUTE, keeping the settings, adds
  models, and replaces PyTorch when the hardware calls for another build, after
  an NVIDIA driver update for instance; an interrupted installation resumes
  where it stopped. Run from a PowerShell opened as administrator, it leaves
  the folder readable without elevation, so that the Desktop shortcut opens
  VOLUTE. Its closing message says that ffmpeg is included and that GIMP, for
  retouching masks by hand, is to be installed separately. Among the models,
  MedSAM2 is offered, unselected: its four checkpoints and the config they
  need, so that it no longer has to be set up by hand; `a` selects every
  model. The question is skipped when every model is already there. It uses
  conda-forge alone, ignoring the channels a `~/.condarc` left by Anaconda or
  Miniconda would add. pip's cache stays in the installation folder, deleted once the
  installation succeeds: nothing is left in the user profile, and a cache
  entry written by an earlier run as administrator, which a later run without
  elevation could not read, no longer stops the installation. The error
  messages of pip and conda are copied into `install.log`, without pip's
  warnings about programs not on `PATH`. Nothing is left in
  `~/.conda/environments.txt`: conda no longer lists the environment there,
  and the line the Miniforge installer writes for its own folder, whatever
  the setting says, is taken out again. On Windows, Miniforge is
  installed with `/NoRegistry=1`: no "Miniforge3" entry is left among the
  installed applications, whose uninstall command failed once the folder was
  deleted.

### Fixed

- Ctrl + click puts a negative point again whatever widget has the keyboard
  focus. The key was read from the last key press the image area received, so
  with the focus on a button or a tab, as it is after clicking **Add points**,
  Ctrl went unseen and the click put a positive point; this showed on
  Windows. The modifier keys held during the click itself are now read, for
  the box and the reference points too, which ignore Ctrl + click.
- The messages about points outside an object's box no longer say that a
  negative point contradicts the box: a negative point there agrees with it,
  marking an area to leave out where the mask spills over the box. The
  confirmation asked for a point placed outside the box now says so, and the
  message shown when a box is drawn leaving points outside says that only the
  positive ones contradict it, the negative ones possibly no longer being needed.
- The model chooser no longer offers models that are not installed as if they
  were: their entries are greyed out, marked "not installed", with a tooltip
  saying how to add them by running the installation command again. Choosing one used to stop VOLUTE with an error; and with the list
  turned off at startup, a missing default model stopped it at every launch.
  The list now opens instead.
- The SAM2 post-processing patch now applies on an NVIDIA machine where SAM2
  was installed without compiling its CUDA extension. It checked only that CUDA
  was available, and exited, leaving masks without the hole-filling step.
- On a Mac without the Xcode Command Line Tools, `VOLUTE.app` now gets the same
  compiled launcher as elsewhere, from a universal binary (Apple Silicon and
  Intel) shipped with its source in `macos_launcher/`. It fell back to a script
  launcher, with which macOS refuses access to an installation under
  `~/Documents`, `~/Desktop` or `~/Downloads`, and `/usr/bin/cc`, a stub there,
  opened a dialog offering to install the tools; it is no longer called.
- The Windows launchers now work by double-click. They ran whichever `python`
  was on `PATH`, which outside an activated conda environment is not the one
  VOLUTE is installed in, or not a Python at all. `install_launchers_windows.bat`
  now finds the environment's interpreter — given as argument, active, on
  `PATH`, or a `sam2_plus` environment of Miniforge, Miniconda or Anaconda —
  checks that it imports SAM2, PyTorch and PyQt5, and writes it into each
  launcher along with the environment's directories on `PATH`. A launcher keeps
  its window open when the application stops on an error, and a **VOLUTE**
  shortcut is added to the Desktop. The script itself can be double-clicked:
  it no longer depends on being started from the root of the installation.
- A checkpoint given by absolute path inside the SAM2-Plus repository, such
  as `--checkpoint /…/SAM2-Plus/checkpoints/sam2.1_hiera_large.pt`, now loads.
  Any path containing `SAM2-Plus` was taken for a SAM2++ checkpoint, and the
  model failed to initialize. The family chosen at startup or with `--model` is
  now passed down to the backend; without `--model`, it is inferred from the
  checkpoint's file name and immediate parent folder only.
- The frame-extraction dialog writes durations and frame rates with the
  interface language's decimal separator: a comma in French, where it showed
  `2.22 s`. Its fields take a point or a comma in either language, and show
  the language's separator; a comma typed in English was read as a thousands
  separator, `1,5` giving 15.
- French interface: « Mode débogage » and « Supprimer des points », which read
  « Mode déboggage » and « Supprimer points ».
- French interface: every label now has a space before its colon, as most
  already did; « Nom de l'objet: » and « Opacité de l'arrière-plan: », among
  others, did not.
- **Batch Processing** speaks the interface language: its progress lines and
  its log — steps, per-frame progress, item results, errors and warnings —
  were in English whatever the language. The statistics after each item keep
  their technical names.
- **Settings** shows its lists in the interface language: « Oui » and « Non »,
  the two paces of the progress animation, and format names such as
  **Excel (XLSX)**, instead of the raw `yes`, `file` or `excel` of the
  configuration file, which are still the values written.
- **Re-propagate from this frame…** opens its span dialog again, and removing a
  set of imported points works: both stopped on an error, two names they use
  never having been imported.
- **Re-propagate from this frame…** now passes a correction on. SAM2 filed a
  correction made on an already-tracked frame apart from the frames it
  conditions on, so the re-propagation returned that frame's former mask, and
  the frames after it hardly changed. In mask mode, a corrected frame now
  becomes a conditioning frame, as in SAM2's own interactive training
  configurations.
- **Batch Processing** works again with **All combinations** selected for the
  reference points, the default: every item stopped on "'NoneType' object has
  no attribute 'get'", the options never reaching the processing. With that
  setting, **Include inter-object distances** and **Export point/mask
  analysis** were ignored as well.
- The first tab of **Batch Processing** reads "Items & Options", not
  "Items_Options": Qt took the "&" for a shortcut marker.
- **Batch Processing** exports the convex hull coordinates when **Export hull
  coordinates** is checked. The export followed **Export closest mask points**
  instead, so the hull box did nothing, and the closest-points box produced a
  hull file as well.
- **Batch Processing** exports the tracked points in SAM2++ point tracking
  mode when **Export tracked points** is checked, a box of the processing
  options, unchecked by default and available only in that mode: the
  trajectories were computed, then never written. Each item's reference frame
  is also seeded as in interactive mode, from each object's first positive
  point, instead of going through the mask-mode prompt.
- **Batch Processing** speaks of points in SAM2++ point tracking mode: its
  propagation box reads **Propagate points**, and its log "Propagating tracked
  points…", where both spoke of masks. In mask mode, **Export tracked points**,
  then unavailable, says in a tooltip which mode it requires.

### Documentation

- Installation guides for Windows and macOS, in English and French, written for
  people who have never used a command line: `docs/install-windows.md` and
  `docs/install-macos.md`, with their `.fr.md` translations.
- A FAQ, in English and French: `docs/faq.md` and `docs/faq.fr.md`.
- A documentation site, in English and French, at
  https://nicolasaudibert.github.io/VOLUTE/: the installation guides and the
  FAQ, under a home page of their own. `build_docs.py` builds it from `docs/`
  with Zensical, and a GitHub Actions workflow publishes it whenever `main`
  changes it.
- A tutorial, in English and French, in `docs/tutorial/`: starting VOLUTE,
  extracting and browsing the frames of a video, outlining an object with a box
  then points, a second object outlined with a box alone, correcting masks on
  that frame, with more points or by hand in GIMP, following the objects
  through the video and correcting the tracking where it goes wrong, the
  display settings and reference points, the exports, saving and resuming a
  project and batch processing, point tracking with SAM2++, and the settings
  and keyboard shortcuts.
  It is illustrated with screenshots, and works on a short excerpt of the
  Nancy real-time MRI corpus (Isaieva et al., 2021, CC0); footnotes explain its
  anatomical terms to readers outside speech science.
  `tutorial/make_excerpt.py` builds the excerpt from the original data, and
  `tutorial/capture_screenshots.py` drives VOLUTE to take the screenshots again.
- The FAQ points to the matching steps of the tutorial as well as to the
  reference documentation on GitHub, each link saying which of the two it leads
  to. On the site, links leading outside it open in a new tab.
- `INSTALL.md`:
  - the CUDA 12.1 command could not succeed, PyTorch 2.7.0 being built for
    CUDA 11.8, 12.6 and 12.8 only; the commands now cover those three, CPU only
    on Windows and Linux, Apple Silicon without the nightly index, and Intel
    Macs, which PyPI no longer serves, through conda-forge;
  - `robocopy` replaces `rsync` on Windows;
  - references to MedSAM2 symlink scripts that do not exist, to a misnamed
    launcher script and to an `en.tsv` file are gone;
  - the command-line options list `--task`, and the model chooser that opens
    when no model is given;
  - the configuration section points to the settings dialog instead of a stale
    copy of the file.

## 0.9.2 — 2026-10-02

### Added

- **File › Extract Frames from Video…** turns a video file into the folder of
  numbered frames the application loads, through ffmpeg, then offers to load
  it. Options: JPEG (default, quality 1–100) or PNG, every frame or a number of
  frames per second, and an optional time range. Frames are named after the
  video, numbered from 0 and zero-padded to at least five digits — more when
  the frame count calls for it — so they sort in playback order in every tool.
- A destination folder that already holds images is refused rather than mixed
  with the new frames. A cancelled or failed extraction leaves no frame behind,
  nor the destination folder when the extraction created it.
- `ffmpeg.executable_path` overrides where ffmpeg is looked for; it defaults to
  none, and discovery searches `PATH`, then the usual Homebrew, MacPorts, conda
  and system locations that an application started from the Finder does not
  see on its `PATH`.

### Fixed

- Saving the settings lost the GIMP and ffmpeg executable paths: a setting
  whose whole section was missing from `volute_config.yaml` was not written,
  so the path applied for the session and was gone at the next start. Such a
  section is now added to the file, and the shipped file carries both,
  documented.
- A setting missing from an existing section of `volute_config.yaml` was
  written after the heading of the next section, where it read as belonging
  to it. It now goes at the end of its own section; the keys already misplaced
  that way in the shipped file are back in their sections.

### Documentation

- `INSTALL.md` explains how to install ffmpeg, and what to check when the
  application does not find it.

## 0.9.1 — 2026-10-02

### Fixed

- The GIMP round-trip now finds GIMP without a hardcoded path. The executable
  override defaulted to the GUI binary inside `GIMP.app`, with two consequences.
  That binary brings up GTK even under `-i`, so it aborted with *"Can't create a
  GtkStyleContext without a display connection"* when started with no usable
  display — as happens before GIMP has been run once since a system update. And
  being an absolute macOS path, it was invalid everywhere else, where an invalid
  override is reported as not detected rather than falling back to `PATH`: the
  round-trip was therefore unavailable on Linux and Windows out of the box.

  The override now defaults to none, and discovery falls back from `PATH` to the
  macOS bundle, through the unversioned symlinks there that keep pointing at the
  right binary across a GIMP update. `gimp-console` is preferred at every step:
  it carries no GUI, opens no window, and cannot fail for want of a display.

### Documentation

- The requirements said GIMP 2.10 or later, where the generated batch script
  calls the GIMP 3 API throughout and nothing from the 2.x procedural database.
  GIMP 3.0 or later is required.
- The configuration reference describes how the executable is actually found,
  and notes that a shell alias cannot help: the application looks the name up
  itself, where aliases do not exist.

## 0.9 — 2026-10-01

First public release.

A PyQt5 application for interactive and batch video segmentation and point
tracking over SAM2, MedSAM2 and SAM2++: objects defined by points, boxes or
imported masks, bidirectional propagation, a correction and re-propagation
workflow, a GIMP round-trip for external mask editing, reference points and
imported point trajectories, batch processing, undo/redo, and exports to masked
images, coordinates, centroids, convex hulls and outer contours.
