# VOLUTE Installation Guide

Complete installation instructions for the SAM2 Video Segmentation GUI.
Supports SAM2, MedSAM2 (optional), and SAM2++ backends in a single environment.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Environment Setup](#environment-setup)
3. [SAM2++ Installation](#sam2-installation)
4. [GUI Dependencies](#gui-dependencies)
5. [GUI Installation](#gui-installation)
6. [Checkpoint Download](#checkpoint-download)
7. [MedSAM2 Setup (Optional)](#medsam2-setup-optional)
8. [Configuration](#configuration)
9. [Running the Application](#running-the-application)
10. [Troubleshooting](#troubleshooting)

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

# Install PyTorch — choose the command matching your hardware:

# CUDA 12.1 (most NVIDIA GPUs)
pip install torch==2.7.0 torchvision==0.22.0 torchaudio==2.7.0 \
    --index-url https://download.pytorch.org/whl/cu121

# CUDA 11.8
pip install torch==2.7.0 torchvision==0.22.0 torchaudio==2.7.0 \
    --index-url https://download.pytorch.org/whl/cu118

# Apple Silicon (MPS) or CPU
pip install torch==2.7.0 torchvision==0.22.0 torchaudio==2.7.0 \
    --extra-index-url https://download.pytorch.org/whl/nightly/cpu 

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
# On macOS, omit "from sam2 import _C" — the extension is not built
python -c "import torch; print(torch.__version__); from sam2_plus.build_sam import build_sam2_video_predictor_plus; print('OK')"
```

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

## GUI Installation

Copy the GUI files into the SAM2-Plus installation:

```bash
# From within the SAM2-Plus directory
cp /path/to/VOLUTE.py tools/
cp -r /path/to/volute/ tools/
cp /path/to/volute_config.yaml .   # optional
```

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

#### macOS and Linux

```bash
cd /path/to/SAM2-Plus

chmod +x tools/setup_medsam2_symlinks.sh
tools/setup_medsam2_symlinks.sh /path/to/MedSAM2
```

#### Windows (Administrator)

```batch
cd C:\path\to\SAM2-Plus
tools\setup_medsam2_symlinks.bat C:\path\to\MedSAM2
```

### Manual Symlink Creation (Alternative)

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

#### Windows (Administrator PowerShell)

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

The active backend (SAM2, MedSAM2, SAM2++) is controlled via `volute_config.yaml`.
Model paths are set in this file but marked informative only — actual path resolution
is handled in `main_window.py` for Hydra compatibility.

```yaml
# SAM2 Video Segmentation GUI Configuration

ui:
  default_language: "en"              # "en", "fr", etc.
  progress_details_font_size: 12
  import_confirmation_default: "yes"

export:
  coordinates_format: "json"          # "json", "csv", "pickle"
  centroids_format: "excel"           # "excel", "csv", "json"
  image_quality: 95                   # JPEG quality (1-100)

debug:
  enabled: false
  show_filename_mappings: false
  show_mask_sync_details: false

performance:
  image_cache_size: 32                # LRU cache size for lazy frame loading (0 = unlimited)
```

### Available Languages

Translation files are in `tools/volute/translations/`. English (`en.tsv`) and French
(`fr.tsv`) are included. Add further languages by creating a TSV file with the same
key structure.

## Running the Application

### Basic Usage

```bash
# Navigate to the SAM2-Plus directory
cd /path/to/SAM2-Plus

# Ensure the environment is active and the path is set
conda activate sam2_plus
export PYTHONPATH=$PYTHONPATH:$(pwd)   # if not already in your shell profile

# Run with SAM2 backend (default)
python tools/VOLUTE.py

# Run with MedSAM2 backend
python tools/VOLUTE.py --model medsam2

# Run with SAM2++ backend
python tools/VOLUTE.py --model sam2plus

# Enable debug mode
python tools/VOLUTE.py --debug
```

### Command-Line Options

```
--model {sam2,medsam2,sam2plus}   Backend to use (default: sam2)
--config PATH                     Override config file path
--checkpoint PATH                 Override checkpoint file path
--working-dir PATH                Set working directory
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

Platform-specific launcher scripts can be generated with `install_launchers_unix.sh`
(macOS/Linux) or `install_launchers_windows.bat`. Ensure they activate the `sam2_plus`
conda environment and set `PYTHONPATH` before launching.

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

Worth applying when running on macOS (Apple Silicon or Intel), or on Windows/Linux
without an NVIDIA GPU, and mask quality matters enough to want the hole-filling step.

Not needed on a CUDA machine: the script detects CUDA and exits without modifying
anything, the compiled extension being faster than the fallback. `scipy` is already a
required dependency above, so nothing extra is installed.

Developed against SAM2-Plus 1.0; a future SAM2 release may make it unnecessary, and the
script refuses to touch a `misc.py` it does not recognise. See
`tools/sam2_misc_patch/SAM2_PATCH_README.md` for details and compatibility notes.

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
- Qt system libraries may be needed: `sudo apt-get install python3-pyqt5 libxcb-xinerama0`.

### Debug Mode

```bash
python tools/VOLUTE.py --debug
```

Outputs: backend type and paths, configuration loading details, device information
(CPU/CUDA/MPS), filename mapping details, and detailed error traces.
