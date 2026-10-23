# VOLUTE Installation Guide

Complete installation instructions for VOLUTE.
Supports SAM2, MedSAM2 (optional), and SAM2++ backends in a single environment.

## Table of Contents

1. [Quick Installation (Windows, macOS and Linux)](#quick-installation-windows-macos-and-linux)
2. [Prerequisites](#prerequisites)
3. [Environment Setup](#environment-setup)
4. [SAM2++ Installation](#sam2-installation)
5. [GUI Dependencies](#gui-dependencies)
6. [GUI Installation](#gui-installation)
7. [Checkpoint Download](#checkpoint-download)
8. [MedSAM2 Setup (Optional)](#medsam2-setup-optional)
9. [Configuration](#configuration)
10. [Running the Application](#running-the-application)
11. [Troubleshooting](#troubleshooting)

## Quick Installation (Windows, macOS and Linux)

One command installs everything VOLUTE needs into a folder of its own — Miniforge, a
Python environment, PyTorch, SAM2-Plus, the models chosen and VOLUTE itself — and creates
the launcher. Nothing else on the computer is changed: an existing Python, conda or
Anaconda installation is left alone, and no shell or `PATH` setting is modified.

**macOS** — open **Terminal** (Applications › Utilities) and paste:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/nicolasaudibert/VOLUTE/main/install/install_volute_macos.sh)"
```

**Windows** — open **PowerShell** (type *PowerShell* in the Start menu) and paste:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://raw.githubusercontent.com/nicolasaudibert/VOLUTE/main/install/install_volute_windows.ps1 | iex"
```

**Linux** (Ubuntu 22.04 and 24.04; other distributions untested) — open a terminal
(Ctrl + Alt + T) and paste, with Ctrl + Shift + V:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/nicolasaudibert/VOLUTE/main/install/install_volute_linux.sh)"
```

or, where `curl` is missing, `bash -c "$(wget -qO- …)"` with the same address. No
administrator rights are needed.

Step-by-step guides, written for newcomers to the command line, walk through it:
[Windows](docs/install-windows.md) ([français](docs/install-windows.fr.md)), [macOS](docs/install-macos.md) ([français](docs/install-macos.fr.md)) and [Linux](docs/install-linux.md) ([français](docs/install-linux.fr.md)).

The installer shows what it detected, asks which models to download, then works on its
own. Depending on the connection, the hardware and the models, it takes 15 to 45 minutes
and 6 to 10 GB of disk space.

- **Folder**: `~/VOLUTE` on macOS and Linux; `%USERPROFILE%\VOLUTE` on Windows, or `C:\VOLUTE`
  when the user folder's path contains spaces or accented letters, which conda handles
  poorly. Set `VOLUTE_PREFIX` to choose another one. It holds `miniforge3` (Python and
  the environment), `SAM2-Plus` — whichever models are chosen, since it also provides
  SAM2's code — with VOLUTE in `SAM2-Plus/tools` and the models in
  `SAM2-Plus/checkpoints`, and `install.log`. pip's cache is kept there too, in
  `pip-cache`, rather than in the user profile; it is deleted once the installation
  succeeds, and kept after an interrupted one, which then resumes from it.
- **Hardware**: a Mac with Apple Silicon gets GPU acceleration (MPS); an Intel Mac the
  PyTorch build of conda-forge, PyPI no longer providing one, and runs markedly slower; an
  NVIDIA GPU the CUDA build matching what its driver supports, read from `nvidia-smi`, and,
  when older than Turing (compute capability below 7.5), the CUDA 12.6 build, the last to
  support it, computing in float32; any other computer a CPU build, which works, but
  segmentation is markedly slower.
- **SAM2's CUDA extension** is not compiled, which would need Visual Studio and the CUDA
  toolkit; the [post-processing patch](#optional-cpumps-fallback-patch-for-mask-post-processing)
  is applied instead.
- **Models**: SAM2.1 Large (selected by default), SAM2.1 Small, SAM2++, and MedSAM2 —
  its four checkpoints, under CC BY-SA 4.0, and the config they need, placed in
  `sam2/configs/medsam2_configs/` — or `a` for all of them; `--models` passed to the
  installer answers the question beforehand.
- **ffmpeg** comes with the environment, for frame extraction from a video.
- **PyQt5**, on Linux, comes from conda-forge rather than PyPI: its Qt brings the X11
  libraries (`libxcb-*`) the PyPI wheel needs from the system, so that nothing has to be
  installed with `sudo`. Before creating the launcher, the installer opens a Qt window for
  an instant, so that a library still missing shows then rather than at VOLUTE's first
  start; it skips that check without a graphical session.
- **Launcher**: `VOLUTE.app` in the `Applications` folder of the home folder on macOS, a
  **VOLUTE** shortcut on the Desktop on Windows, an entry in the applications menu on
  Linux (`~/.local/share/applications/volute.desktop`, running
  `tools/launchers/volute.sh`, which names the environment's Python).
- **Updating**: run the same command again. VOLUTE is updated to its latest release, the
  settings in `volute_config.yaml` are kept, and further models can be added; whatever is
  already installed is not downloaded again. The same applies after an interrupted
  installation.
- **Uninstalling**: delete the folder, and `VOLUTE.app`, the Desktop shortcut or
  `volute.desktop`.
- **Log**: `install.log` in the folder records every step, with the error messages of
  pip and conda, for troubleshooting.

The
sections below describe the installation step by step, for Linux or a setup of one's own.

## Prerequisites

- **Anaconda or Miniconda** installed on your system
- **Python 3.10** (required by SAM2++)
- **Git** for cloning repositories
- **CUDA 11.8+** or **Apple Silicon (MPS)** for GPU acceleration (CPU fallback available)

## Environment Setup

Create and activate a dedicated conda environment:

```bash
conda create -n sam2_plus python=3.10 -y
conda activate sam2_plus
conda install pip
```

**Important:** Always activate this environment before using the GUI:
```bash
conda activate sam2_plus
```

## SAM2++ Installation

SAM2++ bundles both the original `sam2` package and the extended `sam2_plus` package in
a single repository, so a separate SAM2 installation is not required.

```bash
# Clone SAM2-Plus repository
git clone https://github.com/MCG-NJU/SAM2-Plus.git
cd SAM2-Plus

# Make the repo root importable (add to your shell profile for persistence)
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Install PyTorch — choose the command matching your hardware.
# For an NVIDIA GPU, `nvidia-smi` prints the highest CUDA version the driver
# supports, top right; pick the newest build below that does not exceed it.

# NVIDIA GPU, CUDA 12.6 (most current GPUs and drivers)
pip install torch==2.7.0 torchvision==0.22.0 torchaudio==2.7.0 \
    --index-url https://download.pytorch.org/whl/cu126

# NVIDIA GPU, CUDA 12.8 (required by RTX 50-series GPUs)
pip install torch==2.7.0 torchvision==0.22.0 torchaudio==2.7.0 \
    --index-url https://download.pytorch.org/whl/cu128

# NVIDIA GPU, CUDA 11.8 (older drivers)
pip install torch==2.7.0 torchvision==0.22.0 torchaudio==2.7.0 \
    --index-url https://download.pytorch.org/whl/cu118

# No NVIDIA GPU, Windows or Linux (CPU only)
pip install torch==2.7.0 torchvision==0.22.0 torchaudio==2.7.0 \
    --index-url https://download.pytorch.org/whl/cpu

# Mac with Apple Silicon (M1 and later; MPS acceleration included)
pip install torch==2.7.0 torchvision==0.22.0 torchaudio==2.7.0

# Mac with an Intel processor (markedly slower than Apple Silicon): PyTorch no
# longer publishes these builds on PyPI, but conda-forge does
conda install -c conda-forge pytorch=2.7.0 torchvision=0.22.0

# Install SAM2++ dependencies and packages
pip install -r sam2_plus/requirements.txt
pip install -e .
pip install -e ".[dev]"

# Build C++ extensions (NVIDIA GPU only — skip on macOS/MPS)
# On macOS the CUDA extension is unavailable; the warning emitted is non-fatal
# and can be safely ignored. SAM2++ runs without it on MPS.
# An optional patch restores the mask post-processing the extension provides —
# see "Optional: CPU/MPS fallback patch" under Troubleshooting.
python setup.py build_ext --inplace

# Verify installation
python -c "import torch; print(torch.__version__); from sam2_plus.build_sam import build_sam2_video_predictor_plus; print('OK')"

# NVIDIA GPU only: check that the GPU is seen and the extension was built
python -c "import torch; print(torch.cuda.is_available()); from sam2 import _C; print('extension OK')"
```

On an Apple Silicon Mac, `python -c "import torch; print(torch.backends.mps.is_available())"`
should print `True`.

## GUI Dependencies

Install required and optional dependencies:

### Required

```bash
pip install PyQt5 scipy pyyaml
```

### Optional (recommended)

```bash
# Excel export for centroids and closest mask points
pip install pandas openpyxl

# Outer contour computation
pip install scikit-image
# or: pip install opencv-python
```

### Optional: ffmpeg, to extract frames from a video

**File › Extract Frames from Video…** turns a video file into the folder of numbered
images the application loads. It relies on [ffmpeg](https://ffmpeg.org) and on `ffprobe`,
which every ffmpeg distribution ships alongside it. Nothing else in the application needs
them: without ffmpeg, only this menu entry is unavailable.

Install it either into the conda environment, which works the same on every platform:

```bash
conda install -c conda-forge ffmpeg
```

or system-wide:

```bash
brew install ffmpeg          # macOS (Homebrew)
sudo apt install ffmpeg      # Debian, Ubuntu
winget install Gyan.FFmpeg   # Windows; open a new terminal afterwards so PATH is updated
```

Check that both programs answer:

```bash
ffmpeg -version
ffprobe -version
```

The application looks for `ffmpeg` on `PATH`, then in the conda environment it runs from
and in the usual Homebrew, MacPorts and system locations — those cover a launch from the
macOS Finder, which does not inherit the shell's `PATH`. A shell alias is not seen. For an
installation elsewhere, give the path to the executable in **File › Settings… ›
Performance and tools › ffmpeg executable**.

## GUI Installation

The GUI lives in the `tools/` directory of the SAM2-Plus installation, beside the files
SAM2-Plus already ships there. Clone the repository somewhere else and copy its contents
in — `git clone` refuses a destination that is not empty, so it cannot clone into `tools/`
directly:

```bash
# From within the SAM2-Plus directory
git clone https://github.com/nicolasaudibert/VOLUTE.git ../VOLUTE-src
rsync -a --exclude .git ../VOLUTE-src/ tools/
```

Windows has no `rsync`; `robocopy`, built in, does the same from a Command Prompt
(it reports success with an exit code of 1, not 0):

```batch
git clone https://github.com/nicolasaudibert/VOLUTE.git ..\VOLUTE-src
robocopy ..\VOLUTE-src tools /E /XD .git
```

Keep the clone: updating later is `git -C ../VOLUTE-src pull` followed by the same copy.
Delete it if you would rather not.

The copy brings the hidden `.gitignore` along with the rest, and leaves out the `.git`
directory, which `cp -R` or a plain drag and drop would bring too.

Verify the installation structure:

```
SAM2-Plus/
├── checkpoints/
│   ├── SAM2-Plus/
│   │   └── checkpoint_phase123.pt
│   └── sam2.1_hiera_large.pt        (optional, for SAM2 backend)
├── configs/
│   └── sam2.1/
│       ├── sam2.1_hiera_l.yaml
│       └── sam2.1_hiera_b+_predmasks_decoupled_MAME.yaml
├── sam2/                             (bundled SAM2 package)
├── sam2_plus/                        (SAM2++ package)
├── tools/
│   ├── VOLUTE.py
│   └── volute/
│       ├── __init__.py
│       ├── main_window.py
│       ├── config_manager.py
│       └── ... (other modules)
└── volute_config.yaml             (optional)
```

## Checkpoint Download

### SAM2++ checkpoint (required for SAM2++ backend)

```bash
pip install "huggingface_hub[cli]"
huggingface-cli download MCG-NJU/SAM2-Plus \
    --local-dir ./checkpoints/SAM2-Plus
```

### SAM2 checkpoints (optional, for SAM2 backend)

```bash
cd checkpoints
bash download_ckpts.sh
cd ..
```

The application will automatically detect and use the appropriate checkpoint based on
the `volute_config.yaml` configuration.

## MedSAM2 Setup (Optional)

The [one-command installer](#quick-installation-windows-macos-and-linux) downloads MedSAM2 when it is
chosen; the steps below are for a manual installation.

SAM2++ bundles the `sam2` package internally. MedSAM2 also depends on `sam2`, so it
is expected to work with this bundled version — **compatibility should be verified on
first use**, as minor API differences between the bundled copy and the original Meta
SAM2 release may surface.

### 1. Download MedSAM2

```bash
# Clone MedSAM2 repository (outside the SAM2-Plus directory)
cd /path/to/your/projects
git clone https://github.com/bowang-lab/MedSAM2.git
cd MedSAM2
bash download.sh
```

**Note:** You do **not** need to install MedSAM2 — only download the checkpoints and configs.

### 2. Create Symbolic Links

The checkpoints and configurations stay in the MedSAM2 directory; links make them appear
where VOLUTE looks for them.

#### macOS/Linux

```bash
cd /path/to/SAM2-Plus

# Checkpoint symlinks
ln -s /path/to/MedSAM2/checkpoints/MedSAM2_latest.pt checkpoints/MedSAM2_latest.pt
ln -s /path/to/MedSAM2/checkpoints/MedSAM2_2411.pt   checkpoints/MedSAM2_2411.pt
# add other checkpoints as needed

# Config directory symlink
ln -s /path/to/MedSAM2/sam2/configs sam2/configs/medsam2_configs
```

#### Windows (PowerShell as Administrator, or with Developer Mode enabled)

```powershell
cd C:\path\to\SAM2-Plus

New-Item -ItemType SymbolicLink -Path "checkpoints\MedSAM2_latest.pt" `
    -Target "C:\path\to\MedSAM2\checkpoints\MedSAM2_latest.pt"
New-Item -ItemType SymbolicLink -Path "sam2\configs\medsam2_configs" `
    -Target "C:\path\to\MedSAM2\sam2\configs"
```

### 3. Verify MedSAM2 Setup

```bash
ls -la checkpoints/MedSAM2*.pt
ls -la sam2/configs/medsam2_configs
```

## Configuration

Settings live in `tools/volute_config.yaml`, which documents each of them, and are all
editable from **File › Settings…**; the full list is under *Configuration* in
[DOCUMENTATION.md](DOCUMENTATION.md#configuration).

The model is chosen at startup, in the application's model chooser, or with `--model` on
the command line. The model paths in `volute_config.yaml` are informative only: the
configuration and checkpoint files are resolved in `VOLUTE.py`, relative to the SAM2-Plus
directory, for Hydra compatibility.

### Available Languages

English is built into the application, and French is shipped in
`tools/volute/translations/fr.tsv`. A further language takes a new TSV file in that
directory, started from `template.tsv`, with no code change — see
`tools/volute/translations/translation_readme.md`.

## Running the Application

### Basic Usage

```bash
# Navigate to the SAM2-Plus directory
cd /path/to/SAM2-Plus

# Ensure the environment is active and the path is set
conda activate sam2_plus
export PYTHONPATH=$PYTHONPATH:$(pwd)   # if not already in your shell profile

# Start, choosing the model in the application
python tools/VOLUTE.py

# Run with SAM2 backend
python tools/VOLUTE.py --model sam2

# Run with MedSAM2 backend
python tools/VOLUTE.py --model medsam2

# Run with SAM2++ backend, mask or point tracking mode
python tools/VOLUTE.py --model sam2plus
python tools/VOLUTE.py --model sam2plus --task point

# Enable debug mode
python tools/VOLUTE.py --debug
```

### Command-Line Options

```
--model {sam2,medsam2,sam2plus}   Backend to use; skips the startup model chooser
--task {mask,point}               SAM2++ tracking task (sam2plus only)
--config PATH                     Override config file path
--checkpoint PATH                 Override checkpoint file path
--working-dir PATH                Set working directory (default: the SAM2-Plus directory)
--debug                           Enable verbose debug output
```

### Examples

```bash
# Specific MedSAM2 checkpoint
python tools/VOLUTE.py \
  --model medsam2 \
  --checkpoint checkpoints/MedSAM2_CTLesion.pt

# Full manual override
python tools/VOLUTE.py \
  --config configs/sam2.1/sam2.1_hiera_l.yaml \
  --checkpoint checkpoints/sam2.1_hiera_large.pt \
  --debug
```

### Launcher Scripts

Ready-made launchers, one per model plus one that asks, are generated into
`tools/launchers/`:

- **Windows**: double-click `tools\install_launchers_windows.bat`, or run it from a
  Command Prompt. It finds the environment's Python — the one given as argument, else
  that of the active conda environment, else `python` on `PATH`, else a `sam2_plus`
  environment of Miniforge, Miniconda or Anaconda — and keeps the first that can import
  SAM2, PyTorch and PyQt5. The launchers it
  writes run that interpreter directly, so they work by double-click with no environment
  activated, and a **VOLUTE** shortcut is added to the Desktop. Should the application
  stop on an error, the launcher's window stays open to show it. Re-run the script
  after moving the installation or recreating the environment.

  ```batch
  tools\install_launchers_windows.bat
  tools\install_launchers_windows.bat C:\path\to\env\python.exe
  ```

- **macOS/Linux**: `bash tools/install_launchers_Unix_MacOS.sh`. These launchers run
  whichever `python` is on `PATH`, so the `sam2_plus` environment must be active; with
  `--python PATH`, they run that interpreter instead, with no activation needed. On
  macOS, `bash tools/install_app_bundle_macos.sh` instead builds a double-clickable
  `VOLUTE.app` bound to the environment's interpreter, with no activation needed.

## Troubleshooting

### "No module named 'sam2'" or "No module named 'sam2_plus'"

Verify that `PYTHONPATH` includes the SAM2-Plus root and that the package was installed:
```bash
cd /path/to/SAM2-Plus
export PYTHONPATH=$PYTHONPATH:$(pwd)
pip install -e .
python -c "from sam2_plus.build_sam import build_sam2_video_predictor_plus; print('OK')"
```

### C++ extension build failure / CUDA_HOME not set

On **macOS (MPS)** this warning is expected and harmless — the CUDA extension is not
built and not needed. Skip the `build_ext` step or ignore the warning.

On **Linux/Windows with an NVIDIA GPU**, make sure a compatible compiler is available
and that `CUDA_HOME` points to your CUDA toolkit root, then retry:
```bash
python setup.py build_ext --inplace
```
On macOS, Xcode Command Line Tools may be required for other build steps:
`xcode-select --install`.

### Optional: CPU/MPS fallback patch for mask post-processing

Without the CUDA extension, SAM2 skips the post-processing step that fills small holes in
segmentation masks (`fill_holes_in_mask_scores`) and emits:

```
UserWarning: cannot import name '_C' from 'sam2'
Skipping the post-processing step due to the error above.
```

Segmentation still works; masks may simply retain small holes. The scripts under
`tools/sam2_misc_patch/` substitute a `scipy`-based implementation, restoring the step on
machines without an NVIDIA GPU:

```bash
python tools/sam2_misc_patch/patch_sam2_misc.py    # apply
python tools/sam2_misc_patch/restore_sam2_misc.py  # revert
```

Worth applying when running on macOS (Apple Silicon or Intel), on Windows/Linux without
an NVIDIA GPU, or on an NVIDIA machine where the extension was not compiled, and mask
quality matters enough to want the hole-filling step.

Not needed on a CUDA machine where the extension was built: the script detects that it
imports and exits without modifying anything, the compiled extension being faster than
the fallback. `scipy` is already a required dependency above, so nothing extra is
installed.

Developed against SAM2-Plus 1.0; a future SAM2 release may make it unnecessary, and the
script refuses to touch a `misc.py` it does not recognise. See
`tools/sam2_misc_patch/SAM2_PATCH_README.md` for details and compatibility notes.

#### Compiling the CUDA extension instead

The fallback gives the same masks, and costs little: in a measurement on an Apple Silicon
Mac (SAM2.1 Large, two objects, 40 frames), it took 0.5 % of the propagation time, and its
share should stay within a few percent on a fast NVIDIA GPU. Compiling the extension is
possible on an NVIDIA machine, but needs **administrator rights** to install its tools:
the CUDA toolkit of the version PyTorch was built for
(`python -c "import torch; print(torch.version.cuda)"`) and, on Windows, Visual Studio
Build Tools with the *Desktop development with C++* workload. On Windows, run the commands
below from the *x64 Native Tools Command Prompt for VS*, which puts the compiler on `PATH`.
`SAM2_BUILD_ALLOW_ERRORS=0` makes a failed build stop with its error, where SAM2-Plus would
otherwise skip the extension silently.

- **New manual installation**: build the extension as in
  [SAM2++ Installation](#sam2-installation) (`python setup.py build_ext --inplace`), and
  do not apply the patch; the check given there, `from sam2 import _C`, confirms the build.
- **Existing installation where the patch was applied** — the one-command installer
  applies it on every machine: build the extension, then revert the patch, without which
  the fallback stays in use. With the installation's own Python,
  `<folder>/miniforge3/envs/volute/bin/python`, or
  `<folder>\miniforge3\envs\volute\python.exe` on Windows, from its `SAM2-Plus`
  folder:

  ```bash
  SAM2_BUILD_ALLOW_ERRORS=0 python setup.py build_ext --inplace   # Windows: set SAM2_BUILD_ALLOW_ERRORS=0 first
  python tools/sam2_misc_patch/restore_sam2_misc.py
  python -c "import torch; print(torch.cuda.is_available()); from sam2 import _C; print('extension OK')"
  ```

  Running the installer again afterwards keeps the extension: its patch step finds that
  the extension imports and leaves `misc.py` alone. Should the extension stop loading
  later, after PyTorch is replaced following an NVIDIA driver update for instance, that
  same step applies the fallback again; rebuild the extension to return to it.

### "ffmpeg was not found" when extracting frames from a video

ffmpeg is not installed, or not where the application looks: see
[Optional: ffmpeg](#optional-ffmpeg-to-extract-frames-from-a-video). If ffmpeg answers in a
terminal but not in the application, `which ffmpeg` (macOS, Linux) or `where ffmpeg`
(Windows) gives the path to enter in **File › Settings… › Performance and tools**. If that
path is the one already set there and the message names it, it does not point at an
executable file.

When ffprobe alone is missing, extraction still works: the dialog says so, and progress is
shown as a count of frames written rather than as a percentage.

### "No module named 'PyQt5'"

```bash
pip install PyQt5
```

### MedSAM2 not detected

Verify symlinks exist and point to valid files:
```bash
ls -la checkpoints/MedSAM2*.pt
ls -la sam2/configs/medsam2_configs
```

### MedSAM2 API compatibility error

If MedSAM2 fails with an import or attribute error related to the bundled `sam2` copy,
check the installed SAM2 version:
```bash
python -c "import sam2; print(sam2.__version__)"
```
If needed, report the specific error so the symlink or import path can be adjusted.

### "Permission denied" creating symlinks (Windows)

Run Command Prompt or PowerShell as Administrator.

### Platform-Specific Notes

**macOS (Apple Silicon)**
- MPS backend is used automatically.
- `PYTORCH_ENABLE_MPS_FALLBACK=1` may be needed for unsupported ops; the application
  sets this automatically where required.
- Install `scipy` for optimal mask resizing: `pip install scipy`.

**Windows**
- Symlink creation requires Administrator privileges.
- Use PowerShell rather than Command Prompt for symlink commands.

**Linux**
- CUDA support requires an NVIDIA GPU and matching CUDA toolkit.
- PyQt5 from PyPI needs X11 libraries from the system, without which it stops with "Could
  not load the Qt platform plugin xcb": either install PyQt5 from conda-forge instead
  (`conda install -c conda-forge pyqt=5`, after `pip uninstall PyQt5`), whose Qt brings
  them, or install them: `sudo apt-get install libxcb-xinerama0 libxcb-icccm4
  libxcb-image0 libxcb-keysyms1 libxcb-render-util0 libxkbcommon-x11-0`.
- GIMP 3 is needed for the editing round-trip; the `apt` package of Ubuntu 22.04 and
  24.04 is GIMP 2.10. VOLUTE finds GIMP 3 installed as a Flatpak (Flathub) or a Snap.

### Debug Mode

```bash
python tools/VOLUTE.py --debug
```

Outputs: backend type and paths, configuration loading details, device information
(CPU/CUDA/MPS), filename mapping details, and detailed error traces.
