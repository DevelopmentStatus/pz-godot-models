"""The no-game-art rule for community models, as runnable code.

This module is the specification. The Discord bot reimplements these checks in
JavaScript so it can reject a bad submission the moment it is uploaded, but this
file is what CI runs over every .glb in the repository on every push -- so the
rule holds even if a commit ever arrives by some route other than the bot.

The rule
--------
A model in this repository carries geometry and *names*, never pixels. It says
which Project Zomboid sprite supplies its colour by naming its material
"pz:<sprite_id>", and the game resolves that at load time against the atlas the
player generated from their own copy of the game.

So a .glb is rejected if it contains any image or texture at all. Not "any image
that looks like PZ art", not "any image named after a sprite sheet" -- any image.
That makes this a mechanical check with no judgement in it, and nothing can slip
through mislabelled.

A .glb is also rejected if it references an external file, since that would move
the art out of reach of this check rather than removing it.

GLB format, briefly
-------------------
12-byte header ("glTF", version, total length), then a sequence of chunks, each
an 8-byte header (length, type) followed by its payload padded to 4 bytes. The
first chunk is JSON; the second, if present, is the binary buffer. Only the JSON
chunk matters here.

Usage:
    python tools/glb_check.py <file.glb> [...]
    python tools/glb_check.py --catalog catalog/sprites.json models/*.glb
"""

import argparse
import json
import os
import struct
import sys

MAGIC = b"glTF"
CHUNK_JSON = b"JSON"

MATERIAL_PREFIX = "pz:"

# Generous, but a textureless prop that exceeds this is either a mistake or
# somebody's whole scene. The bot enforces Discord's 25 MB attachment cap before
# this ever runs; this is the backstop for anything reaching the repo elsewise.
MAX_BYTES = 16 * 1024 * 1024


class GlbError(Exception):
    """A model that must not be published, with a message aimed at its author."""


def parse_chunks(data):
    """{chunk_type: payload} for a GLB byte string. Raises GlbError if malformed."""
    if len(data) < 12:
        raise GlbError("file is too short to be a .glb (%d bytes)" % len(data))

    magic, version, declared = struct.unpack_from("<4sII", data, 0)
    if magic != MAGIC:
        raise GlbError(
            "not a binary .glb - it starts with %r, not 'glTF'. If you exported "
            "a .gltf, re-export as GLB so everything is in one file." % magic)
    if version != 2:
        raise GlbError("glTF version %d; this project uses glTF 2.0" % version)
    if declared != len(data):
        raise GlbError(
            "header says %d bytes but the file is %d - it is truncated or has "
            "trailing junk" % (declared, len(data)))

    chunks = {}
    offset = 12
    while offset + 8 <= len(data):
        length, kind = struct.unpack_from("<I4s", data, offset)
        offset += 8
        if offset + length > len(data):
            raise GlbError("chunk %r runs past the end of the file" % kind)
        chunks.setdefault(kind, data[offset:offset + length])
        offset += length + (-length % 4)
    return chunks


def parse(data):
    """The glTF JSON document out of a GLB byte string."""
    chunks = parse_chunks(data)
    if CHUNK_JSON not in chunks:
        raise GlbError("no JSON chunk - this is not a usable .glb")
    try:
        return json.loads(chunks[CHUNK_JSON].decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise GlbError("the JSON chunk does not parse: %s" % exc)


def _image_names(gltf):
    names = []
    for index, image in enumerate(gltf.get("images") or []):
        names.append(str(image.get("name") or image.get("uri") or "image %d" % index))
    return names


def check(data, catalog=None):
    """Validate one model's bytes.

    Returns the sorted list of sprite ids the model binds to. Raises GlbError
    with an author-facing message if the model must not be published.

    `catalog`, when given, is the set of sprite ids that exist; a "pz:" material
    naming anything else is rejected as a typo rather than trusted.
    """
    if len(data) > MAX_BYTES:
        raise GlbError("%.1f MB is over the %d MB limit for a model"
                       % (len(data) / 1048576.0, MAX_BYTES // 1048576))

    gltf = parse(data)

    # The rule. Images and textures are separate glTF arrays and either one
    # alone means pixels travelled with the model, so both are checked.
    images = _image_names(gltf)
    if images:
        shown = ", ".join(images[:4]) + ("..." if len(images) > 4 else "")
        raise GlbError(
            "this model has %d embedded texture(s) (%s). Models here carry no "
            "art - name your material 'pz:<sprite_id>' instead and the game will "
            "texture it from the player's own copy of the game. In Blender use "
            "PZ Tile Viewer > Export for Community, which does this for you."
            % (len(images), shown))
    if gltf.get("textures"):
        raise GlbError(
            "this model declares %d texture(s) with no image behind them; export "
            "it with no texture nodes at all" % len(gltf["textures"]))

    # An external reference would put the art beyond the reach of the check
    # above rather than removing it.
    for index, buffer in enumerate(gltf.get("buffers") or []):
        if buffer.get("uri"):
            raise GlbError(
                "buffer %d points at an external file (%s). Everything must be "
                "inside the .glb - export as GLB, not glTF Separate."
                % (index, buffer["uri"]))

    materials = gltf.get("materials") or []
    if not materials:
        raise GlbError("this model has no materials, so nothing says which sprite "
                       "should texture it")

    bindings = []
    for material in materials:
        name = str(material.get("name") or "")
        if not name.startswith(MATERIAL_PREFIX):
            # An author's own flat-colour material. Left alone by the game.
            continue
        sprite_id = name[len(MATERIAL_PREFIX):]
        if not sprite_id:
            raise GlbError("a material is named just '%s' with no sprite id after it"
                           % MATERIAL_PREFIX)
        if catalog is not None and sprite_id not in catalog:
            raise GlbError(
                "material '%s' names a sprite that does not exist. Check the "
                "spelling against catalog/sprites.json." % name)
        bindings.append(sprite_id)

    return sorted(set(bindings))


def check_file(path, catalog=None):
    with open(path, "rb") as handle:
        return check(handle.read(), catalog)


def load_catalog(path):
    with open(path, encoding="utf-8") as handle:
        return set(json.load(handle).get("sprites", {}))


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="*", help=".glb files to check")
    parser.add_argument("--catalog", help="catalog/sprites.json, to validate bindings")
    args = parser.parse_args(argv)

    catalog = load_catalog(args.catalog) if args.catalog else None

    failures = 0
    for path in args.paths:
        try:
            bindings = check_file(path, catalog)
        except GlbError as exc:
            print("FAIL %s\n     %s" % (path, exc))
            failures += 1
        except OSError as exc:
            print("FAIL %s\n     cannot read: %s" % (path, exc))
            failures += 1
        else:
            summary = ", ".join(bindings) if bindings else "no pz: bindings"
            print("ok   %-44s %s" % (os.path.basename(path), summary))

    if failures:
        print("\n%d of %d file(s) rejected" % (failures, len(args.paths)))
        return 1
    if args.paths:
        print("\n%d file(s) ok" % len(args.paths))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
