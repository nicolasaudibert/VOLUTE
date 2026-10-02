# Changelog

Notable changes to VOLUTE. Versions are those reported by **Help › About** and
by the macOS application bundle; `volute/__init__.py` holds the number everything
else reads.

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
