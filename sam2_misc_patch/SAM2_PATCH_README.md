# SAM2 MPS/CPU Fallback Patch

## Background

SAM2 includes a post-processing step (`fill_holes_in_mask_scores`) that fills small holes
in segmentation masks. This step relies on a compiled C++ extension (`sam2._C`) that
**requires CUDA** and therefore cannot be built on:

- macOS (Apple Silicon or Intel), which uses MPS or CPU
- any Windows/Linux environment without an NVIDIA GPU

When the extension is missing, SAM2 displays the following warning and skips post-processing:

```
UserWarning: cannot import name '_C' from 'sam2'
Skipping the post-processing step due to the error above.
```

The two scripts below allow you to apply and revert a patch that substitutes the CUDA
extension with an equivalent Python implementation based on `scipy`.

---

## Location and execution

The scripts are located in:

```
<repo-root>/tools/sam2_misc_patch/
├── patch_sam2_misc.py
├── restore_sam2_misc.py
└── SAM2_PATCH_README.md
```

Throughout this document:

- `<repo-root>` is the directory containing the `sam2/` package folder and `setup.py`.
  It is `sam2/` for an official SAM2 checkout and `SAM2-Plus/` for SAM2-Plus; the patch
  applies to both.
- `<env>` is the conda environment SAM2 is installed in — `sam2_plus` if you followed
  VOLUTE's `INSTALL.md`.

The commands below are written relative to `<repo-root>`, so run them from there. The
scripts themselves locate `misc.py` through the active environment rather than through
the working directory, so invoking them by absolute path from anywhere works too.

```bash
cd /path/to/<repo-root>
conda activate <env>
python tools/sam2_misc_patch/patch_sam2_misc.py
python tools/sam2_misc_patch/restore_sam2_misc.py
```

---

## Scripts

| Script | Role |
|---|---|
| `patch_sam2_misc.py` | Applies the MPS/CPU fallback |
| `restore_sam2_misc.py` | Restores the original state |

---

## Prerequisites

- the conda environment SAM2 is installed in, correctly set up and activated
- SAM2 installed in editable mode (`pip install -e .`) or via pip
- `scipy`, which the patch script installs into the active environment if it is
  missing. VOLUTE already requires it, so an environment set up for the
  application will normally have it.

---

## Usage

### Applying the patch

```bash
cd /path/to/<repo-root>
conda activate <env>
python tools/sam2_misc_patch/patch_sam2_misc.py
```

The script will:

1. Check whether CUDA is available — **exits without any modification** if it is
2. Run `pip install scipy` in the active environment if `scipy` is not importable
3. Back up `misc.py` → `misc.py.bak` in the same directory
4. Replace `get_connected_components` with a `scipy.ndimage`-based implementation
5. Run a smoke test to validate the patch

### Restoring the original state

```bash
cd /path/to/<repo-root>
conda activate <env>
python tools/sam2_misc_patch/restore_sam2_misc.py
```

The script restores `misc.py` from `misc.py.bak` and removes the backup file.

---

## Technical details

The fallback uses `scipy.ndimage.label` with an 8-connected structure, reproducing the
behaviour of SAM2's CUDA kernel. The API is identical: input `(N, 1, H, W)` uint8 tensor,
outputs `labels` and `counts` tensors of the same shape. The difference in final
segmentation results compared to a CUDA run is negligible.

The patch script is idempotent: a second run detects that the patch is already in place
and makes no further changes, and in particular leaves the existing backup untouched.

---

## Compatibility

Developed against **SAM2-Plus 1.0** (upstream commit `09c9ec4`, December 2025), whose
`sam2/utils/misc.py` had been unchanged since October 2025.

The patch locates `get_connected_components` by matching its exact source text. Should a
future SAM2 release rewrite that function, `patch_sam2_misc.py` reports:

```
[WARNING] Original get_connected_components signature not found.
          The file may have been modified. Aborting to avoid corruption.
```

and leaves the file untouched, so a version mismatch cannot corrupt an installation.

The patch also becomes unnecessary if a future SAM2 release ships its own CPU/MPS path
for `fill_holes_in_mask_scores`. Before applying it, check whether the
`cannot import name '_C'` warning still appears.

---

## Notes

- The patch modifies `misc.py` **inside the package installation directory**, located
  dynamically at runtime. The scripts can therefore be run from any working directory,
  provided the environment SAM2 is installed in is active.
- After updating SAM2 (`git pull` + `pip install -e .`), the patch must be **re-applied**.
- The backup file `misc.py.bak` is created in the same directory as `misc.py`. Do not
  delete it manually if you intend to restore the original later.
