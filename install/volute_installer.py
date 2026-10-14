"""
VOLUTE installer
Installs VOLUTE, SAM2-Plus, the models chosen and their Python environment into
one self-contained folder, then creates the launchers. Run again on an existing
installation, it updates VOLUTE and adds any model not yet downloaded, keeping
the settings.

Started by install_volute_macos.sh or install_volute_windows.ps1, which install
Miniforge into the folder first and run this script with Miniforge's own
Python. It uses the standard library only, and touches nothing outside the
folder but the launchers: the Desktop shortcut on Windows, VOLUTE.app in
~/Applications on macOS.

    python volute_installer.py --prefix DIR --miniforge DIR [options]
"""

import argparse
import contextlib
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path


VOLUTE_REPO = "nicolasaudibert/VOLUTE"
SAM2PLUS_ZIP_URL = "https://github.com/MCG-NJU/SAM2-Plus/archive/refs/heads/main.zip"

PYTHON_VERSION = "3.10"
TORCH_VERSION = "2.7.0"
TORCHVISION_VERSION = "0.22.0"
PYTORCH_INDEX = "https://download.pytorch.org/whl/"

# setup.py of SAM2-Plus requires a setuptools within this range to build
SETUPTOOLS_SPEC = "setuptools>=62.3.0,<75.9"

# Warnings pip would print for every package: that it checks for a newer
# version of itself, and that the programs a package brings are not on PATH,
# which VOLUTE, started through its launchers, never needs
PIP_QUIET = ["--disable-pip-version-check", "--no-warn-script-location"]

# conda-forge alone, whatever channels a ~/.condarc left by Anaconda or
# Miniconda adds: Miniforge's conda reads that file too
CONDA_CHANNELS = ["--override-channels", "--channel", "conda-forge"]

# Packages VOLUTE imports beyond those SAM2-Plus brings
GUI_PACKAGES = ["PyQt5", "matplotlib", "scipy", "pyyaml", "pandas", "openpyxl",
                "scikit-image"]

MEDSAM2_CHECKPOINTS = "https://huggingface.co/wanglab/MedSAM2/resolve/main/"
# The one config the MedSAM2 checkpoints need, at a fixed commit of its
# repository; the sam2 package of SAM2-Plus builds the model from it
MEDSAM2_CONFIG = ("https://raw.githubusercontent.com/bowang-lab/MedSAM2/"
                  "0037c910e8b096405447149b526fbdd5f17302a1/sam2/configs/"
                  "sam2.1_hiera_t512.yaml")

# Models offered: key, description, files as (URL, path inside SAM2-Plus),
# approximate size in MB for display, selected by default. A model counts as
# downloaded once all its files are there.
MODELS = [
    ("large", "SAM2.1 Large - best accuracy",
     [("https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_large.pt",
       "checkpoints/sam2.1_hiera_large.pt")], 900, True),
    ("small", "SAM2.1 Small - faster, slightly less accurate",
     [("https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt",
       "checkpoints/sam2.1_hiera_small.pt")], 185, False),
    ("sam2plus", "SAM2++ - needed for point tracking",
     [("https://huggingface.co/MCG-NJU/SAM2-Plus/resolve/main/checkpoint_phase123.pt",
       "checkpoints/SAM2-Plus/checkpoint_phase123.pt")], 800, False),
    ("medsam2", "MedSAM2 - medical images: CT, MRI, ultrasound, 4 models",
     [(MEDSAM2_CHECKPOINTS + name, "checkpoints/" + name)
      for name in ("MedSAM2_latest.pt", "MedSAM2_CTLesion.pt", "MedSAM2_US_Heart.pt",
                   "MedSAM2_MRI_LiverLesion.pt")]
     + [(MEDSAM2_CONFIG, "sam2/configs/medsam2_configs/sam2.1_hiera_t512.yaml")],
     625, False),
]

# Answer to the model question, or value of --models, that selects them all
ALL_MODELS = "a"

# Disk space the environment takes, PyTorch with CUDA being the largest part
ENVIRONMENT_MB = 7000

# Files of an existing installation that an update leaves alone
KEPT_ON_UPDATE = {"volute_config.yaml"}

