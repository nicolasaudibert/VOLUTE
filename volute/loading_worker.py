"""
Loading Worker
QThread worker for background SAM2 inference state initialization
"""
from PyQt5.QtCore import QThread, pyqtSignal


class LoadFolderWorker(QThread):
    """
    Runs sam2_backend.init_inference_state in a background thread.
    Relays per-frame progress to drive a QProgressDialog on the main thread.
    """
    progress = pyqtSignal(int, int, str)   # current, total, phase ("prepare"|"init")
    finished = pyqtSignal(bool)            # success flag
    error    = pyqtSignal(str)             # error message, if any

    def __init__(self, sam2_backend, folder, parent=None):
        super().__init__(parent)
        self.sam2_backend = sam2_backend
        self.folder       = folder
        self.cancelled    = False   # checked inside _prepare_sam2_images

    def cancel(self):
        """Request cancellation; honoured at the next frame boundary."""
        self.cancelled = True

    def run(self):
        try:
            ok = self.sam2_backend.init_inference_state(
                self.folder,
                progress_callback=self._emit_progress,
                cancelled_flag=self,
            )
            self.finished.emit(ok)
        except Exception as e:
            self.error.emit(str(e))
            self.finished.emit(False)

    def _emit_progress(self, current, total, phase):
        if not self.cancelled:
            self.progress.emit(current, total, phase)
