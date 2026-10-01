"""
Patch sam2/utils/misc.py to add a CPU/MPS fallback for get_connected_components,
replacing the CUDA-only _C extension when CUDA is not available.
Run this script once after installing SAM2.
"""

import importlib
import shutil
import subprocess
import sys


# --- Fallback implementation to inject ---
FALLBACK_CODE = '''
def get_connected_components(mask):
    """
    CPU/MPS fallback for get_connected_components using scipy.
    Returns labels and per-pixel component areas, matching the CUDA _C extension API:
    - mask  : (N, 1, H, W) binary uint8 tensor
    - labels: (N, 1, H, W) int32 tensor, component id per foreground pixel (0 = background)
    - counts: (N, 1, H, W) int32 tensor, area of the component for each foreground pixel
    """
    import numpy as np
    from scipy.ndimage import label as scipy_label

    device = mask.device
    mask_np = mask.squeeze(1).cpu().numpy().astype(bool)  # (N, H, W)
    N, H, W = mask_np.shape

    out_labels = np.zeros((N, H, W), dtype=np.int32)
    out_counts = np.zeros((N, H, W), dtype=np.int32)

    struct = np.ones((3, 3), dtype=int)  # 8-connectivity
    for i in range(N):
        labeled, n_components = scipy_label(mask_np[i], structure=struct)
        out_labels[i] = labeled
        for comp_id in range(1, n_components + 1):
            comp_mask = labeled == comp_id
            out_counts[i][comp_mask] = comp_mask.sum()

    labels_t = torch.from_numpy(out_labels).unsqueeze(1).to(device)  # (N,1,H,W)
    counts_t = torch.from_numpy(out_counts).unsqueeze(1).to(device)  # (N,1,H,W)
    return labels_t, counts_t
'''

ORIGINAL_FUNC = '''def get_connected_components(mask):
    """
    Get the connected components (8-connectivity) of binary masks of shape (N, 1, H, W).

    Inputs:
    - mask: A binary mask tensor of shape (N, 1, H, W), where 1 is foreground and 0 is
            background.

    Outputs:
    - labels: A tensor of shape (N, 1, H, W) containing the connected component labels
              for foreground pixels and 0 for background pixels.
    - counts: A tensor of shape (N, 1, H, W) containing the area of the connected
              components for foreground pixels and 0 for background pixels.
    """
    from sam2 import _C

    return _C.get_connected_componnets(mask.to(torch.uint8).contiguous())'''


def check_cuda_available():
    import torch
    return torch.cuda.is_available()


def ensure_dependency(package_name, import_name=None):
    """Install package if not already importable."""
    import_name = import_name or package_name
    try:
        importlib.import_module(import_name)
        print(f"  [OK] {package_name} already installed.")
    except ImportError:
        print(f"  [..] Installing {package_name}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
        print(f"  [OK] {package_name} installed.")


def locate_misc_py():
    """Return the path to sam2/utils/misc.py from the installed package."""
    try:
        import sam2.utils.misc as m
        import inspect
        return inspect.getfile(m)
    except ImportError:
        sys.exit("[ERROR] sam2 package not found. Activate the correct conda environment.")


def patch_misc(misc_path):
    content = misc_path.read_text(encoding="utf-8")

    if "scipy_label" in content:
        print("[INFO] Fallback already applied, nothing to do.")
        return

    if ORIGINAL_FUNC not in content:
        print("[WARNING] Original get_connected_components signature not found.")
        print("          The file may have been modified. Aborting to avoid corruption.")
        return

    # Backup original file
    backup_path = misc_path.with_suffix(".py.bak")
    shutil.copy2(misc_path, backup_path)
    print(f"[INFO] Backup saved to {backup_path}")

    patched = content.replace(ORIGINAL_FUNC, FALLBACK_CODE.strip())
    misc_path.write_text(patched, encoding="utf-8")
    print(f"[OK] Patched {misc_path}")


def main():
    import torch  # noqa: ensure torch importable early
    from pathlib import Path

    print("=== SAM2 MPS/CPU fallback patcher ===\n")

    # 1. Check whether CUDA is available — skip patch if it is
    if check_cuda_available():
        print("[INFO] CUDA is available — patch not needed. Exiting.")
        sys.exit(0)
    else:
        device = "MPS" if torch.backends.mps.is_available() else "CPU"
        print(f"[INFO] CUDA not available (device: {device}). Applying fallback patch.\n")

    # 2. Ensure scipy is available (scikit-image not needed for this fallback)
    print("Checking dependencies...")
    ensure_dependency("scipy")
    print()

    # 3. Locate and patch misc.py
    misc_path = Path(locate_misc_py())
    print(f"[INFO] Patching {misc_path}\n")
    patch_misc(misc_path)

    # 4. Quick smoke test
    print("\nRunning smoke test...")
    try:
        import importlib
        import sam2.utils.misc as m
        importlib.reload(m)
        import torch
        dummy = torch.ones(1, 1, 64, 64, dtype=torch.uint8)
        labels, counts = m.get_connected_components(dummy)
        assert labels.shape == dummy.shape
        assert counts.shape == dummy.shape
        print("[OK] Smoke test passed.")
    except Exception as e:
        print(f"[ERROR] Smoke test failed: {e}")


if __name__ == "__main__":
    main()
