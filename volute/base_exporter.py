"""
Base Exporter — shared base class used by all exporter modules.
Extracted here to avoid circular imports between exporters.py and
reference_point_exporter.py.
"""

import os


class BaseExporter:
    """Base class for all exporters with filename management"""

    def __init__(self, main_window=None, debug_mode=False):
        self.main_window = main_window
        self.debug_mode = debug_mode

    def ensure_directory(self, path):
        """Ensure directory exists"""
        directory = os.path.dirname(path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            if self.debug_mode:
                print(f"Created directory: {directory}")

    def get_original_filename(self, frame_idx):
        """Get original filename for frame index"""
        try:
            if (self.main_window and
                    hasattr(self.main_window, 'sam2_backend') and
                    hasattr(self.main_window.sam2_backend, 'filename_manager')):
                original_name = self.main_window.sam2_backend.filename_manager.get_original_filename(frame_idx)
                if original_name:
                    return original_name

            if (self.main_window and
                    hasattr(self.main_window, 'image_manager') and
                    hasattr(self.main_window.image_manager, 'image_paths') and
                    frame_idx < len(self.main_window.image_manager.image_paths)):
                image_path = self.main_window.image_manager.image_paths[frame_idx]
                return os.path.basename(image_path)

            return f"frame_{frame_idx:05d}.jpg"

        except Exception as e:
            if self.debug_mode:
                print(f"Error getting original filename for frame {frame_idx}: {e}")
            return f"frame_{frame_idx:05d}.jpg"

    def create_export_filename(self, frame_idx, suffix, extension):
        """Create export filename based on original filename"""
        try:
            original_filename = self.get_original_filename(frame_idx)
            name_without_ext = os.path.splitext(original_filename)[0]
            return f"{name_without_ext}_{suffix}.{extension}"
        except Exception:
            return f"frame_{frame_idx:05d}_{suffix}.{extension}"
