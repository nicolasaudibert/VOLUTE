"""
Property Controller
Undo-backed property setters for object/point, tracked point display,
reference point, and imported point properties — each following the same
before/after snapshot, _apply, history_manager.push(Command(...)) pattern.
"""


class PropertyController:
    """Property setters delegated to from main_window. Accesses main_window's
    managers via self.main_window.<attr> rather than caching references, so
    it keeps working if a manager is ever re-instantiated."""

    def __init__(self, main_window):
        self.main_window = main_window

    # ------------------------------------------------------------------
    # Object / point properties
    # ------------------------------------------------------------------

    def choose_object_color(self, color_type):
        """Choose color for all selected objects, with undo support"""
        from PyQt5.QtWidgets import QColorDialog
        from PyQt5.QtGui import QColor
        from .history_manager import Command

        mw = self.main_window
        obj_id = mw.object_manager.current_object_id
        current_color = mw.object_manager.object_colors[obj_id][color_type]

        if color_type == "mask":
            color = QColorDialog.getColor(current_color, mw, f"Choose {color_type} color",
                                        QColorDialog.ShowAlphaChannel)
        else:
            color = QColorDialog.getColor(current_color, mw, f"Choose {color_type} color")

        if color.isValid():
            ids = list(mw.object_manager.selected_object_ids)
            before = {oid: QColor(mw.object_manager.object_colors[oid][color_type]) for oid in ids}
            after = {oid: QColor(color) for oid in ids}

            def _apply(snapshot):
                for oid, c in snapshot.items():
                    mw.object_manager.update_object_color(oid, color_type, c)
                mw.ui_manager.update_object_ui()
                mw.update_display(maintain_global_zoom=True)

            _apply(after)
            mw.history_manager.push(Command(
                undo_fn=lambda: _apply(before),
                redo_fn=lambda: _apply(after),
            ))

    def update_object_marker_style(self):
        """Update marker style for all selected objects, with undo support"""
        from .history_manager import Command
        mw = self.main_window
        combo = mw.ui_manager.get_control('obj_marker_combo')
        if not combo:
            return
        style = combo.currentData()
        ids = list(mw.object_manager.selected_object_ids)
        before = {oid: mw.object_manager.object_markers[oid]['style'] for oid in ids}
        after = {oid: style for oid in ids}

        def _apply(snapshot):
            for oid, s in snapshot.items():
                mw.object_manager.update_object_marker(oid, style=s)
            mw.update_display(maintain_global_zoom=True)

        _apply(after)
        mw.history_manager.push(Command(
            undo_fn=lambda: _apply(before),
            redo_fn=lambda: _apply(after),
        ))

    def update_object_marker_size(self):
        """Update marker size for all selected objects, with undo support"""
        from .history_manager import Command
        mw = self.main_window
        slider = mw.ui_manager.get_control('obj_marker_size_slider')
        if not slider:
            return
        size = slider.value()
        ids = list(mw.object_manager.selected_object_ids)
        before = {oid: mw.object_manager.object_markers[oid]['size'] for oid in ids}
        after = {oid: size for oid in ids}

        def _apply(snapshot):
            for oid, s in snapshot.items():
                mw.object_manager.update_object_marker(oid, size=s)
            mw.update_display(maintain_global_zoom=True)

        _apply(after)
        mw.history_manager.push(Command(
            undo_fn=lambda: _apply(before),
            redo_fn=lambda: _apply(after),
        ))

    def update_object_mask_opacity(self):
        """Update mask opacity for all selected objects, with undo support"""
        from PyQt5.QtGui import QColor
        from .history_manager import Command
        mw = self.main_window
        slider = mw.ui_manager.get_control('obj_mask_opacity_slider')
        if not slider:
            return
        opacity = slider.value() / 100
        ids = list(mw.object_manager.selected_object_ids)
        before = {oid: mw.object_manager.object_colors[oid]['mask'].alphaF() for oid in ids}
        after = {oid: opacity for oid in ids}

        def _apply(snapshot):
            for oid, a in snapshot.items():
                color = mw.object_manager.object_colors[oid]['mask']
                color.setAlphaF(a)
                mw.object_manager.object_colors[oid]['mask'] = color
            mw.update_display(maintain_global_zoom=True)

        _apply(after)
        mw.history_manager.push(Command(
            undo_fn=lambda: _apply(before),
            redo_fn=lambda: _apply(after),
        ))

    # ------------------------------------------------------------------
    # Tracked point display (SAM2++ point mode)
    # ------------------------------------------------------------------

    def update_tracked_point_style(self):
        from .history_manager import Command
        mw = self.main_window
        combo = mw.ui_manager.get_control('tracked_point_style_combo')
        if not combo:
            return
        style = combo.currentData()
        before, after = mw.object_manager.tracked_point_style, style

        def _apply(value):
            mw.object_manager.tracked_point_style = value
            mw.update_display(maintain_global_zoom=True)

        _apply(after)
        mw.history_manager.push(Command(
            undo_fn=lambda: _apply(before),
            redo_fn=lambda: _apply(after),
        ))

    def update_tracked_point_size(self):
        from .history_manager import Command
        mw = self.main_window
        slider = mw.ui_manager.get_control('tracked_point_size_slider')
        if not slider:
            return
        size = slider.value()
        before, after = mw.object_manager.tracked_point_size, size

        def _apply(value):
            mw.object_manager.tracked_point_size = value
            mw.update_display(maintain_global_zoom=True)

        _apply(after)
        mw.history_manager.push(Command(
            undo_fn=lambda: _apply(before),
            redo_fn=lambda: _apply(after),
        ))

    # ------------------------------------------------------------------
    # Reference point properties
    # ------------------------------------------------------------------

    def choose_ref_point_color(self):
        """Choose color for all selected reference points, with undo support"""
        from PyQt5.QtWidgets import QColorDialog
        from PyQt5.QtGui import QColor
        from .history_manager import Command

        mw = self.main_window
        rpm = mw.ref_point_manager
        current = rpm.current_ref_point_name
        if not current:
            return
        current_color = rpm.ref_point_colors.get(current, QColor(rpm.default_color))

        color = QColorDialog.getColor(current_color, mw, "Choose reference point color")
        if not color.isValid():
            return

        names = list(rpm.selected_ref_point_names) or [current]
        before = {n: QColor(rpm.ref_point_colors[n]) for n in names if n in rpm.ref_point_colors}
        after = {n: QColor(color) for n in names}

        def _apply(snapshot):
            for n, c in snapshot.items():
                rpm.ref_point_colors[n] = QColor(c)
            mw.ui_manager.ref_point_controls.update_ref_point_ui()
            mw.update_display(maintain_global_zoom=True)

        _apply(after)
        mw.history_manager.push(Command(
            undo_fn=lambda: _apply(before),
            redo_fn=lambda: _apply(after),
        ))

    def update_ref_point_marker_style(self):
        """Update marker style for all selected reference points, with undo support"""
        from .history_manager import Command
        mw = self.main_window
        combo = mw.ui_manager.get_control('ref_point_marker_combo')
        if not combo:
            return
        style = combo.currentData()
        rpm = mw.ref_point_manager
        current = rpm.current_ref_point_name
        if not current:
            return
        names = list(rpm.selected_ref_point_names) or [current]
        before = {n: rpm.ref_point_markers[n]['style'] for n in names if n in rpm.ref_point_markers}
        after = {n: style for n in names}

        def _apply(snapshot):
            for n, s in snapshot.items():
                rpm.ref_point_markers.setdefault(n, {'style': s, 'size': rpm.default_marker_size})
                rpm.ref_point_markers[n]['style'] = s
            mw.ui_manager.ref_point_controls.update_ref_point_ui()
            mw.update_display(maintain_global_zoom=True)

        _apply(after)
        mw.history_manager.push(Command(
            undo_fn=lambda: _apply(before),
            redo_fn=lambda: _apply(after),
        ))

    def update_ref_point_marker_size(self):
        """Update marker size for all selected reference points, with undo support"""
        from .history_manager import Command
        mw = self.main_window
        slider = mw.ui_manager.get_control('ref_point_marker_size_slider')
        if not slider:
            return
        size = slider.value()
        rpm = mw.ref_point_manager
        current = rpm.current_ref_point_name
        if not current:
            return
        names = list(rpm.selected_ref_point_names) or [current]
        before = {n: rpm.ref_point_markers[n]['size'] for n in names if n in rpm.ref_point_markers}
        after = {n: size for n in names}

        def _apply(snapshot):
            for n, s in snapshot.items():
                rpm.ref_point_markers.setdefault(n, {'style': rpm.default_marker, 'size': s})
                rpm.ref_point_markers[n]['size'] = s
            mw.ui_manager.ref_point_controls.update_ref_point_ui()
            mw.update_display(maintain_global_zoom=True)

        _apply(after)
        mw.history_manager.push(Command(
            undo_fn=lambda: _apply(before),
            redo_fn=lambda: _apply(after),
        ))

    def update_ref_point_extrapolation_policy(self):
        """Update extrapolation policy for all selected reference points, with undo support"""
        from .history_manager import Command
        mw = self.main_window
        combo = mw.ui_manager.get_control('ref_point_extrapolation_combo')
        if not combo:
            return
        policy = combo.currentData()
        rpm = mw.ref_point_manager
        current = rpm.current_ref_point_name
        if not current:
            return
        names = list(rpm.selected_ref_point_names) or [current]
        before = {n: rpm.ref_point_extrapolation_policy.get(n, rpm.default_extrapolation_policy) for n in names}
        after = {n: policy for n in names}

        def _apply(snapshot):
            for n, p in snapshot.items():
                rpm.ref_point_extrapolation_policy[n] = p
            mw.update_display(maintain_global_zoom=True)

        _apply(after)
        mw.history_manager.push(Command(
            undo_fn=lambda: _apply(before),
            redo_fn=lambda: _apply(after),
        ))

    def update_ref_point_interpolation_mode(self):
        """Update interpolation mode for all selected reference points, with undo support"""
        from .history_manager import Command
        mw = self.main_window
        combo = mw.ui_manager.get_control('ref_point_interpolation_combo')
        if not combo:
            return
        mode = combo.currentData()
        rpm = mw.ref_point_manager
        current = rpm.current_ref_point_name
        if not current:
            return
        names = list(rpm.selected_ref_point_names) or [current]
        before = {n: rpm.ref_point_interpolation_mode.get(n, rpm.default_interpolation_mode) for n in names}
        after = {n: mode for n in names}

        def _apply(snapshot):
            for n, m in snapshot.items():
                rpm.ref_point_interpolation_mode[n] = m
            mw.update_display(maintain_global_zoom=True)

        _apply(after)
        mw.history_manager.push(Command(
            undo_fn=lambda: _apply(before),
            redo_fn=lambda: _apply(after),
        ))

    # ------------------------------------------------------------------
    # Imported point properties
    # ------------------------------------------------------------------

    def choose_imported_point_color(self):
        """Choose color for the currently selected imported point, with undo support"""
        from PyQt5.QtWidgets import QColorDialog
        from PyQt5.QtGui import QColor
        from .history_manager import Command

        mw = self.main_window
        ipm = mw.imported_point_manager
        current = ipm.current_imported_point_name
        if not current:
            return
        current_color = ipm.imported_point_colors.get(current, QColor(ipm.default_color))

        color = QColorDialog.getColor(current_color, mw, "Choose imported point color")
        if not color.isValid():
            return

        before, after = QColor(current_color), QColor(color)

        def _apply(c):
            ipm.imported_point_colors[current] = QColor(c)
            mw.ui_manager.imported_point_controls.update_imported_point_ui()
            mw.update_display(maintain_global_zoom=True)

        _apply(after)
        mw.history_manager.push(Command(
            undo_fn=lambda: _apply(before),
            redo_fn=lambda: _apply(after),
        ))

    def update_imported_point_marker_style(self):
        """Update marker style for the currently selected imported point, with undo support"""
        from .history_manager import Command
        mw = self.main_window
        combo = mw.ui_manager.get_control('imported_point_marker_combo')
        ipm = mw.imported_point_manager
        current = ipm.current_imported_point_name
        if not combo or not current:
            return
        style = combo.currentData()
        before = ipm.imported_point_markers[current]['style']
        after = style

        def _apply(s):
            ipm.imported_point_markers.setdefault(
                current, {'style': s, 'size': ipm.default_marker_size}
            )
            ipm.imported_point_markers[current]['style'] = s
            mw.update_display(maintain_global_zoom=True)

        _apply(after)
        mw.history_manager.push(Command(
            undo_fn=lambda: _apply(before),
            redo_fn=lambda: _apply(after),
        ))

    def update_imported_point_marker_size(self):
        """Update marker size for the currently selected imported point, with undo support"""
        from .history_manager import Command
        mw = self.main_window
        slider = mw.ui_manager.get_control('imported_point_marker_size_slider')
        ipm = mw.imported_point_manager
        current = ipm.current_imported_point_name
        if not slider or not current:
            return
        size = slider.value()
        before = ipm.imported_point_markers[current]['size']
        after = size

        def _apply(s):
            ipm.imported_point_markers.setdefault(
                current, {'style': ipm.default_marker, 'size': s}
            )
            ipm.imported_point_markers[current]['size'] = s
            mw.update_display(maintain_global_zoom=True)

        _apply(after)
        mw.history_manager.push(Command(
            undo_fn=lambda: _apply(before),
            redo_fn=lambda: _apply(after),
        ))
