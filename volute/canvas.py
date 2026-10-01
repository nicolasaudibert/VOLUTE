"""
Canvas and Navigation Components
Handles the matplotlib canvas and custom navigation toolbar
"""

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from PyQt5.QtWidgets import QSizePolicy

class Canvas(FigureCanvas):
    """Custom matplotlib canvas for image display"""
    
    def __init__(self, parent=None, width=8, height=6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = self.fig.add_subplot(111)
        self.axes.axis('off')
        
        super(Canvas, self).__init__(self.fig)
        self.setParent(parent)
        
        FigureCanvas.setSizePolicy(self,
                                   QSizePolicy.Expanding,
                                   QSizePolicy.Expanding)
        FigureCanvas.updateGeometry(self)
    
    def clear_display(self):
        """Clear the canvas"""
        self.axes.clear()
        self.axes.axis('off')
        self.draw()
    
    def set_title(self, title):
        """Set canvas title"""
        self.axes.set_title(title)
        self.draw()

class CustomNavigationToolbar(NavigationToolbar):
    """Enhanced navigation toolbar with custom functionality"""
    
    def __init__(self, canvas, parent, coordinates=True, debug_mode=False):
        super().__init__(canvas, parent, coordinates)
        self.parent_app = None
        self.debug_mode = debug_mode
        
        # Add flags to track state
        self.tool_activated = False
        self.zoom_started = False
        self.zoombox_start = None
        
        # Remove unwanted buttons
        self._remove_unwanted_actions()
        
        # Connect navigation signals
        self._connect_navigation_actions()
    
    def _remove_unwanted_actions(self):
        """Remove unwanted toolbar buttons"""
        actions_to_remove = []
        for action in self.actions():
            # Remove "Subplots" button
            if action.text() in ["Configure subplots", "Subplots"]:
                actions_to_remove.append(action)
        
        for action in actions_to_remove:
            self.removeAction(action)
            if self.debug_mode:
                print(f"Removed toolbar action: {action.text()}")
    
    def _connect_navigation_actions(self):
        """Connect navigation button actions"""
        for action in self.actions():
            if action.text() in ["Home", "Back", "Forward", "Pan", "Zoom"]:
                action.triggered.connect(self.on_navigation_action)
    
    def on_navigation_action(self):
        """Handle navigation button actions"""
        action = self.sender()
        action_text = action.text() if hasattr(action, "text") else "Unknown"
        
        if self.debug_mode:
            print(f"Navigation action triggered: {action_text}")
        
        # Handle different actions
        if action_text == "Home":
            # When returning to original view, reset global zoom
            if self.parent_app and hasattr(self.parent_app, 'reset_global_zoom'):
                self.parent_app.reset_global_zoom()
        elif action_text in ["Back", "Forward", "Pan"]:
            # Capture new zoom after navigation
            if self.parent_app and hasattr(self.parent_app, 'capture_global_zoom_state'):
                self.parent_app.capture_global_zoom_state()
    
    def press_zoom(self, event):
        """Intercept zoom operation start"""
        if self.debug_mode:
            print("Zoom started")
        self.zoom_started = True
        
        # Keep initial click location to check area later
        if event.xdata is not None and event.ydata is not None:
            self.zoombox_start = (event.xdata, event.ydata)
        
        # Let parent class handle normal action
        super().press_zoom(event)
    
    def release_zoom(self, event):
        """Intercept zoom operation end"""
        if self.debug_mode:
            print("Zoom completed")
        
        # Check if zoom generated a valid area
        valid_zoom = False
        if (hasattr(self, 'zoombox_start') and self.zoombox_start is not None and 
            event.xdata is not None and event.ydata is not None):
            # Calculate distance to check if it's a real zoom or just a click
            xdiff = abs(self.zoombox_start[0] - event.xdata)
            ydiff = abs(self.zoombox_start[1] - event.ydata)
            # If area is significant, consider as valid zoom
            valid_zoom = xdiff > 5 and ydiff > 5
        
        # Call original method
        super().release_zoom(event)
        
        # Process zoom only if valid
        if self.zoom_started:
            if valid_zoom and self.parent_app and hasattr(self.parent_app, 'capture_global_zoom_state'):
                # Capture new zoom state
                self.parent_app.capture_global_zoom_state()
            
            # Force deactivation of zoom mode
            self._deactivate_zoom()
            self.zoom_started = False
    
    def _deactivate_zoom(self):
        """Deactivate zoom mode (compatible with different matplotlib versions)"""
        try:
            active_mode = getattr(self, '_active', None)
            if active_mode == "ZOOM":
                if self.debug_mode:
                    print("Deactivating zoom")
                self.zoom()
        except AttributeError:
            # Fallback if _active doesn't exist
            try:
                if self.debug_mode:
                    print("Alternative zoom deactivation attempt")
                self.zoom()
            except:
                pass  # Ignore if zoom deactivation fails
    
    def set_parent_app(self, parent_app):
        """Set reference to parent application"""
        self.parent_app = parent_app
    
    def is_tool_active(self):
        """
        Check if a toolbar tool (zoom, pan, etc.) is active
        Compatible with different Matplotlib versions
        """
        # Try multiple possible attributes to find active tool
        if hasattr(self, '_active'):
            return self._active is not None
        elif hasattr(self, 'mode'):
            return self.mode != ''
        elif hasattr(self, '_actions'):
            # Check if an action is active via checked property
            try:
                for action in self._actions.values():
                    if action.isChecked():
                        return True
            except:
                pass
        
        # Default return False
        return False
    
    def get_current_tool(self):
        """Get currently active tool name"""
        if hasattr(self, '_active'):
            return self._active
        elif hasattr(self, 'mode'):
            return self.mode
        else:
            return None
    
    def reset_tool(self):
        """Reset to default tool (no tool active)"""
        try:
            # Try to deactivate current tool
            if hasattr(self, 'pan'):
                if self.is_tool_active():
                    current_tool = self.get_current_tool()
                    if current_tool == "PAN":
                        self.pan()
                    elif current_tool == "ZOOM":
                        self.zoom()
        except:
            pass  # Ignore errors during tool reset
        
        if self.debug_mode:
            print("Toolbar reset to default state")
