"""
VOLUTE tutorial excerpt
Builds docs/tutorial/nancy_P1_S1_excerpt.mp4, the video the tutorial works on,
from the Nancy real-time MRI corpus, whose reference CITATION gives; its data
are on figshare, under CC0.

The excerpt is speaker 1 saying SENTENCE, the first sentence of sequence 1:
111 frames, 20 ms apart, from 1.04 s to 3.26 s. Only those frames and the
denoised sound are fetched, through HTTP range requests into the speaker's
2.5 GB archive, not the archive itself; excerpt_frames.txt lists them. Each
136 x 136 frame of 12-bit DICOM is windowed to 8 bits, the same window for the
whole excerpt, and enlarged four times, then ffmpeg encodes the frames and the
matching sound.

Requires pydicom, NumPy, Pillow and ffmpeg.

    python tutorial/make_excerpt.py
"""

import argparse
import io
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pydicom
from PIL import Image

HERE = Path(__file__).resolve().parent
OUTPUT = HERE.parent / "docs" / "tutorial" / "nancy_P1_S1_excerpt.mp4"
FRAME_LIST = HERE / "excerpt_frames.txt"

CITATION = (
    "Isaieva K., Laprie Y., Leclère J., Douros I. K., Felblinger J., Vuissoz P.-A. (2021). "
    "Multimodal dataset of real-time 2D and static 3D MRI of healthy French speakers. "
    "Scientific Data 8, 258."
)

# Speaker 1's archive
FIGSHARE_ARCHIVE_URL = "https://ndownloader.figshare.com/files/28531992"
FRAME_DIR = "P1/DCM_2D/S1/"
DENOISED_SOUND = "P1/OTHER/S1/DENOISED_SOUND_P1_S1.wav"
SENTENCE = "Le filou et la fripouille"

FRAME_RATE = 50
# Instance n is acquired at (n - 1) / 50 s from the start of the sound
FIRST_INSTANCE = 53
SCALE = 4
# Intensity window, as percentiles of the whole excerpt
WINDOW = (0.5, 99.8)
FFMPEG = "ffmpeg"


class RemoteFile(io.RawIOBase):
    """Seekable, read-only view of a remote file, read through HTTP range
    requests, so that zipfile reads the archive's directory and the members
    asked for, and nothing else."""

    def __init__(self, url):
        self.source = url
        self.position = 0
        self.refresh()

    def refresh(self):
        # figshare redirects to a signed storage address, which expires
        response = urllib.request.urlopen(urllib.request.Request(self.source, method="HEAD"))
        self.url = response.geturl()
        self.size = int(response.headers["Content-Length"])

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.position

    def seek(self, offset, whence=io.SEEK_SET):
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self.position, io.SEEK_END: self.size}[whence]
        self.position = base + offset
        return self.position

    def readinto(self, buffer):
        count = min(len(buffer), self.size - self.position)
        if count <= 0:
            return 0
        byte_range = f"bytes={self.position}-{self.position + count - 1}"
        for attempt in range(3):
            request = urllib.request.Request(self.url, headers={"Range": byte_range})
            try:
                data = urllib.request.urlopen(request).read()
                break
            except urllib.error.HTTPError as error:
                if error.code != 403 or attempt == 2:
                    raise
                self.refresh()
        buffer[:len(data)] = data
        self.position += len(data)
        return len(data)


def read_frame_list():
    """(instance number, file name) pairs of excerpt_frames.txt, in order."""
    frames = []
    for line in FRAME_LIST.read_text().splitlines():
        if line and not line.startswith("#"):
            number, name = line.split()
            frames.append((int(number), name))
    return frames


def fetch(frames, workdir):
    print(f"Fetching {len(frames)} frames and the sound from figshare...")
    archive = zipfile.ZipFile(io.BufferedReader(RemoteFile(FIGSHARE_ARCHIVE_URL), buffer_size=1 << 18))
    for member in [FRAME_DIR + name for _, name in frames] + [DENOISED_SOUND]:
        with archive.open(member) as source, open(workdir / Path(member).name, "wb") as target:
            shutil.copyfileobj(source, target)


def convert(frames, workdir):
    pixels = []
    for number, name in frames:
        dicom = pydicom.dcmread(workdir / name)
        if int(dicom.InstanceNumber) != number:
            sys.exit(f"{name}: instance {dicom.InstanceNumber}, expected {number}")
        pixels.append(dicom.pixel_array.astype(float))
    stack = np.stack(pixels)
    low, high = np.percentile(stack, WINDOW)
    for index, frame in enumerate(stack):
        scaled = np.clip((frame - low) / (high - low), 0, 1) * 255
        image = Image.fromarray(scaled.astype(np.uint8))
        size = (image.width * SCALE, image.height * SCALE)
        image.resize(size, Image.LANCZOS).save(workdir / f"frame_{index:03d}.png")


def encode(frames, workdir, output):
    start = (FIRST_INSTANCE - 1) / FRAME_RATE
    duration = len(frames) / FRAME_RATE
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        FFMPEG, "-v", "error", "-y",
        "-framerate", str(FRAME_RATE), "-i", str(workdir / "frame_%03d.png"),
        "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(workdir / Path(DENOISED_SOUND).name),
        "-c:v", "libx264", "-crf", "16", "-preset", "slow", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart",
        str(output),
    ], check=True)
    print(f"Written {output}")
    print(f"Source: {CITATION}")


def main():
    parser = argparse.ArgumentParser(description="Build the tutorial's video excerpt.")
    parser.add_argument("--output", type=Path, default=OUTPUT, help=f"default: {OUTPUT}")
    args = parser.parse_args()
    frames = read_frame_list()
    if [number for number, _ in frames] != list(range(FIRST_INSTANCE, FIRST_INSTANCE + len(frames))):
        sys.exit(f"{FRAME_LIST.name}: instances must run on from {FIRST_INSTANCE}")
    with tempfile.TemporaryDirectory() as workdir:
        workdir = Path(workdir)
        fetch(frames, workdir)
        convert(frames, workdir)
        encode(frames, workdir, args.output)


if __name__ == "__main__":
    main()