USER_AGENT = "VOLUTE-installer"
IS_WINDOWS = sys.platform == "win32"
IS_MACOS = sys.platform == "darwin"


class InstallError(Exception):
    """A step failed; the message says what to do about it."""


class InstallCancelled(Exception):
    """The person declined to go on."""


class Installer:

    def __init__(self, args):
        self.args = args
        self.prefix = Path(args.prefix).resolve()
        self.miniforge = Path(args.miniforge).resolve()
        self.env = self.miniforge / "envs" / "volute"
        self.root = self.prefix / "SAM2-Plus"
        self.tools = self.root / "tools"
        self.log_path = self.prefix / "install.log"
        # pip's cache, kept in the folder rather than in the user profile:
        # nothing outside the folder is left behind, and a cache written by
        # an earlier run as administrator cannot block a later one. Kept
        # after an interrupted run, which then resumes without downloading
        # everything again; deleted once the installation succeeds.
        self.pip_cache = self.prefix / "pip-cache"
        self.step_index = 0
        self.step_count = 8

    # ------------------------------------------------------------------
    # Output and subprocesses
    # ------------------------------------------------------------------

    def log(self, text):
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(text.rstrip("\n") + "\n")

    def say(self, text=""):
        print(text, flush=True)
        self.log(text)

    def step(self, title):
        self.step_index += 1
        self.say("")
        self.say(f"[{self.step_index}/{self.step_count}] {title}")

    def run(self, cmd, cwd=None, env=None, what=None, stdin_text=None):
        """Run a command with its output on the console, so that pip and
        conda show their own progress; raise InstallError if it fails. Its
        error output also goes to the log, where a failure can be read."""
        self.log("$ " + subprocess.list2cmdline([str(c) for c in cmd]))
        # CONDA_REGISTER_ENVS: conda would otherwise list the environment in
        # ~/.conda/environments.txt, the one file it writes outside the folder
        full_env = dict(os.environ, PIP_CACHE_DIR=str(self.pip_cache),
                        CONDA_REGISTER_ENVS="false", **(env or {}))
        try:
            process = subprocess.Popen(
                [str(c) for c in cmd], cwd=cwd, env=full_env,
                stdin=subprocess.PIPE if stdin_text is not None else None,
                stderr=subprocess.PIPE)
        except OSError as e:
            raise InstallError(f"Could not run {cmd[0]}: {e}")
        if stdin_text is not None:
            process.stdin.write(stdin_text.encode())
            process.stdin.close()
        # Passed on as it comes, carriage returns included, so that progress
        # bars drawn on the error output still redraw in place
        errors = bytearray()
        for chunk in iter(lambda: process.stderr.read1(4096), b""):
            sys.stderr.buffer.write(chunk)
            sys.stderr.flush()
            errors += chunk
        returncode = process.wait()
        for line in errors.decode(errors="replace").split("\n"):
            # Of a line a progress bar redrew, its final state
            line = line.rstrip("\r").rsplit("\r", 1)[-1].rstrip()
            if line:
                self.log("  | " + line)
        self.log(f"  exit code {returncode}")
        if returncode != 0:
            raise InstallError(f"{what or 'A command'} failed (exit code "
                               f"{returncode}); its messages are above.")

    def output(self, cmd):
        """Standard output of a command, or None when it cannot run."""
        try:
            result = subprocess.run([str(c) for c in cmd], capture_output=True,
                                    text=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            return None
        return result.stdout if result.returncode == 0 else None

    def ask(self, question, default=True):
        if self.args.yes:
            return default
        hint = "[Y/n]" if default else "[y/N]"
        while True:
            try:
                answer = input(f"{question} {hint} ").strip().lower()
            except EOFError:
                return default
            if not answer:
                return default
            if answer in ("y", "yes", "o", "oui"):
                return True
            if answer in ("n", "no", "non"):
                return False

    # ------------------------------------------------------------------
    # Downloads
    # ------------------------------------------------------------------

    def fetch_json(self, url):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)

    def download(self, url, target, label):
        """Download url to target through a .part file, so that an
        interrupted download is never mistaken for a complete one."""
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + ".part")
        self.log(f"download {url} -> {target}")
        for attempt in range(1, 4):
            try:
                request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(request, timeout=60) as response, \
                        open(partial, "wb") as out:
                    total = int(response.headers.get("Content-Length") or 0)
                    done, shown = 0, -1
                    while True:
                        chunk = response.read(1 << 20)
                        if not chunk:
                            break
                        out.write(chunk)
                        done += len(chunk)
                        if total:
                            percent = done * 100 // total
                            if percent != shown:
                                shown = percent
                                print(f"\r    {label}: {percent:3d}%  "
                                      f"({done >> 20} of {total >> 20} MB)",
                                      end="", flush=True)
                print(flush=True)
                if total and done != total:
                    raise OSError(f"received {done} bytes of {total}")
                os.replace(partial, target)
                return
            except OSError as e:
                print(flush=True)
                self.say(f"    Download interrupted ({e}), attempt {attempt} of 3.")
                time.sleep(3 * attempt)
        partial.unlink(missing_ok=True)
        raise InstallError(f"Could not download {label}. Check the Internet "
                           "connection, then run the installer again: what is "
                           "already installed is kept.")

    def extract_zip(self, archive, destination):
        """Extract a zip archive, restoring the executable bits it records,
        and return the single top-level folder GitHub archives contain."""
        destination = Path(destination)
        with zipfile.ZipFile(archive) as z:
            z.extractall(destination)
            for info in z.infolist():
                mode = (info.external_attr >> 16) & 0o777
                if mode and not info.is_dir():
                    os.chmod(destination / info.filename, mode)
        entries = [p for p in destination.iterdir()]
        return entries[0] if len(entries) == 1 and entries[0].is_dir() else destination

    @staticmethod
    def remove_tree(path):
        """Delete a folder, read-only files included; what still cannot be
        deleted is left in place rather than stopping the installation."""
        def retry(func, target, _):
            try:
                os.chmod(target, stat.S_IWRITE)
                func(target)
            except OSError:
                pass
        handler = "onexc" if sys.version_info >= (3, 12) else "onerror"
        shutil.rmtree(path, **{handler: retry})

    @contextlib.contextmanager
    def work_dir(self):
        """Scratch folder inside the installation folder, deleted on leaving,
        error or interruption included. It is an ordinary folder, inheriting
        the permissions of the installation folder: tempfile creates its
        folders with mode 0o700, which recent Pythons turn on Windows into an
        access list restricted to the owner, administrators and the system.
        The extracted files keep that list once moved into the installation,
        and when the installer runs as administrator, the owner being the
        Administrators group, Explorer can then neither open the launchers
        nor show their icon."""
        # Folders left by an earlier run that was killed are deleted first
        for stale in self.prefix.glob(".volute-work-*"):
            self.remove_tree(stale)
        path = self.prefix / f".volute-work-{os.getpid()}"
        path.mkdir()
        try:
            yield path
        finally:
            self.remove_tree(path)

    # ------------------------------------------------------------------
    # Paths inside the environment
    # ------------------------------------------------------------------

    @property
    def conda(self):
        if IS_WINDOWS:
            return self.miniforge / "Scripts" / "conda.exe"
        return self.miniforge / "bin" / "conda"

    @property
    def python(self):
        if IS_WINDOWS:
            return self.env / "python.exe"
        return self.env / "bin" / "python"

    def pip(self, *packages, what, extra=()):
        self.run([self.python, "-m", "pip", "install", *PIP_QUIET,
                  *extra, *packages], what=what)

    def env_check(self, code):
        """True when the environment's Python runs code without error."""
        return self.output([self.python, "-c", code]) is not None

    # ------------------------------------------------------------------
    # 1. System
    # ------------------------------------------------------------------

    def detect_cuda(self):
        """Highest CUDA version the NVIDIA driver supports, or None."""
        text = self.output(["nvidia-smi"])
        if not text:
            return None
        match = re.search(r"CUDA Version:\s*(\d+)\.(\d+)", text)
        return (int(match.group(1)), int(match.group(2))) if match else None

    def choose_torch(self):
        """PyTorch build to install: 'pypi', 'conda-forge', 'cpu' or a
        'cuXYZ' index, and a sentence describing why."""
        if self.args.torch != "auto":
            return self.args.torch, f"PyTorch build forced: {self.args.torch}"
        machine = platform.machine().lower()
        if IS_MACOS:
            if machine == "arm64":
                return "pypi", "Mac with Apple Silicon: GPU acceleration (MPS)"
            return "conda-forge", ("Mac with an Intel processor: PyTorch from conda-forge, "
                                   "PyPI no longer providing it; segmentation will be "
                                   "slower than on Apple Silicon")
        cuda = self.detect_cuda()
        if cuda is None:
            return "cpu", "No NVIDIA GPU found: CPU only, so segmentation will be slow"
        for index, minimum in (("cu128", (12, 8)), ("cu126", (12, 6)), ("cu118", (11, 8))):
            if cuda >= minimum:
                return index, (f"NVIDIA GPU, driver supporting CUDA {cuda[0]}.{cuda[1]}: "
                               f"PyTorch for CUDA {minimum[0]}.{minimum[1]}")
        return "cpu", (f"NVIDIA driver too old (CUDA {cuda[0]}.{cuda[1]}): CPU only. "
                       "Updating the NVIDIA driver, then running the installer "
                       "again, would enable the GPU")

    def check_system(self):
        self.step("Checking the computer")
        self.torch_build, torch_reason = self.choose_torch()
        self.say(f"    {platform.system()} {platform.release()}, {platform.machine()}")
        self.say(f"    {torch_reason}")
        self.say(f"    Installation folder: {self.prefix}")

        self.models = self.choose_models()
        needed = (0 if self.python.exists() else ENVIRONMENT_MB) + sum(
            size for key, _, files, size, _ in MODELS
            if key in self.models and not self.downloaded(files))
        free = shutil.disk_usage(self.prefix).free >> 20
        if needed:
            self.say(f"    Disk space: about {needed / 1000:.1f} GB needed, "
                     f"{free / 1000:.1f} GB free")
        if free < needed:
            self.say("    There may not be enough free disk space.")
            if not self.ask("    Continue anyway?", default=False):
                raise InstallCancelled()

        if self.python.exists():
            question = "\nStart the update?"
        else:
            question = ("\nStart the installation? It takes a while and downloads "
                        "several gigabytes.")
        if not self.ask(question):
            raise InstallCancelled()

    def downloaded(self, files):
        return all((self.root / path).exists() for _, path in files)

    def choose_models(self):
        every = {key for key, *_ in MODELS}
        if self.args.models is not None:
            chosen = {m.strip() for m in self.args.models.split(",") if m.strip()}
            if ALL_MODELS in chosen:
                return every
            unknown = chosen - every - {"none"}
            if unknown:
                raise InstallError(f"Unknown model(s): {', '.join(sorted(unknown))}")
            return chosen - {"none"}

        # Nothing left to offer: the question would only list what is there
        if all(self.downloaded(files) for _, _, files, *_ in MODELS):
            self.say("    Models: all already downloaded.")
            return set()

        # On an installation that already has a model, Enter adds none: the
        # installer is most likely run again to update VOLUTE
        if any(self.downloaded(files) for _, _, files, *_ in MODELS):
            defaults = set()
        else:
            defaults = {key for key, *_, default in MODELS if default}
        self.say("")
        self.say("    Models to download (more can be added later by running the "
                 "installer again):")
        for number, (key, label, files, size, _) in enumerate(MODELS, 1):
            state = "already downloaded" if self.downloaded(files) else f"{size} MB"
            mark = "*" if key in defaults else " "
            self.say(f"     {mark} {number}. {label} ({state})")
        remaining = sum(size for _, _, files, size, _ in MODELS if not self.downloaded(files))
        self.say(f"       {ALL_MODELS}. All of the above ({remaining} MB)")
        if self.args.yes:
            return defaults
        default_numbers = " ".join(str(n) for n, m in enumerate(MODELS, 1)
                                   if m[0] in defaults) or "none"
        while True:
            try:
                answer = input(f"    Numbers of the models to download, separated by "
                               f"spaces, or {ALL_MODELS} for all "
                               f"[{default_numbers}]: ").strip()
            except EOFError:
                answer = ""
            if not answer:
                return defaults
            if answer.lower() == "none":
                return set()
            if answer.lower() in (ALL_MODELS, "all"):
                return every
            numbers = answer.replace(",", " ").split()
            if all(n.isdigit() and 1 <= int(n) <= len(MODELS) for n in numbers):
                return {MODELS[int(n) - 1][0] for n in numbers}
            print(f"    Please type numbers between 1 and {len(MODELS)}, "
                  f"or {ALL_MODELS} for all.")

    # ------------------------------------------------------------------
    # 2. Python environment
    # ------------------------------------------------------------------

    def create_environment(self):
        self.step("Python environment")
        if self.python.exists():
            self.say("    Already present.")
            return
        # ffmpeg comes with the environment: frame extraction from a video
        # relies on it, and conda-forge builds include ffprobe
        self.run([self.conda, "create", "--yes", "--prefix", self.env, *CONDA_CHANNELS,
                  f"python={PYTHON_VERSION}", "pip", "ffmpeg"],
                 what="Creating the Python environment")

    # ------------------------------------------------------------------
    # 3. PyTorch
    # ------------------------------------------------------------------

    def install_torch(self):
        self.step("PyTorch")
        build = self.torch_build
        # Builds from the PyTorch index carry their variant as a local version
        # label (2.7.0+cu126), which the check compares so that another
        # variant, installed before a driver update for instance, is replaced
        indexed = build not in ("pypi", "conda-forge")
        if indexed:
            check = (f"import torch, torchvision; "
                     f"assert torch.__version__ == '{TORCH_VERSION}+{build}'")
        else:
            check = (f"import torch, torchvision; "
                     f"assert torch.__version__.startswith('{TORCH_VERSION}')")
        if self.env_check(check):
            self.say("    Already installed.")
            return
        self.say("    This is the largest download, and can take several minutes.")
        if build == "conda-forge":
            self.run([self.conda, "install", "--yes", "--prefix", self.env, *CONDA_CHANNELS,
                      f"pytorch={TORCH_VERSION}", f"torchvision={TORCHVISION_VERSION}"],
                     what="Installing PyTorch")
        elif build == "pypi":
            self.pip(f"torch=={TORCH_VERSION}", f"torchvision=={TORCHVISION_VERSION}",
                     what="Installing PyTorch")
        else:
            # Pinned with the label: pip disregards it when comparing versions,
            # and would otherwise keep an installed build of another variant
            self.pip(f"torch=={TORCH_VERSION}+{build}",
                     f"torchvision=={TORCHVISION_VERSION}+{build}",
                     what="Installing PyTorch",
                     extra=("--index-url", PYTORCH_INDEX + build))

    # ------------------------------------------------------------------
    # 4. SAM2-Plus
    # ------------------------------------------------------------------

    def install_sam2plus(self):
        self.step("SAM2-Plus")
        if not (self.root / "setup.py").exists():
            with self.work_dir() as tmp:
                archive = tmp / "sam2plus.zip"
                self.download(SAM2PLUS_ZIP_URL, archive, "SAM2-Plus")
                top = self.extract_zip(archive, tmp / "x")
                shutil.move(str(top), str(self.root))
        else:
            self.say("    Already downloaded.")
        self.pip(SETUPTOOLS_SPEC, "wheel", what="Installing build tools")
        # Without compiling the CUDA extension, which would need Visual Studio
        # and the CUDA toolkit; the patch applied later restores what it does.
        # Without build isolation either, which would download a second PyTorch
        # to build in, and could not on an Intel Mac.
        self.run([self.python, "-m", "pip", "install", *PIP_QUIET,
                  "--no-build-isolation", "-e", self.root],
                 env={"SAM2_BUILD_CUDA": "0", "SAM2_BUILD_ALLOW_ERRORS": "1"},
                 what="Installing SAM2-Plus")
        requirements = self.root / "sam2_plus" / "requirements.txt"
        if requirements.exists():
            self.pip("-r", requirements, what="Installing the SAM2++ dependencies")

    # ------------------------------------------------------------------
    # 5. VOLUTE
    # ------------------------------------------------------------------

    @staticmethod
    def version_key(tag):
        return tuple(int(n) for n in re.findall(r"\d+", tag))

    def latest_tag(self):
        tags = [t["name"] for t in
                self.fetch_json(f"https://api.github.com/repos/{VOLUTE_REPO}/tags?per_page=100")]
        tags = [t for t in tags if re.fullmatch(r"v?\d+(\.\d+)*", t)]
        if not tags:
            raise InstallError("No VOLUTE release found on GitHub.")
        return max(tags, key=self.version_key)

    @staticmethod
    def source_files(source):
        """Files of a VOLUTE source folder, relative to it: those its upload
        list names when it has one, so that a development copy holding other
        files installs only the application."""
        listing = source / "volute_upload_list.txt"
        if listing.exists():
            names = [line.strip() for line in listing.read_text(encoding="utf-8").splitlines()
                     if line.strip() and not line.startswith("#")]
            return [Path(n) for n in names if (source / n).is_file()]
        return [p.relative_to(source) for p in source.rglob("*")
                if p.is_file() and ".git" not in p.relative_to(source).parts]

    def copy_volute(self, source):
        updating = (self.tools / "volute" / "__init__.py").exists()
        for relative in self.source_files(source):
            target = self.tools / relative
            if updating and relative.name in KEPT_ON_UPDATE and target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source / relative, target)

    def installed_version(self):
        init = self.tools / "volute" / "__init__.py"
        if not init.exists():
            return None
        match = re.search(r'__version__\s*=\s*"([^"]+)"', init.read_text(encoding="utf-8"))
        return match.group(1) if match else None

    def install_volute(self):
        self.step("VOLUTE")
        before = self.installed_version()
        if self.args.volute_source:
            self.say(f"    Copying from {self.args.volute_source}")
            self.copy_volute(Path(self.args.volute_source).resolve())
        else:
            ref = self.args.volute_ref or self.latest_tag()
            url = f"https://github.com/{VOLUTE_REPO}/archive/refs/" + (
                f"heads/{ref}.zip" if ref == "main" else f"tags/{ref}.zip")
            with self.work_dir() as tmp:
                archive = tmp / "volute.zip"
                self.download(url, archive, f"VOLUTE {ref}")
                self.copy_volute(self.extract_zip(archive, tmp / "x"))
        after = self.installed_version()
        if before and before != after:
            self.say(f"    Updated from {before} to {after}; settings kept.")
        else:
            self.say(f"    Version {after}.")
        self.pip(*GUI_PACKAGES, what="Installing the VOLUTE dependencies")

    # ------------------------------------------------------------------
    # 6. SAM2 post-processing patch
    # ------------------------------------------------------------------

    def patch_sam2(self):
        self.step("SAM2 mask post-processing")
        # The patch replaces a step of SAM2 that needs its compiled CUDA
        # extension, which this installation does not build; it exits by
        # itself where the extension is usable
        self.run([self.python, self.tools / "sam2_misc_patch" / "patch_sam2_misc.py"],
                 cwd=self.root, what="Patching SAM2")

    # ------------------------------------------------------------------
    # 7. Models
    # ------------------------------------------------------------------

    def download_models(self):
        self.step("Models")
        if not self.models:
            self.say("    None selected.")
        for key, label, files, size, _ in MODELS:
            if key not in self.models:
                continue
            if self.downloaded(files):
                self.say(f"    {label}: already downloaded.")
                continue
            for url, path in files:
                target = self.root / path
                if not target.exists():
                    self.download(url, target, f"{label}: {target.name}"
                                  if len(files) > 1 else label)
        present = [label for key, label, files, *_ in MODELS if self.downloaded(files)]
        if not present:
            self.say("    No model is installed: VOLUTE needs at least one. Run the "
                     "installer again to download one.")

    # ------------------------------------------------------------------
    # 8. Launchers and final check
    # ------------------------------------------------------------------

    def create_launchers(self):
        self.step("Launchers")
        if not self.env_check("import torch, sam2, sam2_plus, PyQt5, scipy, yaml, matplotlib"):
            raise InstallError("The environment cannot import everything VOLUTE "
                               "needs; see the messages above and install.log.")
        if IS_WINDOWS:
            # Started from the tools folder by its bare name, so that cmd.exe
            # never sees a quoted path it might strip the quotes from
            self.run(["cmd", "/c", "install_launchers_windows.bat", self.python],
                     cwd=self.tools, stdin_text="\n", what="Creating the launchers")
        elif IS_MACOS:
            applications = Path.home() / "Applications"
            applications.mkdir(exist_ok=True)
            self.run(["bash", self.tools / "install_app_bundle_macos.sh",
                      "--python", self.python, "--output", applications],
                     cwd=self.root, what="Creating VOLUTE.app")
        else:
            self.run(["bash", self.tools / "install_launchers_Unix_MacOS.sh"],
                     cwd=self.root, what="Creating the launchers")

    def summary(self):
        self.say("")
        self.say("=" * 70)
        self.say(f"VOLUTE {self.installed_version()} is installed.")
        self.say("=" * 70)
        if IS_WINDOWS:
            self.say("Start it with the VOLUTE shortcut on the Desktop, or with")
            self.say(f"  {self.tools / 'launchers' / 'volute.bat'}")
        elif IS_MACOS:
            self.say("Start it with VOLUTE in the Applications folder of your home")
            self.say(f"folder ({Path.home() / 'Applications' / 'VOLUTE.app'});")
            self.say("drag it to the Dock to keep it at hand.")
        else:
            self.say(f"Start it with {self.tools / 'launchers' / 'volute.sh'}")
        self.say("")
        self.say("ffmpeg, which extracts frames from a video, is included. GIMP, for")
        self.say("retouching masks by hand, is not: if you need it, install GIMP 3.0")
        self.say("or later from https://www.gimp.org")
        self.say("")
        self.say("To update VOLUTE or add a model, run the installer again.")
        self.say(f"To uninstall, delete the folder {self.prefix}")
        if IS_WINDOWS:
            self.say("and the VOLUTE shortcut on the Desktop.")
        elif IS_MACOS:
            self.say("and VOLUTE.app in the Applications folder of your home folder.")
        self.say(f"Installation log: {self.log_path}")

    def install(self):
        self.prefix.mkdir(parents=True, exist_ok=True)
        self.log(f"\n===== VOLUTE installer, {time.strftime('%Y-%m-%d %H:%M:%S')} =====")
        self.log(f"arguments: {vars(self.args)}")
        self.check_system()
        self.create_environment()
        self.install_torch()
        self.install_sam2plus()
        self.install_volute()
        self.patch_sam2()
        self.download_models()
        self.create_launchers()
        if self.pip_cache.exists():
            self.remove_tree(self.pip_cache)
        self.summary()


