# Installing VOLUTE on macOS

*[Version française](install-macos.fr.md)*

This guide is for anyone who has never installed a Python program and rarely, if ever,
types commands. You will copy one line, paste it into a window, and answer one question:
the installer does the rest.

Nothing else on the Mac is changed. VOLUTE gets a folder of its own, with its own copy of
Python, so any Python, Anaconda or Miniconda already installed is left alone — you do not
need to know whether you have one. No password is asked, and no developer tools are
needed.

## Before you start

- **macOS 11 (Big Sur) or later.**
- **About 10 GB of free disk space**, and an Internet connection. The installation
  downloads several gigabytes; count 20 to 60 minutes depending on the connection.
- **Which processor the Mac has** makes a difference in speed, not in the procedure: the
  installer detects it by itself. To find out, open the Apple menu, at the top left of the
  screen, then **About This Mac**:
  - **Chip: Apple M1, M2, M3…** — VOLUTE uses the Mac's graphics processor, and runs
    fairly fast;
  - **Processor: … Intel …** — VOLUTE works, but segmentation is noticeably slower.

## 1. Open the Terminal

The Terminal is the window in which commands are typed.

1. Press **Command (⌘) + Space** to open Spotlight, type `Terminal`, and press **Enter**.
   (The Terminal is also in **Applications › Utilities**.)

A window opens, showing a line that ends with `%`, such as `yourname@MacBook ~ %`. That
line is where commands go.

## 2. Paste the installation command

1. Select the whole line below and copy it (⌘ + C), or click the copy button at the right
   of the box:

   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/nicolasaudibert/VOLUTE/main/install/install_volute_macos.sh)"
   ```

2. Click in the Terminal window, then paste with **⌘ + V**.
3. Press **Enter**.

## 3. Answer the installer

The installer first installs **Miniforge**, the Python distribution VOLUTE runs on: a bar of
`#` signs shows the download, and the installation takes a minute or two. It then shows
what it found about the Mac, for example:

```
[1/8] Checking the computer
    Darwin 24.6.0, arm64
    Mac with Apple Silicon: GPU acceleration (MPS)
    Installation folder: /Users/yourname/VOLUTE
```

and asks which pretrained **models** to download. A model is the artificial intelligence
that does the segmentation; at least one is needed.

```
    Models to download (more can be added later by running the installer again):
     * 1. SAM2.1 Large - best accuracy (900 MB)
       2. SAM2.1 Small - faster, slightly less accurate (185 MB)
       3. SAM2++ - needed for point tracking (800 MB)
       4. MedSAM2 - medical images: CT, MRI, ultrasound, 4 models (625 MB)
       a. All of the above (2510 MB)
    Numbers of the models to download, separated by spaces, or a for all [1]:
```

- To take the suggested choice, marked with `*`, just press **Enter**.
- To choose others, type their numbers separated by spaces, then Enter: `1 3` downloads
  SAM2.1 Large and SAM2++. To download them all, type `a`. On an Intel Mac, `2` alone, the
  faster model, is worth considering.

When unsure, press Enter: other models can be added later.

The installer then asks `Start the installation? [Y/n]`: press **Enter** to accept.

## 4. Wait

The installer now works on its own, in eight steps numbered `[1/8]` to `[8/8]`. Lines
scroll by, sometimes with progress bars; the longest steps can stay a few minutes on the
same line. This is normal: leave the window open, and the Mac awake.

It is finished when it shows:

```
======================================================================
VOLUTE 0.9.3 is installed.
======================================================================
```

with the current version number. The Terminal can then be closed (⌘ + Q).

## 5. Start VOLUTE

VOLUTE is in the **Applications** folder of your home folder — not the main
Applications folder, which would require an administrator password.

1. In the Finder, choose **Go › Home** (⇧ + ⌘ + H), then open **Applications**.
2. Double-click **VOLUTE**. To keep it at hand, drag it to the Dock.

Spotlight finds it too: ⌘ + Space, then type `VOLUTE`.

VOLUTE first asks which model to use: pick one you downloaded. If macOS asks whether
VOLUTE may access your **Documents**, **Desktop** or **Downloads** folder, click **Allow**:
otherwise VOLUTE cannot read the images kept there.

The [Getting started](https://github.com/nicolasaudibert/VOLUTE/blob/main/README.md#getting-started) section of the README walks through a
first session.

ffmpeg, which extracts the frames of a video (**File › Extract Frames from Video…**),
is installed with VOLUTE. GIMP, used to retouch masks by hand, is not: if you need it,
install it from [gimp.org](https://www.gimp.org) (version 3.0 or later).

## What the VOLUTE folder holds

- `miniforge3`: VOLUTE's Python distribution and its environment;
- `SAM2-Plus`: the code of the models, which VOLUTE is part of (`SAM2-Plus/tools`), and
  the downloaded models (`SAM2-Plus/checkpoints`). It bears this name whichever models
  were chosen: SAM2-Plus also provides the code of SAM2;
- `install.log`: the installation log.

Nothing in it needs editing by hand: settings are changed in **File › Settings…**.

## Updating VOLUTE, or adding a model

Do **steps 1 and 2** again. An existing installation is recognised:

- VOLUTE is updated to its latest version, and your settings are kept;
- the list of models shows those already downloaded; press **Enter** to add none, or
  type the numbers of the models to add. When all are already downloaded, the question
  is not asked;
- nothing already installed is downloaded again, so an update takes a few minutes.

If an installation was interrupted — a lost connection, a closed window — doing steps
1 and 2 again resumes it where it stopped.

## Uninstalling

1. Move the **VOLUTE** folder of your home folder to the Trash.
2. Move **VOLUTE** from the Applications folder of your home folder to the Trash.

Nothing else was installed.

## If something goes wrong

**The installation stopped with an `ERROR:` line.** Read the line: it says what to do.
Most often, the connection dropped during a download: do steps 1 and 2 again, and the
installation resumes. If the problem persists, the file `install.log` in the VOLUTE folder
records every step; it is what to send with a request for help.

**The Terminal answers `command not found` or `parse error`.** The line was not pasted
whole. Copy it again with the copy button, and paste it once more.

**The download is very slow or fails every time.** Some institutional networks filter
large downloads. Try from another network, or ask the IT department to allow
`github.com`, `conda-forge.org`, `download.pytorch.org`, `pypi.org`,
`files.pythonhosted.org`, `dl.fbaipublicfiles.com` and `huggingface.co`.

**VOLUTE does not open, or shows an alert at startup.** The alert quotes the end of the
log that VOLUTE keeps in `~/Library/Logs/VOLUTE.log` (in the Finder: **Go › Go to
Folder…**, then paste that path). That message is what to send with a request for help.

**VOLUTE cannot open images in Documents, the Desktop or Downloads.** The access was
probably refused when macOS asked. Open **System Settings › Privacy & Security › Files and
Folders**, find VOLUTE, and allow the folders concerned.

The [FAQ](faq.md) answers the most common questions.
For a step-by-step installation by hand, see [INSTALL.md](https://github.com/nicolasaudibert/VOLUTE/blob/main/INSTALL.md).
