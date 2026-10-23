# Installing VOLUTE on Linux

*[Version française](install-linux.fr.md)*

This guide is for anyone who has never installed a Python program and rarely, if ever,
types commands. You will copy one line, paste it into a terminal, and answer one question:
the installer does the rest.

Nothing else on the computer is changed. VOLUTE gets a folder of its own, with its own
copy of Python, so the system's Python, Anaconda or Miniconda, if installed, are left
alone. No password is asked: the installation needs no administrator rights.

## Before you start

- **Ubuntu 22.04 or 24.04**, on a 64-bit PC (Intel or AMD processor). VOLUTE may work on
  other distributions, but only Ubuntu has been tested.
- **About 10 GB of free disk space**, and an Internet connection. The installation
  downloads several gigabytes; count 20 to 60 minutes depending on the connection.
- **An NVIDIA graphics card makes VOLUTE much faster**, and the installer detects it by
  itself, provided its NVIDIA driver is installed. To check, open **Software & Updates**,
  **Additional Drivers** tab: the selected driver should be an NVIDIA driver, preferably
  the one marked *recommended*. If you change it, restart the computer before installing
  VOLUTE. Without an NVIDIA card, VOLUTE works too, but more slowly.

## 1. Open a terminal

The terminal is the window in which commands are typed.

1. Press **Ctrl + Alt + T**. (The terminal is also among the applications: click
   **Show Apps**, at the bottom of the dock, then type `Terminal`.)

A window opens, showing a line that ends with `$`, such as `yourname@yourcomputer:~$`.
That line is where commands go.

## 2. Paste the installation command

1. Select the whole line below and copy it (Ctrl + C), or click the copy button at the
   right of the box:

   ```bash
   bash -c "$(curl -fsSL https://raw.githubusercontent.com/nicolasaudibert/VOLUTE/main/install/install_volute_linux.sh)"
   ```

2. Click in the terminal window, then paste with **Ctrl + Shift + V**: in a terminal,
   Ctrl + V alone does not paste.
3. Press **Enter**.

If the terminal answers `Command 'curl' not found`, `curl` is not installed on this
computer: use this line instead, which does the same with `wget`:

```bash
bash -c "$(wget -qO- https://raw.githubusercontent.com/nicolasaudibert/VOLUTE/main/install/install_volute_linux.sh)"
```

## 3. Answer the installer

The installer first installs **Miniforge**, the Python distribution VOLUTE runs on: a bar
shows the download, and the installation takes a minute or two. It then shows what it
found about the computer, for example:

```
[1/8] Checking the computer
    Ubuntu 24.04.1 LTS (Linux 6.8.0-45-generic), x86_64
    NVIDIA GPU of compute capability 8.6, driver supporting CUDA 12.8: PyTorch for CUDA 12.8
    Installation folder: /home/yourname/VOLUTE
```

that is, the system, the graphics card found and the installation folder. Without an
NVIDIA card, the second line reads
`No NVIDIA GPU found: CPU only, so segmentation will be slow`.

It then asks which pretrained **models** to download. A model is the artificial
intelligence that performs the segmentation; at least one is needed.

```
    Models to download (more can be added later by running the installer again):
     * 1. SAM2.1 Large - best accuracy (900 MB)
       2. SAM2.1 Small - faster, slightly less accurate (185 MB)
       3. SAM2++ - needed for point tracking (800 MB)
       4. MedSAM2 - medical images: CT, MRI, ultrasound, 4 models (625 MB)
       a. All of the above (2510 MB)
    Numbers of the models to download, separated by spaces, or a for all [1]:
```

The four choices are: SAM2.1 Large, the most accurate; SAM2.1 Small, faster and slightly
less accurate; SAM2++, needed for point tracking; MedSAM2, four variants of SAM2 trained
on medical images (CT, MRI, ultrasound).

- To keep the proposed choice, marked with a `*`, just press **Enter**.
- To choose others, type their numbers separated by spaces, then Enter: `1 3` downloads
  SAM2.1 Large and SAM2++. To download them all, type `a`. Without an NVIDIA card, `2`
  alone, the fastest model, is worth considering.

