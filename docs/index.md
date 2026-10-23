# VOLUTE

*[Version française](index.fr.md)*

**V**ideo **O**bject **L**abeling, **U**ser-guided **T**racking and **E**xtraction

VOLUTE is a desktop application for segmenting and tracking objects through a
sequence of video frames. Mark an object with a box and a few points on one frame;
VOLUTE follows it through the whole sequence, with
[SAM 2](https://github.com/facebookresearch/segment-anything-2),
[MedSAM2](https://github.com/bowang-lab/MedSAM2) or
[SAM2++](https://github.com/MCG-NJU/SAM2-Plus), and exports masks, coordinates,
centroids and contours. Everything runs on your own computer.

This application was developed for research in speech sciences, to track articulatory
structures across video frames, but none of the methods it implements is specific to that
field. VOLUTE can therefore be applied in other fields where the analysis of video data is
relevant.

## Installing

One command installs VOLUTE and everything it needs, Python included, into a folder
of its own. The guides walk through it without assuming any knowledge of the command
line:

- [Installing VOLUTE on Windows](install-windows.md)
- [Installing VOLUTE on macOS](install-macos.md)
- [Installing VOLUTE on Linux (Ubuntu)](install-linux.md)

On another Linux distribution, or to install by hand, see
[INSTALL.md](https://github.com/nicolasaudibert/VOLUTE/blob/main/INSTALL.md).

## Using VOLUTE

- The [tutorial](tutorial/index.md) walks through VOLUTE one step at a time, with
  screenshots, on a short dynamic MRI video of a speaker.
- The [Getting started](https://github.com/nicolasaudibert/VOLUTE/blob/main/README.md#getting-started)
  section of the README sums up a first session in eight steps.
- The [FAQ](faq.md) answers the most common questions.
- The [reference documentation](https://github.com/nicolasaudibert/VOLUTE/blob/main/DOCUMENTATION.md)
  describes every feature in detail.

## Source code and help

VOLUTE is free software, under the
[GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0.html). Its
source code is on [GitHub](https://github.com/nicolasaudibert/VOLUTE), where
questions and problems can be reported as
[issues](https://github.com/nicolasaudibert/VOLUTE/issues). To cite it, see
[How do I cite VOLUTE?](faq.md#how-do-i-cite-volute)
