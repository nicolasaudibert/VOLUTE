"""
Event Manager
Handles user interactions like clicks, keyboard events, and point management
"""

from collections import defaultdict
from PyQt5.QtCore import Qt
# from PyQt5.QtWidgets import QApplication
import matplotlib.patches as patches
import copy
from .history_manager import Command
from .dialogs import localize_standard_buttons

class EventManager:
    """Manages user events and interactions"""

    # Minimum drag, in image pixels and in both dimensions, for a box to be kept
    MIN_BOX_DRAG_PX = 3

    def __init__(self, main_window):
        self.main_window = main_window

        # Variables for rectangular selection
        self.rect_start = None
        self.rect_end = None
        self.rect = None
        self.selecting_rect = False

        # Variables for bounding-box definition
        self.box_start = None
        self.box_end = None
        self.box_rect = None
        self.selecting_box = False

        # Session-only "don't ask again" flags for the reference point
        # repositioning and point-outside-box confirmations. Not persisted
        # across app restarts.
        self._ref_point_dont_ask_reposition = False
        self._dont_ask_point_outside_box = False
    
    def _push_points_command(self, obj_id, frame_idx, before, label=""):
        """Push an undo command capturing a point-list change for (obj_id, frame_idx).
        `before` is the deep-copied {'positive': [...], 'negative': [...]} snapshot
        captured prior to the mutation; the "after" snapshot is captured now."""
        om = self.main_window.object_manager
        after = copy.deepcopy(om.object_points[obj_id][frame_idx])

        def _restore(snapshot):
            om.object_points[obj_id][frame_idx] = copy.deepcopy(snapshot)
            self.main_window.display_manager.update_display(maintain_global_zoom=True)

        self.main_window.history_manager.push(Command(
            undo_fn=lambda: _restore(before),
            redo_fn=lambda: _restore(after),
            label=label,
        ))
    
    def _place_ref_point(self, rpm, name, frame_idx, x, y):
        """Place/replace the position of `name` on `frame_idx`, honoring simple vs
        advanced mode and, in advanced mode, confirming before repositioning a point
        that already has an interpolated position on this frame."""
        before = copy.deepcopy(rpm.reference_points.get(name, {}))

        if not rpm.advanced_mode:
            # Simple mode: overwrite the single constant position for all frames
            # (clear then re-add at the current frame — relies on the n==1
            # constant-across-frames case in get_interpolated_coords).
            rpm.reference_points[name] = {}
            rpm.add_point(name, frame_idx, x, y)
        else:
            existing_frames = rpm.get_frames(name)
            repositioning = bool(existing_frames) and frame_idx not in existing_frames
            if repositioning and not self._ref_point_dont_ask_reposition:
                if not self._confirm_ref_point_reposition():
                    return
            rpm.add_point(name, frame_idx, x, y)

        after = copy.deepcopy(rpm.reference_points.get(name, {}))

        def _restore(snapshot):
            if snapshot:
                rpm.reference_points[name] = copy.deepcopy(snapshot)
            else:
                rpm.reference_points.pop(name, None)
            self.main_window.ui_manager.update_ref_points_list()
            self.main_window.display_manager.update_display(maintain_global_zoom=True)

        self.main_window.history_manager.push(Command(
            undo_fn=lambda: _restore(before),
            redo_fn=lambda: _restore(after),
            label="Place reference point",
        ))
        self.main_window.ui_manager.update_ref_points_list()
        self.main_window.display_manager.update_display(maintain_global_zoom=True)

    def _confirm_ref_point_reposition(self):
        """Show a confirmation dialog before repositioning an interpolated reference
        point, with a 'don't ask again' checkbox (session-only persistence)."""
        from PyQt5.QtWidgets import QMessageBox, QCheckBox
        box = QMessageBox(self.main_window)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(self.main_window.localization.get_text("confirmation"))
        box.setText(self.main_window.localization.get_text("ref_point_reposition_confirm"))
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        localize_standard_buttons(box, self.main_window.localization)
        checkbox = QCheckBox(self.main_window.localization.get_text("dont_ask_again"))
        box.setCheckBox(checkbox)
        result = box.exec_()
        if checkbox.isChecked():
            self._ref_point_dont_ask_reposition = True
        return result == QMessageBox.Yes
    
    def connect_to_ui(self, ui_manager):
        """Connect to UI manager and setup event handlers"""
        self.ui_manager = ui_manager
        self.setup_canvas_events()
    
    def setup_canvas_events(self):
        """Setup canvas event handlers"""
        if hasattr(self.ui_manager, 'canvas'):
            self.ui_manager.canvas.mpl_connect('button_press_event', self.on_click)
            self.ui_manager.canvas.mpl_connect('motion_notify_event', self.on_motion)
            self.ui_manager.canvas.mpl_connect('button_release_event', self.on_release)
    
    def on_click(self, event):
        """Handle mouse clicks on canvas"""
        if (event.inaxes != self.ui_manager.canvas.axes or 
            not self.main_window.image_manager.has_images()):
            return
        
        # Ignore clicks if toolbar tool is active
        if hasattr(self.ui_manager, 'toolbar') and hasattr(self.ui_manager.toolbar, 'is_tool_active'):
            if self.ui_manager.toolbar.is_tool_active():
                if self.main_window.debug_mode:
                    print("Navigation tool active, click ignored")
                return

        # Prediction tab active: no point of any kind can be added or modified
        if self.main_window.active_tab_index == self.main_window.TAB_PREDICTION:
            return
        
        # Get normalized coordinates (between 0 and 1)
        image_info = self.main_window.image_manager.get_current_image_info()
        h, w = image_info['height'], image_info['width']
        x = event.xdata / w
        y = event.ydata / h
        frame_idx = self.main_window.image_manager.current_image_idx

        # Ref. Points tab active: plain left-click places/replaces the position of
        # the currently selected reference point on the current frame; right-click
        # and Ctrl+click are ignored (no negative equivalent for reference points).
        if self.main_window.active_tab_index == self.main_window.TAB_REF_POINTS:
            if event.button != 1 or event.key == 'control':
                return
            rpm = getattr(self.main_window, 'ref_point_manager', None)
            if not rpm:
                return
            if len(rpm.selected_ref_point_names) > 1:
                self.main_window.ui_manager.show_message(
                    "warning", "",
                    self.main_window.localization.get_text("multi_selection_add_points_blocked")
                )
                return
            if rpm.current_ref_point_name:
                self._place_ref_point(rpm, rpm.current_ref_point_name, frame_idx, x, y)
            else:
                self.main_window.ui_manager.show_message(
                    "warning", "",
                    self.main_window.localization.get_text("no_ref_point_selected")
                )
            return

        # Objects/Points tab active: existing add/remove/point-tracking logic below

        # Remove points mode: start rectangular selection on left click
        remove_points_radio = self.ui_manager.get_control('remove_points_radio')
        if remove_points_radio and remove_points_radio.isChecked():
            if event.button == 1:
                self.rect_start = (event.xdata, event.ydata)
                self.selecting_rect = True
            return

        # Define box mode: start a click-and-drag defining the current object's
        # bounding box. Left button only; right-click and Ctrl+click ignored.
        define_box_radio = self.ui_manager.get_control('define_box_radio')
        if define_box_radio and define_box_radio.isChecked():
            if event.button != 1 or event.key == 'control':
                return
            if len(self.main_window.object_manager.selected_object_ids) > 1:
                self.main_window.ui_manager.show_message(
                    "warning", "",
                    self.main_window.localization.get_text("multi_selection_add_points_blocked")
                )
                return
            self.box_start = (event.xdata, event.ydata)
            self.selecting_box = True
            return

        # Point tracking mode (SAM2++): left click replaces the seed point
        # (clear + add positive); no negative points, no remove mode.
        if self.main_window.is_point_mode():
            if len(self.main_window.object_manager.selected_object_ids) > 1:
                self.main_window.ui_manager.show_message(
                    "warning", "",
                    self.main_window.localization.get_text("multi_selection_add_points_blocked")
                )
                return
            if event.button == 1:
                obj_id = self.main_window.object_manager.current_object_id
                before = copy.deepcopy(self.main_window.object_manager.object_points[obj_id][frame_idx])
                self.main_window.object_manager.clear_points(obj_id, frame_idx)
                self.main_window.object_manager.add_point(obj_id, frame_idx, 'positive', x, y)
                self._push_points_command(obj_id, frame_idx, before, label="Replace seed point")
                self.main_window.display_manager.update_display(maintain_global_zoom=True)
            return
        
        # Add points mode: left click = positive, right click / Ctrl+left click = negative
        add_points_radio = self.ui_manager.get_control('add_points_radio')
        if add_points_radio and add_points_radio.isChecked():
            if len(self.main_window.object_manager.selected_object_ids) > 1:
                self.main_window.ui_manager.show_message(
                    "warning", "",
                    self.main_window.localization.get_text("multi_selection_add_points_blocked")
                )
                return
            obj_id = self.main_window.object_manager.current_object_id

            is_ctrl_click = (event.button == 1 and event.key == 'control')
            is_right_click = (event.button == 3)

            if is_right_click or is_ctrl_click:
                point_type = 'negative'
            elif event.button == 1:
                point_type = 'positive'
            else:
                return  # Ignore middle button or other buttons

            # A point outside the object's box on this frame contradicts it (D6)
            box = self.main_window.object_manager.get_box(obj_id, frame_idx)
            if (box is not None
                    and not self.main_window.object_manager.point_in_box(box, x, y)
                    and not self._dont_ask_point_outside_box):
                if not self._confirm_point_outside_box():
                    return

            before = copy.deepcopy(self.main_window.object_manager.object_points[obj_id][frame_idx])
            self.main_window.object_manager.add_point(obj_id, frame_idx, point_type, x, y)
            self._push_points_command(obj_id, frame_idx, before, label=f"Add {point_type} point")

            if self.main_window.debug_mode:
                print(f"Added {point_type} point at ({x:.3f}, {y:.3f}) "
                      f"[button={event.button}, key={event.key}]")

            # Update display
            self.main_window.display_manager.update_display(maintain_global_zoom=True)
    
    def on_motion(self, event):
        """Handle mouse movement during point-removal selection or box definition"""
        if not self.selecting_rect and not self.selecting_box:
            return

        if (event.inaxes != self.ui_manager.canvas.axes or
            not self.main_window.image_manager.has_images()):
            return

        if self.selecting_rect:
            remove_points_radio = self.ui_manager.get_control('remove_points_radio')
            if not remove_points_radio or not remove_points_radio.isChecked():
                return
            self.rect_end = (event.xdata, event.ydata)
            if self.rect:
                self.rect.remove()
            self.rect = self._draw_preview_rect(
                self.rect_start, self.rect_end, edgecolor='r', linestyle='-', linewidth=1)
        else:
            define_box_radio = self.ui_manager.get_control('define_box_radio')
            if not define_box_radio or not define_box_radio.isChecked():
                return
            self.box_end = (event.xdata, event.ydata)
            if self.box_rect:
                self.box_rect.remove()
            self.box_rect = self._draw_preview_rect(
                self.box_start, self.box_end, edgecolor=self._current_box_color(),
                linestyle='--', linewidth=1.5)

    def _draw_preview_rect(self, start, end, edgecolor, linestyle, linewidth):
        """Draw and return the live preview rectangle between two canvas points."""
        if not start or not end:
            return None
        x0, y0 = start
        x1, y1 = end
        rect = patches.Rectangle(
            (x0, y0), x1 - x0, y1 - y0,
            linewidth=linewidth, edgecolor=edgecolor, facecolor='none', linestyle=linestyle
        )
        self.ui_manager.canvas.axes.add_patch(rect)
        self.ui_manager.canvas.draw()
        return rect

    def _current_box_color(self):
        """Mask color of the current object, used for the box preview and display."""
        om = self.main_window.object_manager
        colors = om.object_colors.get(om.current_object_id)
        return colors['mask'].name() if colors else 'w'

    def on_release(self, event):
        """Handle mouse button release"""
        if self.selecting_rect:
            self._finish_point_removal()
        elif self.selecting_box:
            self._finish_box_definition()

    def _finish_point_removal(self):
        """Remove the current object's points inside the rectangle just drawn."""
        remove_points_radio = self.ui_manager.get_control('remove_points_radio')

        self.selecting_rect = False
        start, end = self.rect_start, self.rect_end
        self.rect_start = None
        self.rect_end = None
        if self.rect:
            self.rect.remove()
            self.rect = None

        if not remove_points_radio or not remove_points_radio.isChecked():
            return

        if start and end and self.main_window.image_manager.has_images():
            # Remove points in selection
            x0, y0 = min(start[0], end[0]), min(start[1], end[1])
            x1, y1 = max(start[0], end[0]), max(start[1], end[1])

            # Normalize coordinates
            image_info = self.main_window.image_manager.get_current_image_info()
            h, w = image_info['height'], image_info['width']
            x0, x1 = x0 / w, x1 / w
            y0, y1 = y0 / h, y1 / h

            # Remove points for current object in selected area
            obj_id = self.main_window.object_manager.current_object_id
            frame_idx = self.main_window.image_manager.current_image_idx

            before = copy.deepcopy(
                self.main_window.object_manager.object_points[obj_id][frame_idx]
            )
            self.main_window.object_manager.remove_points_in_area(obj_id, frame_idx, x0, y0, x1, y1)
            self._push_points_command(obj_id, frame_idx, before, label="Remove points in area")

        # Update display
        self.main_window.display_manager.update_display()

    def _finish_box_definition(self):
        """Store the current object's box from the drag just completed."""
        define_box_radio = self.ui_manager.get_control('define_box_radio')

        self.selecting_box = False
        start, end = self.box_start, self.box_end
        self.box_start = None
        self.box_end = None
        if self.box_rect:
            self.box_rect.remove()
            self.box_rect = None
            self.ui_manager.canvas.draw()

        if not define_box_radio or not define_box_radio.isChecked():
            return
        if not start or not end or not self.main_window.image_manager.has_images():
            return

        # A plain click (or a degenerate drag) defines no box
        if (abs(end[0] - start[0]) < self.MIN_BOX_DRAG_PX or
                abs(end[1] - start[1]) < self.MIN_BOX_DRAG_PX):
            return

        image_info = self.main_window.image_manager.get_current_image_info()
        h, w = image_info['height'], image_info['width']
        x0, x1 = sorted((start[0] / w, end[0] / w))
        y0, y1 = sorted((start[1] / h, end[1] / h))
        # Clamp to the image: a release outside the axes keeps the last position
        # seen inside them, but a drag may still reach slightly past the edges.
        x0, y0 = max(x0, 0.0), max(y0, 0.0)
        x1, y1 = min(x1, 1.0), min(y1, 1.0)

        obj_id = self.main_window.object_manager.current_object_id
        frame_idx = self.main_window.image_manager.current_image_idx

        # A box competes with the mask conditioning an import provided (D7)
        delete_mask = False
        if frame_idx in self.main_window.object_manager.mask_import_origin.get(obj_id, set()):
            proceed, delete_mask = self._confirm_box_over_imported_mask()
            if not proceed:
                return

        self._set_box_with_undo(obj_id, frame_idx, (x0, y0, x1, y1),
                                label="Define box", delete_mask=delete_mask)

    def _set_box_with_undo(self, obj_id, frame_idx, box, label, delete_mask=False):
        """Set, replace, or remove (box=None) the object's box on a frame,
        offering to delete the points a new box contradicts and optionally
        deleting the frame's mask, all under a single undo command."""
        om = self.main_window.object_manager

        def _capture():
            return {
                'box': om.get_box(obj_id, frame_idx),
                'points': copy.deepcopy(om.object_points[obj_id][frame_idx]),
                'mask': om.object_masks.get(obj_id, {}).get(frame_idx),
                'imported': frame_idx in om.mask_imported_frames.get(obj_id, set()),
                'import_origin': frame_idx in om.mask_import_origin.get(obj_id, set()),
            }

        def _restore(state):
            if state['box'] is None:
                om.remove_box(obj_id, frame_idx)
            else:
                om.set_box(obj_id, frame_idx, *state['box'])
            om.object_points[obj_id][frame_idx] = copy.deepcopy(state['points'])
            if state['mask'] is None:
                om.remove_mask(obj_id, frame_idx)
            else:
                om.store_mask(obj_id, frame_idx, state['mask'])
            for frames, present in ((om.mask_imported_frames, state['imported']),
                                    (om.mask_import_origin, state['import_origin'])):
                if present:
                    frames.setdefault(obj_id, set()).add(frame_idx)
                else:
                    frames.get(obj_id, set()).discard(frame_idx)
            self.main_window.display_manager.update_display(maintain_global_zoom=True)

        before = _capture()

        if box is None:
            om.remove_box(obj_id, frame_idx)
        else:
            om.set_box(obj_id, frame_idx, *box)
            n_pos, n_neg = om.points_outside_box(obj_id, frame_idx)
            if (n_pos or n_neg) and self._confirm_delete_points_outside_box(n_pos, n_neg):
                om.remove_points_outside_box(obj_id, frame_idx)

        if delete_mask:
            om.remove_mask(obj_id, frame_idx)
            om.mask_imported_frames.get(obj_id, set()).discard(frame_idx)
            om.mask_import_origin.get(obj_id, set()).discard(frame_idx)

        after = _capture()

        self.main_window.history_manager.push(Command(
            undo_fn=lambda: _restore(before),
            redo_fn=lambda: _restore(after),
            label=label,
        ))
        self.main_window.display_manager.update_display(maintain_global_zoom=True)

    def _confirm_delete_points_outside_box(self, n_pos, n_neg):
        """Report the points the new box contradicts and offer to delete them."""
        from PyQt5.QtWidgets import QMessageBox
        loc = self.main_window.localization
        box = QMessageBox(self.main_window)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(loc.get_text("box_points_outside_title"))
        box.setText(loc.get_text("box_points_outside_msg", n_pos, n_neg))
        box.setInformativeText(loc.get_text("box_points_outside_delete_hint"))
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        box.setDefaultButton(QMessageBox.No)
        localize_standard_buttons(box, loc)
        return box.exec_() == QMessageBox.Yes

    def _confirm_box_over_imported_mask(self):
        """Confirm before adding a box to a frame whose mask came from an import,
        offering to delete that mask right away rather than leaving it displayed
        until the next prediction replaces it.

        Returns (proceed, delete_mask)."""
        from PyQt5.QtWidgets import QMessageBox, QCheckBox
        loc = self.main_window.localization
        box = QMessageBox(self.main_window)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(loc.get_text("confirmation"))
        box.setText(loc.get_text("box_mask_import_conflict"))
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        box.setDefaultButton(QMessageBox.Cancel)
        localize_standard_buttons(box, loc)
        checkbox = QCheckBox(loc.get_text("box_delete_imported_mask"))
        box.setCheckBox(checkbox)
        result = box.exec_()
        return result == QMessageBox.Yes, checkbox.isChecked()

    def _confirm_point_outside_box(self):
        """Confirm before adding a point outside the object's box on this frame,
        with a 'don't ask again' checkbox (session-only persistence)."""
        from PyQt5.QtWidgets import QMessageBox, QCheckBox
        loc = self.main_window.localization
        box = QMessageBox(self.main_window)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(loc.get_text("confirmation"))
        box.setText(loc.get_text("point_outside_box_confirm"))
        box.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        localize_standard_buttons(box, loc)
        checkbox = QCheckBox(loc.get_text("dont_ask_again"))
        box.setCheckBox(checkbox)
        result = box.exec_()
        if checkbox.isChecked():
            self._dont_ask_point_outside_box = True
        return result == QMessageBox.Yes

    def remove_box(self):
        """Remove the current object's box on the current frame"""
        om = self.main_window.object_manager
        obj_id = om.current_object_id
        frame_idx = self.main_window.image_manager.current_image_idx
        if om.get_box(obj_id, frame_idx) is None:
            return
        self._set_box_with_undo(obj_id, frame_idx, None, label="Remove box")

    def clear_points(self):
        """Clear all points for the selected object(s) on the current frame"""
        om = self.main_window.object_manager
        frame_idx = self.main_window.image_manager.current_image_idx
        ids = list(om.selected_object_ids)

        before = {oid: copy.deepcopy(om.object_points[oid][frame_idx]) for oid in ids}
        for oid in ids:
            om.clear_points(oid, frame_idx)
        after = {oid: copy.deepcopy(om.object_points[oid][frame_idx]) for oid in ids}

        # Update legacy data for backward compatibility
        if hasattr(self.main_window, 'positive_points'):
            self.main_window.positive_points[frame_idx] = []
        if hasattr(self.main_window, 'negative_points'):
            self.main_window.negative_points[frame_idx] = []

        def _restore(snapshot):
            for oid, pts in snapshot.items():
                om.object_points[oid][frame_idx] = copy.deepcopy(pts)
            self.main_window.display_manager.update_display()

        self.main_window.history_manager.push(Command(
            undo_fn=lambda: _restore(before),
            redo_fn=lambda: _restore(after),
            label="Clear points",
        ))

        self.main_window.display_manager.update_display()
    
    def handle_key_press(self, event):
        """Handle keyboard events"""
        if event.key() == Qt.Key_Left:
            # Left arrow: previous image
            self.main_window.image_manager.prev_image()
        elif event.key() == Qt.Key_Right:
            # Right arrow: next image
            self.main_window.image_manager.next_image()
        else:
            # Let parent class handle other events
            self.main_window.__class__.__bases__[0].keyPressEvent(self.main_window, event)
