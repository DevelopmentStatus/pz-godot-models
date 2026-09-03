"""Whole-repository consistency check. This is what CI runs on every push.

The bot is the only thing that writes here, so in the normal case everything
below is true by construction. The point of checking it anyway is that "the bot
is the only writer" is an assumption, not a guarantee: a hand-edited entry, a
half-applied commit, a restored backup, or a future second writer would all
break invariants that nothing else would notice until a player's install came
out wrong.

What it asserts
---------------
1. Every .glb passes the no-game-art rule in glb_check.py. Belt and braces: the
   bot already refused anything that fails, so a failure here means a file got
   in some other way.
2. models/ and entries/ are in exact correspondence -- no model without an
   entry describing it, no entry pointing at a model that is not there.
3. Each entry is shaped the way schema/entry.schema.json says.
4. Each entry's sha256 and size actually match the bytes on disk, and its
   texture_bindings match what the .glb really declares.
5. Version numbers are unique and descending through history, and only the
   current version may have a null commit_sha.
6. index.json agrees with the entries in every field it duplicates. It is a
   derived file; drift means the installer would hand players something other
   than what this repo says it has.

Usage: python tools/validate_repo.py [--root .]
"""

import argparse
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import glb_check  # noqa: E402


class Report:
    def __init__(self):
        self.errors = []

    def error(self, where, message):
        self.errors.append("%s: %s" % (where, message))

    def ok(self):
        return not self.errors


def _load_json(path, report, where):
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        report.error(where, "cannot read: %s" % exc)
        return None


# ---------------------------------------------------------------- schema
#
# Hand-rolled rather than pulling in jsonschema: the schema file is the
# published contract for anyone reading the repo, and this checks the parts of
# it that can actually go wrong in practice. Keeping CI dependency-free means it
# runs anywhere, including offline.

REQUIRED_VERSION_KEYS = [
    "version", "blob_sha", "sha256", "size", "author", "license",
    "texture_bindings", "embedded_textures", "override", "approved_by",
    "approved_at",
]
LICENSES = {"CC0-1.0", "CC-BY-4.0", "MIT"}


def _check_version_shape(version, report, where):
    for key in REQUIRED_VERSION_KEYS:
        if key not in version:
            report.error(where, "missing required key %r" % key)
            return False

    if not isinstance(version["version"], int) or version["version"] < 1:
        report.error(where, "version must be a positive integer")
    if not _is_hex(version.get("blob_sha"), 40):
        report.error(where, "blob_sha is not a 40-character git blob sha")
    if version.get("commit_sha") is not None and not _is_hex(version["commit_sha"], 40):
        report.error(where, "commit_sha is neither null nor a 40-character sha")
    if not _is_hex(version.get("sha256"), 64):
        report.error(where, "sha256 is not a 64-character hex digest")
    if version.get("license") not in LICENSES:
        report.error(where, "license %r is not one of %s"
                     % (version.get("license"), ", ".join(sorted(LICENSES))))

    author = version.get("author")
    if not isinstance(author, dict) or "discord_id" not in author:
        report.error(where, "author must be an object with a discord_id")

    override = version.get("override")
    if not isinstance(override, dict):
        report.error(where, "override must be an object")
    else:
        offset = override.get("offset")
        if not (isinstance(offset, list) and len(offset) == 3):
            report.error(where, "override.offset must be three numbers")
        if not isinstance(override.get("rotation"), (int, float)):
            report.error(where, "override.rotation must be a number")
        scale = override.get("scale")
        if not isinstance(scale, (int, float)) or scale <= 0:
            report.error(where, "override.scale must be a positive number")

    if version.get("embedded_textures") and not version.get("textures_approved_by"):
        report.error(where, "embedded_textures is true but no admin is recorded in "
                            "textures_approved_by -- an embedded texture must be "
                            "signed off, never silently allowed")
    return True


def _is_housekeeping(name):
    """Files that are allowed to sit alongside the data without being data.

    Dotfiles, and the README each of those folders carries explaining that the
    bot owns it. Anything else is either a stray or something routing around the
    checks, and is worth failing on.
    """
    return name.startswith(".") or name == "README.md"


def _is_hex(value, length):
    if not isinstance(value, str) or len(value) != length:
        return False
    return all(c in "0123456789abcdef" for c in value)


# ----------------------------------------------------------------- entries

