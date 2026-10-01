"""
Progress Dialog
Advanced progress dialog for long-running operations like SAM2 export/import
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                            QProgressBar, QPushButton, QTextEdit, QApplication,
                            QProgressDialog, QStyle)
from PyQt5.QtCore import Qt, QTimer, QSize, pyqtSignal
from PyQt5.QtGui import QFont

from . import progress_animation

class SAM2ProgressDialog(QDialog):
    """Advanced progress dialog for SAM2 operations with detailed feedback"""
    
    # Signals
    cancelled = pyqtSignal()
    
    def __init__(self, parent=None, title="Operation Progress", 
                 show_details=True, cancellable=True):
        super().__init__(parent)
        
        self.cancelled_by_user = False
        self.show_details = show_details
        self.cancellable = cancellable
        
        self.setWindowTitle(title)
        self.setModal(True)

        self.setup_ui()
        self.steps_with_progress = (
            self.progress_animation is not None
            and progress_animation.configured_pacing(self) == progress_animation.PACING_PROGRESS)

        # Sized after the widgets exist: an animation, when one is installed,
        # takes a row of its own at the top and the dialog has to grow by that
        # much. Without one the height is what it has always been.
        base_height = 300 if show_details else 150
        extra = 0 if self.progress_animation is None else (
            self.progress_animation.height() + self.layout().spacing())
        self.setFixedSize(500, base_height + extra)
        
        # Timer for smooth progress updates
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._process_events)
    
    def _get_details_font_size(self):
        """Get details font size from configuration or use default"""
        try:
            # Try to get font size from parent's config manager
            if hasattr(self.parent(), 'config_manager'):
                return self.parent().config_manager.get_progress_font_size()
            elif hasattr(self.parent(), 'main_window') and hasattr(self.parent().main_window, 'config_manager'):
                return self.parent().main_window.config_manager.get_progress_font_size()
            else:
                # Default font size if no config manager available
                return 12
        except Exception as e:
            print(f"Warning: Could not get font size from config, using default: {e}")
            return 12
    
    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout(self)
        
        # Optional animation, centred above everything else rather than in
        # place of any of it
        animation_row, self.progress_animation = progress_animation.create_centred_row(self)
        if animation_row is not None:
            layout.addLayout(animation_row)

        # Main status label
        self.status_label = QLabel("Initializing...")
        self.status_label.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        self.status_label.setFont(font)
        layout.addWidget(self.status_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        # Sub-status label (for detailed operations)
        self.substatus_label = QLabel("")
        self.substatus_label.setAlignment(Qt.AlignCenter)
        self.substatus_label.setStyleSheet("color: #666666; font-size: 9pt;")
        layout.addWidget(self.substatus_label)
        
        # Details text area (optional)
        if self.show_details:
            layout.addWidget(QLabel("Details:"))
            self.details_text = QTextEdit()
            self.details_text.setMaximumHeight(120)
            
            # Configurable font size for details
            details_font_size = self._get_details_font_size()
            self.details_text.setFont(QFont("Consolas", details_font_size))
            self.details_text.setStyleSheet("background-color: #f8f8f8; border: 1px solid #cccccc;")
            layout.addWidget(self.details_text)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        if self.cancellable:
            self.cancel_button = QPushButton("Cancel")
            self.cancel_button.clicked.connect(self.cancel_operation)
            button_layout.addWidget(self.cancel_button)
        
        # Add stretch to center buttons
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
    
    def update_progress(self, value, status=None, substatus=None, details=None):
        """Update progress with optional status messages"""
        try:
            # Update progress bar
            if isinstance(value, (int, float)):
                self.progress_bar.setValue(min(100, max(0, int(value))))
            
            # Update status label
            if status:
                self.status_label.setText(str(status))
            
            # Update substatus label
            if substatus:
                self.substatus_label.setText(str(substatus))
            elif substatus == "":  # Explicitly clear
                self.substatus_label.setText("")
            
            if self.steps_with_progress:
                progress_animation.step(self.progress_animation)

            # Update details
            if details and self.show_details:
                self.details_text.append(str(details))
                # Auto-scroll to bottom
                cursor = self.details_text.textCursor()
                cursor.movePosition(cursor.End)
                self.details_text.setTextCursor(cursor)
            
            # Process events to keep UI responsive
            QApplication.processEvents()
            
        except Exception as e:
            print(f"Error updating progress dialog: {e}")
    
    def set_indeterminate(self, indeterminate=True):
        """Set progress bar to indeterminate mode"""
        if indeterminate:
            self.progress_bar.setRange(0, 0)  # Indeterminate
        else:
            self.progress_bar.setRange(0, 100)  # Determinate
    
    def showEvent(self, event):
        """Run the animation only while the dialog is on screen"""
        super().showEvent(event)
        if self.steps_with_progress:
            progress_animation.show_first_frame(self.progress_animation)
        else:
            progress_animation.start(self.progress_animation)

    def complete_operation(self, success=True, final_message=None):
        """Mark operation as complete"""
        progress_animation.stop(self.progress_animation)
        if success:
            self.progress_bar.setValue(100)
            if final_message:
                self.status_label.setText(final_message)
            else:
                self.status_label.setText("Operation completed successfully")
            self.substatus_label.setText("")
            
            if hasattr(self, 'cancel_button'):
                self.cancel_button.setText("Close")
                self.cancel_button.clicked.disconnect()
                self.cancel_button.clicked.connect(self.accept)
        else:
            self.status_label.setText(final_message or "Operation failed")
            self.substatus_label.setText("")
            
            if hasattr(self, 'cancel_button'):
                self.cancel_button.setText("Close")
                self.cancel_button.clicked.disconnect()
                self.cancel_button.clicked.connect(self.reject)
    
    def cancel_operation(self):
        """Handle operation cancellation"""
        self.cancelled_by_user = True
        self.status_label.setText("Cancelling operation...")
        self.substatus_label.setText("Please wait...")
        
        if hasattr(self, 'cancel_button'):
            self.cancel_button.setEnabled(False)
        
        # Emit cancelled signal
        self.cancelled.emit()
        
        QApplication.processEvents()
    
    def was_cancelled(self):
        """Check if operation was cancelled by user"""
        return self.cancelled_by_user
    
    def _process_events(self):
        """Process Qt events to keep UI responsive"""
        QApplication.processEvents()
    
    def closeEvent(self, event):
        """Handle dialog close event"""
        progress_animation.stop(self.progress_animation)
        if self.cancellable and not self.cancelled_by_user:
            self.cancel_operation()
        event.accept()

class SAM2ExportProgressDialog(SAM2ProgressDialog):
    """Specialized progress dialog for SAM2 export operations"""
    
    def __init__(self, parent=None):
        super().__init__(parent, 
                        title="Exporting SAM2 Inference State",
                        show_details=True, 
                        cancellable=True)
    
    def update_export_stage(self, stage, progress=None, details=None):
        """Update progress for specific export stages"""
        stage_messages = {
            'initializing': ('Initializing export...', ''),
            'serializing': ('Serializing SAM2 data...', 'Converting tensors and state data'),
            'compressing': ('Compressing data...', 'Creating compressed archive'),
            'saving': ('Saving file...', 'Writing to disk'),
            'complete': ('Export completed successfully', 'File saved successfully')
        }
        
        if stage in stage_messages:
            status, substatus = stage_messages[stage]
            self.update_progress(progress or 0, status, substatus, details)

class SAM2ImportProgressDialog(SAM2ProgressDialog):
    """Specialized progress dialog for SAM2 import operations"""
    
    def __init__(self, parent=None):
        super().__init__(parent, 
                        title="Importing SAM2 Inference State",
                        show_details=True, 
                        cancellable=True)
    
    def update_import_stage(self, stage, progress=None, details=None):
        """Update progress for specific import stages"""
        stage_messages = {
            'loading': ('Loading file...', 'Reading compressed data'),
            'validating': ('Validating data...', 'Checking file integrity'),
            'deserializing': ('Deserializing SAM2 data...', 'Converting data back to tensors'),
            'restoring': ('Restoring inference state...', 'Rebuilding SAM2 state'),
            'synchronizing': ('Synchronizing masks...', 'Updating object manager'),
            'correcting_dimensions': ('Correcting mask dimensions...', 'Resizing masks to match images'),
            'finalizing': ('Finalizing import...', 'Updating display'),
            'complete': ('Import completed successfully', 'All masks restored and displayed')
        }
        
        if stage in stage_messages:
            status, substatus = stage_messages[stage]
            self.update_progress(progress or 0, status, substatus, details)

class AnimatedProgressDialog(QProgressDialog):
    """QProgressDialog showing the optional animation centred above its label.

    A drop-in replacement: everything callers rely on — wasCanceled(),
    canceled(), minimumDuration, autoReset and autoClose — is inherited
    unchanged. With no animation installed the methods below change nothing,
    so the dialog is a plain QProgressDialog down to its geometry.

    QProgressDialog positions its children by hand rather than through a
    layout: the label fills the height above the bar, the cancel button sits
    at the bottom. This class grows the size hint by one animation row and,
    each time Qt lays the children out, moves the label down to free that row.

    configurable_pacing=True makes the dialog honour the pacing setting of
    progress_animation; the operations whose work always ran in a worker
    thread leave it off, their animation having always followed the file.
    """

    # The base constructor already calls sizeHint() and the event handlers
    # below, before __init__ has had a chance to set these
    progress_animation = None
    steps_with_progress = False

    def __init__(self, *args, configurable_pacing=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.progress_animation = progress_animation.create_progress_animation(self)
        if self.progress_animation is not None:
            # The base constructor sized the dialog before the animation existed
            self.resize(self.sizeHint())
            self.steps_with_progress = (
                configurable_pacing
                and progress_animation.configured_pacing(self) == progress_animation.PACING_PROGRESS)

    def setValue(self, value):
        super().setValue(value)
        if self.steps_with_progress:
            progress_animation.step(self.progress_animation)

    def _animation_row_height(self):
        """Height taken above the label: top margin, animation and spacing"""
        style = self.style()
        return (style.pixelMetric(QStyle.PM_LayoutTopMargin, None, self)
                + self.progress_animation.height()
                + style.pixelMetric(QStyle.PM_LayoutVerticalSpacing, None, self))

    def _text_label(self):
        """The label QProgressDialog manages, which it exposes no accessor for"""
        for child in self.findChildren(QLabel, options=Qt.FindDirectChildrenOnly):
            if child is not self.progress_animation:
                return child
        return None

    def _place_animation(self):
        """Put the animation in its row and shrink the label to the rest"""
        if self.progress_animation is None:
            return
        top = self.style().pixelMetric(QStyle.PM_LayoutTopMargin, None, self)
        self.progress_animation.move(
            (self.width() - self.progress_animation.width()) // 2, top)
        label = self._text_label()
        if label is not None:
            area = label.geometry()
            label_top = self._animation_row_height()
            label.setGeometry(area.x(), label_top, area.width(),
                              max(0, area.bottom() + 1 - label_top))

    def sizeHint(self):
        hint = super().sizeHint()
        if self.progress_animation is None:
            return hint
        return hint + QSize(0, self._animation_row_height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._place_animation()

    def changeEvent(self, event):
        # A style change makes QProgressDialog lay its children out again
        super().changeEvent(event)
        self._place_animation()

    def showEvent(self, event):
        """Run the animation only while the dialog is on screen"""
        super().showEvent(event)
        if self.steps_with_progress:
            progress_animation.show_first_frame(self.progress_animation)
        else:
            progress_animation.start(self.progress_animation)

    def hideEvent(self, event):
        progress_animation.stop(self.progress_animation)
        super().hideEvent(event)

# Utility functions for easy use
def show_export_progress(parent=None):
    """Show export progress dialog"""
    return SAM2ExportProgressDialog(parent)

def show_import_progress(parent=None):
    """Show import progress dialog"""
    return SAM2ImportProgressDialog(parent)

def show_generic_progress(parent=None, title="Processing...", 
                         show_details=False, cancellable=True):
    """Show generic progress dialog"""
    return SAM2ProgressDialog(parent, title, show_details, cancellable)