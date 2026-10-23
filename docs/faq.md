# Frequently asked questions

*[Version française](faq.fr.md)*

Short answers, each pointing to where the subject is covered in full: in the
[tutorial](tutorial/index.md) of this site, which shows the features step by step on an
example, or in the reference documentation, the files `INSTALL.md`, `README.md` and
`DOCUMENTATION.md` of the GitHub repository. Each link says which of the two it leads to.

- [Installing and starting](#installing-and-starting)
- [Using VOLUTE](#using-volute)
- [Data, results and citing](#data-results-and-citing)

## Installing and starting

### Do I need to know Python, or to install it first?

No. On Windows, macOS and Linux (Ubuntu), one command installs everything VOLUTE needs,
Python included; the [Windows](install-windows.md), [macOS](install-macos.md) and
[Linux](install-linux.md) guides walk through it without assuming any knowledge of the
command line.

### Will the installation change my existing Python, Anaconda or Miniconda?

No. VOLUTE is installed into a folder of its own, with its own copy of Python, and nothing
outside that folder is changed apart from the VOLUTE shortcut. Uninstalling means deleting
that folder and the shortcut.

### Can I install VOLUTE on Linux?

Yes. On Ubuntu 22.04 and 24.04, one command installs it, as on Windows and macOS: see
the [Linux](install-linux.md) guide. That command may suit other distributions but has not
been tested on them; failing that, the reference documentation, on GitHub, describes the
installation by hand in
[INSTALL.md](https://github.com/nicolasaudibert/VOLUTE/blob/main/INSTALL.md).

### Does VOLUTE need an Internet connection?

Only to be installed or updated. Once installed, it works offline: see also
[Is my data sent anywhere?](#is-my-data-sent-anywhere)

### How do I update VOLUTE?

Run the installation command again: VOLUTE is updated to its latest version, your
settings are kept, and nothing already installed is downloaded again. The same command
adds models, and resumes an interrupted installation. For an installation made by hand,
see the reference documentation, on GitHub:
[INSTALL.md](https://github.com/nicolasaudibert/VOLUTE/blob/main/INSTALL.md#gui-installation).

### Is my graphics card used?

VOLUTE picks the fastest device available by itself, in this order of preference: an
NVIDIA graphics card, then the graphics processor of a Mac with Apple Silicon, and the
main processor (CPU) otherwise.
The installer states at its first step which case applies.

On the CPU alone VOLUTE works, but segmentation is many times slower. If a better
equipped computer is available, the work can then be shared. On the slower installation,
place the points or boxes of each sequence on a few chosen frames, checking the
prediction on those frames only, and save the project (**File › Project Data › Export
Project Data**). On the faster computer, with the same image folders, **File › Batch
Processing…** then propagates those projects through their whole sequences and exports
the results. Pass on the project file (`.volute`) rather than the inference state
(`.voluteinf`): the latter is experimental, and not guaranteed to carry over from one
machine or device to another.

If an NVIDIA card goes unused, its driver is usually too old: the installer says so.
Update the driver, then run the installation command again, which replaces what needs to
be.

### On macOS, the Dock shows "python" instead of VOLUTE

This happens when VOLUTE is started from the Terminal. Started from `VOLUTE.app`, as the
installer sets it up, it shows its own name and icon.

### On macOS, the file dialogs stay in English although VOLUTE is in French

Those dialogs are drawn by macOS, which follows the language of the system rather than
that of the application. Unticking **System file dialogs** in **File › Settings…**,
*Interface* tab, makes VOLUTE draw its own, which follow its language; the change applies
at the next start.

## Using VOLUTE

### Which model should I choose?

- **SAM2.1 Large** is the most accurate, and the one to start with.
- **SAM2.1 Small** is faster and slightly less accurate: worth it on a computer without a
  suitable graphics card, or for long sequences.
- **SAM2++** is needed to track **points** rather than outline objects; it also has a mask
  mode, comparable to SAM2.
- **MedSAM2** is trained on medical images (CT, MRI, ultrasound). The installer offers it,
  unselected by default: unless you already chose it when first installing VOLUTE, run the
  installation command again and choose it. For an installation made by hand, see the
  reference documentation, on GitHub:
  [INSTALL.md](https://github.com/nicolasaudibert/VOLUTE/blob/main/INSTALL.md#medsam2-setup-optional).
  It is used with a **box**: draw a box around the structure first, then refine with
  positive or negative points if needed; step 3 of the tutorial,
  [A first object](tutorial/first-object.md#bounding-the-region-with-a-box), shows how. A
  point alone rarely gives a good result, MedSAM2 having been designed to be prompted
  with boxes.

No rule tells in advance which one suits a given kind of image best: running a few trials
on some frames and comparing the results is the quickest way to find out. The model is
chosen at each start: see, in the tutorial,
[step 1, Choosing a model](tutorial/start.md#choosing-a-model), and for SAM2++,
[step 10, Following points with SAM2++](tutorial/points.md).

### My images are a video: how do I load them?

**File › Extract Frames from Video…** turns the video into a folder of numbered images,
then offers to load it. It relies on ffmpeg, which the installer provides. In the
tutorial: [step 2, Loading the frames](tutorial/load-frames.md). In the reference
documentation, on GitHub: [Extracting frames from a video](https://github.com/nicolasaudibert/VOLUTE/blob/main/DOCUMENTATION.md#extracting-frames-from-a-video).

### Which images can VOLUTE load, and in what order?

A folder of JPEG, PNG, BMP or TIFF images, all of the **same size**: one image per frame.
They are taken in the order of their names, numbers compared as numbers, so `frame_2`
comes before `frame_10`. An image whose name ends in `00000` is taken as the first frame.

### The tracking goes wrong on some frames: how do I correct it?

Go to a frame where the mask is wrong, add points there, positive inside the object and
negative outside, and predict again. Then click **Re-propagate from this frame…**: only
that object is tracked again, from that frame, over as many frames as you choose. In the
tutorial, [step 6, Following the objects through the video](tutorial/tracking.md) goes
through it on an example, from
[the correction on the frame](tutorial/tracking.md#correcting-on-the-frame) to
[its re-propagation to the neighbouring frames](tutorial/tracking.md#passing-the-correction-on-to-the-neighbouring-frames).
In the reference documentation, on GitHub, the
[Getting started](https://github.com/nicolasaudibert/VOLUTE/blob/main/README.md#getting-started)
section of the README sums up the whole sequence.

This correction is the one to try first. Should it not give a satisfactory result, the
masks can be edited by hand: see
[Can I edit a mask by hand?](#can-i-edit-a-mask-by-hand)

### Do the same points always give exactly the same masks?

Nearly, but not always to the pixel. The models use no randomness when predicting, but
their computations, run in parallel on the graphics card and at reduced precision, do not
always round the same way: from one run to the next, a mask may gain or lose a few pixels
along its edges. The differences are somewhat larger from one computer to another (Mac,
NVIDIA card, processor only) or from one PyTorch version to another.

Two cases call for care:

- **SAM2++ point tracking** is more sensitive: a slight difference is enough to decide
  whether the point is found or lost on a frame. Step 10 of the tutorial gives an
  example, its English and French versions having been captured in two different runs:
  see [The point and the masks together](tutorial/points.md#the-point-and-the-masks-together).
- **The order of predictions matters.** On a frame, SAM2 takes into account the mask it
  has already predicted there: placing three points then predicting once does not
  necessarily give the same mask as predicting after each point. A mask computed again
  in one go from the same points, when a project is reopened or in batch processing, may
  therefore differ slightly from the one obtained during the session.

For reproducible results, keep the exported files (masks, coordinates) rather than
relying on computing them again, and note the model used.

### Can I edit a mask by hand?

Yes: **File › Export Frame for Editing…** exports a frame and its masks for GIMP or
another image editor, and **File › Import Masks…** brings the edited masks back. GIMP is not
installed with VOLUTE: download it from [gimp.org](https://www.gimp.org) (version 3.0 or later);
on Ubuntu 22.04 and 24.04, install it as a Snap or a Flatpak, since the `apt` version is
2.10, which is not compatible with VOLUTE. In the tutorial:
[Retouching a mask by hand in GIMP](tutorial/corrections.md#retouching-a-mask-by-hand-in-gimp),
in step 5. In the reference documentation, on GitHub:
[GIMP-assisted mask editing](https://github.com/nicolasaudibert/VOLUTE/blob/main/DOCUMENTATION.md#gimp-assisted-mask-editing-mask-mode-only).

### Propagation is slow, or the computer runs out of memory

- Use **SAM2.1 Small** instead of SAM2.1 Large.
- In **File › Settings…**, tab *Performance and tools*, lower **Frames kept in memory**.
- Split a very long sequence into several shorter ones.

Without a suitable graphics card, propagation is slow whatever the settings.

### The masks have small holes, or a message mentions "Skipping the post-processing step"

SAM2 fills small holes with a component that requires an NVIDIA card and a compilation
step. The installer replaces it by an equivalent that works everywhere. On an installation
made by hand, apply that replacement as described in the reference documentation, on
GitHub: [INSTALL.md](https://github.com/nicolasaudibert/VOLUTE/blob/main/INSTALL.md#optional-cpumps-fallback-patch-for-mask-post-processing).

With an NVIDIA card, the original component can also be compiled by hand, provided you
have administrator rights to install the tools it needs. The speed gain is small, and the
masks stay the same: the replacement VOLUTE installs fills small holes in the same way.
See the reference documentation, on GitHub:
[INSTALL.md](https://github.com/nicolasaudibert/VOLUTE/blob/main/INSTALL.md#compiling-the-cuda-extension-instead).

### How do I save my work and resume it later?

**File › Project Data › Export Project Data** (Ctrl+S, ⌘S on a Mac) saves objects,
points, boxes and reference points in a `.volute` file. Predicted masks are not stored:
predicting or propagating again regenerates them. Imported masks, which nothing could
regenerate, are stored unless you choose otherwise. In the tutorial:
[step 9, Saving, resuming, batch processing](tutorial/project.md). In the reference
documentation, on GitHub: [Project data management](https://github.com/nicolasaudibert/VOLUTE/blob/main/DOCUMENTATION.md#project-data-management).

### Can I process many sequences without stepping in at each stage?

Yes: **File › Batch Processing…** works through a list of saved projects, each paired
with its image folder, and exports the results. In the tutorial:
[Batch processing](tutorial/project.md#batch-processing), in step 9. In the reference
documentation, on GitHub: [Batch processing](https://github.com/nicolasaudibert/VOLUTE/blob/main/DOCUMENTATION.md#batch-processing).

### How do I change the language, or other settings?

The **Language** menu switches between English and French at once. The other settings
are in **File › Settings…**; they are kept in the file `volute_config.yaml`, which an update
leaves untouched. In the tutorial:
[step 11, Settings, language, shortcuts](tutorial/settings.md).

## Data, results and citing

### Is my data sent anywhere?

No. VOLUTE and the models run entirely on your computer, and VOLUTE makes no network
connection: images, masks and results never leave it. In other words, if copying the
data to your computer (or accessing it from your computer) complies with the rules that
apply to that data, using VOLUTE to process it makes no difference.

### What can I export?

Images with the masks shown on them, mask coordinates, centroids, convex hulls, outer
contours, distances to reference points, and tracked point trajectories: as images, JSON,
CSV, Excel (XLSX) or Pickle files. In the tutorial:
[step 8, Exporting the results](tutorial/export.md), and for tracked points
[Exporting the positions](tutorial/points.md#exporting-the-positions), in step 10. In the
reference documentation, on GitHub: [Export](https://github.com/nicolasaudibert/VOLUTE/blob/main/DOCUMENTATION.md#export).

### How do I cite VOLUTE?

Cite the model you used — SAM 2, and MedSAM2 or SAM 2++ if you used them: the BibTeX
entries are in **Help › About** and in the reference documentation, on GitHub:
[Credits and acknowledgements](https://github.com/nicolasaudibert/VOLUTE/blob/main/DOCUMENTATION.md#credits-and-acknowledgements).
For VOLUTE itself, cite its repository, https://github.com/nicolasaudibert/VOLUTE, with
the version used, shown in **Help › About**.

### Under what licence is VOLUTE distributed?

The [GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.html): VOLUTE
can be used, studied, modified and redistributed freely; a modified version that is
redistributed must remain under the same licence.

### Where can I get help, or report a problem?

Open an issue on [GitHub](https://github.com/nicolasaudibert/VOLUTE/issues), describing
what you did and what happened. Attach the error message if there is one, and for an
installation problem the file `install.log` from the VOLUTE folder.
