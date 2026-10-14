"""
VOLUTE documentation site builder
Builds the bilingual site published on GitHub Pages from docs/, with Zensical:
English at the root, French under fr/.

Zensical does not yet serve translated content, so each language is built on
its own, from a source tree this script prepares in .docs_build/:

- en/ holds every page, in docs/ and its folders, but the .fr.md translations;
- fr/ holds the translations renamed x.fr.md -> x.md, so both languages share
  the same addresses, with their links to x.fr.md pointed to x.md, and the
  English page wherever a translation is missing.

Each page opens with a link to its counterpart in the other language, needed
on GitHub; on the site the language selector replaces it, so it is dropped.
Files other than pages are copied to both trees.

mkdocs.yml builds the English site, mkdocs.fr.yml the French one, both in
strict mode: a broken link or anchor stops the build.

    python build_docs.py           # build into site/
    python build_docs.py --serve   # build, then serve it on this computer
"""

import argparse
import functools
import http.server
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DOCS = ROOT / "docs"
BUILD = ROOT / ".docs_build"
SITE = ROOT / "site"
MKDOCS_CONFIGS = ["mkdocs.yml", "mkdocs.fr.yml"]
TRANSLATION = ".fr.md"
ZENSICAL = [sys.executable, "-m", "zensical"]

# A Markdown link target ending in .fr.md, anchor and all: ](faq.fr.md#x
FR_LINK = re.compile(r"\]\(([^()\s:#]+)\.fr\.md(?=[)#])")


def counterpart_line(target):
    """Pattern of the line linking a page to its counterpart, e.g. *[English version](faq.md)*."""
    return re.compile(r"^\*\[[^\]]+\]\(" + re.escape(target) + r"\)\*[ \t]*\n", re.M)


def prepare():
    shutil.rmtree(BUILD, ignore_errors=True)
    en, fr = BUILD / "en", BUILD / "fr"
    en.mkdir(parents=True)
    fr.mkdir()

    for path in sorted(DOCS.rglob("*")):
        relative = path.relative_to(DOCS)
        if path.is_dir():
            (en / relative).mkdir()
            (fr / relative).mkdir()
        elif path.name.endswith(TRANSLATION):
            name = path.name[: -len(TRANSLATION)] + ".md"
            text = counterpart_line(name).sub("", path.read_text(encoding="utf-8"), count=1)
            (fr / relative.parent / name).write_text(FR_LINK.sub(r"](\1.md", text), encoding="utf-8")
        elif path.suffix == ".md":
            translation = path.with_name(path.stem + TRANSLATION)
            text = counterpart_line(translation.name).sub("", path.read_text(encoding="utf-8"), count=1)
            (en / relative).write_text(text, encoding="utf-8")
            if not translation.exists():
                (fr / relative).write_text(text, encoding="utf-8")
        else:
            shutil.copy2(path, en / relative)
            shutil.copy2(path, fr / relative)


def build():
    shutil.rmtree(SITE, ignore_errors=True)
    for config in MKDOCS_CONFIGS:
        result = subprocess.run(
            ZENSICAL + ["build", "--strict", "-f", config], cwd=ROOT
        )
        if result.returncode:
            sys.exit(f"Build failed: {config}")


def base_path():
    """Path the site is published under, from site_url in mkdocs.yml: /VOLUTE/."""
    match = re.search(r"^site_url:\s*https?://[^/\s]+(/\S*)", (ROOT / MKDOCS_CONFIGS[0]).read_text(), re.M)
    path = match.group(1) if match else "/"
    return path if path.endswith("/") else path + "/"


def serve(port):
    prefix = base_path()

    class Handler(http.server.SimpleHTTPRequestHandler):
        # Strips the publication path, so that the absolute links of the
        # language selector resolve as they do on GitHub Pages.
        def translate_path(self, path):
            if path.startswith(prefix):
                path = "/" + path[len(prefix):]
            return super().translate_path(path)

    handler = functools.partial(Handler, directory=str(SITE))
    with http.server.ThreadingHTTPServer(("localhost", port), handler) as server:
        print(f"Serving at http://localhost:{port}{prefix} (Ctrl+C to stop)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


def main():
    parser = argparse.ArgumentParser(description="Build the VOLUTE documentation site.")
    parser.add_argument("--serve", action="store_true", help="serve the site once built")
    parser.add_argument("--port", type=int, default=8000, help="port for --serve (default: 8000)")
    args = parser.parse_args()
    prepare()
    build()
    if args.serve:
        serve(args.port)


if __name__ == "__main__":
    main()