def check_entry(root, sprite_id, entry, report, catalog):
    where = "entries/%s.json" % sprite_id

    if entry.get("sprite_id") != sprite_id:
        report.error(where, "sprite_id is %r but the filename says %r"
                     % (entry.get("sprite_id"), sprite_id))
    if catalog is not None and sprite_id not in catalog:
        report.error(where, "%r is not in catalog/sprites.json" % sprite_id)

    expected_sheet = sprite_id.rsplit("_", 1)[0]
    if entry.get("sheet") != expected_sheet:
        report.error(where, "sheet is %r, expected %r"
                     % (entry.get("sheet"), expected_sheet))

    current = entry.get("current")
    if not isinstance(current, dict):
        report.error(where, "no current version")
        return
    history = entry.get("history")
    if not isinstance(history, list):
        report.error(where, "history must be an array (empty is fine)")
        history = []

    for index, version in enumerate([current] + history):
        label = "current" if index == 0 else "history[%d]" % (index - 1)
        _check_version_shape(version, report, "%s %s" % (where, label))

    # Version numbers unique, and history strictly descending below current.
    numbers = [v.get("version") for v in [current] + history if isinstance(v.get("version"), int)]
    if len(set(numbers)) != len(numbers):
        report.error(where, "duplicate version numbers: %s" % numbers)
    if numbers != sorted(numbers, reverse=True):
        report.error(where, "versions are not newest-first: %s" % numbers)

    # Only the live version may lack a commit sha -- it could not know its own.
    for index, version in enumerate(history):
        if version.get("commit_sha") is None:
            report.error(where, "history[%d] has no commit_sha; only the current "
                                "version may be missing one" % index)

    # The model on disk must be the one this entry describes.
    model_path = os.path.join(root, "models", "%s.glb" % sprite_id)
    if not os.path.exists(model_path):
        report.error(where, "models/%s.glb does not exist" % sprite_id)
        return

    with open(model_path, "rb") as handle:
        data = handle.read()

    digest = hashlib.sha256(data).hexdigest()
    if current.get("sha256") != digest:
        report.error(where, "current.sha256 does not match models/%s.glb (%s on disk)"
                     % (sprite_id, digest))
    if current.get("size") != len(data):
        report.error(where, "current.size is %s but the file is %d bytes"
                     % (current.get("size"), len(data)))

    try:
        bindings = glb_check.check(data, catalog)
    except glb_check.GlbError as exc:
        report.error("models/%s.glb" % sprite_id, str(exc))
        return

    declared = current.get("texture_bindings")
    if isinstance(declared, list) and sorted(set(declared)) != bindings:
        report.error(where, "current.texture_bindings is %s but the .glb declares %s"
                     % (sorted(set(declared)), bindings))


# ------------------------------------------------------------------- index

INDEX_MIRRORED = ["sha256", "size", "license", "texture_bindings"]


def check_index(root, index, entries, report):
    where = "index.json"
    models = index.get("models")
    if not isinstance(models, dict):
        report.error(where, "models must be an object")
        return

    if index.get("count") != len(models):
        report.error(where, "count is %s but there are %d models"
                     % (index.get("count"), len(models)))

    missing = sorted(set(entries) - set(models))
    extra = sorted(set(models) - set(entries))
    if missing:
        report.error(where, "no index row for %s" % ", ".join(missing[:8]))
    if extra:
        report.error(where, "index rows with no entry file: %s" % ", ".join(extra[:8]))

    for sprite_id, row in sorted(models.items()):
        entry = entries.get(sprite_id)
        if entry is None:
            continue
        current = entry.get("current", {})
        for key in INDEX_MIRRORED:
            want = current.get(key)
            got = row.get(key)
            if isinstance(want, list):
                want, got = sorted(want or []), sorted(got or [])
            if want != got:
                report.error(where, "%s.%s is %r but the entry says %r"
                             % (sprite_id, key, got, want))
        if row.get("version") != current.get("version"):
            report.error(where, "%s.version is %r but the entry says %r"
                         % (sprite_id, row.get("version"), current.get("version")))
        expected_path = "models/%s.glb" % sprite_id
        if row.get("path") != expected_path:
            report.error(where, "%s.path is %r, expected %r"
                         % (sprite_id, row.get("path"), expected_path))
        override = current.get("override", {})
        for key in ["offset", "rotation", "scale"]:
            if row.get(key) != override.get(key):
                report.error(where, "%s.%s is %r but the entry says %r"
                             % (sprite_id, key, row.get(key), override.get(key)))


# -------------------------------------------------------------------- main

def validate(root):
    report = Report()

    catalog_path = os.path.join(root, "catalog", "sprites.json")
    catalog = None
    catalog_doc = _load_json(catalog_path, report, "catalog/sprites.json")
    if catalog_doc is not None:
        catalog = set(catalog_doc.get("sprites", {}))
        if not catalog:
            report.error("catalog/sprites.json", "no sprites listed")

    models_dir = os.path.join(root, "models")
    entries_dir = os.path.join(root, "entries")
    model_ids = set()
    if os.path.isdir(models_dir):
        for name in sorted(os.listdir(models_dir)):
            if name.endswith(".glb"):
                model_ids.add(name[:-4])
            elif not _is_housekeeping(name):
                report.error("models/%s" % name, "only .glb files belong here")

    entries = {}
    if os.path.isdir(entries_dir):
        for name in sorted(os.listdir(entries_dir)):
            if not name.endswith(".json"):
                if not _is_housekeeping(name):
                    report.error("entries/%s" % name, "only .json files belong here")
                continue
            sprite_id = name[:-5]
            entry = _load_json(os.path.join(entries_dir, name), report,
                               "entries/%s" % name)
            if entry is not None:
                entries[sprite_id] = entry

    for sprite_id in sorted(model_ids - set(entries)):
        report.error("models/%s.glb" % sprite_id,
                     "no entries/%s.json describing it" % sprite_id)

    for sprite_id in sorted(entries):
        check_entry(root, sprite_id, entries[sprite_id], report, catalog)

    index = _load_json(os.path.join(root, "index.json"), report, "index.json")
    if index is not None:
        check_index(root, index, entries, report)

    return report, len(model_ids), len(entries)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=".")
    args = parser.parse_args(argv)

    report, model_count, entry_count = validate(args.root)

    if report.ok():
        print("validate_repo: OK (%d model(s), %d entr%s)"
              % (model_count, entry_count, "y" if entry_count == 1 else "ies"))
        return 0

    for error in report.errors:
        print("FAIL %s" % error)
    print("\nvalidate_repo: %d problem(s)" % len(report.errors))
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
