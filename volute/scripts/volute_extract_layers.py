"""
VOLUTE - GIMP mask layer extraction script (Python-Fu)
============================================================================
Companion to the app's "Export Frame for Editing..." (.xcf mode). Run
after opening and finishing edits on the exported .xcf file, via a single
non-interactive GIMP CLI invocation:

    SAM2GUI_XCF_PATH="/path/to/edited.xcf" gimp -i \
        --batch-interpreter=python-fu-eval \
        -b "$(cat scripts/volute_extract_layers.py)" --quit

Optional: set SAM2GUI_XCF_OUTPUT_DIR to choose the output root; defaults
to the .xcf file's own parent folder.

For every layer named "mask::<object id>::<object name>::<filename>"
(the "background" layer is skipped), isolates that layer's own pixels
into a flattened single-layer image and saves it directly under
"<output root>/obj<id>_<name>/<filename>" — fully automatic, no native
save dialog per layer (uses os.makedirs() to create the per-object
subfolders, unlike the former Script-Fu version).
============================================================================
"""

import os
from gi.repository import Gimp, Gio

LAYER_NAME_SEP = "::"


def extract_layers(xcf_path, output_root):
    xcf_file = Gio.File.new_for_path(xcf_path)
    image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, xcf_file)

    for layer in image.get_layers():
        lname = layer.get_name()
        if not lname.startswith("mask" + LAYER_NAME_SEP):
            continue
        parts = lname.split(LAYER_NAME_SEP)
        if len(parts) < 4:
            continue
        obj_id, obj_name, filename = parts[1], parts[2], parts[3]

        tmp_image = Gimp.Image.new(image.get_width(), image.get_height(), Gimp.ImageBaseType.RGB)
        tmp_layer = Gimp.Layer.new_from_drawable(layer, tmp_image)
        tmp_image.insert_layer(tmp_layer, None, 0)
        tmp_image.flatten()

        subfolder = os.path.join(output_root, f"obj{obj_id}_{obj_name}")
        os.makedirs(subfolder, exist_ok=True)
        out_path = os.path.join(subfolder, filename)
        out_file = Gio.File.new_for_path(out_path)
        Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, tmp_image, out_file, None)
        tmp_image.delete()
        Gimp.message(f"Extracted: {out_path}")

    image.delete()
    Gimp.message("Extraction complete.")


_xcf_path = os.environ.get("SAM2GUI_XCF_PATH")
if not _xcf_path:
    Gimp.message("SAM2GUI_XCF_PATH not set — nothing to extract.")
else:
    _output_root = os.environ.get("SAM2GUI_XCF_OUTPUT_DIR") or os.path.dirname(_xcf_path)
    extract_layers(_xcf_path, _output_root)
