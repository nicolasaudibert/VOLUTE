"""
Object Manager
Manages objects, their points, masks, and properties in the segmentation tool
"""

import numpy as np
import random
from collections import defaultdict
from PyQt5.QtGui import QColor

# Predefined palette of visually distinct mask colors (RGBA with 50% opacity)
def _default_points():
    """Factory for per-frame point storage — defined at module level for pickle compatibility"""
    return {'positive': [], 'negative': []}

MASK_COLOR_PALETTE = [
    QColor(31,  119, 180, 128),  # blue
    QColor(255, 127,  14, 128),  # orange
    QColor( 44, 160,  44, 128),  # green
    QColor(214,  39,  40, 128),  # red
    QColor(148, 103, 189, 128),  # purple
    QColor(140,  86,  75, 128),  # brown
    QColor(227, 119, 194, 128),  # pink
    QColor(188, 189,  34, 128),  # olive
    QColor( 23, 190, 207, 128),  # cyan
    QColor(255, 187, 120, 128),  # light orange
]

class ObjectManager:
    """Manages objects, their points, masks, and properties"""

    def __init__(self, localization_manager, debug_mode=False):
        self.localization = localization_manager
        self.debug_mode = debug_mode

        # Current selection
        self.current_object_id = 1
        self.selected_object_ids = {1}   # set of obj_ids currently selected in the list

        # Object data structures
        self.object_points = {1: defaultdict(_default_points)}
        self.object_masks = {1: {}}
        self.object_colors = {1: {
            'positive': QColor(0, 255, 0),
            'negative': QColor(255, 0, 0),
            'mask': self._get_palette_color()
        }}
        self.object_markers = {1: {'style': 'o', 'size': 5}}
        self.object_names = {1: self.localization.get_text("object") + " 1"}
        self.object_show_points = {1: True}
        self.object_centroids = {}
        self.object_hulls = {}            # {obj_id: {frame_idx: np.ndarray (N, 2) normalized}}
        self.object_hull_coverage = {}    # {obj_id: {frame_idx: float}}
        self.object_contours = {}         # {obj_id: {frame_idx: np.ndarray (N, 2) normalized}}
        self.object_contour_coverage = {} # {obj_id: {frame_idx: float}}
        # Bounding-box prompts (mask mode only): one optional box per
        # (object, frame), normalized like object_points and ordered so that
        # x0 < x1 and y0 < y1. Sent to SAM2 alongside the frame's points.
        self.object_boxes = {}            # {obj_id: {frame_idx: (x0, y0, x1, y1)}}
        # Strict confinement of predicted masks to the box. Applied before the
        # mask is stored, so it also constrains centroid, hull and contour —
        # and cannot be undone by turning the setting back off.
        self.strict_box_clipping = False
        self.box_clipping_mode = 'box_frames'   # or 'reference_box'
        # Point tracking (SAM2++ point mode)
        self.object_tracked_points = {}   # {obj_id: {frame_idx: (x_px, y_px)}}
        self.show_tracked_points   = True
        self.tracked_point_color   = QColor(255, 200, 0)   # amber — distinct from ref points
        self.tracked_point_size    = 8
        self.tracked_point_style   = 'P'   # matplotlib marker; global across all objects
        self.point_mode = False   # set once at startup by main_window

        # Mask-based initialization (mask mode only): frames whose mask conditioning
        # came from an imported mask and has not yet been refined by a point-based
        # predict call. Used to resend the mask via add_mask immediately before the
        # point call, which would otherwise silently discard it.
        self.mask_imported_frames = {}    # {obj_id: set(frame_idx)}

        # Durable record of which stored masks originated from an import, kept
        # after mask_imported_frames has been cleared by a point refinement:
        # these masks are the only ones that cannot be regenerated from prompts.
        self.mask_import_origin = {}      # {obj_id: set(frame_idx)}

        # Frames where an already-tracked mask was corrected by a fresh point-based
        # prediction: drives the "Re-propagate from this frame…" button's
        # enabled state, cleared once that frame has been re-propagated from.
        self.object_corrected_frames = {}  # {obj_id: set(frame_idx)}

        # Global display settings
        self.show_centroids = False
        self.centroid_color = QColor(255, 255, 255)  # White by default
        self.centroid_size = 10

        # Convex hull display settings
        self.show_hulls = False
        self.hull_line_width = 2
        self.hull_outline_color = QColor(255, 255, 255)  # White outline by default
        self.hull_outline_visible = False
        self.hull_smoothing = 0.0  # 0.0 = raw hull, 1.0 = maximum smoothing

        # Outer contour display settings
        self.show_contours = False
        self.contour_line_width = 2
        self.contour_outline_color = QColor(255, 255, 255)  # White outline by default
        self.contour_outline_visible = False
        self.contour_smoothing = 0.0  # 0.0 = raw contour, 1.0 = maximum smoothing

    def _get_palette_color(self):
        """Return the palette color most distinct from all currently used mask colors"""
        used = [self.object_colors[oid]['mask'] for oid in getattr(self, 'object_colors', {})]
        if not used:
            return QColor(MASK_COLOR_PALETTE[0])
        def min_dist(candidate):
            return min(
                (candidate.red()   - c.red())   ** 2 +
                (candidate.green() - c.green()) ** 2 +
                (candidate.blue()  - c.blue())  ** 2
                for c in used
            )
        return QColor(max(MASK_COLOR_PALETTE, key=min_dist))

    def set_point_mode(self, point_mode):
        """Set point tracking mode flag and rename the default object accordingly.
        Called once at startup, before any user renaming."""
        self.point_mode = point_mode
        word = self.localization.get_text("point" if point_mode else "object")
        for obj_id in list(self.object_names.keys()):
            self.object_names[obj_id] = f"{word} {obj_id}"

    # ------------------------------------------------------------------
    # Convex hull computation
    # ------------------------------------------------------------------

    def compute_hull(self, mask):
        """
        Compute convex hull vertices from a binary mask.

        Returns normalized (N, 2) array of (x_norm, y_norm) vertices, or None
        if the mask has fewer than 3 non-collinear active pixels.
        """
        m = mask
        while len(m.shape) > 2:
            m = m.squeeze(0)
        ys, xs = np.where(m.astype(bool))
        if len(xs) < 3:
            return None
        try:
            from scipy.spatial import ConvexHull
            pts = np.column_stack([xs, ys])
            hull = ConvexHull(pts)
            verts = pts[hull.vertices]
            H, W = m.shape
            return np.column_stack([verts[:, 0] / W, verts[:, 1] / H])
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Outer contour computation
    # ------------------------------------------------------------------

    def compute_contour(self, mask):
        """
        Compute outer contour vertices from a binary mask.

        Uses skimage.measure.find_contours (primary) or cv2.findContours (fallback).
        When multiple contours are present, selects the longest one (largest region boundary).

        Returns normalized (N, 2) array of (x_norm, y_norm), or None if the mask
        has fewer than 3 active pixels or no supported library is available.
        """
        m = mask
        while len(m.shape) > 2:
            m = m.squeeze(0)
        if m.astype(bool).sum() < 3:
            return None
        H, W = m.shape

        # Primary: skimage
        try:
            from skimage.measure import find_contours
            contours = find_contours(m.astype(float), level=0.5)
            if not contours:
                return None
            contour = max(contours, key=len)  # longest = largest region boundary
            # skimage returns (row, col) == (y, x)
            return np.column_stack([contour[:, 1] / W, contour[:, 0] / H])
        except ImportError:
            pass

        # Fallback: OpenCV
        try:
            import cv2
            m_u8 = m.astype(bool).astype(np.uint8) * 255
            contours, _ = cv2.findContours(m_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            if not contours:
                return None
            contour = max(contours, key=cv2.contourArea)
            pts = contour.squeeze(1)  # (N, 2) in (x, y) order
            if pts.ndim != 2:
                return None
            return np.column_stack([pts[:, 0] / W, pts[:, 1] / H])
        except ImportError:
            return None

    # ------------------------------------------------------------------
    # Shared polygon smoothing
    # ------------------------------------------------------------------

    @staticmethod
    def _smooth_polygon(vertices, smoothing=0.0):
        """
        Smooth polygon vertices using periodic Gaussian smoothing with area preservation.

        Shared implementation used by both smooth_hull() and smooth_contour().

        Args:
            vertices: (N, 2) normalized vertex array.
            smoothing: 0.0 = no smoothing; 1.0 = maximum smoothing.

        Returns normalized (N, 2) array; falls back to raw vertices on failure.
        """
        if smoothing <= 0.0 or len(vertices) < 4:
            return vertices
        try:
            from scipy.ndimage import gaussian_filter1d
            sigma = smoothing * len(vertices) / 4.0
            if sigma < 0.1:
                return vertices

            # Periodic padding keeps the curve closed across the seam
            pad = int(sigma * 4) + 1
            xs = np.concatenate([vertices[-pad:, 0], vertices[:, 0], vertices[:pad, 0]])
            ys = np.concatenate([vertices[-pad:, 1], vertices[:, 1], vertices[:pad, 1]])
            sx = gaussian_filter1d(xs, sigma=sigma)[pad: pad + len(vertices)]
            sy = gaussian_filter1d(ys, sigma=sigma)[pad: pad + len(vertices)]
            smoothed = np.column_stack([sx, sy])

            # Rescale to preserve the original polygon area (Gaussian smoothing shrinks it)
            orig_area = ObjectManager._polygon_area(vertices)
            sm_area   = ObjectManager._polygon_area(smoothed)
            if sm_area > 1e-10 and orig_area > sm_area:
                scale  = np.sqrt(orig_area / sm_area)
                cx, cy = smoothed[:, 0].mean(), smoothed[:, 1].mean()
                smoothed = np.column_stack([
                    cx + (smoothed[:, 0] - cx) * scale,
                    cy + (smoothed[:, 1] - cy) * scale,
                ])

            return np.clip(smoothed, 0.0, 1.0)
        except Exception:
            return vertices

    def smooth_hull(self, vertices, smoothing=0.0):
        """Smooth hull vertices using periodic Gaussian smoothing; delegates to _smooth_polygon()."""
        return self._smooth_polygon(vertices, smoothing)

    def smooth_contour(self, vertices, smoothing=0.0):
        """Smooth contour vertices using periodic Gaussian smoothing; delegates to _smooth_polygon()."""
        return self._smooth_polygon(vertices, smoothing)

    @staticmethod
    def _polygon_area(verts):
        """Polygon area via the shoelace formula."""
        x, y = verts[:, 0], verts[:, 1]
        return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))

    @staticmethod
    def compute_hull_coverage(mask, hull_vertices):
        """
        Compute the fraction of active mask pixels contained within the hull polygon.

        Args:
            mask:          2-D (or squeeze-able) boolean/uint8 mask array.
            hull_vertices: (N, 2) normalized vertex array.

        Returns:
            Float in [0, 1], or None if the mask has no active pixels.
        """
        m = mask
        while len(m.shape) > 2:
            m = m.squeeze(0)
        ys, xs = np.where(m.astype(bool))
        if len(xs) == 0:
            return None
        H, W = m.shape
        px_verts = np.column_stack([hull_vertices[:, 0] * W, hull_vertices[:, 1] * H])
        try:
            from matplotlib.path import Path
            path = Path(px_verts)
            pts  = np.column_stack([xs.astype(float), ys.astype(float)])
            return float(path.contains_points(pts).sum()) / len(xs)
        except Exception:
            return None

    @staticmethod
    def compute_contour_coverage(mask, contour_vertices):
        """
        Compute the fraction of active mask pixels contained within the contour polygon.

        Mirrors compute_hull_coverage(). For unsmoothed contours this equals 1.0;
        values below 1.0 reflect geometric distortion introduced by smoothing.

        Returns Float in [0, 1], or None if the mask has no active pixels.
        """
        m = mask
        while len(m.shape) > 2:
            m = m.squeeze(0)
        ys, xs = np.where(m.astype(bool))
        if len(xs) == 0:
            return None
        H, W = m.shape
        px_verts = np.column_stack([contour_vertices[:, 0] * W, contour_vertices[:, 1] * H])
        try:
            from matplotlib.path import Path
            path = Path(px_verts)
            pts  = np.column_stack([xs.astype(float), ys.astype(float)])
            return float(path.contains_points(pts).sum()) / len(xs)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Point/mask geometry helpers (imported point vs. object analysis)
    # ------------------------------------------------------------------

    @staticmethod
    def point_in_mask(x_px, y_px, mask):
        """
        Direct boolean pixel lookup: is (x_px, y_px) inside the active mask
        region? Trivial containment check, no polygon involved.
        """
        m = mask
        while len(m.shape) > 2:
            m = m.squeeze(0)
        H, W = m.shape
        xi, yi = int(round(x_px)), int(round(y_px))
        if xi < 0 or yi < 0 or xi >= W or yi >= H:
            return False
        return bool(m[yi, xi])

    @staticmethod
    def point_in_polygon(x_px, y_px, polygon_verts_norm, img_w, img_h):
        """
        Test whether a pixel-space point falls inside a normalized polygon
        (convex hull or outer contour vertices, as returned by compute_hull()
        or compute_contour()). Shared helper since both are closed polygons
        in the same normalized coordinate convention.

        Returns True/False, or None if the polygon is missing or degenerate
        (fewer than 3 vertices).
        """
        if polygon_verts_norm is None or len(polygon_verts_norm) < 3:
            return None
        try:
            from matplotlib.path import Path
            px_verts = np.column_stack([
                polygon_verts_norm[:, 0] * img_w, polygon_verts_norm[:, 1] * img_h
            ])
            path = Path(px_verts)
            return bool(path.contains_point((x_px, y_px)))
        except Exception:
            return None

    @staticmethod
    def point_to_mask_distance(x_px, y_px, mask):
        """
        Nearest-pixel distance from (x_px, y_px) to the active pixels of a
        mask. Mirrors the np.hypot-based nearest-pixel search pattern used
        by ClosestMaskPointExporter, applied to a single query point.

        Returns (closest_x, closest_y, distance) or (None, None, None) if
        the mask has no active pixels.
        """
        m = mask
        while len(m.shape) > 2:
            m = m.squeeze(0)
        ys, xs = np.where(m.astype(bool))
        if len(xs) == 0:
            return None, None, None
        dists = np.hypot(xs - x_px, ys - y_px)
        idx_min = np.argmin(dists)
        return int(xs[idx_min]), int(ys[idx_min]), float(dists[idx_min])

    @staticmethod
    def point_to_polygon_boundary_distance(x_px, y_px, polygon_verts_norm, img_w, img_h):
        """
        Nearest distance in pixels from (x_px, y_px) to the boundary of a
        closed polygon (convex hull or outer contour), given as normalized
        vertices. Shared helper for both hull and contour boundary distance.

        Computed as the minimum point-to-segment distance over all polygon
        edges (closed: the last vertex connects back to the first), using
        pure NumPy vector projection — no new dependency (shapely) needed.

        Returns a float distance in pixels, or None if the polygon is
        missing or degenerate (fewer than 2 vertices).
        """
        if polygon_verts_norm is None or len(polygon_verts_norm) < 2:
            return None
        px_verts = np.column_stack([
            polygon_verts_norm[:, 0] * img_w, polygon_verts_norm[:, 1] * img_h
        ])
        p = np.array([x_px, y_px], dtype=np.float64)
        a = px_verts
        b = np.roll(px_verts, -1, axis=0)  # closed polygon: edge i = (a[i], b[i])
        ab = b - a
        ab_len_sq = np.sum(ab ** 2, axis=1)
        ab_len_sq[ab_len_sq == 0] = 1e-12  # guard against duplicate/degenerate vertices
        t = np.clip(np.sum((p - a) * ab, axis=1) / ab_len_sq, 0.0, 1.0)
        closest = a + t[:, None] * ab
        dists = np.hypot(closest[:, 0] - p[0], closest[:, 1] - p[1])
        return float(dists.min())

    # ------------------------------------------------------------------
    # Object lifecycle
    # ------------------------------------------------------------------

    def remove_object(self, obj_id):
        """Remove object by ID"""
        if obj_id not in self.object_colors:
            if self.debug_mode:
                print(f"Warning: Object {obj_id} not found")
            return False

        for d in (
            self.object_points, self.object_masks, self.object_colors,
            self.object_markers, self.object_names, self.object_show_points,
            self.object_centroids,
            self.object_hulls, self.object_hull_coverage,
            self.object_contours, self.object_contour_coverage,
            self.object_tracked_points, self.object_boxes,
            self.mask_imported_frames, self.mask_import_origin,
            self.object_corrected_frames,
        ):
            d.pop(obj_id, None)

        self.selected_object_ids.discard(obj_id)

        if self.debug_mode:
            print(f"Removed object {obj_id}")
        return True

    def get_object_count(self):
        """Get number of objects"""
        return len(self.object_colors)

    def get_object_ids(self):
        """Get list of all object IDs"""
        return sorted(self.object_colors.keys())

    def get_objects_with_points(self, frame_idx):
        """Get objects that have points defined on given frame"""
        objects_with_points = []
        for obj_id in self.object_points.keys():
            if frame_idx in self.object_points[obj_id]:
                pos_points = self.object_points[obj_id][frame_idx].get('positive', [])
                neg_points = self.object_points[obj_id][frame_idx].get('negative', [])
                if pos_points or neg_points:
                    objects_with_points.append(obj_id)
        return objects_with_points

    def get_objects_with_prompts(self, frame_idx):
        """Get objects that have at least one prompt — points or a box — on given frame"""
        objects = set(self.get_objects_with_points(frame_idx))
        for obj_id, frames in self.object_boxes.items():
            if frame_idx in frames:
                objects.add(obj_id)
        return sorted(objects)

    def get_objects_with_masks(self):
        """Get objects that have at least one mask defined"""
        objects_with_masks = {}
        for obj_id, masks in self.object_masks.items():
            if masks:
                objects_with_masks[obj_id] = min(masks.keys())
        return objects_with_masks

    def get_frames_with_any_mask(self):
        """Return sorted list of frame indices where at least one object has a mask defined."""
        frames = set()
        for masks in self.object_masks.values():
            frames.update(masks.keys())
        return sorted(frames)

    def add_point(self, obj_id, frame_idx, point_type, x, y):
        """Add point to object"""
        if obj_id not in self.object_points:
            self.object_points[obj_id] = defaultdict(_default_points)
        if point_type not in ['positive', 'negative']:
            raise ValueError(f"Invalid point type: {point_type}")
        self.object_points[obj_id][frame_idx][point_type].append((x, y))
        if self.debug_mode:
            print(f"Added {point_type} point ({x:.3f}, {y:.3f}) to object {obj_id} on frame {frame_idx}")

    def remove_points_in_area(self, obj_id, frame_idx, x0, y0, x1, y1):
        """Remove points within specified rectangular area"""
        if obj_id not in self.object_points or frame_idx not in self.object_points[obj_id]:
            return 0
        removed_count = 0
        original_pos = len(self.object_points[obj_id][frame_idx]['positive'])
        self.object_points[obj_id][frame_idx]['positive'] = [
            (x, y) for x, y in self.object_points[obj_id][frame_idx]['positive']
            if not (x0 <= x <= x1 and y0 <= y <= y1)
        ]
        removed_count += original_pos - len(self.object_points[obj_id][frame_idx]['positive'])
        original_neg = len(self.object_points[obj_id][frame_idx]['negative'])
        self.object_points[obj_id][frame_idx]['negative'] = [
            (x, y) for x, y in self.object_points[obj_id][frame_idx]['negative']
            if not (x0 <= x <= x1 and y0 <= y <= y1)
        ]
        removed_count += original_neg - len(self.object_points[obj_id][frame_idx]['negative'])
        if self.debug_mode and removed_count > 0:
            print(f"Removed {removed_count} points from object {obj_id} on frame {frame_idx}")
        return removed_count

    def clear_points(self, obj_id, frame_idx):
        """Clear all points for object on given frame"""
        if obj_id in self.object_points and frame_idx in self.object_points[obj_id]:
            pos_count = len(self.object_points[obj_id][frame_idx]['positive'])
            neg_count = len(self.object_points[obj_id][frame_idx]['negative'])
            self.object_points[obj_id][frame_idx]['positive'] = []
            self.object_points[obj_id][frame_idx]['negative'] = []
            if self.debug_mode:
                print(f"Cleared {pos_count + neg_count} points from object {obj_id} on frame {frame_idx}")

    def get_points_for_sam(self, obj_id, frame_idx, image_width, image_height):
        """Get points in format suitable for SAM2 (pixel coordinates)"""
        if obj_id not in self.object_points or frame_idx not in self.object_points[obj_id]:
            return np.array([]), np.array([])
        points = []
        labels = []
        for x, y in self.object_points[obj_id][frame_idx]['positive']:
            points.append([int(x * image_width), int(y * image_height)])
            labels.append(1)
        for x, y in self.object_points[obj_id][frame_idx]['negative']:
            points.append([int(x * image_width), int(y * image_height)])
            labels.append(0)
        return np.array(points, dtype=np.float32), np.array(labels)

    # ------------------------------------------------------------------
    # Bounding-box prompts
    # ------------------------------------------------------------------

    def set_box(self, obj_id, frame_idx, x0, y0, x1, y1):
        """Set the object's box on a frame, replacing any existing one.
        Normalized coordinates, reordered so that x0 < x1 and y0 < y1."""
        box = (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
        self.object_boxes.setdefault(obj_id, {})[frame_idx] = box
        if self.debug_mode:
            print(f"Set box {tuple(round(c, 3) for c in box)} "
                  f"for object {obj_id} on frame {frame_idx}")

    def remove_box(self, obj_id, frame_idx):
        """Remove the object's box on a frame; returns the removed box or None"""
        return self.object_boxes.get(obj_id, {}).pop(frame_idx, None)

    def get_box(self, obj_id, frame_idx):
        """Get the object's normalized box on a frame, or None"""
        return self.object_boxes.get(obj_id, {}).get(frame_idx)

    def get_box_for_sam(self, obj_id, frame_idx, image_width, image_height):
        """Get the box in format suitable for SAM2 (pixel coordinates), or None"""
        box = self.get_box(obj_id, frame_idx)
        if box is None:
            return None
        x0, y0, x1, y1 = box
        return np.array([x0 * image_width, y0 * image_height,
                         x1 * image_width, y1 * image_height], dtype=np.float32)

    def get_reference_box(self, obj_id):
        """Box defined on the object's lowest frame index, or None. Used by the
        'reference_box' clipping variant to constrain frames without a box."""
        frames = self.object_boxes.get(obj_id)
        if not frames:
            return None
        return frames[min(frames)]

    @staticmethod
    def clip_mask_to_box(mask, box_norm):
        """Return a copy of the mask with everything outside the box cleared.
        Boundary pixels are kept; an inverted box is left untouched (set_box
        orders the corners, so this only guards against malformed input)."""
        m = mask
        while len(m.shape) > 2:
            m = m.squeeze(0)
        H, W = m.shape
        x0, y0, x1, y1 = box_norm
        c0 = max(int(np.floor(x0 * W)), 0)
        r0 = max(int(np.floor(y0 * H)), 0)
        c1 = min(int(np.ceil(x1 * W)), W - 1)
        r1 = min(int(np.ceil(y1 * H)), H - 1)
        if c1 < c0 or r1 < r0:
            return m
        clipped = np.zeros_like(m)
        clipped[r0:r1 + 1, c0:c1 + 1] = m[r0:r1 + 1, c0:c1 + 1]
        return clipped

    @staticmethod
    def point_in_box(box, x, y):
        """Test whether a normalized point falls inside a box; boundary included."""
        x0, y0, x1, y1 = box
        return x0 <= x <= x1 and y0 <= y <= y1

    def get_points_outside_box(self, obj_id, frame_idx):
        """Return the (positive, negative) point lists the object's box on a
        frame excludes; both empty when there is no box."""
        box = self.get_box(obj_id, frame_idx)
        if (box is None or obj_id not in self.object_points
                or frame_idx not in self.object_points[obj_id]):
            return [], []
        frame_points = self.object_points[obj_id][frame_idx]
        return (
            [(x, y) for x, y in frame_points['positive'] if not self.point_in_box(box, x, y)],
            [(x, y) for x, y in frame_points['negative'] if not self.point_in_box(box, x, y)],
        )

    def points_outside_box(self, obj_id, frame_idx):
        """Count the object's points the box on a frame excludes, as
        (n_positive, n_negative)."""
        outside_pos, outside_neg = self.get_points_outside_box(obj_id, frame_idx)
        return len(outside_pos), len(outside_neg)

    def remove_points_outside_box(self, obj_id, frame_idx):
        """Remove the object's points falling outside its box on a frame —
        remove_points_in_area with an inverted predicate."""
        box = self.get_box(obj_id, frame_idx)
        if (box is None or obj_id not in self.object_points
                or frame_idx not in self.object_points[obj_id]):
            return 0
        removed_count = 0
        for point_type in ('positive', 'negative'):
            original = self.object_points[obj_id][frame_idx][point_type]
            kept = [(x, y) for x, y in original if self.point_in_box(box, x, y)]
            removed_count += len(original) - len(kept)
            self.object_points[obj_id][frame_idx][point_type] = kept
        if self.debug_mode and removed_count > 0:
            print(f"Removed {removed_count} points outside the box of object {obj_id} "
                  f"on frame {frame_idx}")
        return removed_count

    def store_mask(self, obj_id, frame_idx, mask):
        """Store mask and update centroid, convex hull, and outer contour."""
        if obj_id not in self.object_masks:
            self.object_masks[obj_id] = {}
        self.object_masks[obj_id][frame_idx] = mask

        # Centroid
        centroid = self.calculate_centroid(mask)
        if centroid:
            if obj_id not in self.object_centroids:
                self.object_centroids[obj_id] = {}
            self.object_centroids[obj_id][frame_idx] = centroid

        # Convex hull + coverage
        hull_verts = self.compute_hull(mask)
        if hull_verts is not None:
            hull_verts = self.smooth_hull(hull_verts, self.hull_smoothing)
            if obj_id not in self.object_hulls:
                self.object_hulls[obj_id] = {}
            self.object_hulls[obj_id][frame_idx] = hull_verts
            coverage = self.compute_hull_coverage(mask, hull_verts)
            if obj_id not in self.object_hull_coverage:
                self.object_hull_coverage[obj_id] = {}
            self.object_hull_coverage[obj_id][frame_idx] = coverage
        elif obj_id in self.object_hulls:
            self.object_hulls[obj_id].pop(frame_idx, None)
            if obj_id in self.object_hull_coverage:
                self.object_hull_coverage[obj_id].pop(frame_idx, None)

        # Outer contour + coverage
        contour_verts = self.compute_contour(mask)
        if contour_verts is not None:
            contour_verts = self.smooth_contour(contour_verts, self.contour_smoothing)
            if obj_id not in self.object_contours:
                self.object_contours[obj_id] = {}
            self.object_contours[obj_id][frame_idx] = contour_verts
            coverage = self.compute_contour_coverage(mask, contour_verts)
            if obj_id not in self.object_contour_coverage:
                self.object_contour_coverage[obj_id] = {}
            self.object_contour_coverage[obj_id][frame_idx] = coverage
        elif obj_id in self.object_contours:
            self.object_contours[obj_id].pop(frame_idx, None)
            if obj_id in self.object_contour_coverage:
                self.object_contour_coverage[obj_id].pop(frame_idx, None)

        if self.debug_mode:
            print(f"Stored mask for object {obj_id} on frame {frame_idx}, active pixels: {np.sum(mask)}")

    def remove_mask(self, obj_id, frame_idx):
        """Remove a stored mask along with everything derived from it (centroid,
        convex hull, outer contour, and their coverages).

        Returns the removed mask, or None if the frame had none."""
        mask = self.object_masks.get(obj_id, {}).pop(frame_idx, None)
        for d in (self.object_centroids,
                  self.object_hulls, self.object_hull_coverage,
                  self.object_contours, self.object_contour_coverage):
            if obj_id in d:
                d[obj_id].pop(frame_idx, None)
        if self.debug_mode and mask is not None:
            print(f"Removed mask for object {obj_id} on frame {frame_idx}")
        return mask

    def calculate_centroid(self, mask):
        """Calculate centroid of mask"""
        if len(mask.shape) > 2:
            if len(mask.shape) == 4:
                mask = mask[0, 0]
            elif len(mask.shape) == 3:
                if mask.shape[0] == 1:
                    mask = mask[0]
                elif mask.shape[2] == 1:
                    mask = mask[:, :, 0]
                else:
                    mask = mask[0]
        if len(mask.shape) != 2:
            if self.debug_mode:
                print(f"Warning: unexpected mask shape after normalization: {mask.shape}")
            return None
        y_indices, x_indices = np.where(mask)
        if len(x_indices) > 0 and len(y_indices) > 0:
            return (np.mean(x_indices), np.mean(y_indices))
        return None

    def clear_tracked_points(self, obj_id=None):
        """Clear tracked points for one object, or all objects if obj_id is None."""
        if obj_id is None:
            for frames in self.object_tracked_points.values():
                frames.clear()
        elif obj_id in self.object_tracked_points:
            self.object_tracked_points[obj_id].clear()

    def update_object_name(self, obj_id, name):
        """Update object name"""
        if obj_id in self.object_names:
            self.object_names[obj_id] = name
            if self.debug_mode:
                print(f"Updated object {obj_id} name to: {name}")

    def update_object_color(self, obj_id, color_type, color):
        """Update object color"""
        if obj_id in self.object_colors and color_type in self.object_colors[obj_id]:
            self.object_colors[obj_id][color_type] = color
            if self.debug_mode:
                print(f"Updated object {obj_id} {color_type} color")

    def update_object_marker(self, obj_id, style=None, size=None):
        """Update object marker properties"""
        if obj_id not in self.object_markers:
            return
        if style is not None:
            self.object_markers[obj_id]['style'] = style
        if size is not None:
            self.object_markers[obj_id]['size'] = size
        if self.debug_mode:
            print(f"Updated object {obj_id} marker: style={style}, size={size}")

    def set_object_points_visibility(self, obj_id, visible):
        """Set whether points should be visible for object"""
        if obj_id in self.object_show_points:
            self.object_show_points[obj_id] = visible

    def get_object_info(self, obj_id):
        """Get comprehensive information about an object"""
        if obj_id not in self.object_colors:
            return None
        info = {
            'id': obj_id,
            'name': self.object_names.get(obj_id, f"Object {obj_id}"),
            'colors': self.object_colors[obj_id],
            'marker': self.object_markers[obj_id],
            'show_points': self.object_show_points.get(obj_id, True),
            'frames_with_points':    list(self.object_points[obj_id].keys()) if obj_id in self.object_points else [],
            'frames_with_masks':     list(self.object_masks[obj_id].keys()) if obj_id in self.object_masks else [],
            'frames_with_centroids': list(self.object_centroids[obj_id].keys()) if obj_id in self.object_centroids else [],
            'frames_with_hulls':     list(self.object_hulls[obj_id].keys()) if obj_id in self.object_hulls else [],
            'frames_with_contours':  list(self.object_contours[obj_id].keys()) if obj_id in self.object_contours else [],
        }
        total_points = 0
        if obj_id in self.object_points:
            for frame_points in self.object_points[obj_id].values():
                total_points += len(frame_points['positive']) + len(frame_points['negative'])
        info['total_points'] = total_points
        return info

    def get_summary(self):
        """Get summary of all objects"""
        summary = {
            'total_objects': len(self.object_colors),
            'current_object_id': self.current_object_id,
            'objects': []
        }
        for obj_id in sorted(self.object_colors.keys()):
            summary['objects'].append(self.get_object_info(obj_id))
        return summary

    def add_new_object(self):
        """Add new object and return its ID"""
        obj_ids = list(self.object_colors.keys())
        new_id = max(obj_ids) + 1 if obj_ids else 1
        self.object_points[new_id] = defaultdict(_default_points)
        self.object_masks[new_id] = {}
        self.object_colors[new_id] = {
            'positive': QColor(0, 255, 0),
            'negative': QColor(255, 0, 0),
            'mask': self._get_palette_color()
        }
        self.object_markers[new_id] = {'style': 'o', 'size': 5}
        word = self.localization.get_text("point" if self.point_mode else "object")
        self.object_names[new_id] = f"{word} {new_id}"
        self.object_show_points[new_id] = True
        if self.debug_mode:
            print(f"Added new object with ID {new_id}")
        return new_id

    def snapshot_object(self, obj_id):
        """Capture a deep copy of all per-object state, for undo/redo of add/remove."""
        import copy
        return {
            'points': copy.deepcopy(dict(self.object_points.get(obj_id, {}))),
            'masks': copy.deepcopy(self.object_masks.get(obj_id, {})),
            'boxes': copy.deepcopy(self.object_boxes.get(obj_id, {})),
            'import_origin': set(self.mask_import_origin.get(obj_id, set())),
            'colors': {k: QColor(v) for k, v in self.object_colors.get(obj_id, {}).items()},
            'markers': copy.deepcopy(self.object_markers.get(obj_id, {})),
            'name': self.object_names.get(obj_id),
            'show_points': self.object_show_points.get(obj_id, True),
        }

    def restore_object(self, obj_id, snapshot):
        """Reinsert an object's full state from a snapshot captured by snapshot_object()."""
        self.object_points[obj_id] = defaultdict(_default_points, snapshot['points'])
        self.object_masks[obj_id] = snapshot['masks'] or {}
        self.object_boxes[obj_id] = snapshot['boxes'] or {}
        self.mask_import_origin[obj_id] = snapshot['import_origin'] or set()
        self.object_colors[obj_id] = snapshot['colors']
        self.object_markers[obj_id] = snapshot['markers']
        self.object_names[obj_id] = snapshot['name']
        self.object_show_points[obj_id] = snapshot['show_points']

    def clear_all_data(self):
        """Clear all object data (for new video sequence)"""
        for d in (
            self.object_points, self.object_masks, self.object_colors,
            self.object_markers, self.object_names, self.object_show_points,
            self.object_centroids,
            self.object_hulls, self.object_hull_coverage,
            self.object_contours, self.object_contour_coverage,
            self.object_tracked_points, self.object_boxes,
            self.mask_imported_frames, self.mask_import_origin,
            self.object_corrected_frames,
        ):
            d.clear()

        # Reset to default object
        self.current_object_id = 1
        self.object_points[1] = defaultdict(_default_points)
        self.object_masks[1] = {}
        self.object_colors[1] = {
            'positive': QColor(0, 255, 0),
            'negative': QColor(255, 0, 0),
            'mask': self._get_palette_color()
        }
        self.object_markers[1] = {'style': 'o', 'size': 5}
        word = self.localization.get_text("point" if self.point_mode else "object")
        self.object_names[1] = f"{word} 1"
        self.object_show_points[1] = True
        self.selected_object_ids = {1}

        if self.debug_mode:
            print("Cleared all object data and reset to default")
