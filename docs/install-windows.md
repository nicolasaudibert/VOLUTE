# Installing VOLUTE on Windows

*[Version française](install-windows.fr.md)*

This guide is for anyone who has never installed a Python program and rarely, if ever,
types commands. You will copy one line, paste it into a window, and answer one question:
the installer does the rest.

Nothing else on the computer is changed. VOLUTE gets a folder of its own, with its own
copy of Python, so any Python, Anaconda or Miniconda already installed is left alone — you
do not need to know whether you have one.

## Before you start

- **Windows 10 or 11, 64-bit.** Almost every PC sold in the last ten years qualifies.
- **About 10 GB of free disk space**, and an Internet connection. The installation
  downloads several gigabytes; count 20 to 60 minutes depending on the connection.
- **No administrator rights** are needed.
- **An NVIDIA graphics card makes VOLUTE much faster**, and the installer finds it by
  itself. To check whether the computer has one, open the Task Manager (Ctrl + Shift +
  Esc), go to the **Performance** tab and look for a **GPU** entry naming NVIDIA. If it
  does, updating its driver first is worthwhile: open **NVIDIA App** or **GeForce
  Experience** if installed, or get the driver from
  [nvidia.com/drivers](https://www.nvidia.com/drivers). Without an NVIDIA card VOLUTE
  works too, but more slowly.

## 1. Open PowerShell

PowerShell is the window in which commands are typed.

1. Click the **Start** button, and type `PowerShell`.
2. Click **Windows PowerShell**. Be careful **not** to right-click it and choose *Run as
   administrator*: no administrator rights are needed (see above), and it would later
   cause problems with access to some folders.

A window with a dark blue or black background opens, showing a line that ends with `>`,
such as `PS C:\Users\yourname>`. That line is where commands go.

## 2. Paste the installation command

1. Select the whole line below and copy it (Ctrl + C), or click the copy button at the
   right of the box:

   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/nicolasaudibert/VOLUTE/main/install/install_volute_windows.ps1 | iex"
   ```

2. Click in the PowerShell window, then paste with a **right-click** (or Ctrl + V).
3. Press **Enter**.

## 3. Answer the installer

The installer first installs **Miniforge**, the Python distribution VOLUTE runs on, which
takes a few minutes. It then shows what it found about the computer, for example:

```
[1/8] Checking the computer
    Windows 10, AMD64
    NVIDIA GPU of compute capability 8.6, driver supporting CUDA 12.8: PyTorch for CUDA 12.8
    Installation folder: C:\Users\yourname\VOLUTE
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
  SAM2.1 Large and SAM2++. To download them all, type `a`.

When unsure, press Enter: other models can be added later.

The installer then asks `Start the installation? [Y/n]`: press **Enter** to accept.

## 4. Wait

The installer now works on its own, in eight steps numbered `[1/8]` to `[8/8]`. Lines
scroll by, sometimes with progress bars; the longest step is **PyTorch**, which can stay
several minutes on the same line. This is normal: leave the window open, and the
computer awake.

It is finished when it shows:

```
======================================================================
VOLUTE 0.9.3 is installed.
======================================================================
```

with the current version number, followed by `Press Enter to close`. Press Enter: the
window closes.

## 5. Start VOLUTE

Double-click the **VOLUTE** icon on the Desktop.

A black window opens first, then VOLUTE's own window, which asks which model to use: pick
one you downloaded. **Leave the black window open** while you work — it is part of VOLUTE,
and closing it closes the application. If VOLUTE stops because of a problem, that window
stays open with a message explaining it.

The [Getting started](https://github.com/nicolasaudibert/VOLUTE/blob/main/README.md#getting-started) section of the README walks through a
first session.

ffmpeg, which extracts the frames of a video (**File › Extract Frames from Video…**),
is installed with VOLUTE. GIMP, used to retouch masks by hand, is not: if you need it,
install it from [gimp.org](https://www.gimp.org) (version 3.0 or later).

## What the VOLUTE folder holds

- `miniforge3`: VOLUTE's Python distribution and its environment;
- `SAM2-Plus`: the code of the models, which VOLUTE is part of (`SAM2-Plus\tools`), and
  the downloaded models (`SAM2-Plus\checkpoints`). It bears this name whichever models
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

1. Delete the **VOLUTE** folder: `C:\Users\<your name>\VOLUTE`, or `C:\VOLUTE` (see
   below).
2. Delete the **VOLUTE** shortcut on the Desktop.

Nothing else was installed.

## If something goes wrong

**The installation stopped with a red `Error` or an `ERROR:` line.** Read the line: it
says what to do. Most often, the connection dropped during a download: do steps 1 and 2
again, and the installation resumes. If the problem persists, the file `install.log` in
the VOLUTE folder records every step; it is what to send with a request for help.

**The installation folder is `C:\VOLUTE` rather than in my user folder.** This happens
when the user name contains spaces or accented letters (`C:\Users\First Last`,
`C:\Users\Hélène`), which the Python tools VOLUTE relies on handle poorly. It changes
nothing in use.

**The download is very slow or fails every time.** Some institutional networks filter
large downloads. Try from another network, or ask the IT department to allow
`github.com`, `conda-forge.org`, `download.pytorch.org`, `pypi.org`,
`files.pythonhosted.org`, `dl.fbaipublicfiles.com` and `huggingface.co`.

**An antivirus warns about the installation, or slows it down a lot.** The installer
writes thousands of small files, which some antivirus programs examine one by one. The
installation should not be considered a security risk; if the antivirus blocks it, ask the
IT department.

**The message says the GPU is not used although the computer has an NVIDIA card.** The
driver is probably too old: the installer then says so, and installs a version that runs
without the card. Update the driver (see *Before you start*), then do steps 1 and 2 again.

**The black window shows an error when VOLUTE starts.** Note the message, or take a
screenshot of it: it says what went wrong, and is what to send with a request for help.

The [FAQ](faq.md) answers the most common questions.
For a step-by-step installation by hand, see [INSTALL.md](https://github.com/nicolasaudibert/VOLUTE/blob/main/INSTALL.md).
