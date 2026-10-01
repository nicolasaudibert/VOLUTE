"""
Progress Worker
Runs a long operation in a worker thread behind a modal progress dialog, so
the GUI thread stays free to repaint the dialog and play its animation.
"""

import threading

from PyQt5.QtCore import QThread, QEventLoop, pyqtSignal


class _TaskThread(QThread):
    """Runs task(report, is_cancelled) and keeps its outcome for the GUI thread"""

    # Positional and keyword arguments of one report() call
    reported = pyqtSignal(object, object)
    # Named apart from QThread.finished, which it would otherwise shadow
    returned = pyqtSignal()

    def __init__(self, task, cancel_event):
        super().__init__()
        self.task = task
        self.cancel_event = cancel_event
        self.result = None
        self.error = None

    def run(self):
        try:
            self.result = self.task(self.report, self.cancel_event.is_set)
        except Exception as e:
            self.error = e
        self.returned.emit()

    def report(self, *args, **kwargs):
        self.reported.emit(args, kwargs)


def _update_progress_dialog(dialog):
    """Default report handler for a QProgressDialog: report(value, label),
    either left as None to keep what the dialog shows"""
    def handle(value=None, label=None):
        if label is not None:
            dialog.setLabelText(label)
        if value is not None:
            dialog.setValue(value)
    return handle


def run_with_progress(dialog, task, on_report=None):
    """Run task(report, is_cancelled) in a worker thread and return its result.

    The caller creates and shows the dialog; this waits in a local event loop
    until the task returns, so the dialog stays responsive and modal meanwhile.
    Each report(...) made by the task reaches on_report(...) on the GUI thread,
    in order; by default it drives a QProgressDialog as report(value, label).
    is_cancelled() becomes True once the dialog's cancel signal fires, and
    stands in for polling the dialog, which is not safe from another thread.
    An exception raised by the task is raised again here, on the GUI thread.

    The task must not touch widgets: whatever it has to show goes through
    report(), and messages belong to the caller once this returns.
    """
    if on_report is None:
        on_report = _update_progress_dialog(dialog)
    # QProgressDialog names its signal canceled, SAM2ProgressDialog cancelled
    cancel_signal = getattr(dialog, "canceled", None) or dialog.cancelled

    cancel_event = threading.Event()
    returned = [False]
    thread = _TaskThread(task, cancel_event)
    loop = QEventLoop()

    def on_cancel():
        # Closing the dialog also emits the cancel signal: ignore it once the
        # task is done
        if not returned[0]:
            cancel_event.set()

    def on_returned():
        returned[0] = True
        loop.quit()

    thread.reported.connect(lambda args, kwargs: on_report(*args, **kwargs))
    thread.returned.connect(on_returned)
    cancel_signal.connect(on_cancel)
    try:
        thread.start()
        loop.exec_()
        thread.wait()
    finally:
        cancel_signal.disconnect(on_cancel)

    if thread.error is not None:
        raise thread.error
    return thread.result
