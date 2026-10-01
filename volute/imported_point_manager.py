"""
Imported Point Manager
Named points imported from a SAM2++ point-mode "Export tracked points" file,
displayed and analyzed against mask-mode objects.

Unlike ReferencePointManager, imported points have no interpolation or
extrapolation: they come from a dense per-frame propagation, so a frame with
no explicit entry means tracking failure, not a gap to fill in. Coordinates
are stored in pixel space (not normalized 0-1), since they may originate from
a session with different image dimensions than the current one.
"""

from typing import Dict, List, Optional, Tuple
from PyQt5.QtGui import QColor


class ImportedPointManager:
    """
    Stores imported points as {name: {frame_idx: (x_px, y_px)}}.

    No interpolation: get_coords() returns None on any frame without an
    explicit entry for that name, full stop.
    """

    def __init__(self):
        self.imported_points: Dict[str, Dict[int, Tuple[float, float]]] = {}
        self.current_imported_point_name: Optional[str] = None
        # Names currently selected in the Imported Points list.
        # Single-selection model for now (imported points are typically set
        # once at import time and rarely edited individually afterward);
        # kept as a set rather than a scalar so multi-selection can be added
        # later without changing the storage shape.
        self.selected_imported_point_names: set = set()

        # Distinct from ReferencePointManager.default_color (gold) and
        # ObjectManager.tracked_point_color (amber) so all three point kinds
        # stay visually discernible when displayed together.
        self.default_color = QColor(0, 180, 255)  # sky blue
        self.default_marker = 'X'
        self.default_marker_size = 10

        self.imported_point_colors: Dict[str, QColor] = {}
        self.imported_point_markers: Dict[str, Dict[str, int]] = {}  # {'style': str, 'size': int}

        # Global visibility toggle, mirroring ObjectManager.show_hulls / show_contours
        self.show_imported_points: bool = True

    # ------------------------------------------------------------------
    # Main Operations
    # ------------------------------------------------------------------

    def add_point(self, name: str, frame_idx: int, x_px: float, y_px: float):
        is_new_name = name not in self.imported_points
        self.imported_points.setdefault(name, {})[frame_idx] = (x_px, y_px)
        if is_new_name:
            self.imported_point_colors.setdefault(name, QColor(self.default_color))
            self.imported_point_markers.setdefault(
                name, {'style': self.default_marker, 'size': self.default_marker_size}
            )

    def remove_point(self, name: str, frame_idx: int):
        frames = self.imported_points.get(name)
        if frames is not None:
            frames.pop(frame_idx, None)
            if not frames:
                self.remove_all_points(name)

    def remove_all_points(self, name: str):
        self.imported_points.pop(name, None)
        self.imported_point_colors.pop(name, None)
        self.imported_point_markers.pop(name, None)
        self.selected_imported_point_names.discard(name)
        if self.current_imported_point_name == name:
            self.current_imported_point_name = next(iter(self.imported_points), None)

    def rename_point(self, old_name: str, new_name: str):
        if old_name in self.imported_points and new_name not in self.imported_points:
            self.imported_points[new_name] = self.imported_points.pop(old_name)
            if old_name in self.imported_point_colors:
                self.imported_point_colors[new_name] = self.imported_point_colors.pop(old_name)
            if old_name in self.imported_point_markers:
                self.imported_point_markers[new_name] = self.imported_point_markers.pop(old_name)
            if old_name in self.selected_imported_point_names:
                self.selected_imported_point_names.discard(old_name)
                self.selected_imported_point_names.add(new_name)
            if self.current_imported_point_name == old_name:
                self.current_imported_point_name = new_name

    def get_names(self) -> List[str]:
        return list(self.imported_points.keys())

    def get_frames(self, name: str) -> Dict[int, Tuple[float, float]]:
        return self.imported_points.get(name, {})

    def has_point(self, name: str, frame_idx: int) -> bool:
        return frame_idx in self.imported_points.get(name, {})

    def clear(self):
        self.imported_points.clear()
        self.imported_point_colors.clear()
        self.imported_point_markers.clear()
        self.selected_imported_point_names.clear()
        self.current_imported_point_name = None

    # ------------------------------------------------------------------
    # Coordinate lookup (no interpolation)
    # ------------------------------------------------------------------

    def get_coords(self, name: str, frame_idx: int) -> Optional[Tuple[float, float]]:
        """Return (x_px, y_px) for an explicitly-imported frame, or None otherwise."""
        return self.imported_points.get(name, {}).get(frame_idx)

    def get_all_coords(self, name: str) -> Dict[int, Tuple[float, float]]:
        """Return all explicitly-defined (frame_idx -> (x_px, y_px)) entries for a name."""
        return dict(self.imported_points.get(name, {}))

    # ------------------------------------------------------------------
    # Import-time validation helpers
    # ------------------------------------------------------------------

    def frame_count(self, name: str) -> int:
        """Number of explicitly-defined frames for a name."""
        return len(self.imported_points.get(name, {}))

    def out_of_bounds_count(self, name: str, image_width: int, image_height: int) -> int:
        """
        Count how many of this name's stored points fall outside
        [0, image_width) x [0, image_height) — used by the import dialog to
        flag a likely image-dimension mismatch with the source session.
        """
        return sum(
            1 for x_px, y_px in self.imported_points.get(name, {}).values()
            if not (0 <= x_px < image_width and 0 <= y_px < image_height)
        )
