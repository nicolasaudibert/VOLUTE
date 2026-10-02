# VOLUTE

**V**ideo **O**bject **L**abeling, **U**ser-guided **T**racking and **E**xtraction

A PyQt5 desktop application for interactive and batch video segmentation and point tracking using [SAM2](https://github.com/facebookresearch/segment-anything-2), [MedSAM2](https://github.com/bowang-lab/MedSAM2), and [SAM2++](https://github.com/MCG-NJU/SAM2-Plus).

---

## Features

### Model Support
- **SAM2** (standard): all `sam2.1_hiera_*` checkpoints
- **MedSAM2**: `MedSAM2_latest.pt` and domain-specific variants (US Heart, MRI Liver Lesion, CT Lesion)
- **SAM2++**: unified tracking at mask, bounding-box, and point granularity; currently supported modes are **mask** (drop-in compatible with SAM2) and **point** (tracked point trajectories)
- Automatic model type detection from checkpoint filename
- Model name displayed in window title after loading; for SAM2++, the active sub-mode (Mask mode / Point tracking mode) is also shown, localized and rebuilt automatically on language change

### Point-Based Segmentation (mask mode)
- **Add points mode** — unified interaction:
  - Left click → positive point (green)
  - Right click or Ctrl+click → negative point (red)
- **Remove points mode** — click and drag to draw a rectangle; all enclosed points are removed
- **Define box mode** — click and drag to define a bounding box (see Box-Based Prompting below)
- Tooltips on each mode button explain the interaction model
- Clear all points button for the current object and frame
- Adding points is only available with a single object/point selected; attempting it with a multi-selection active shows a warning dialog

### Box-Based Prompting (mask mode only)
A third way to define a mask, combinable with the points above: an optional bounding box per (object, frame), passed to SAM2 in the same call as that frame's points.

- **Define box** mode (Points Configuration panel): click and drag to draw the box; a drag shorter than 3 pixels in either dimension is treated as an accidental click and ignored. Drawing a new box replaces the object's existing one on that frame. **Remove box** deletes it, and is enabled only when the current object has a box on the current frame
- One box per object and frame. Prompt order is irrelevant — points may be placed before or after the box
- No box means prediction runs on the whole frame, exactly as before
- The box is displayed as a dashed rectangle in the object's mask color, for every selected object
- **The box is a soft prompt**: SAM2 receives it alongside the points and is not geometrically constrained by it. Points outside the box are *not* discarded — they contradict it. Two guards follow from this:
  - drawing a box that excludes existing points reports how many positive and negative points it contradicts, and offers to delete them — a single Ctrl/⌘+Z then restores both the previous box and the deleted points
  - adding a point outside an existing box asks for confirmation, with a session-only *Don't ask again* checkbox
- **Box on a frame with an imported mask**: a box and an imported mask are competing conditioning inputs, so a cancelable warning explains that the next prediction will replace the imported mask, with an option to delete that mask right away. The reverse case — importing a mask onto an object/frame that already has a box — asks the same question once for the whole import
- A box added to an already-tracked frame counts as a correction once a prediction has used it: **Re-propagate from this frame…** becomes available then, not at the moment the box is drawn (the box only reaches SAM2 at the next prediction)
- Strict confinement of the resulting mask to the box is available as an option — see Mask Prediction and Propagation

### Multi-Object Management
- Add or remove named objects (points, in SAM2++ point mode) at any time
- Default names follow the active mode: "Object 1", "Object 2", … in mask mode; "Point 1", "Point 2", … in SAM2++ point mode
- The name field sits directly below the object/point list, above the **Import from file…** button
- **Multi-selection** (Ctrl+click, Shift+click, click-and-drag) in the object/point list:
  - Bulk property editing applies color, marker style/size, and mask opacity changes to every selected object/point at once
  - The name field is disabled (and cleared) while more than one object/point is selected
  - The **Current Object/Point Configuration** panel shows a mixed-value indicator whenever selected objects/points differ on a property: a hatched pattern on color swatches, no selection in the marker style dropdown, a dash placeholder instead of a number for marker size and mask opacity, and a grey-recolored slider track/handle for marker size and mask opacity
  - The **Remove** button deletes all selected objects/points at once (with an adapted confirmation message), but always keeps at least one object/point
  - The **Show points (current object)** / **Show current point** toggle displays points for every selected object, while point addition itself remains restricted to a single selection
  - A newly created object/point becomes the exclusive selection, clearing any prior selection
- Each object has independently configurable:
  - Positive / negative point colors (mask mode) — point mode instead exposes a seed point color and a tracked point color, with no negative color and no opacity
  - Mask color and opacity (mask mode only)
  - Marker style and size
- Mask colors are automatically assigned from a perceptually distinct palette; new colors are chosen to maximize distance from all currently used colors (including manually modified ones)
- Names can be imported in bulk from a plain-text file (one name per line) via the **Import from file…** button below the name field. If non-default objects already exist, a dialog asks whether to overwrite or append; duplicate names can be renamed with a numeric suffix or skipped.

### Mask Prediction and Propagation (SAM2 / MedSAM2 / SAM2++ mask mode)
- **Predict on current frame** — runs SAM2 inference for all objects carrying a prompt on the active frame: points, a bounding box, or both
- **Propagate through video** — bidirectional propagation (forward from reference frame, then backward if the reference is not the first frame)
- **Strict box confinement** (optional, Prediction tab) — clears every predicted pixel falling outside the object's bounding box. Two variants: *Frames with a box* clips only the frames that carry one, leaving propagated frames untouched; *All frames (reference box)* falls back to the box defined on the object's first frame everywhere else — only meaningful for an object that does not move, and warned about once per session
  - Clipping is applied before the mask is stored, so centroid, convex hull and outer contour all describe the clipped mask. It is therefore **not reversible**: turning the option back off affects subsequent predictions only, and an already-clipped mask has to be regenerated by predicting or propagating again
  - **Forward/backward asymmetry**: clipping affects only the mask stored application-side. SAM2's internal state keeps the unclipped logits, so forward propagation from a clipped frame propagates the unclipped shape, whereas backward propagation — which resets the backend and replays the stored masks via `add_mask` — propagates the clipped one

### Mask-Based Initialization (mask mode only)
For objects hard to segment from points alone, a pre-composed external binary mask (e.g. built in GIMP from combined geometric shapes) can be imported as the conditioning input for one or more frames, instead of — or before — placing points.

- **File › Import Masks…** opens a file dialog accepting any image format supported by `FileManager`/PIL, or one or more `.xcf` files (as produced by **Export Frame/All Frames for Editing…** above); available in mask mode only
- **XCF format**: each mask layer (named `mask::<id>::<name>::<filename>`) is matched to an object by name — creating a new object for an unmatched name — and to a frame by filename, mirroring the plain-file multi-frame matching below. Extraction runs via a batched GIMP invocation covering every selected `.xcf` file at once (see GIMP-Assisted Mask Editing). If the session currently holds only the untouched default object (no points, no masks), the person is offered to replace it with the imported object(s) instead of adding to it. No color-detection heuristics involved — unlike the plain-image formats below — since the layer name is unambiguous. Mask boundary: alpha ≥ 128 per pixel
- **Single-object format**: one image per (object, frame), any non-zero pixel counts as foreground — the imported mask is applied to the currently selected object (single selection required, mirroring the point-add restriction)
- **Multi-object color-composite format**: one image covering several objects at once, each painted with a distinct flat color (e.g. one GIMP layer per object, flattened before export). Detected automatically when an image contains more than one significant non-background color (a color covering at least 0.5% of pixels; smaller regions are treated as anti-aliasing/compression noise, not a genuine color). A one-time dialog then maps each detected color to an existing object or a newly created one; the mapping is applied identically to every multi-object file in a multi-frame import
  - **Known limitation**: a flat composite image cannot represent two objects overlapping on the same frame. Frames with expected overlap must use the single-object format (one file per object) instead
- **Multi-frame import**: selecting several mask files at once matches them to frames by original filename against the current image folder, mirroring the filename-matching approach used for tracked-point import; unmatched filenames are skipped with a warning
- Imported masks are stored exactly like predicted ones (`object_manager.store_mask`) — centroid, hull, and contour recomputation, and display, all follow automatically with no separate code path
- **Point refinement before propagation**: adding a positive/negative point to a frame that already has an imported mask (and no prior points) automatically resends the stored mask to SAM2 immediately before the point, since SAM2 would otherwise silently discard it. This is fully automatic — no extra UI action needed
- **Point refinement after propagation, with optional bounded re-propagation**: a correction point can be added to any already-tracked frame through the ordinary point-add flow, which SAM2 treats natively as a correction. The **Re-propagate from this frame…** button (Prediction tab) becomes enabled once such a correction has been made on the currently selected object/frame, and opens a small dialog with two optional integer fields (forward/backward span in frames, 0 = unbounded) before re-running propagation for that object only, without resetting the rest of the session
- Imported masks can be persisted in `.volute` project files, unlike predicted ones: a dialog at save time offers to include them, and a reloaded project re-registers them with SAM2 as conditioning (see Project Data Management)

### GIMP-Assisted Mask Editing (mask mode only)
Exports the current frame's background image plus one mask image per object as a starting point for external editing in GIMP (or any image editor via the plain-files mode), for later re-import via **Import Masks…** above — either directly as `.xcf`, or via the per-object subfolders produced by the plain-files mode.

- **File › Export Frame for Editing…** opens a dialog offering two modes:
  - **Single .xcf file** — background and one layer per object (named `mask::<id>::<name>::<filename>`) assembled into a multi-layer `.xcf` by invoking GIMP itself in non-interactive batch mode (Python-Fu). The output file is named after the source frame's basename, consistently with the multi-frame export. Available only when a GIMP command-line executable is detected (`gimp-console`/`gimp` on `PATH`, or an explicit override — see Configuration)
  - **Separate image files** — background copied as-is, plus one mask image per object written into a per-object subfolder (`obj<id>_<name>/`), each keeping the exact source frame filename so it's directly reusable as Format A **Import Mask…** input, no GIMP round-trip needed
- **File › Export All Frames for Editing…** — same two modes, applied to every frame that has at least one object mask defined, after a confirmation dialog stating how many frames will be exported. `.xcf` mode assembles every frame's file in a single batched GIMP invocation (one GIMP startup for the whole export, not one per frame); plain-files mode writes one subfolder per frame, each holding the background and per-object mask subfolders as above
- Each mask image: filled with the object's configured mask color at full opacity where a prediction already exists on this frame, fully transparent elsewhere (ready to hand-paint)
- Both GIMP export actions, and `.xcf` mask import (below), run in a background thread with a progress dialog while GIMP starts and runs — the application stays responsive during what can otherwise be a multi-second freeze. The dialog starts indeterminate (GIMP's startup dominates before the first item completes) and switches to determinate once per-item progress is reported
- **Cancellation** — the progress dialog's Cancel button kills the running GIMP process immediately, with no confirmation step. What survives depends on the operation:
  - *Multi-frame `.xcf` export and plain-files export*: frames already fully written are kept on disk (the output folder may hold pre-existing files, so wiping it is not an option); only the frame being written when GIMP was killed — possibly truncated — is removed. The resulting message reports how many frames of the total completed
  - *Single-frame `.xcf` export*: the possibly truncated output file is removed, leaving nothing behind
  - *`.xcf` mask import*: all-or-nothing by construction — the GIMP step only writes temporary artifacts, and nothing is applied to the session until extraction has fully returned, so a cancelled import leaves the session untouched and needs no rollback
- **GIMP round-trip workflow**: export as `.xcf` (single frame or all frames) → edit and save in GIMP → re-import directly via **File › Import Masks…**, selecting one or more edited `.xcf` files at once. Each mask layer's name already identifies its object and source frame, so import is fully automatic — no manual per-object extraction step, no Script-Fu/Python-Fu console interaction needed

### Point Tracking (SAM2++ point mode)
Place one positive point per object on a reference frame, then propagate. SAM2++ tracks each point across the video by returning per-frame argmax coordinates of a Gaussian heatmap, rather than a binary mask.

- Left click places the seed point for the current object on the current frame, replacing any previous seed point; there are no negative points and no Remove points mode
- Adding a seed point is only available with a single object/point selected; a warning dialog appears otherwise
- Tracked positions are shown on each frame as markers in the object's color, with a style and size configurable globally in the **Tracked Point Display** panel (Prediction tab); default style is a filled plus
- The object's name is shown next to its marker when **Show labels** is enabled
- A localized mode indicator appears both in the window title and above the canvas when this mode is active
- Mask-specific controls (centroids, contours, hulls, mask opacity) are not applicable in point mode
- Results are exported independently from masks (see Export section), including distances to reference points

### Display Options
- Background image opacity slider
- Object label overlay toggle
- **Global show-points toggle** — when enabled, displays points for all currently selected objects (or their current seed points, in point mode); updates automatically when the selection changes
- Centroid display with configurable color and size (mask mode only)

#### Mask Contours (mask mode only)
Optional per-object outer contour and convex hull display, grouped in a single "Mask Contours" panel with two sub-tabs.

**Outer Contour** tab — uses `skimage.measure.find_contours` (fallback: `cv2.findContours`):
- **Show outer contours** — global show/hide toggle, disabled by default
- **Smoothing** — periodic Gaussian smoothing of the raw contour (0 = raw, 100 = maximum); contour area is preserved by rescaling after smoothing; recomputation is triggered on slider release
- **Line width** — contour thickness (1–10 px)
- **Show outer border** — optional border rendered via `patheffects.withStroke` (~1.5 px on each side of the primary line, no geometric distortion); disabled by default
- **Border color** — picker for the border color

**Convex Hull** tab — uses `scipy.spatial.ConvexHull`:
- **Show convex hulls** — global show/hide toggle, disabled by default
- **Smoothing** — periodic Gaussian smoothing of the raw hull (0 = raw, 100 = maximum); hull area is preserved by rescaling from the centroid after smoothing; recomputation is triggered on slider release
- **Line width** — contour thickness (1–10 px)
- **Show outer contour** — optional inner and outer border lines drawn using a geometric radial offset for legibility; disabled by default
- **Contour color** — picker for the border color

#### Tracked Point Display (SAM2++ point mode only)
- **Marker style** — combo box (`P`, `o`, `s`, `^`, `D`, `*`, `X`); applied globally to all objects' tracked points
- **Marker size** — slider (3–30)

### Reference Points
Named, frame-aware reference points can be placed independently of segmentation objects and stored in the project file, in both mask mode and SAM2++ point tracking mode.

- Canvas click behavior depends on which control-panel tab is active: with the **Ref. Points** tab active, a plain left-click places or replaces the position of the currently selected reference point on the current frame; right-click and Ctrl+click are ignored (no negative equivalent for reference points). See **UI Layout** below for the full per-tab click behavior.
- Multiple named points supported; each point can have a different position per frame
- Each reference point has an independently configurable color, marker style, and marker size, set in the Ref. Points tab and mirroring the per-object configuration on the Objects/Points tab
- **Multi-selection** (Ctrl+click, Shift+click, click-and-drag) in the reference point list:
  - Bulk property editing applies color, marker style, and marker size changes to every selected reference point at once
  - The **Current Reference Point Configuration** panel shows a mixed-value indicator whenever selected reference points differ on a property (hatched color swatch, blank marker-style dropdown, dash placeholder and greyed slider for marker size)
  - The name field is disabled (and cleared) while more than one reference point is selected; renaming requires a single selection
  - **Remove (all frames)** and **Remove (this frame)** both apply to every selected reference point at once, with a grouped confirmation message when more than one is selected
  - Placing a point via canvas click is restricted to a single selection; a warning dialog appears otherwise
  - A newly created reference point becomes the exclusive selection, clearing any prior selection
- Editing the point name field renames the selected reference point immediately (live rename); it does not affect the name assigned when creating a new point, which is always auto-generated (mirroring **Add object** / **Add point** on the Objects/Points tab)
- Reference point names can be imported in bulk from a plain-text file (one name per line) via the **Import from file…** button; the same overwrite / append / duplicate-handling logic as for object import applies
- Positions between annotated frames are linearly interpolated; extrapolation outside the annotated range is flagged with a warning before export
- Reference points are stored in the `.volute` project file under a dedicated key (backward-compatible)
- **Advanced mode** (per-name toggle, disabled/simple by default): in simple mode a
  reference point has a single position, constant across all frames. In advanced
  mode, each point can have a distinct position per frame, with:
  - The Ref. Points list showing the number of defined frames next to each name
  - A confirmation dialog (with a "don't ask again" option, session-only) before
    a canvas click changes an already-interpolated position
  - Per-point **extrapolation policy**, shown once at least 2 frames are defined
    with at least one of them neither the first nor the last frame of the sequence:
    extrapolate (default), leave undefined, or clamp to the nearest boundary position
  - Per-point **interpolation mode**, shown once more than 2 frames are defined:
    cubic spline (default) or linear
  - Explicitly-defined positions are shown with a thicker marker edge and a bolder
    label, in addition to full opacity (vs. 0.55 for interpolated ones)
- Disabling advanced mode is blocked while any reference point still has more than
  one explicitly defined frame
- **Navigation buttons** to jump to the previous/next frame with an explicitly
  defined position for the selected point, available in both simple and advanced
  mode (useful in simple mode to jump back to the frame the position was originally
  set on, for visual verification); only one button is active when just one frame
  is defined, and both are disabled if no other defined frame exists in that
  direction; disabled during multi-selection

### Imported Points (mask mode only)
Named points imported from a SAM2++ point-mode "Export tracked points" file, displayed
alongside masks and analyzed against mask-mode objects (containment and distance metrics).

- **File › Import Tracked Points…** opens a file dialog accepting `.xlsx` / `.csv` / `.json`
  (the formats produced by the point-mode tracked point export); available in mask mode only
- Points are matched to the current session by **original filename**, not by frame index,
  so imports remain valid across different frame orderings or subsets
- Import validation, each non-blocking unless noted:
  - **Frame count mismatch** between the imported file and the current image folder — blocking
    confirmation dialog before proceeding
  - **Unmatched filenames** — warns and proceeds with the matched subset; if no filenames match
    at all, the import is aborted with an error
  - **Out-of-bounds coordinates** — after import, warns per name if imported positions fall
    outside the current image dimensions, which may indicate a dimension mismatch with the
    source session
  - **Name conflicts** with existing objects or reference points — non-blocking warning,
    mirroring the existing cross-name-conflict pattern
- Imported points use **pixel coordinates** directly (not normalized), since they may originate
  from a session with different image dimensions; no interpolation or extrapolation — a point
  is shown only on frames where it was explicitly present in the imported file
- Each imported point name has an independently configurable color, marker style, and marker
  size, set in the **Imported Points** panel (Prediction tab, mask mode only)
- **Global show/hide toggle** for all imported points
- Selection is single-selection only; removing an imported point removes all of its frames
- Imported points are stored in the `.volute` project file under a dedicated key
  (backward-compatible)

#### Point/mask analysis export
For each (object, imported point) pair and each frame where both a mask and an imported point
position exist, computes containment flags and distance metrics.

Export columns: `Object_Name`, `Object_ID`, `Imported_Point_Name`, `Frame_Index`,
`Original_Filename`, `Point_X_px`, `Point_Y_px`, `Inside_Mask`, `Inside_Hull`, `Inside_Contour`,
`Distance_To_Centroid_px`, `Distance_To_Mask_px`, `Distance_To_Hull_px`,
`Distance_To_Contour_px`. Hull/contour columns are blank when no hull/contour was computed for
that object/frame.

Uses the same pair-selection dialog as closest mask points, restricted to imported points as
targets. Enabled only when both masks and imported points exist.

### Undo / Redo History
An Edit menu exposes **Undo** (Ctrl/⌘+Z) and **Redo** (Ctrl/⌘+Shift+Z), backed by a generic command stack (`history_manager.py`). Covered actions:
- Point edits: add, remove-in-area, clear (single object or bulk clear across a multi-selection)
- Box edits: add, replace, remove — each as a single step also covering the points deleted for contradicting the box, and the imported mask deleted alongside it when that option was ticked
- Property changes: positive/negative/mask/tracked-point colors, marker style, marker size, mask opacity, tracked point global style/size — one undo step per bulk action, not per object
- Object/point add and remove (including bulk removal of a multi-selection)
- Object/point name changes (recorded once editing finishes, not per keystroke)
- Reference point add, remove (all frames / current frame only, single or bulk across a multi-selection), and rename
- Reference point property changes: color, marker style, marker size — one undo step per bulk action, not per point

Object mask prediction/propagation and reference point interpolation are not part of the undo history.

### Export
All exports use original source filenames. Export actions are disabled (greyed out) until at least one mask has been predicted or, in point tracking mode, at least one point trajectory has been computed. In SAM2++ point tracking mode, the Export menu only contains the point-tracking export items below — the other export types are not shown.

| Export type | Format | Keyboard shortcut |
|---|---|---|
| Masked images (mask mode) / Images with tracked points (point mode) | JPEG | Ctrl/⌘+Shift+I |
| Mask coordinates | JSON / CSV / Pickle | Ctrl/⌘+Shift+M |
| Centroids | XLSX / CSV / JSON | Ctrl/⌘+Shift+T |
| Closest mask points (mask mode) / Closest tracked point distances (point mode) | XLSX / CSV / JSON | Ctrl/⌘+Shift+K |
| Convex hull coordinates | XLSX / CSV / JSON | Ctrl/⌘+Shift+H |
| Contour coordinates | XLSX / CSV / JSON | Ctrl/⌘+Shift+U |
| Point/mask analysis (imported points vs. objects, mask mode) | XLSX / CSV / JSON | Ctrl/⌘+Shift+A |
| Tracked points (SAM2++ point mode) | XLSX / CSV / JSON | Ctrl/⌘+Shift+P |
| Project data (save) | `.volute` | Ctrl/⌘+S |
| Project data (open) | `.volute` | Ctrl/⌘+O |
| SAM2 inference state | `.voluteinf` | — |

#### Closest mask point export (mask mode)
For each (object, target) pair and each frame where both a mask and a target position exist, the mask pixel closest to the target is recorded along with the Euclidean distance in pixels.

Targets can be:
- **Reference points** — interpolated position of a named reference point
- **Other objects** — closest pixel of another object's mask to the source object's mask on the same frame, i.e. the pixel pair realising the minimum inter-mask distance (opt-in)

Export columns: `Object_Name`, `Object_ID`, `Target_Type`, `Target_Name`, `Frame_Index`, `Original_Filename`, `Closest_X`, `Closest_Y`, `Distance_px`, `Ref_X_px`, `Ref_Y_px`.

A pair-selection dialog opens before the file dialog, offering:
- All combinations (default)
- A manually curated list of pairs, with dropdown selection of objects and targets
- TSV import / export of the pair list
- When inter-object distances are enabled, the target list for a given object automatically excludes that object itself (no self-distance pairs)

#### Closest tracked point distance export (SAM2++ point mode)
Same pair-selection dialog as above, applied to tracked point positions instead of mask pixels: for each (object, target) pair and frame, the Euclidean distance between the object's tracked point and its target (a reference point, or another object's tracked point when inter-object distances are enabled) is recorded directly — no nearest-pixel search is involved since tracked points are single coordinates.

Export columns: `Object_Name`, `Object_ID`, `Target_Type`, `Target_Name`, `Frame_Index`, `Original_Filename`, `Point_X_px`, `Point_Y_px`, `Target_X_px`, `Target_Y_px`, `Distance_px`.

#### Convex hull export
Output columns: `Object_Name`, `Object_ID`, `Frame_Index`, `Original_Filename`, `Vertex_Index`, `X_norm`, `Y_norm`, `X_px`, `Y_px`, `Mask_Coverage`.

`Mask_Coverage` is the fraction of active mask pixels contained within the (possibly smoothed) hull polygon. It equals 1.0 for unsmoothed hulls; values below 1.0 reflect the geometric effect of smoothing combined with area rescaling.

#### Contour coordinates export
Output columns: `Object_Name`, `Object_ID`, `Frame_Index`, `Original_Filename`, `Vertex_Index`, `X_norm`, `Y_norm`, `X_px`, `Y_px`, `Mask_Coverage`.

`Mask_Coverage` is the fraction of active mask pixels contained within the (possibly smoothed) contour polygon. It equals 1.0 for unsmoothed contours; values below 1.0 reflect geometric distortion introduced by smoothing combined with area rescaling.

#### Tracked point export (SAM2++ point mode)
Output columns: `Object_Name`, `Object_ID`, `Frame_Index`, `Original_Filename`, `X_px`, `Y_px`.

One row per (object, frame) pair where a tracked position is available.

### Project Data Management
- **Export project data** (Ctrl/⌘+S) — saves object names, colors, markers, points, **bounding boxes**, reference points, imported points, and tracked point trajectories (SAM2++ point mode); predicted masks and centroids are intentionally excluded to keep files small and portable, since predicting or propagating again regenerates them
- **Imported masks** are the exception: no prompt can regenerate them, so when the project contains any, a dialog offers to include them in the file (larger, self-contained) or to leave them out and re-import them after loading. Including them is the default
- **Import project data** (Ctrl/⌘+O) — restores objects, points, boxes, reference points, imported points, and tracked trajectories; re-registers the imported masks and then each object's prompts with the SAM2 backend, so prediction can resume immediately
- Files written by earlier versions (without boxes or imported masks) import unchanged
- Image dimension mismatch detected on import with user confirmation

### Batch Processing
The batch dialog (`File › Batch Processing…`) processes a list of (`.volute` file, image folder) pairs without user interaction.

Everything a `.volute` file defines is used automatically, with no dedicated option: points, bounding boxes, and imported masks when the file carries them. An object defined by a box alone, or by an imported mask alone, is processed like any other. Strict box clipping is a session-level display setting, is not stored in the project file, and therefore **never applies to batch runs**.

**Tab 1 — Items & Options**

- Add rows manually or import a TSV file with columns `sam2_file`, `image_folder`, `ref_frame`
- Browse buttons populate the selected row's `.volute` file or image folder
- The `Ref Frame` column is optional; leave empty to use the first frame carrying any object definition — points, a bounding box, or an imported mask
- Export the table to TSV for reuse
- The `Tracked Points File` column (optional) accepts `.xlsx` / `.csv` / `.json`, matching interactive-mode import; leave empty to fall back to `imported_point_data` already stored in the `.volute` file, if any

Processing options:

| Option | Default |
|---|---|
| Propagate masks | ✓ |
| Export masked images | ✓ |
| Export centroids | ✓ |
| Export mask coordinates | ✓ |
| Export hull coordinates | ✗ |
| Export contour coordinates | ✗ |
| Export tracked points (point mode) | ✗ |
| Export inference state after prediction | ✗ |
| Export inference state after propagation | ✗ |
| Background opacity slider | 100 % — enabled only when Export masked images is ticked |
| Hull smoothing (0–100) | 0 — enabled only when Export hull coordinates is ticked |
| Contour smoothing (0–100) | 0 — enabled only when Export contour coordinates is ticked |

**Tab 2 — Reference Points**

Enables closest mask point export for batch items. The tab content is inactive unless the **Export closest mask points** checkbox is ticked.

- **All combinations** — every (object, reference point) pair found in each `.volute` file
- **Selected pairs** — a manually curated table of (object, target) pairs; target type (reference point or object) is set per row via a dropdown
- **Include inter-object distances** — when enabled, objects are also available as targets (centroid-to-mask distance)
- TSV import / export of the pair list (columns: `object`, `target`, `target_type`)

**Tab 3 — Imported Points**

Enables point/mask analysis export for batch items. The tab content is inactive unless the **Export point/mask analysis** checkbox is ticked.

- **All combinations** — every (object, imported point) pair found in each item
- **Selected pairs** — a manually curated table of (object, imported point) pairs
- TSV import / export of the pair list (columns: `object`, `imported_point`)

Import and validation of tracked points happens automatically per item (via the `Tracked Points File` column or the `.volute` fallback) before prediction; frame-count mismatches, unmatched filenames, and out-of-bounds coordinates are logged as non-blocking warnings rather than interrupting the item.

**Output structure:**
```
<output_dir>/
  <folder_name>/
    masked_images/
      *.jpg
    <folder_name>_centroids.xlsx
    <folder_name>_coordinates.json
    <folder_name>_tracked_points.xlsx        (point mode)
    <folder_name>_closest_mask_points.xlsx   (optional)
    <folder_name>_hull_coordinates.xlsx      (optional)
    <folder_name>_contour_coordinates.xlsx   (optional)
    <folder_name>_predict.voluteinf            (optional)
    <folder_name>_propagate.voluteinf          (optional)
    <folder_name>_point_mask_analysis.xlsx   (optional)
```

Two progress bars are displayed during processing: one at item level (batch progress) and one at mask level (per-frame / per-object progress during SAM2 tasks).

### Keyboard Shortcuts

| Shortcut (Win/Linux) | Shortcut (macOS) | Action |
|---|---|---|
| Ctrl+D | ⌘D | Select image folder |
| Ctrl+Shift+G | ⌘⇧G | Import masks |
| Ctrl+Shift+J | ⌘⇧J | Import tracked points |
| Ctrl+Shift+B | ⌘⇧B | Export frame for GIMP |
| Ctrl+Shift+F | ⌘⇧F | Export all frames for GIMP |
| Ctrl+O | ⌘O | Import project data |
| Ctrl+S | ⌘S | Export project data |
| Ctrl+Z | ⌘Z | Undo |
| Ctrl+Shift+Z | ⌘⇧Z | Redo |
| Ctrl+Shift+I | ⌘⇧I | Export masked images / images with tracked points |
| Ctrl+Shift+M | ⌘⇧M | Export mask coordinates |
| Ctrl+Shift+T | ⌘⇧T | Export centroids |
| Ctrl+Shift+K | ⌘⇧K | Export closest mask points / closest tracked point distances |
| Ctrl+Shift+H | ⌘⇧H | Export convex hull coordinates |
| Ctrl+Shift+U | ⌘⇧U | Export contour coordinates |
| Ctrl+Shift+A | ⌘⇧A | Export point/mask analysis (imported points, mask mode) |
| Ctrl+Shift+P | ⌘⇧P | Export tracked points (SAM2++ point mode) |
| ← / → | ← / → | Previous / next frame |

### UI Layout

The interface is divided into a visualization area (left) and a tabbed control panel (right).
The visualization area and control panel are separated by a draggable splitter,
letting the control panel be resized to fit tab content without horizontal
scrolling on narrower screens. The initial split is sized to fit the control
panel's content; only the visualization area absorbs subsequent window resizes,
so the control panel's width stays stable until the user drags the splitter handle.

**Visualization area:**
- Folder name, current frame indicator, and active tracking mode (localized, e.g. "Point tracking mode") displayed above the canvas, with the original filename of the current image on a second line — handy for matching frames against the files the GIMP round-trip produces. Hidden by unticking **Show the image filename** in the settings
- Matplotlib canvas for image, mask, point, centroid, hull, contour, reference point, and tracked point rendering
- Navigation toolbar below the canvas (zoom, pan, home)
- Navigation bar below the toolbar: **Previous** button — slider (≥ 60 % of width) — frame spinbox (1-based, directly editable) — **Next** button

**Control panel tabs:**

**Tab 1 — Objects** (mask mode) **/ Points** (SAM2++ point mode):
- Point mode selection (mask mode only): **Add points** (left click = positive, right click or Ctrl+click = negative), **Remove points** (click and drag to draw a selection rectangle), and **Define box** (click and drag to draw the object's bounding box), followed by a **Remove box** button enabled only when the current object has a box on the current frame. In point mode, left click always places/replaces the current object's seed point instead.
- Object/point list with **Add** / **Remove** buttons; supports multi-selection (Ctrl+click, Shift+click, click-and-drag). **Add** always selects the newly created object/point exclusively. **Remove** deletes all selected objects/points at once, always keeping at least one.
- Name field for the currently selected object/point; disabled and cleared when multiple objects/points are selected
- Bulk **Import from file…**
- **Show points (current object)** toggle (mask mode) / **Show current point** toggle (point mode) — displays points for all currently selected objects; adding new points is restricted to a single selection and triggers a warning dialog otherwise
- **Clear point** / **Clear points** button (point mode only, label adapts to selection size) — clears the seed point of all selected objects on the current frame
- Per-object/point configuration group, with a mixed-value indicator (hatched color swatch, blank marker-style dropdown, dash placeholder and greyed slider track for marker size / mask opacity) whenever the current multi-selection has differing values:
  - Mask mode: positive/negative point colors, mask color, marker style and size, mask opacity
  - Point mode: seed point color, tracked point color, marker style and size — no negative color, no opacity

**Tab 2 — Ref. Points:**
- Reference point list with multi-selection (Ctrl+click, Shift+click, click-and-drag); **Add** / **Remove (all frames)** / **Remove (this frame)** buttons apply to the full selection
- Name field with live rename on edit; disabled during multi-selection
- Bulk **Import from file…**
- Per-reference-point configuration group (**Current Reference Point Configuration**): color, marker style, marker size — with a mixed-value indicator when the current multi-selection has differing values

**Canvas click routing** — which tab is active on the control panel determines what a canvas click does:
- **Objects/Points tab** active: left-click / right-click (or Ctrl+click) add positive/negative points to the current object, as described above
- **Ref. Points tab** active: plain left-click places/replaces the current reference point's position on the current frame; right-click and Ctrl+click are ignored
- **Prediction tab** active: clicking the canvas has no effect — no point of any kind can be added or modified
- In all cases, clicking with a multi-selection active (multiple objects, or multiple reference points, selected) shows a warning dialog instead of adding a point

**Tab 3 — Prediction:**
- **Predict masks on current image** and **Propagate masks through video** buttons (in point tracking mode, labelled **Predict points on current frame** and **Propagate points through video**)
- **Re-propagate from this frame…** button (mask mode only) — enabled once a correction point has been added to an already-tracked frame for the currently selected object; opens a bounded-span dialog before re-running propagation for that object only
- **Masks strictly confined to box** checkbox and its **Clipping applies to** selector (mask mode only) — the selector is enabled only when the checkbox is ticked, and choosing the reference-box variant warns once per session
- **Background opacity** slider
- **Show labels** toggle
- Mask mode:
  - **Centroid Configuration** group — show/hide toggle (disabled by default), color picker, size slider
  - **Mask Contours Configuration** group with two sub-tabs:
    - **Outer Contour** — show/hide toggle, smoothing slider (0–100), line width slider (1–10 px), outer border toggle, border color picker
    - **Convex Hull** — identical controls for the convex hull; border uses geometric radial offset instead of `patheffects`
  - **Imported Points** group — global show/hide toggle, list of imported point names, per-name color/marker style/size, remove button
- Point mode:
  - **Tracked Point Display** group — marker style combo and size slider, applied globally to all tracked points

**Menu bar:** File (folder selection, mask import, export, project data, SAM2 inference state, batch processing) — **Edit** (Undo / Redo) — Language — Help.

### Startup Model Chooser
Unless a model is given on the command line, the application opens a small dialog before loading anything heavy: the list of model configurations — the same eight the launchers offer — with three checkboxes.

- **Set as default** (unchecked) writes the highlighted model to `models.default_model`, which preselects it here and is the model used when this list is not shown
- **Show this list at startup** (checked) writes `ui.show_model_dialog: false` when unchecked, so later launches start straight away with the default model. The tooltip points to the settings dialog, where the choice can be reversed
- **Debug mode** (unchecked) turns on verbose technical output for this session only — the console, or the log file when the application was started from a macOS bundle. Its persistent counterpart is `debug.enabled` in the settings

Dismissing the dialog quits without loading a model. The model catalog lives in `model_dialog.py` and is the single source of truth for the configurations offered.

**Command-line options take precedence**: passing any of `--model`, `--config`, `--checkpoint` or `--task` starts that model directly and skips the dialog, which is what the generated launchers and the per-model macOS bundles do. `--debug` combines with whichever route is taken.

### Settings
**File › Settings…** edits everything `volute_config.yaml` holds, in four tabs — Interface, Export, Performance and tools, Debugging. **Restore defaults** puts the shipped values back in the fields, writing nothing until **Save**; **Save** writes the file, **Cancel** discards.

Saving rewrites the values in place: the comments documenting each setting survive, and a setting the file does not carry yet is appended to its section. Most settings take effect at the next start — the interface language, the file-dialog style and the model are read once at startup — which the dialog states.

### Application Name in the Dock and Taskbar
`QApplication.setApplicationName`, `setApplicationDisplayName` and `setDesktopFileName` name the application for Qt, the window manager and the taskbar.

**Known limitation on macOS**: started from the command line, the Dock labels the application after the interpreter ("python 3.10") rather than VOLUTE. That label comes from the executable LaunchServices registers when the process starts, before any application code runs — setting `NSProcessInfo`'s process name or the main bundle's `CFBundleName` afterwards has no effect on it, and re-executing through a symlink named after the application did not prove reliable either. Launching from the macOS bundle gives the right name, its interpreter symlink being named after the application; the limitation is cosmetic and affects command-line launches only.

### Application Icon
Dropping an icon file in `volute/resources/` gives the application its own icon on every platform, with no code change: `icon_<size>.png` files are combined into one multi-resolution icon, or a single `icon.png` / `icon.svg` / `icon.ico` is used. Windows and Linux apply it to windows and the taskbar; on macOS an application bundle's own `.icns` takes precedence for the Dock, and this icon covers the windows. Absent any file, the platform's default Python icon is used. See that directory's README.

### Progress Animation
Dropping an animated `progress.webp` or `progress.gif` in `volute/resources/` makes every progress dialog show it centred above its progress bar, as a complement to the bar rather than a replacement. Without such a file the dialogs keep their usual layout and size. See that directory's README for authoring notes.

Every operation that shows a progress dialog runs its work in a worker thread, so the dialog stays responsive and the animation plays at the frame durations stored in the file. `ui.progress_animation_pacing` (settings dialog, *Progress animation pace*) switches prediction, propagation and the SAM2 state export and import to `"progress"`, where the animation advances one frame per progress update instead, never faster than the file.

### Localization
- English and French UI; language switchable at runtime from the `Language` menu
- Translations loaded from external TSV files in `translations/`; multi-line messages use `\n` escapes, decoded at load time
- Default language configurable via `volute_config.yaml`
- Widgets drawn by Qt itself (standard dialog buttons, non-native file dialogs) follow the application language through Qt's own translation catalog, reloaded on each switch; the Yes/No/Cancel buttons of the application's own dialogs are relabelled explicitly
- File dialog titles and type filters are always localized. The **panel itself** — its buttons, sidebar and search field — depends on who draws it:
  - by default the system does (`ui.native_file_dialogs: true`), which keeps the platform look. On macOS that panel is drawn by a separate system process which, for an application started from a plain interpreter, has no application language to follow and stays in English. Bundling the launcher (see Installation) gives the process an application identity and pins `AppleLanguages` to the configured language, but the panel may still ignore it
  - setting `ui.native_file_dialogs: false` in `volute_config.yaml` hands file dialogs to Qt instead, which localizes them from its own catalog and therefore always follows the application language. The trade-off is the loss of the system panel's look and integration (favourites, iCloud, search). The setting also applies to the color picker, for the same reason
- Window title, canvas mode indicator, and all mixed-selection / multi-selection labels are fully localized and rebuilt on language change

### Configuration
External YAML configuration file (`volute_config.yaml`), editable from **File › Settings…**, controls:
- Default UI language
- Whether the startup model chooser is shown (`ui.show_model_dialog`) and which model it preselects (`models.default_model`)
- Whether the current image's filename is shown above the canvas (`ui.show_image_filename`)
- Whether file dialogs are drawn by the system or by Qt (`ui.native_file_dialogs`, default `true` — see Localization)
- Export formats (coordinates, centroids) and JPEG quality
- Debug flags (`enabled`, `show_filename_mappings`, `show_mask_sync_details`)
- Maximum number of frames kept in memory during SAM2 inference (LRU cache), parameter `performance.image_cache_size`. Default: 32. Set to 0 for unlimited.
- SAM2++ task (`models.sam2plus.task`): `mask` (default) or `point`
- GIMP command-line executable override for the mask-editing export (`gimp.executable_path`); leave unset, which is the default, to auto-detect. Detection looks up `gimp-console` then `gimp` on `PATH`, and failing that inside `/Applications/GIMP.app/Contents/MacOS/`, since a macOS install puts neither on `PATH` — note that a shell alias does not help there, the application looks the name up itself and aliases do not exist outside the shell. `gimp-console` is preferred at every step: it carries no GUI, so it opens no window, flashes no Dock icon, and cannot fail for want of a display connection, which the full binary can even under `-i`. Set the override only to name an installation the search does not reach; an override that does not point at an executable file is reported as "not detected" rather than quietly falling back to the search

---

## Installation

See [INSTALL.md](INSTALL.md) for detailed installation instructions for all supported backends (SAM2, MedSAM2, SAM2++).

### Launching
```bash
# SAM2 (default)
python tools/VOLUTE.py

# MedSAM2
python tools/VOLUTE.py --model medsam2

# SAM2++ mask mode
python tools/VOLUTE.py --model sam2plus

# SAM2++ point tracking mode
python tools/VOLUTE.py --model sam2plus --task point

# Explicit paths
python tools/VOLUTE.py --checkpoint ./checkpoints/sam2.1_hiera_large.pt \
                         --config configs/sam2.1/sam2.1_hiera_l.yaml
```

Platform-specific launcher scripts can be generated with `install_launchers_Unix_MacOS.sh` (macOS / Linux) or `install_launchers_windows.bat`, into `tools/launchers/`. Their one job is to move to the root of the installation before starting the GUI, which the application cannot do for itself: `volute.sh` names no model, so the startup chooser opens as usual, while the per-model scripts pass the model on the command line and skip it. The whole `launchers/` directory, its README included, is generated — re-run the script to refresh it, and keep it out of version control.

### macOS application bundle (optional)

`install_app_bundle_macos.sh` wraps the launcher in a double-clickable `.app`. Run it from the root of your SAM2 installation, **with the environment VOLUTE runs in activated**:

```bash
conda activate sam2_plus
tools/install_app_bundle_macos.sh
tools/install_app_bundle_macos.sh --name "SAM2++ Point Tracking" --args "--model sam2plus --task point"
```

The bundle records the interpreter that is on `PATH` at build time and runs that exact one, with no environment activated. Built from a shell where the environment is not active, it picks up the wrong interpreter and the application dies at launch. The script therefore refuses to build when the interpreter it would record cannot import `sam2`, `torch` and `PyQt5`; pass `--python /path/to/env/bin/python` to name one explicitly. Re-run the script after moving the installation or changing environment.

A bundle built without `--args` starts the application plainly, so the startup model chooser opens as usual; one built with `--args` passes the model on the command line and goes straight to it, which is the way to get a per-model application (a SAM2++ point-tracking bundle, say).

Beyond the Dock icon, the bundle is also what gives the **native file dialog** a chance to be localized. Two mechanisms are involved:

- macOS derives an application's identity from the location of the *running executable*. The bundle therefore holds a symlink to the interpreter at `Contents/MacOS/python` and starts it through that path, so the process belongs to the bundle — which declares English plus every language shipped in `translations/`. Started through its own path (`python tools/VOLUTE.py`), the interpreter belongs to no application and everything the system draws for it stays in English.
- The panel itself is drawn by a separate system process (`com.apple.appkit.xpc.openAndSavePanelService`), which takes its language from the application's own preferences rather than from anything the GUI process sets for itself. At every launch the bundle therefore writes `AppleLanguages` into its preference domain, matching `default_language` in `volute_config.yaml`. Undo it with `defaults delete org.volute.volute-gui AppleLanguages`.

The panel consequently follows the language configured in the YAML file, fixed at launch — the runtime **Language** menu cannot move it, since the panel belongs to another process started before any menu choice. Should it stay in English regardless, `ui.native_file_dialogs: false` replaces it with Qt's own dialog, which does follow the application language (see Localization).

The bundle only starts `tools/VOLUTE.py` from this installation, with the Python interpreter found when the script ran — no sources are copied, so it keeps working as the code changes. Re-run the script after moving the installation or switching Python environment (activate the environment first, or pass `--python`). Console output goes to `~/Library/Logs/<name>.log`, and a startup failure raises an alert quoting the last lines of that log rather than dying silently.

**Folder access.** An application launched from the Finder is subject to macOS privacy protection: it cannot read `~/Documents`, `~/Desktop` or `~/Downloads` without consent, and an installation under one of those otherwise fails at startup with `Operation not permitted`, before the GUI appears.

macOS attributes such an access to the *executable* that performs it. A bundle whose executable is a shell script is therefore judged to be `/bin/bash` — a system binary with no claim on anyone's folders — and the read is denied outright, with no prompt shown and nothing to see but a window that never opens. The bundle produced here consequently ships a small **compiled** launcher, signed as part of the bundle, which runs `Contents/Resources/run.sh`; processes it starts inherit the bundle's identity, so the installation folder becomes readable. This requires a C compiler at generation time — the Xcode Command Line Tools (`xcode-select --install`). Without one, the script falls back to a script launcher and says so: the application then only starts if the installation sits outside the three protected folders.

The bundle is also ad-hoc signed (`codesign -s -`), so its identity is stable: an unsigned bundle gets a new one at every launch, and any permission granted to it is forgotten. Should access still be refused, add the bundle to *System Settings › Privacy & Security › Full Disk Access*, or move the installation outside the protected folders, where no permission is involved at all.

---

## File Formats

### Versioning

Two independent numbers:

- the **application** version, `__version__` in `volute/__init__.py` (currently `0.9`) — the single source of truth, reported by `QApplication` and stamped into the macOS bundle;
- the **`.volute` file format** version, `ProjectStateManager.PROJECT_VERSION` (currently `1.1`), written into every project file and checked on import against `SUPPORTED_VERSIONS`. It moves only when the schema changes, not with each release: `1.0` is the original format, `1.1` adds bounding boxes and optional imported masks. Both load without warning; anything else warns and then imports on a best-effort basis, since the reader ignores keys it does not know.

### `.volute` — Project Data
Gzip-compressed pickle containing object definitions (names, colors, markers), per-frame points and bounding boxes, reference point data, and tracked point trajectories (SAM2++ point mode). Predicted masks and centroids are **not** included; imported masks are, unless the person opts out at save time. Version `1.1`; files written as `1.0` (no boxes, no masks) still load. Compatible across machines with the same image dimensions.

### `.voluteinf` — SAM2 Inference State
Gzip-compressed serialization of the SAM2 internal inference state. Marked **experimental**: portability across different systems, devices, or model versions is not guaranteed.

---

## License

This project is licensed under the **GNU General Public License v3.0** — see the [LICENSE](LICENSE) file for details.

---

## Credits and Acknowledgements

This GUI was developed by **[Nicolas Audibert](https://lpp.cnrs.fr/nicolas-audibert/)** with the assistance of [Claude](https://claude.ai) (Anthropic) as an AI pair-programming assistant. The logo was created by Solène Bodiou.

### SAM2

This application builds on **SAM 2: Segment Anything in Video** by Meta AI Research. If you use this tool in academic work, please cite:

```bibtex
@article{ravi2024sam2,
  title     = {SAM 2: Segment Anything in Video},
  author    = {Ravi, Nikhila and Gabeur, Valentin and Hu, Yuan-Ting and
               Hu, Ronghang and Ryali, Chaitanya and Ma, Tengyu and
               Khedr, Haitham and R{\"a}dle, Roman and Rolland, Chloe and
               Gustafson, Laura and Mintun, Eric and Pan, Junting and
               Alwala, Kalyan Vasudev and Carion, Nicolas and Wu, Chao-Yuan and
               Girshick, Ross and Doll{\'a}r, Piotr and Feichtenhofer, Christoph},
  journal   = {arXiv preprint arXiv:2408.00714},
  year      = {2024}
}
```

### MedSAM2 (optional)

If you use the MedSAM2 backend, please also cite:

```bibtex
@article{ma2025medsam2,
  title   = {MedSAM2: Segment Anything in 3D Medical Images and Videos},
  author  = {Ma, Jun and Chen, Zitian and Vochescu, Alexandru and others},
  journal = {arXiv preprint arXiv:2504.03600},
  year    = {2025}
}
```

### SAM2++ (optional)

If you use the SAM2++ backend, please also cite:

```bibtex
@article{zhang2025sam2trackinggranularity,
  title   = {SAM 2++: Tracking Anything at Any Granularity},
  author  = {Zhang, Jiaming and Liang, Cheng and Yang, Yichun and
             Zeng, Chenkai and Cui, Yutao and Zhang, Xinwen and Zhou, Xin and
             Ma, Kai and Wu, Gangshan and Wang, Limin},
  journal = {arXiv preprint arXiv:2510.18822},
  url     = {https://arxiv.org/abs/2510.18822},
  year    = {2025}
}
```

---

## Architecture Overview

| Module | Responsibility |
|---|---|
| `main_window.py` | Application coordinator and state |
| `ui_manager.py` | UI layout, delegating to `ui_components/` |
| `event_manager.py` | Mouse and keyboard events, point and bounding-box management |
| `display_manager.py` | Image, mask, point, box, centroid, hull, contour, reference point, and tracked point rendering |
| `object_manager.py` | Per-object data structures (masks, points, bounding boxes, tracked trajectories, mask-import/correction tracking, selection state), box geometry helpers and mask clipping |
| `history_manager.py` | Generic undo/redo command stack |
| `reference_point_manager.py` | Reference point data model and interpolation |
| `imported_point_manager.py` | Imported point data model (no interpolation; pixel coordinates) |
| `image_manager.py` | Image loading and navigation |
| `prediction_manager.py` | SAM2 prediction and propagation; point track prediction and propagation (interactive); bounded single-object re-propagation |
| `sam2_backend.py` | SAM2 / MedSAM2 / SAM2++ model interface |
| `export_manager.py` | Export orchestration |
| `base_exporter.py` | Shared base class for all exporters |
| `exporters.py` | Image, coordinate, centroid, convex hull, contour, and tracked point exporters |
| `reference_point_exporter.py` | Closest mask point and closest tracked point distance exporters |
| `imported_point_mask_analysis_exporter.py` | Containment/distance metrics between imported points and mask-mode objects |
| `pair_selection_dialog.py` | (Object, target) pair selection dialog |
| `project_state_manager.py` | `.volute` save / load |
| `inference_state_manager.py` | Delegates to project and SAM2 state managers |
| `sam2_state_manager.py` | `.voluteinf` save / load |
| `batch_processor.py` | Headless batch pipeline |
| `batch_dialog.py` | Batch processing UI |
| `progress_dialog.py` | Progress dialogs: SAM2 state export/import, and `AnimatedProgressDialog`, the `QProgressDialog` used everywhere else |
| `progress_animation.py` | Optional progress animation, shared by every progress dialog, and its pacing |
| `progress_worker.py` | Runs a long operation in a worker thread behind a modal progress dialog |
| `localization.py` | Translation loading and lookup |
| `config_manager.py` | YAML configuration |
| `gimp_export_manager.py` | GIMP CLI detection; frame/mask export for external editing (.xcf or plain files), single-frame or batched across all frames; `.xcf` mask layer extraction for import |
| `model_dialog.py` | Model catalog and startup model chooser |
| `settings_dialog.py` | Settings dialog over the YAML configuration |
| `dialogs.py` | Standalone `QDialog` subclasses (`RepropagationSpanDialog`, `ColorObjectMappingDialog`, `GimpExportDialog`) and the localized message-box helpers |
| `gimp_ui_controller.py` | UI-facing GIMP round-trip: export-for-editing dialogs, background-thread progress, plain-image and `.xcf` mask import |
| `export_actions.py` | Menu-triggered export actions (masked images, coordinates, centroids, hull/contour coordinates, closest-point exports, tracked points, point/mask analysis) |
| `property_controller.py` | Undo-backed property setters for object/point, tracked point display, reference point, and imported point properties |
