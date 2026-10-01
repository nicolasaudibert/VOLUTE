"""
Restore sam2/utils/misc.py to its original state by replacing it with the
.py.bak backup created by patch_sam2_misc.py.
"""

import inspect
import sys
from pathlib import Path


def locate_misc_py():
    try:
        import sam2.utils.misc as m
        return Path(inspect.getfile(m))
    except ImportError:
        sys.exit("[ERROR] sam2 package not found. Activate the correct conda environment.")


def main():
    print("=== SAM2 misc.py restore ===\n")

    misc_path = locate_misc_py()
    backup_path = misc_path.with_suffix(".py.bak")

    if not backup_path.exists():
        print(f"[INFO] No backup found at {backup_path}.")
        print("       Either patch_sam2_misc.py was never run or the backup was deleted.")
        sys.exit(0)

    # Check that the current file is actually patched
    content = misc_path.read_text(encoding="utf-8")
    if "scipy_label" not in content:
        print("[INFO] misc.py does not appear to be patched. Nothing to restore.")
        backup_path.unlink()
        print(f"[INFO] Removed unused backup {backup_path}.")
        sys.exit(0)

    backup_path.replace(misc_path)
    print(f"[OK] Restored {misc_path} from backup.")

    # Quick smoke test: _C import should fail gracefully (expected without CUDA)
    print("\nRunning smoke test...")
    try:
        import importlib
        import sam2.utils.misc as m
        importlib.reload(m)
        assert "scipy_label" not in inspect.getsource(m.get_connected_components)
        print("[OK] Smoke test passed — original get_connected_components restored.")
    except Exception as e:
        print(f"[WARNING] Smoke test inconclusive: {e}")


if __name__ == "__main__":
    main()
