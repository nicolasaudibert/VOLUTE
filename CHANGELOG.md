# Changelog

Notable changes to VOLUTE. Versions are those reported by **Help › About** and
by the macOS application bundle; `volute/__init__.py` holds the number everything
else reads.

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
