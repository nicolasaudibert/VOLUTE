"""
Reference Point Manager
Named reference points with per-frame coordinates and interpolation.
"""

from typing import Dict, List, Optional, Tuple
from PyQt5.QtGui import QColor


class ReferencePointManager:
    """
    Stores named reference points as {name: {frame_idx: (norm_x, norm_y)}}.
    Coordinates are normalized (0-1), same convention as ObjectManager.

    Interpolation rules (per name):
      - 1 defined frame  → constant across all frames
      - 2 defined frames → linear interpolation / extrapolation
      - >2 defined frames → cubic spline (scipy); piecewise-linear fallback
    Extrapolation (n > 1) triggers a UI warning before export.
    """

    def __init__(self):
        self.reference_points: Dict[str, Dict[int, Tuple[float, float]]] = {}
        self.current_ref_point_name: Optional[str] = None
        # Names currently selected in the Ref. Points list (multi-selection support)
        self.selected_ref_point_names: set = set()

        # Global advanced-mode toggle: False = simple mode (one constant position
        # per name, across all frames); True = current multi-frame/interpolated behavior.
        self.advanced_mode: bool = False

        # Fallback values used to seed a new name's entry in the per-name dicts below.
        # Kept as constants (rather than dropped) so future defaults can be tweaked
        # in one place without touching add_point().
        self.default_color = QColor(255, 200, 0)  # gold
        self.default_marker = '+'
        self.default_marker_size = 10
        self.default_extrapolation_policy = 'extrapolate'
        self.default_interpolation_mode = 'cubic'

        # Per-name color/marker, mirroring ObjectManager.object_colors / object_markers.
        # Kept as separate dicts (rather than folded into `reference_points`) so that
        # display/UI code can evolve independently between the Objects/Points tab and
        # the Ref. Points tab if their behaviors diverge later.
        self.ref_point_colors: Dict[str, QColor] = {}
        self.ref_point_markers: Dict[str, Dict[str, int]] = {}  # {'style': str, 'size': int}
        # Per-name advanced-mode settings (only meaningful when >=2 frames are defined)
        self.ref_point_extrapolation_policy: Dict[str, str] = {}  # 'extrapolate' | 'undefined' | 'clamp'
        self.ref_point_interpolation_mode: Dict[str, str] = {}    # 'cubic' | 'linear'

    # ------------------------------------------------------------------
    # Main Operations
    # ------------------------------------------------------------------

    def add_point(self, name: str, frame_idx: int, norm_x: float, norm_y: float):
        is_new_name = name not in self.reference_points
        self.reference_points.setdefault(name, {})[frame_idx] = (norm_x, norm_y)
        if is_new_name:
            self.ref_point_colors.setdefault(name, QColor(self.default_color))
            self.ref_point_markers.setdefault(
                name, {'style': self.default_marker, 'size': self.default_marker_size}
            )
            self.ref_point_extrapolation_policy.setdefault(name, self.default_extrapolation_policy)
            self.ref_point_interpolation_mode.setdefault(name, self.default_interpolation_mode)

    def remove_point(self, name: str, frame_idx: int):
        frames = self.reference_points.get(name)
        if frames is not None:
            frames.pop(frame_idx, None)
            if not frames:
                del self.reference_points[name]
                self.ref_point_colors.pop(name, None)
                self.ref_point_markers.pop(name, None)
                self.ref_point_extrapolation_policy.pop(name, None)
                self.ref_point_interpolation_mode.pop(name, None)
                self.selected_ref_point_names.discard(name)
                if self.current_ref_point_name == name:
                    self.current_ref_point_name = next(iter(self.reference_points), None)

    def remove_all_points(self, name: str):
        self.reference_points.pop(name, None)
        self.ref_point_colors.pop(name, None)
        self.ref_point_markers.pop(name, None)
        self.ref_point_extrapolation_policy.pop(name, None)
        self.ref_point_interpolation_mode.pop(name, None)
        self.selected_ref_point_names.discard(name)
        if self.current_ref_point_name == name:
            self.current_ref_point_name = next(iter(self.reference_points), None)

    def rename_point(self, old_name: str, new_name: str):
        if old_name in self.reference_points and new_name not in self.reference_points:
            self.reference_points[new_name] = self.reference_points.pop(old_name)
            if old_name in self.ref_point_colors:
                self.ref_point_colors[new_name] = self.ref_point_colors.pop(old_name)
            if old_name in self.ref_point_markers:
                self.ref_point_markers[new_name] = self.ref_point_markers.pop(old_name)
            if old_name in self.ref_point_extrapolation_policy:
                self.ref_point_extrapolation_policy[new_name] = self.ref_point_extrapolation_policy.pop(old_name)
            if old_name in self.ref_point_interpolation_mode:
                self.ref_point_interpolation_mode[new_name] = self.ref_point_interpolation_mode.pop(old_name)
            if old_name in self.selected_ref_point_names:
                self.selected_ref_point_names.discard(old_name)
                self.selected_ref_point_names.add(new_name)
            if self.current_ref_point_name == old_name:
                self.current_ref_point_name = new_name

    def get_names(self) -> List[str]:
        return list(self.reference_points.keys())

    def get_frames(self, name: str) -> Dict[int, Tuple[float, float]]:
        return self.reference_points.get(name, {})

    def has_point(self, name: str, frame_idx: int) -> bool:
        return frame_idx in self.reference_points.get(name, {})

    def clear(self):
        self.reference_points.clear()
        self.ref_point_colors.clear()
        self.ref_point_markers.clear()
        self.ref_point_extrapolation_policy.clear()
        self.ref_point_interpolation_mode.clear()
        self.selected_ref_point_names.clear()
        self.current_ref_point_name = None

    # ------------------------------------------------------------------
    # Interpolation
    # ------------------------------------------------------------------

    def get_interpolated_coords(
        self, name: str, frame_idx: int
    ) -> Optional[Tuple[float, float]]:
        """
        Return (norm_x, norm_y) for frame_idx using interpolation/extrapolation.
        Returns None if name is unknown, has no defined frames, or the
        'undefined' extrapolation policy applies to this out-of-range frame.
        """
        frames = self.reference_points.get(name)
        if not frames:
            return None
        sorted_f = sorted(frames.keys())
        n = len(sorted_f)

        if n == 1:
            return frames[sorted_f[0]]

        first_f, last_f = sorted_f[0], sorted_f[-1]
        out_of_range = frame_idx < first_f or frame_idx > last_f

        if out_of_range:
            policy = self.ref_point_extrapolation_policy.get(name, self.default_extrapolation_policy)
            if policy == 'undefined':
                return None
            if policy == 'clamp':
                boundary_f = first_f if frame_idx < first_f else last_f
                return frames[boundary_f]
            # policy == 'extrapolate' falls through to the interpolation below

        xs = [frames[f][0] for f in sorted_f]
        ys = [frames[f][1] for f in sorted_f]

        if n == 2:
            f0, f1 = sorted_f
            t = (frame_idx - f0) / (f1 - f0)
            return (xs[0] + t * (xs[1] - xs[0]), ys[0] + t * (ys[1] - ys[0]))

        mode = self.ref_point_interpolation_mode.get(name, self.default_interpolation_mode)
        if mode == 'linear':
            import bisect
            i = max(0, min(bisect.bisect_right(sorted_f, frame_idx) - 1, n - 2))
            f0, f1 = sorted_f[i], sorted_f[i + 1]
            t = (frame_idx - f0) / (f1 - f0)
            return (xs[i] + t * (xs[i + 1] - xs[i]), ys[i] + t * (ys[i + 1] - ys[i]))

        # Cubic spline (n > 2, mode == 'cubic')
        try:
            from scipy.interpolate import CubicSpline
            cs_x = CubicSpline(sorted_f, xs)
            cs_y = CubicSpline(sorted_f, ys)
            return (float(cs_x(frame_idx)), float(cs_y(frame_idx)))
        except ImportError:
            # Piecewise-linear fallback when scipy unavailable
            import bisect
            i = max(0, min(bisect.bisect_right(sorted_f, frame_idx) - 1, n - 2))
            f0, f1 = sorted_f[i], sorted_f[i + 1]
            t = (frame_idx - f0) / (f1 - f0)
            return (xs[i] + t * (xs[i + 1] - xs[i]), ys[i] + t * (ys[i + 1] - ys[i]))

    def get_all_interpolated(
        self, name: str, total_frames: int
    ) -> Dict[int, Tuple[float, float]]:
        """Return interpolated coords for every frame in [0, total_frames)."""
        result = {}
        for f in range(total_frames):
            c = self.get_interpolated_coords(name, f)
            if c is not None:
                result[f] = c
        return result

    def check_extrapolation(self, name: str, total_frames: int) -> Tuple[bool, bool]:
        """
        Return (extrap_before_first, extrap_after_last).
        Only meaningful when >= 2 frames are defined and the 'extrapolate' policy
        is active for this name (the default); 'undefined'/'clamp' policies never
        extrapolate, so both values are always False for them.
        """
        frames = self.reference_points.get(name)
        if not frames or len(frames) < 2:
            return False, False
        policy = self.ref_point_extrapolation_policy.get(name, self.default_extrapolation_policy)
        if policy != 'extrapolate':
            return False, False
        s = sorted(frames.keys())
        return s[0] > 0, s[-1] < total_frames - 1

    def any_extrapolation_needed(self, total_frames: int) -> List[str]:
        """Return names of ref points that require extrapolation."""
        return [
            name for name in self.reference_points
            if any(self.check_extrapolation(name, total_frames))
        ]

    def get_adjacent_defined_frame(self, name: str, current_frame: int, forward: bool) -> Optional[int]:
        """
        Return the nearest explicitly-defined frame after (forward=True) or before
        (forward=False) current_frame for this name, or None if there isn't one.
        """
        frames = self.reference_points.get(name)
        if not frames:
            return None
        candidates = [f for f in frames if (f > current_frame if forward else f < current_frame)]
        if not candidates:
            return None
        return min(candidates) if forward else max(candidates)

    def names_with_multi_frame_data(self) -> List[str]:
        """Return names that have more than one explicitly defined frame."""
        return [name for name, frames in self.reference_points.items() if len(frames) > 1]
