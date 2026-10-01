"""
About Dialog
Displays application credits, license, and citation information.
"""

from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTextBrowser, QDialogButtonBox,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap


class AboutDialog(QDialog):

    # Height when there is no parent to measure, and the floor below which the
    # dialog never shrinks however small the main window is.
    BASE_HEIGHT = 520
    # How much shorter than the main window the dialog stands, so it reads as
    # sitting inside it rather than covering it.
    PARENT_INSET = 60

    def __init__(self, localization, parent=None):
        super().__init__(parent)
        self.setWindowTitle(localization.get_text("about_title"))
        self.setMinimumWidth(540)

        height = self.BASE_HEIGHT
        if parent is not None and parent.height() > 0:
            height = max(height, parent.height() - self.PARENT_INSET)
        self.resize(560, height)

        self._setup_ui(localization)

    def _setup_ui(self, loc):
        v = QVBoxLayout(self)

        # Logo, when one is installed. about_logo.png is expected to carry the
        # name itself, so the text title steps aside for it; the plain icon does
        # not, and sits above the title.
        logo, carries_name = _find_logo()
        if logo is not None:
            image = QLabel()
            image.setPixmap(logo)
            image.setAlignment(Qt.AlignCenter)
            v.addWidget(image)

        if logo is None or not carries_name:
            title = QLabel(loc.get_text("window_title"))
            title.setAlignment(Qt.AlignCenter)
            title.setStyleSheet("font-size: 16px; font-weight: bold;")
            v.addWidget(title)

        subtitle = QLabel(loc.get_text("about_subtitle"))
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        v.addWidget(subtitle)

        # Imported here rather than at module level, since the package defines
        # __version__ after importing the modules that lead to this one
        from . import __version__
        version = QLabel(loc.get_text("about_version", __version__))
        version.setAlignment(Qt.AlignCenter)
        version.setStyleSheet("color: gray; margin-bottom: 4px;")
        v.addWidget(version)

        # Scrollable content
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(_build_html(loc))
        v.addWidget(browser)

        # Close button
        bb = QDialogButtonBox(QDialogButtonBox.Close)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)


def _find_logo():
    """Return (pixmap, carries_name) for the About dialog, or (None, False).

    about_logo.png is a lockup including the application name — a transparent
    background suits it best; icon_128.png is the plain application icon.
    """
    resources = Path(__file__).parent / "resources"
    lockup = resources / "about_logo.png"
    if lockup.exists():
        return QPixmap(str(lockup)).scaledToWidth(320, Qt.SmoothTransformation), True
    icon = resources / "icon_128.png"
    if icon.exists():
        return QPixmap(str(icon)).scaledToWidth(96, Qt.SmoothTransformation), False
    return None, False


def _build_html(loc):
    return f"""
<style>
  body  {{ font-family: sans-serif; font-size: 13px; margin: 8px; }}
  h3    {{ margin-top: 14px; margin-bottom: 4px; }}
  pre   {{ background: #f4f4f4; padding: 8px; border-radius: 4px;
           font-size: 11px; white-space: pre-wrap; }}
  a     {{ color: #0066cc; }}
</style>

<h3>{loc.get_text("about_credits_title")}</h3>
<p>{loc.get_text("about_credits_body")} {loc.get_text("about_logo_credit")}</p>

<h3>{loc.get_text("about_repository_title")}</h3>
<p>{loc.get_text("about_repository_body")}</p>

<h3>{loc.get_text("about_license_title")}</h3>
<p>{loc.get_text("about_license_body")}</p>

<h3>{loc.get_text("about_sam2_title")}</h3>
<p>{loc.get_text("about_sam2_body")}</p>
<pre>@article{{ravi2024sam2,
  title   = {{SAM 2: Segment Anything in Video}},
  author  = {{Ravi, Nikhila and Gabeur, Valentin and Hu, Yuan-Ting and
             Hu, Ronghang and Ryali, Chaitanya and Ma, Tengyu and
             Khedr, Haitham and R{{\"a}}dle, Roman and Rolland, Chloe and
             Gustafson, Laura and Mintun, Eric and Pan, Junting and
             Alwala, Kalyan Vasudev and Carion, Nicolas and Wu, Chao-Yuan and
             Girshick, Ross and Doll{{\'a}}r, Piotr and
             Feichtenhofer, Christoph}},
  journal = {{arXiv preprint arXiv:2408.00714}},
  year    = {{2024}}
}}</pre>

<h3>{loc.get_text("about_medsam2_title")}</h3>
<p>{loc.get_text("about_medsam2_body")}</p>
<pre>@article{{ma2025medsam2,
  title   = {{MedSAM2: Segment Anything in 3D Medical Images and Videos}},
  author  = {{Ma, Jun and Chen, Zitian and Vochescu, Alexandru and others}},
  journal = {{arXiv preprint arXiv:2504.03600}},
  year    = {{2025}}
}}</pre>

<h3>{loc.get_text("about_sam2plus_title")}</h3>
<p>{loc.get_text("about_sam2plus_body")}</p>
<pre>@article{{zhang2025sam2trackinggranularity,
  title   = {{SAM 2++: Tracking Anything at Any Granularity}},
  author  = {{Zhang, Jiaming and Liang, Cheng and Yang, Yichun and
             Zeng, Chenkai and Cui, Yutao and Zhang, Xinwen and Zhou, Xin and
             Ma, Kai and Wu, Gangshan and Wang, Limin}},
  journal = {{arXiv preprint arXiv:2510.18822}},
  url     = {{https://arxiv.org/abs/2510.18822}},
  year    = {{2025}}
}}</pre>
"""
