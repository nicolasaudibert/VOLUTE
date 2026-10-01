"""
Display Manager
Handles image display, masks, centroids, points and zoom management
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as patches

class DisplayManager:
    """Manages display of images, masks, points, and centroids"""
    
    def __init__(self, main_window):
        self.main_window = main_window
        
        # Global zoom state
        self.global_xlim = None
        self.global_ylim = None
    
    def connect_to_ui(self, ui_manager):
        """Connect to UI manager for canvas access"""
        self.ui_manager = ui_manager
    
    def update_display(self, maintain_global_zoom=False):
        """Update image and annotations display"""
        if not self.main_window.image_manager.has_images():
            return
        
        self.ui_manager.canvas.axes.clear()
        
        image = self.main_window.image_manager.get_current_image()
        
        bg_opacity_slider = self.ui_manager.get_control('background_opacity_slider')
        bg_opacity = bg_opacity_slider.value() / 100 if bg_opacity_slider else 1.0
        self.ui_manager.canvas.axes.imshow(image, alpha=bg_opacity)
        
        h, w = image.shape[:2]
        
        self.display_masks(h, w)
        self.display_centroids()
        self.display_hulls(h, w)
        self.display_contours(h, w)
        self.display_boxes(w, h)
        self.display_points(w, h)
        self.display_ref_points(w, h)
        self.display_tracked_points(w, h)
        self.display_imported_points(w, h)
        
        self.ui_manager.canvas.axes.axis('off')
        
        self.update_image_title_with_qlabel()
        
        self.ui_manager.canvas.fig.tight_layout()
        
        if maintain_global_zoom:
            self.maintain_global_zoom_state()
        
        self.ui_manager.canvas.draw()
        
        if hasattr(self.ui_manager, 'refresh_export_state'):
            self.ui_manager.refresh_export_state()
        if hasattr(self.ui_manager, 'ref_point_controls'):
            self.ui_manager.ref_point_controls.update_ref_point_ui()
        if hasattr(self.main_window, '_refresh_repropagate_button_state'):
            self.main_window._refresh_repropagate_button_state()
        if hasattr(self.main_window, '_refresh_remove_box_button_state'):
            self.main_window._refresh_remove_box_button_state()
    
    def update_image_title_with_qlabel(self):
        """Update the title label (created by UIManager) with folder + image info."""
        label = getattr(self.ui_manager, 'title_label', None)
        if label is None:
            return

        current_idx  = self.main_window.image_manager.current_image_idx
        total_images = len(self.main_window.image_manager.image_paths)
        image_word   = self.main_window.localization.get_text("image")

        folder_name = ""
        if (hasattr(self.main_window, 'image_manager') and
                self.main_window.image_manager.current_folder):
            folder_name = os.path.basename(
                self.main_window.image_manager.current_folder.rstrip(os.sep)
            )

        parts = []
        if folder_name:
            parts.append(folder_name)
        parts.append(f"{image_word} {current_idx + 1}/{total_images}")
        backend = getattr(self.main_window, 'sam2_backend', None)
        if (backend and getattr(backend, 'is_sam2plus', False)
                and getattr(backend, 'sam2plus_task', 'mask') == 'point'):
            mode_key = "mode_point_tracking"
            parts.append(f"[{self.main_window.localization.get_text(mode_key)}]")
        text = "  |  ".join(parts)

        # Original filename, on a second line: the GIMP round-trip names its
        # files after it, so having it in view makes the match immediate
        if self.main_window.config_manager.show_image_filename():
            path = self.main_window.image_manager.get_current_image_path()
            if path:
                text += f"\n{os.path.basename(path)}"

        label.setText(text)
    
    def display_masks(self, h, w):
        """Display all object masks with enhanced debugging"""
        if self.main_window.debug_mode:
            print(f"=== DISPLAY_MASKS DEBUG: frame {self.main_window.image_manager.current_image_idx} ===")
            print(f"Image dimensions for display: {h}x{w}")
        
        show_labels_checkbox = self.ui_manager.get_control('show_object_labels_checkbox')
        show_labels = show_labels_checkbox.isChecked() if show_labels_checkbox else True
        
        masks_displayed = 0
        masks_attempted = 0
        current_frame_idx = self.main_window.image_manager.current_image_idx
        
        if self.main_window.debug_mode:
            print(f"Current frame index: {current_frame_idx}")
            print(f"Available objects: {list(self.main_window.object_manager.object_masks.keys())}")
        
        for obj_id in sorted(self.main_window.object_manager.object_masks.keys()):
            if current_frame_idx not in self.main_window.object_manager.object_masks[obj_id]:
                if self.main_window.debug_mode:
                    available_frames = list(self.main_window.object_manager.object_masks[obj_id].keys())
                    print(f"  Object {obj_id}: NO mask for frame {current_frame_idx}, available: {available_frames}")
                continue
                
            masks_attempted += 1
            mask = self.main_window.object_manager.object_masks[obj_id][current_frame_idx]
            mask_color = self.main_window.object_manager.object_colors[obj_id]['mask']
            
            if self.main_window.debug_mode:
                print(f"  Object {obj_id}: Processing mask")
                print(f"    Original mask shape: {mask.shape}, type: {type(mask)}, dtype: {mask.dtype}")
                print(f"    Active pixels: {np.sum(mask)}")
                print(f"    Color: RGBA({mask_color.red()}, {mask_color.green()}, {mask_color.blue()}, {mask_color.alpha()})")
            
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
            
            if self.main_window.debug_mode:
                print(f"    Processed mask shape: {mask.shape}")
                print(f"    Target display dimensions: {h}x{w}")
            
            if mask.shape[:2] != (h, w):
                if self.main_window.debug_mode:
                    print(f"    ERROR: Mask dimensions {mask.shape[:2]} != image dimensions ({h}, {w})")
                continue
            
            mask_color_rgb = np.array([
                mask_color.red(), 
                mask_color.green(), 
                mask_color.blue()
            ]) / 255.0
            mask_opacity = mask_color.alphaF()
            
            mask_overlay = np.zeros((h, w, 3), dtype=np.float32)
            mask_overlay[:, :, 0] = mask_color_rgb[0]
            mask_overlay[:, :, 1] = mask_color_rgb[1]
            mask_overlay[:, :, 2] = mask_color_rgb[2]
            
            if len(mask.shape) == 2:
                mask_3d = mask[:, :, np.newaxis]
            else:
                mask_3d = mask
            
            if mask_overlay.shape[:2] == mask_3d.shape[:2]:
                mask_img = mask_overlay * mask_3d
                
                try:
                    self.ui_manager.canvas.axes.imshow(mask_img, alpha=mask_opacity * mask)
                    masks_displayed += 1
                    
                    if show_labels and obj_id in self.main_window.object_manager.object_names:
                        self.add_object_label(obj_id, mask, mask_color_rgb)
                        
                except Exception as display_error:
                    if self.main_window.debug_mode:
                        print(f"    ERROR displaying mask: {display_error}")
        
        if self.main_window.debug_mode:
            print(f"=== DISPLAY_MASKS RESULT: {masks_displayed}/{masks_attempted} masks displayed ===")
        
        if hasattr(self.main_window, '_last_display_result'):
            self.main_window._last_display_result = {
                'masks_displayed': masks_displayed,
                'masks_attempted': masks_attempted,
                'current_frame': current_frame_idx
            }
    
    def get_last_display_result(self):
        """Get the result of the last display_masks call for debugging"""
        return getattr(self.main_window, '_last_display_result', None)
    
    def add_object_label(self, obj_id, mask, mask_color_rgb):
        """Add object name label on mask"""
        current_frame_idx = self.main_window.image_manager.current_image_idx
        
        if (obj_id in self.main_window.object_manager.object_centroids and 
            current_frame_idx in self.main_window.object_manager.object_centroids[obj_id]):
            center_x, center_y = self.main_window.object_manager.object_centroids[obj_id][current_frame_idx]
        else:
            y_indices, x_indices = np.where(mask)
            if len(x_indices) > 0 and len(y_indices) > 0:
                center_x = np.mean(x_indices)
                center_y = np.mean(y_indices)
            else:
                return
        
        obj_name = self.main_window.object_manager.object_names[obj_id]
        
        try:
            self.ui_manager.canvas.axes.text(
                center_x, center_y, obj_name,
                color='white', fontsize=10, ha='center', va='center',
                bbox=dict(facecolor=mask_color_rgb, alpha=0.7, boxstyle='round,pad=0.3')
            )
        except Exception as e:
            if self.main_window.debug_mode:
                print(f"Warning: Unicode text display issue for object label: {e}")
            try:
                self.ui_manager.canvas.axes.text(
                    center_x, center_y, f"Obj {obj_id}",
                    color='white', fontsize=10, ha='center', va='center',
                    bbox=dict(facecolor=mask_color_rgb, alpha=0.7, boxstyle='round,pad=0.3')
                )
            except:
                pass
    
    def display_centroids(self):
        """Display centroids if enabled"""
        show_centroids_checkbox = self.ui_manager.get_control('show_centroids_checkbox')
        if not show_centroids_checkbox or not show_centroids_checkbox.isChecked():
            return
        
        current_frame_idx = self.main_window.image_manager.current_image_idx
        
        for obj_id in sorted(self.main_window.object_manager.object_centroids.keys()):
            if current_frame_idx not in self.main_window.object_manager.object_centroids[obj_id]:
                continue
                
            centroid_x, centroid_y = self.main_window.object_manager.object_centroids[obj_id][current_frame_idx]
            
            circle = plt.Circle(
                (centroid_x, centroid_y), 
                self.main_window.object_manager.centroid_size, 
                color=self.main_window.object_manager.centroid_color.name(), 
                fill=True, 
                alpha=0.8
            )
            self.ui_manager.canvas.axes.add_patch(circle)
            
            circle_border = plt.Circle(
                (centroid_x, centroid_y), 
                self.main_window.object_manager.centroid_size, 
                color='black', 
                fill=False, 
                linewidth=1
            )
            self.ui_manager.canvas.axes.add_patch(circle_border)

    def display_hulls(self, h, w):
        """Display convex hull outlines for all objects on the current frame."""
        om = self.main_window.object_manager
        if not getattr(om, 'show_hulls', False):
            return

        from matplotlib.patches import Polygon as MplPolygon

        frame_idx = self.main_window.image_manager.current_image_idx

        for obj_id in sorted(om.object_hulls.keys()):
            frames = om.object_hulls[obj_id]
            if frame_idx not in frames or frames[frame_idx] is None:
                continue
            verts = frames[frame_idx]
            if len(verts) < 3:
                continue

            px_verts = np.column_stack([verts[:, 0] * w, verts[:, 1] * h])

            mask_color = om.object_colors[obj_id]['mask']
            edge_color = (
                mask_color.red()   / 255.0,
                mask_color.green() / 255.0,
                mask_color.blue()  / 255.0,
            )

            # Primary contour — mask color at full opacity
            self.ui_manager.canvas.axes.add_patch(MplPolygon(
                px_verts, closed=True,
                edgecolor=edge_color, facecolor='none',
                linewidth=om.hull_line_width,
            ))

            # Optional border: one thin line inside, one outside the primary contour.
            # Geometric offset (radial scaling from centroid) preserves convex hull shape.
            if getattr(om, 'hull_outline_visible', False):
                oc = om.hull_outline_color
                outline_color = (oc.red() / 255.0, oc.green() / 255.0, oc.blue() / 255.0)
                outline_lw    = 0.75
                offset_px     = om.hull_line_width / 2.0 + outline_lw / 2.0 + 0.5

                cx = px_verts[:, 0].mean()
                cy = px_verts[:, 1].mean()
                dx = px_verts[:, 0] - cx
                dy = px_verts[:, 1] - cy
                radii = np.maximum(np.sqrt(dx ** 2 + dy ** 2), 1e-6)

                for sign in (+1, -1):   # outer contour, then inner contour
                    f = 1.0 + sign * offset_px / radii
                    self.ui_manager.canvas.axes.add_patch(MplPolygon(
                        np.column_stack([cx + dx * f, cy + dy * f]),
                        closed=True,
                        edgecolor=outline_color,
                        facecolor='none',
                        linewidth=outline_lw,
                    ))

    def display_contours(self, h, w):
        """Display outer contour outlines for all objects on the current frame.

        Uses matplotlib.patheffects.withStroke for the optional border, which avoids
        geometric distortion on non-convex shapes (unlike the radial offset used for hulls).
        """
        om = self.main_window.object_manager
        if not getattr(om, 'show_contours', False):
            return

        import matplotlib.patheffects as pe
        from matplotlib.patches import Polygon as MplPolygon

        frame_idx = self.main_window.image_manager.current_image_idx

        for obj_id in sorted(om.object_contours.keys()):
            frames = om.object_contours[obj_id]
            if frame_idx not in frames or frames[frame_idx] is None:
                continue
            verts = frames[frame_idx]
            if len(verts) < 3:
                continue

            px_verts = np.column_stack([verts[:, 0] * w, verts[:, 1] * h])

            mask_color = om.object_colors[obj_id]['mask']
            edge_color = (
                mask_color.red()   / 255.0,
                mask_color.green() / 255.0,
                mask_color.blue()  / 255.0,
            )

            # Build path effects list: stroke rendered behind the primary line acts as border
            path_effects = []
            if getattr(om, 'contour_outline_visible', False):
                oc = om.contour_outline_color
                outline_color = (oc.red() / 255.0, oc.green() / 255.0, oc.blue() / 255.0)
                path_effects = [
                    pe.withStroke(linewidth=om.contour_line_width + 3.0, foreground=outline_color),
                ]

            patch = MplPolygon(
                px_verts, closed=True,
                edgecolor=edge_color, facecolor='none',
                linewidth=om.contour_line_width,
            )
            if path_effects:
                patch.set_path_effects(path_effects)
            self.ui_manager.canvas.axes.add_patch(patch)

    def display_points(self, w, h):
        """Display points for all selected objects if global show points is enabled"""
        if not getattr(self.main_window, 'show_points_global', True):
            return

        current_frame_idx = self.main_window.image_manager.current_image_idx
        om = self.main_window.object_manager

        for obj_id in sorted(om.selected_object_ids):
            obj_points = om.object_points.get(obj_id)
            if not obj_points or current_frame_idx not in obj_points:
                continue
            if obj_id not in om.object_markers or obj_id not in om.object_colors:
                continue

            marker_style = om.object_markers[obj_id]['style']
            marker_size = om.object_markers[obj_id]['size'] * 10

            pos_points = obj_points[current_frame_idx]['positive']
            if pos_points:
                pos_x = [p[0] * w for p in pos_points]
                pos_y = [p[1] * h for p in pos_points]
                pos_color = om.object_colors[obj_id]['positive'].name()
                self.ui_manager.canvas.axes.scatter(pos_x, pos_y, c=[pos_color], marker=marker_style, s=marker_size)

            neg_points = obj_points[current_frame_idx]['negative']
            if neg_points:
                neg_x = [p[0] * w for p in neg_points]
                neg_y = [p[1] * h for p in neg_points]
                neg_color = om.object_colors[obj_id]['negative'].name()
                self.ui_manager.canvas.axes.scatter(neg_x, neg_y, c=[neg_color], marker=marker_style, s=marker_size)

    def display_boxes(self, w, h):
        """Display the bounding box of every selected object on the current frame,
        as a dashed rectangle in the object's mask color."""
        current_frame_idx = self.main_window.image_manager.current_image_idx
        om = self.main_window.object_manager

        for obj_id in sorted(om.selected_object_ids):
            box = om.get_box(obj_id, current_frame_idx)
            if box is None or obj_id not in om.object_colors:
                continue
            x0, y0, x1, y1 = box
            self.ui_manager.canvas.axes.add_patch(patches.Rectangle(
                (x0 * w, y0 * h), (x1 - x0) * w, (y1 - y0) * h,
                linewidth=1.5, linestyle='--', facecolor='none',
                edgecolor=om.object_colors[obj_id]['mask'].name(),
            ))

    def display_ref_points(self, w, h):
        """Display reference points (interpolated position) for the current frame.

        Explicitly defined frames are rendered at full opacity with a thicker
        marker edge and an underlined label; interpolated/extrapolated positions
        use reduced opacity (0.55), a thinner edge, and a plain label. Each
        reference point uses its own per-name color and marker style/size.
        """
        rpm = getattr(self.main_window, 'ref_point_manager', None)
        if not rpm:
            return

        frame_idx = self.main_window.image_manager.current_image_idx

        for name in rpm.get_names():
            coords = rpm.get_interpolated_coords(name, frame_idx)
            if coords is None:
                continue
            nx, ny = coords
            px, py = nx * w, ny * h
            is_explicit = rpm.has_point(name, frame_idx)
            alpha = 1.0 if is_explicit else 0.55
            edge_width = 2.5 if is_explicit else 1.5

            color = rpm.ref_point_colors.get(name, rpm.default_color)
            marker = rpm.ref_point_markers.get(
                name, {'style': rpm.default_marker, 'size': rpm.default_marker_size}
            )
            color_hex = color.name()

            self.ui_manager.canvas.axes.plot(
                px, py,
                marker=marker['style'],
                color=color_hex,
                markersize=marker['size'],
                markeredgewidth=edge_width,
                linestyle='None',
                alpha=alpha,
            )
            try:
                fontweight = 'heavy' if is_explicit else 'bold'
                self.ui_manager.canvas.axes.annotate(
                    name, (px, py),
                    xytext=(6, 4), textcoords='offset points',
                    color=color_hex, fontsize=8, fontweight=fontweight,
                )
            except Exception:
                pass

    def display_tracked_points(self, w, h):
        """Display SAM2++ tracked point positions on the current frame."""
        om = self.main_window.object_manager
        if not getattr(om, 'show_tracked_points', True):
            return
        if not om.object_tracked_points:
            return

        show_labels_checkbox = self.ui_manager.get_control('show_object_labels_checkbox')
        show_labels = (show_labels_checkbox.isChecked()
                       if show_labels_checkbox else True)

        frame_idx = self.main_window.image_manager.current_image_idx

        for obj_id, frames in om.object_tracked_points.items():
            if frame_idx not in frames:
                continue
            if obj_id not in om.object_colors:
                continue
            x_px, y_px = frames[frame_idx]
            color = om.object_colors[obj_id]['mask']
            self.ui_manager.canvas.axes.plot(
                x_px, y_px,
                marker=om.tracked_point_style,
                color=color.name(),
                markersize=om.tracked_point_size,
                markeredgewidth=1.5,
                markeredgecolor='white',
                linestyle='None',
                alpha=0.9,
                zorder=5,
            )
            if show_labels and obj_id in om.object_names:
                self.ui_manager.canvas.axes.annotate(
                    om.object_names[obj_id], (x_px, y_px),
                    xytext=(6, 4), textcoords='offset points',
                    color=color.name(), fontsize=9, fontweight='bold',
                    zorder=6,
                )

    def display_imported_points(self, w, h):
        """Display imported points (from a SAM2++ point-mode export) on the
        current frame. Direct pixel coordinates, no interpolation — a name
        with no explicit entry on this frame is simply not drawn."""
        ipm = getattr(self.main_window, 'imported_point_manager', None)
        if not ipm or not getattr(ipm, 'show_imported_points', True):
            return
        if not ipm.imported_points:
            return

        show_labels_checkbox = self.ui_manager.get_control('show_object_labels_checkbox')
        show_labels = (show_labels_checkbox.isChecked()
                       if show_labels_checkbox else True)

        frame_idx = self.main_window.image_manager.current_image_idx

        for name in ipm.get_names():
            coords = ipm.get_coords(name, frame_idx)
            if coords is None:
                continue
            x_px, y_px = coords

            color = ipm.imported_point_colors.get(name, ipm.default_color)
            marker = ipm.imported_point_markers.get(
                name, {'style': ipm.default_marker, 'size': ipm.default_marker_size}
            )
            color_hex = color.name()

            self.ui_manager.canvas.axes.plot(
                x_px, y_px,
                marker=marker['style'],
                color=color_hex,
                markersize=marker['size'],
                markeredgewidth=1.5,
                markeredgecolor='white',
                linestyle='None',
                zorder=5,
            )
            if show_labels:
                self.ui_manager.canvas.axes.annotate(
                    name, (x_px, y_px),
                    xytext=(6, 4), textcoords='offset points',
                    color=color_hex, fontsize=9, fontweight='bold',
                    zorder=6,
                )

    # ------------------------------------------------------------------
    # Zoom management
    # ------------------------------------------------------------------

    def reset_global_zoom(self):
        """Reset global zoom state"""
        self.global_xlim = None
        self.global_ylim = None
        if self.main_window.debug_mode:
            print("Global zoom state reset")
    
    def capture_global_zoom_state(self):
        """Capture current zoom state"""
        if self.main_window.image_manager.has_images() and hasattr(self, 'ui_manager'):
            self.global_xlim = self.ui_manager.canvas.axes.get_xlim()
            self.global_ylim = self.ui_manager.canvas.axes.get_ylim()
            if self.main_window.debug_mode:
                print(f"Global zoom captured: xlim={self.global_xlim}, ylim={self.global_ylim}")
    
    def maintain_global_zoom_state(self):
        """Apply global zoom state if defined"""
        if (self.global_xlim is not None and self.global_ylim is not None and 
            hasattr(self, 'ui_manager')):
            self.ui_manager.canvas.axes.set_xlim(self.global_xlim)
            self.ui_manager.canvas.axes.set_ylim(self.global_ylim)
            if self.main_window.debug_mode:
                print("Global zoom applied")
