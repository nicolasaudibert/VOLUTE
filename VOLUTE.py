#!/usr/bin/env python3
"""
Launch script for VOLUTE, with model selection
External configuration only, for application UI settings
"""

import os
import sys
import argparse
from pathlib import Path

def find_sam2_installation():
    """Find SAM2 installation directory"""
    try:
        import sam2
        sam2_module_path = Path(sam2.__file__).parent
        sam2_root = sam2_module_path.parent
        print(f"Found SAM2 installation at: {sam2_root}")
        return sam2_root
    except ImportError:
        print("SAM2 module not found. Please install SAM2 first.")
        print("Installation guide: https://github.com/facebookresearch/sam2")
        sys.exit(1)

def setup_environment():
    """Setup environment for SAM2"""
    # Configuration for MPS on Apple Silicon
    os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
    
    # Make sure we can import SAM2
    try:
        import sam2
    except ImportError:
        # Try to add common SAM2 locations to path
        script_dir = Path(__file__).parent
        possible_sam2_paths = [
            script_dir / "sam2",
            script_dir / ".." / "sam2",
            script_dir / ".." / ".." / "sam2",
        ]
        
        for sam2_path in possible_sam2_paths:
            if (sam2_path / "sam2" / "__init__.py").exists():
                sys.path.insert(0, str(sam2_path))
                print(f"Added SAM2 path: {sam2_path}")
                break
        else:
            print("Could not find SAM2 installation. Please install SAM2 or adjust paths.")
            sys.exit(1)

def get_model_paths(model_type, custom_config=None, custom_checkpoint=None):
    """Get config and checkpoint paths based on model type"""
    if custom_config and custom_checkpoint:
        return custom_config, custom_checkpoint
    
    if model_type == 'medsam2':
        # MedSAM2 defaults
        config = custom_config or "configs/medsam2_configs/sam2.1_hiera_t512.yaml"
        checkpoint = custom_checkpoint or "./checkpoints/MedSAM2_latest.pt"
    elif model_type == 'sam2plus':
        config = custom_config or \
            "configs/sam2.1/sam2.1_hiera_b+_predmasks_decoupled_MAME.yaml"
        checkpoint = custom_checkpoint or \
            "./checkpoints/SAM2-Plus/checkpoint_phase123.pt"
    else:  # sam2
        # SAM2 defaults
        config = custom_config or "configs/sam2.1/sam2.1_hiera_l.yaml"
        checkpoint = custom_checkpoint or "./checkpoints/sam2.1_hiera_large.pt"
    
    return config, checkpoint

def _load_gui_module(script_dir, name):
    """Import one volute submodule without importing the package itself.

    The package's __init__ imports the main window, hence torch and SAM2 —
    several seconds the startup chooser should not wait for. The modules loaded
    this way import nothing from the package, so they can stand alone.
    """
    import importlib.util

    path = Path(script_dir) / "volute" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_volute_launcher_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def resolve_model_selection(args, script_dir):
    """Decide which model to start and whether debug output is on.

    Command-line options win: passing any of --model, --config, --checkpoint or
    --task starts that model straight away. Otherwise the startup chooser opens,
    unless it has been turned off, in which case the configured default model is
    used without asking.

    Returns (model, config, checkpoint, task, debug), or None when the person
    dismissed the chooser.
    """
    if any(value is not None for value in
           (args.model, args.config, args.checkpoint, args.task)):
        return (args.model or 'sam2', args.config, args.checkpoint,
                args.task or 'mask', args.debug)

    config_manager = _load_gui_module(script_dir, 'config_manager').ConfigManager()
    model_dialog = _load_gui_module(script_dir, 'model_dialog')
    entry = model_dialog.find_entry(config_manager.get_default_model())
    debug = args.debug

    if config_manager.show_model_dialog():
        localization = _load_gui_module(script_dir, 'localization').LocalizationManager(
            default_language=config_manager.get_default_language())
        dialog = model_dialog.ModelSelectionDialog(localization, config_manager)
        if dialog.exec_() != dialog.Accepted:
            return None
        entry = dialog.chosen_entry
        debug = debug or dialog.debug_enabled

    return (entry['model'], entry.get('config'), entry.get('checkpoint'),
            entry.get('task', 'mask'), debug)


