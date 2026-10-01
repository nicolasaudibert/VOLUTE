"""
History Manager
Generic undo/redo stack for point edits and property changes
"""

class Command:
    """A single undoable action, described by an undo and a redo closure."""

    def __init__(self, undo_fn, redo_fn, label=""):
        self.undo_fn = undo_fn
        self.redo_fn = redo_fn
        self.label = label


class HistoryManager:
    """Undo/redo stack. Commands pushed while replaying (undo/redo) are ignored,
    so undo_fn/redo_fn can safely call the normal mutation methods."""

    def __init__(self, main_window, max_size=100):
        self.main_window = main_window
        self.undo_stack = []
        self.redo_stack = []
        self.max_size = max_size
        self._replaying = False

    def push(self, command):
        if self._replaying:
            return
        self.undo_stack.append(command)
        if len(self.undo_stack) > self.max_size:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self._refresh_actions()

    def undo(self):
        if not self.undo_stack:
            return
        command = self.undo_stack.pop()
        self._replaying = True
        try:
            command.undo_fn()
        finally:
            self._replaying = False
        self.redo_stack.append(command)
        self._refresh_actions()

    def redo(self):
        if not self.redo_stack:
            return
        command = self.redo_stack.pop()
        self._replaying = True
        try:
            command.redo_fn()
        finally:
            self._replaying = False
        self.undo_stack.append(command)
        self._refresh_actions()

    def can_undo(self):
        return bool(self.undo_stack)

    def can_redo(self):
        return bool(self.redo_stack)

    def clear(self):
        self.undo_stack.clear()
        self.redo_stack.clear()
        self._refresh_actions()

    def _refresh_actions(self):
        if hasattr(self.main_window, 'update_undo_redo_actions'):
            self.main_window.update_undo_redo_actions()