def main():
    parser = argparse.ArgumentParser(description="Install or update VOLUTE.")
    parser.add_argument("--prefix", required=True,
                        help="installation folder")
    parser.add_argument("--miniforge", required=True,
                        help="Miniforge installation to create the environment with")
    parser.add_argument("--models", default=None,
                        help="comma-separated models to download, among "
                             + ", ".join(key for key, *_ in MODELS)
                             + f", or none, or {ALL_MODELS} for all; asked when omitted")
    parser.add_argument("--torch", default="auto",
                        choices=["auto", "pypi", "conda-forge", "cpu", "cu118", "cu126", "cu128"],
                        help="PyTorch build; detected from the hardware by default")
    parser.add_argument("--volute-ref", default=None,
                        help="VOLUTE tag or 'main' to install (default: the latest tag)")
    parser.add_argument("--volute-source", default=None,
                        help="local VOLUTE folder to install instead of downloading it")
    parser.add_argument("--yes", action="store_true",
                        help="ask nothing, taking the default answers")
    args = parser.parse_args()

    installer = Installer(args)
    try:
        installer.install()
    except InstallError as e:
        installer.say("")
        installer.say(f"ERROR: {e}")
        installer.say(f"Installation log: {installer.log_path}")
        return 1
    except InstallCancelled:
        installer.say("")
        installer.say("Installation cancelled; nothing more was changed.")
        return 1
    except KeyboardInterrupt:
        installer.say("")
        installer.say("Installation interrupted. Run the installer again to resume: "
                      "what is already installed is kept.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