def find_app_icon(script_dir):
    """Return the application icon, or None when none is installed.

    Drop a file named icon.png (or icon.svg, or icon.ico) in
    volute/resources/ to give the application its own icon; several
    icon_<size>.png files are combined into a single multi-resolution icon.
    See that directory's README for the conventions.

    On macOS the .icns of an application bundle takes precedence for the Dock;
    this icon covers the windows, and the Dock when the GUI runs outside one.
    """
    from PyQt5.QtGui import QIcon

    resources = Path(script_dir) / "volute" / "resources"
    sized = sorted(resources.glob("icon_*.png"))
    if sized:
        icon = QIcon()
        for path in sized:
            icon.addFile(str(path))
        return icon
    for name in ("icon.png", "icon.svg", "icon.ico"):
        path = resources / name
        if path.exists():
            return QIcon(str(path))
    return None


def main():
    """Main launcher function"""
    parser = argparse.ArgumentParser(description='Launch VOLUTE')
    parser.add_argument('--debug', action='store_true', 
                       help='Enable debug mode with verbose console output')
    parser.add_argument('--model', type=str, choices=['sam2', 'medsam2', 'sam2plus'],
                       default=None,
                       help='Model type to use; bypasses the startup chooser')
    parser.add_argument('--config', type=str, default=None,
                       help='Path to configuration file (overrides model defaults)')
    parser.add_argument('--checkpoint', type=str, default=None,
                       help='Path to checkpoint file (overrides model defaults)')
    parser.add_argument('--working-dir', type=str, default=None,
                       help='Working directory (default: SAM2 installation directory)')
    parser.add_argument('--task', type=str, choices=['mask', 'point'],
                    default=None,
                    help='SAM2++ tracking task (sam2plus only); bypasses the startup chooser')
    args = parser.parse_args()
    
    print("VOLUTE Launcher")
    print("=" * 50)
    
    # Setup environment
    setup_environment()
    
    # Find SAM2 installation
    sam2_root = find_sam2_installation()
    
    # Determine working directory - crucial for Hydra
    if args.working_dir:
        working_dir = Path(args.working_dir).resolve()
    else:
        working_dir = sam2_root
    
    # Store original directory
    original_cwd = Path.cwd()
    print(f"Original working directory: {original_cwd}")
    print(f"Working directory for SAM2: {working_dir}")
    
    if not working_dir.exists():
        print(f"Error: Working directory does not exist: {working_dir}")
        sys.exit(1)
    
    # IMPORTANT: Change to SAM2 working directory BEFORE importing the GUI
    # This ensures that relative paths work correctly
    os.chdir(working_dir)
    print(f"Changed working directory to: {Path.cwd()}")
    
    try:
        # Import PyQt5 first
        from PyQt5.QtWidgets import QApplication

        script_dir = Path(__file__).parent
        gui_module_path = script_dir / "volute"
        if not gui_module_path.exists():
            print("Error: Could not import VOLUTE modules.")
            print(f"Make sure the volute directory exists at: {gui_module_path}")
            sys.exit(1)
        sys.path.insert(0, str(script_dir))

        app = QApplication(sys.argv)
        app.setApplicationName("VOLUTE")
        # Name shown by the window manager and the taskbar: without these, Linux
        # and Windows label the application after the launcher script
        app.setApplicationDisplayName("VOLUTE")
        app.setDesktopFileName("VOLUTE")

        icon = find_app_icon(script_dir)
        if icon is not None:
            app.setWindowIcon(icon)

        # Model selection comes before importing the GUI package, so the chooser
        # appears immediately rather than after torch and SAM2 have loaded
        selection = resolve_model_selection(args, script_dir)
        if selection is None:
            return 0
        model_type, model_config, model_checkpoint, task, debug_mode = selection

        config_path, checkpoint_path = get_model_paths(
            model_type,
            model_config,
            model_checkpoint
        )

        from volute import SAM2VideoSegmentationApp, __version__ as APP_VERSION
        app.setApplicationVersion(APP_VERSION)

        print(f"Model type: {model_type.upper()}")
        print(f"Config path: {config_path}")
        print(f"Checkpoint path: {checkpoint_path}")
        print(f"Debug mode: {debug_mode}")
        print("=" * 50)

        # Create main window with explicit paths
        window = SAM2VideoSegmentationApp(
            debug_mode=debug_mode,
            config_path=config_path,
            checkpoint_path=checkpoint_path,
            sam2plus_task=task,
        )
        
        # Start event loop
        return app.exec_()
        
    except Exception as e:
        print(f"Error starting application: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())