When in doubt, press Enter: more models can be added later.

The installer finally asks `Start the installation? [Y/n]`: press **Enter** to accept.

## 4. Wait

The installer now works on its own, in eight steps numbered `[1/8]` to `[8/8]`. Lines
scroll by, sometimes with progress bars; the longest steps may stay on the same line for
a few minutes. This is normal: leave the window open, and the computer on.

At the last step, a small empty window opens and closes at once: the installer checks
that VOLUTE will be able to open its windows.

The installation is finished when this appears:

```
======================================================================
VOLUTE 0.9.4 is installed.
======================================================================
```

with the number of the current version. The terminal can then be closed.

## 5. Start VOLUTE

VOLUTE is among the applications, like any other program:

1. Click **Show Apps**, at the bottom of the dock, or press the **Super** key (the one
   with the Windows logo on most keyboards).
2. Type `VOLUTE`, then click its icon.

To keep it at hand, once VOLUTE is open, right-click its icon in the dock and choose
**Pin to Dash** (**Add to Favorites** on Ubuntu 22.04).

VOLUTE first asks which model to use: pick one you downloaded.

The [Getting started](https://github.com/nicolasaudibert/VOLUTE/blob/main/README.md#getting-started) section of the README walks through a
first session.

ffmpeg, which extracts the frames of a video (**File › Extract Frames from Video…**),
is installed with VOLUTE. GIMP, used to retouch masks by hand, is not: if you need it,
install **GIMP 3.0 or later**, from Ubuntu's **App Center** (Snap package) or from
[Flathub](https://flathub.org/apps/org.gimp.GIMP) (Flatpak package). VOLUTE finds either.
The GIMP that `apt install gimp` installs on Ubuntu 22.04 and 24.04 is version 2.10,
which VOLUTE cannot use. With the Snap package, keep the files exchanged with GIMP in your
home folder or on removable media: the Snap package has no access to the rest of the
disk.

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

Paste the following line into a terminal, then press Enter:

```bash
rm -rf ~/VOLUTE ~/.local/share/applications/volute.desktop
```

It deletes the **VOLUTE** folder of your home folder and VOLUTE's entry among the
applications. Nothing else was installed.

## If something goes wrong

**The installation stopped with an `ERROR:` line.** Read the line: it says what to do.
Most often, the connection dropped during a download: do steps 1 and 2 again, and the
installation resumes. If the problem persists, the file `install.log` in the VOLUTE folder
records every step; it is what to send with a request for help.

**The terminal answers `syntax error`, or shows nothing after pasting.** The line was not
pasted whole, or not at all. Copy it again with the copy button, and paste it with
Ctrl + Shift + V.

**The error says `Qt could not open a window`.** A system library needed to display
windows is missing; the lines above name it. Send `install.log` with a request for help.

**The download is very slow or fails every time.** Some institutional networks filter
large downloads. Try from another network, or ask the IT department to allow
`github.com`, `conda-forge.org`, `download.pytorch.org`, `pypi.org`,
`files.pythonhosted.org`, `dl.fbaipublicfiles.com` and `huggingface.co`.

**The message says the graphics card is not used although the computer has an NVIDIA
card.** Either its driver is not installed (`No NVIDIA GPU found`), or it is too old
(`NVIDIA driver too old`); the installer then installs a version that works without the
card. Install or update the driver (see *Before you start*), restart, then do steps 1
and 2 again.

**VOLUTE does not open from the applications.** Start it from a terminal, which shows
its messages:

```bash
~/VOLUTE/SAM2-Plus/tools/launchers/volute.sh
```

The message shown is what to send with a request for help.

The [FAQ](faq.md) answers the most common questions.
For a step-by-step installation by hand, on another distribution for instance, see
[INSTALL.md](https://github.com/nicolasaudibert/VOLUTE/blob/main/INSTALL.md).
