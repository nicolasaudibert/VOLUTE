from .main_window import SAM2VideoSegmentationApp
from .localization import LocalizationManager
from .file_utils import FileManager
from .sam2_backend import SAM2Backend
from .object_manager import ObjectManager
from .canvas import Canvas, CustomNavigationToolbar
from .exporters import ImageExporter, CoordinateExporter, CentroidExporter
from .inference_state_manager import InferenceStateManager

# Application version — single source of truth, read by the launcher and by
# install_app_bundle_macos.sh. Distinct from the .volute file format version
# (ProjectStateManager.PROJECT_VERSION), which tracks the schema instead.
__version__ = "0.9.1"
__author__ = "Nicolas Audibert"

__all__ = [
    'SAM2VideoSegmentationApp',
    'LocalizationManager', 
    'FileManager',
    'SAM2Backend',
    'ObjectManager',
    'Canvas',
    'CustomNavigationToolbar',
    'ImageExporter',
    'CoordinateExporter',
    'CentroidExporter',
    'InferenceStateManager'
]