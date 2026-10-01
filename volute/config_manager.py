"""
Configuration Manager
Handles loading and validation of external configuration files for VOLUTE
"""

import copy
import os
import re
import yaml
from pathlib import Path

class ConfigManager:
    """
    Manages application configuration from external YAML files
    
    Features:
    - Automatic config file discovery in multiple locations
    - Merging with default values for missing keys
    - Validation of critical paths and settings
    - Dynamic configuration access with dot notation
    - Configuration saving and reloading
    """
    
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
        self.config = {}
        self.config_file_path = None
        
        # Default configuration (fallback values)
        # Note: SAM2 paths are handled in main_window.py for Hydra compatibility
        self.default_config = {
            'ui': {
                'default_language': 'en',
                'progress_details_font_size': 12,
                'progress_animation_pacing': 'file',
                'import_confirmation_default': 'yes',
                'native_file_dialogs': True,
                'show_model_dialog': True,
                'show_image_filename': True
            },
            'models': {
                'default_model': 'sam2_default'
            },
            'export': {
                'coordinates_format': 'json',
                'centroids_format': 'excel',
                'image_quality': 95
            },
            'debug': {
                'enabled': False,
                'show_filename_mappings': False,
                'show_mask_sync_details': False
            },
            'performance': {
                'image_cache_size': 32,   # max frames in LRU cache (0 = unlimited)
            },
            'gimp': {
                'executable_path': '/Applications/GIMP.app/Contents/MacOS/gimp',   # manual override; None = auto-detect on PATH
            },
        }
        
        self._load_config()
    
    def _load_config(self):
        """
        Load configuration from file or use defaults
        
        Searches for config files in multiple locations:
        1. volute_config.yaml (current directory)
        2. config/volute_config.yaml (config subdirectory)
        3. ~/.volute/config.yaml (user home directory)
        4. tools/volute_config.yaml (tools directory)
        """
        # Look for config file in multiple locations
        config_paths = [
            'volute_config.yaml',  # Current directory
            'config/volute_config.yaml',  # Config subdirectory
            os.path.expanduser('~/.volute/config.yaml'),  # User home
            'tools/volute_config.yaml'  # Tools directory
        ]
        
        for config_path in config_paths:
            if os.path.exists(config_path):
                try:
                    self.config_file_path = config_path
                    self._load_yaml_config(config_path)
                    if self.debug_mode:
                        print(f"Loaded configuration from: {config_path}")
                    return
                except Exception as e:
                    if self.debug_mode:
                        print(f"Error loading config from {config_path}: {e}")
                    continue
        
        # No config file found, use defaults
        self.config = copy.deepcopy(self.default_config)
        if self.debug_mode:
            print("No configuration file found, using default settings")
    
    def _load_yaml_config(self, config_path):
        """
        Load configuration from YAML file and merge with defaults
        
        Args:
            config_path: Path to the YAML configuration file
        """
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                loaded_config = yaml.safe_load(f)
            
            # Merge with defaults (preserves defaults for missing keys)
            self.config = self._merge_configs(self.default_config, loaded_config)
            
            # Validate critical paths and settings
            self._validate_config()
            
        except yaml.YAMLError as e:
            if self.debug_mode:
                print(f"YAML parsing error: {e}")
            raise
        except Exception as e:
            if self.debug_mode:
                print(f"Config loading error: {e}")
            raise
    
    def _merge_configs(self, default, loaded):
        """
        Recursively merge loaded config with defaults
        
        Args:
            default: Default configuration dictionary
            loaded: Loaded configuration dictionary
            
        Returns:
            Merged configuration dictionary
        """
        merged = default.copy()
        
        for key, value in loaded.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                # Recursively merge nested dictionaries
                merged[key] = self._merge_configs(merged[key], value)
            else:
                # Override or add new value
                merged[key] = value
        
        return merged
    
    def _validate_config(self):
        """
        Validate critical configuration values
        
        Performs validation on:
        - UI setting values
        - Export format values
        Note: SAM2 paths are handled in main_window.py
        """
        # Validate UI settings
        ui_config = self.config.get('ui', {})
        if ui_config.get('import_confirmation_default', 'yes').lower() not in ['yes', 'no']:
            if self.debug_mode:
                print("Warning: Invalid import_confirmation_default value, using 'yes'")
            self.config['ui']['import_confirmation_default'] = 'yes'
        
        # Validate export formats
        export_config = self.config.get('export', {})
        valid_coord_formats = ['json', 'csv', 'pickle']
        valid_centroid_formats = ['excel', 'csv', 'json']
        
        if export_config.get('coordinates_format') not in valid_coord_formats:
            if self.debug_mode:
                print(f"Warning: Invalid coordinates format, using 'json'")
            self.config['export']['coordinates_format'] = 'json'
        
        if export_config.get('centroids_format') not in valid_centroid_formats:
            if self.debug_mode:
                print(f"Warning: Invalid centroids format, using 'excel'")
            self.config['export']['centroids_format'] = 'excel'
    
    def get(self, key_path, default=None):
        """
        Get configuration value using dot notation
        
        Args:
            key_path: Dot-separated path to the configuration value
            default: Default value if key not found
            
        Returns:
            Configuration value or default
            
        Examples:
            config.get('sam2.config_path')
            config.get('ui.progress_details_font_size')
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def set(self, key_path, value):
        """
        Set configuration value using dot notation
        
        Args:
            key_path: Dot-separated path to the configuration value
            value: Value to set
            
        Examples:
            config.set('ui.default_language', 'fr')
            config.set('debug.enabled', True)
        """
        keys = key_path.split('.')
        config_dict = self.config
        
        # Navigate to the parent dictionary
        for key in keys[:-1]:
            if key not in config_dict:
                config_dict[key] = {}
            config_dict = config_dict[key]
        
        # Set the final value
        config_dict[keys[-1]] = value
    
    def save_config(self, config_path=None):
        """
        Save current configuration to file

        When the file already exists its values are rewritten in place, so the
        comments documenting each setting survive; a key the file does not carry
        yet is appended to its section. A plain dump is used only when there is
        no file to update.

        Args:
            config_path: Optional path to save to, uses current path if None

        Returns:
            True if successful, False otherwise
        """
        if config_path is None:
            config_path = self.config_file_path or 'volute_config.yaml'

        try:
            config_dir = os.path.dirname(config_path)
            if config_dir and not os.path.exists(config_dir):
                os.makedirs(config_dir)

            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    lines = f.read().split('\n')
                text = '\n'.join(self._rewrite_yaml_values(lines))
                with open(config_path, 'w', encoding='utf-8') as f:
                    f.write(text)
            else:
                with open(config_path, 'w', encoding='utf-8') as f:
                    yaml.dump(self.config, f, default_flow_style=False, indent=2)

            self.config_file_path = config_path
            if self.debug_mode:
                print(f"Configuration saved to: {config_path}")

            return True

        except Exception as e:
            if self.debug_mode:
                print(f"Error saving configuration: {e}")
            return False

    @staticmethod
    def _format_yaml_scalar(value):
        """Render a scalar the way the configuration file writes it."""
        if isinstance(value, bool):
            return 'true' if value else 'false'
        if isinstance(value, (int, float)) or value is None:
            return 'null' if value is None else str(value)
        return '"{}"'.format(str(value).replace('"', '\\"'))

    def _rewrite_yaml_values(self, lines):
        """Return the configuration file's lines with current values substituted.

        Blank lines, comments and anything that is not a `key: value` pair are
        copied through untouched, so the file keeps its structure and its
        documentation. Keys held in memory but absent from the file are appended
        to the end of the section they belong to.
        """
        missing = self._pending_keys()
        out, stack = [], []   # stack of (indent, key) for the open sections

        def close_sections(indent):
            """Emit the keys missing from every section shallower than `indent`."""
            while stack and stack[-1][0] >= indent:
                section = '.'.join(k for _, k in stack)
                child_indent = stack[-1][0] + 2
                for dotted in list(missing):
                    parent, _, key = dotted.rpartition('.')
                    if parent == section:
                        out.append(f"{' ' * child_indent}{key}: "
                                   f"{self._format_yaml_scalar(self.get(dotted))}")
                        missing.remove(dotted)
                stack.pop()

        for line in lines:
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            match = re.match(r'^([A-Za-z0-9_]+):(.*)$', stripped)
            if not stripped or stripped.startswith('#') or not match:
                out.append(line)
                continue

            key, rest = match.group(1), match.group(2)
            value_part, comment = re.match(r'^\s*(.*?)(\s+#.*)?$', rest).groups()
            close_sections(indent)
            dotted = '.'.join([k for _, k in stack] + [key])

            if value_part == '':
                stack.append((indent, key))
                out.append(line)
                continue

            if dotted in missing:
                missing.remove(dotted)
            sentinel = object()
            current = self.get(dotted, sentinel)
            if current is sentinel or isinstance(current, (dict, list)):
                out.append(line)
            else:
                out.append(f"{' ' * indent}{key}: "
                           f"{self._format_yaml_scalar(current)}{comment or ''}")

        close_sections(0)
        return out

    def _pending_keys(self):
        """Every scalar setting held in memory, as dotted paths."""
        keys = []

        def walk(node, prefix):
            for key, value in node.items():
                path = f"{prefix}.{key}" if prefix else key
                if isinstance(value, dict):
                    walk(value, path)
                else:
                    keys.append(path)

        walk(self.config, '')
        return keys

    def restore_defaults(self):
        """Reset every setting to the value the application ships with."""
        self.config = copy.deepcopy(self.default_config)

    def create_default_config_file(self, config_path='volute_config.yaml'):
        """
        Create a default configuration file
        
        Args:
            config_path: Path where to create the config file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.default_config, f, default_flow_style=False, indent=2)
            
            if self.debug_mode:
                print(f"Default configuration file created: {config_path}")
            
            return True
            
        except Exception as e:
            if self.debug_mode:
                print(f"Error creating default config file: {e}")
            return False
    
    # Convenience methods for commonly accessed configuration values
    # Note: SAM2 paths are handled in main_window.py for Hydra compatibility
    
    def get_default_language(self):
        """Get default UI language"""
        return self.get('ui.default_language', 'en')
    
    def get_progress_font_size(self):
        """Get progress dialog details font size"""
        return self.get('ui.progress_details_font_size', 12)
    
    def get_progress_animation_pacing(self):
        """How the progress animation advances: 'file' plays it at the frame
        durations stored in the file, 'progress' one frame per progress update
        of the operations that report steps. Anything else reads as 'file'."""
        value = self.get('ui.progress_animation_pacing', 'file')
        return value if value in ('file', 'progress') else 'file'

    def use_native_file_dialogs(self):
        """Whether file dialogs are drawn by the system (macOS/Windows) or by Qt.
        The system panel keeps the platform look but, on macOS, is drawn by another
        process that ignores the application language; Qt's own follows it."""
        return bool(self.get('ui.native_file_dialogs', True))

    def show_image_filename(self):
        """Whether the original filename is shown under the frame indicator"""
        return bool(self.get('ui.show_image_filename', True))

    def show_model_dialog(self):
        """Whether the model chooser is shown at startup"""
        return bool(self.get('ui.show_model_dialog', True))

    def get_default_model(self):
        """Key of the model entry the chooser preselects, and the one used
        directly when the chooser is disabled (see model_catalog)"""
        return self.get('models.default_model', 'sam2_default')

    def get_import_confirmation_default(self):
        """Get default response for import confirmation dialogs (True for Yes, False for No)"""
        return self.get('ui.import_confirmation_default', 'yes').lower() == 'yes'
    
    def get_coordinates_format(self):
        """Get default coordinates export format"""
        return self.get('export.coordinates_format', 'json')
    
    def get_centroids_format(self):
        """Get default centroids export format"""
        return self.get('export.centroids_format', 'excel')
    
    def get_image_quality(self):
        """Get default image export quality (1-100)"""
        return self.get('export.image_quality', 95)
    
    def is_debug_enabled(self):
        """Check if debug mode is enabled in config"""
        return self.get('debug.enabled', False)
    
    def get_image_cache_size(self) -> int:
        """Get LRU frame cache size for SAM2 lazy loading (0 = unlimited)"""
        return int(self.get('performance.image_cache_size', 32))
    
    def get_sam2plus_task(self) -> str:
        """Get SAM2++ tracking task ('mask' | 'point')"""
        return self.get('models.sam2plus.task', 'mask')
    
    def get_gimp_path(self):
        """Get manual override path for the GIMP executable (None = auto-detect on PATH)"""
        return self.get('gimp.executable_path', None)
    
    def show_filename_mappings(self):
        """Check if filename mapping debug is enabled"""
        return self.get('debug.show_filename_mappings', False)
    
    def show_mask_sync_details(self):
        """Check if mask sync debug is enabled"""
        return self.get('debug.show_mask_sync_details', False)
    
    def print_config(self):
        """Print current configuration (debug utility)"""
        if self.debug_mode:
            print("=== CURRENT CONFIGURATION ===")
            print(yaml.dump(self.config, default_flow_style=False, indent=2))
            print("=== END CONFIGURATION ===")
    
    def get_config_info(self):
        """
        Get information about configuration source
        
        Returns:
            Dictionary with configuration information
        """
        return {
            'config_file_path': self.config_file_path,
            'using_defaults': self.config_file_path is None,
            'config_exists': self.config_file_path and os.path.exists(self.config_file_path)
        }