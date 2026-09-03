"""Install community 3D models from the public database into this checkout.

What this is for
----------------
PZ draws everything as flat isometric sprites. Some objects read badly that way
no matter how the texture is treated, so the community makes real 3D models for
them and publishes them at:

    https://github.com/DevelopmentStatus/pz-godot-models

`assets/models/furniture/` is gitignored, so cloning this repo gets you none of
them. This is how they arrive.

Why the models have no textures in them
---------------------------------------
Project Zomboid's art belongs to The Indie Stone and is not redistributable, so
nothing in that repository contains a single pixel of it. A model carries
geometry, normals and UVs, and names the sprite it wants pixels from in its
material ("pz:fixtures_counters_01_67"). The game resolves that at load time
against the atlas YOU generated from YOUR OWN copy of the game - see
MeshOverrides._pz_material() in scripts/world/MeshOverrides.gd.

The practical consequence: a model whose sprite is missing from your export
renders in flat colours rather than looking right. This script warns about that
up front rather than leaving you to notice in game.

What it touches
---------------
    assets/models/furniture/<sprite_id>.glb   downloaded, hash-verified
    data/mesh_overrides.json                  by_type entries merged in
    data/pz_models_installed.json             receipt, so --prune can undo it

It only ever writes `by_type` keys for sprite ids present in the published
index. Hand-authored entries for anything else - and by_sheet, by_kind, the
comments, `enabled` - are left exactly as they are. A .bak is written first.

Usage:
    tools\\install_models.bat                  (Windows, the normal way)
    python tools/install_models.py             (same thing)
    python tools/install_models.py --dry-run   say what would change, write nothing
    python tools/install_models.py --only fixtures_counters
    python tools/install_models.py --list      show what is published
    python tools/install_models.py --prune     remove what this script installed
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
from datetime import datetime, timezone

REPO = "DevelopmentStatus/pz-godot-models"
RAW_BASE = "https://raw.githubusercontent.com"
DEFAULT_BRANCH = "main"

MODEL_DIR = os.path.join("assets", "models", "furniture")
OVERRIDES_PATH = os.path.join("data", "mesh_overrides.json")
RECEIPT_PATH = os.path.join("data", "pz_models_installed.json")
MANIFEST_PATH = os.path.join("assets", "pz", "manifest.json")
MISSING_PATH = os.path.join("assets", "pz", "missing.json")

RECEIPT_SCHEMA = 1
USER_AGENT = "pz-godot-install-models"

# Anything larger than this from a "textureless model" is not a model.
MAX_MODEL_BYTES = 16 * 1024 * 1024


class InstallError(Exception):
    """Something that should stop the run, phrased for whoever ran it."""


# --------------------------------------------------------------- repo layout

def find_repo_root(explicit=None):
    """The pz-godot checkout to install into."""
    if explicit:
        root = os.path.abspath(explicit)
        if not os.path.exists(os.path.join(root, "project.godot")):
            raise InstallError(f"{root} is not a Godot project (no project.godot in it)")
        return root

    # Walk up from this script, so it works from anywhere including a
    # double-clicked .bat that starts in system32.
    here = os.path.dirname(os.path.abspath(__file__))
    while True:
        if os.path.exists(os.path.join(here, "project.godot")):
            return here
        parent = os.path.dirname(here)
        if parent == here:
            raise InstallError(
                "Could not find the pz-godot checkout. Run this from inside it, "
                "or pass --repo-root <path>."
            )
        here = parent


# ------------------------------------------------------------------ fetching

def fetch(url, binary=False):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise InstallError(f"{url} -> HTTP {exc.code} {exc.reason}")
    except urllib.error.URLError as exc:
        raise InstallError(
            f"Could not reach GitHub ({exc.reason}). Check your connection and try again."
        )
    return data if binary else data.decode("utf-8")


def resolve_commit(branch):
    """The commit a branch currently points at, or None if it cannot be asked.

    Everything in a run is then fetched at that commit rather than at the branch
    name, for two reasons that are really one reason.

    raw.githubusercontent caches by URL, and a branch URL is mutable, so a run
    can genuinely see index.json from one commit and a model file from the next -
    which surfaces as a checksum mismatch and reads to the user as a corrupted
    download rather than what it is. Pinning to a commit SHA makes the URLs
    immutable, so a cache hit is necessarily the right bytes and the whole run is
    one consistent snapshot.

    Unauthenticated, so it is subject to GitHub's 60-requests-per-hour-per-IP
    limit. That is one request per run, but if it does fail the run carries on
    against the branch name - a possibly-stale install is better than no install.
    """
    text = fetch(f"https://api.github.com/repos/{REPO}/commits/{branch}")
    if text is None:
        return None
    try:
        return json.loads(text)["sha"]
    except (ValueError, KeyError):
        return None


def fetch_index(ref, branch):
    text = fetch(f"{RAW_BASE}/{REPO}/{ref}/index.json")
    if text is None:
        raise InstallError(f"index.json is not in {REPO} on branch {branch}")
    try:
        index = json.loads(text)
    except ValueError as exc:
        raise InstallError(f"index.json did not parse: {exc}")
    if "models" not in index:
        raise InstallError("index.json has no models section; the repository may be mid-update")
    return index


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# ------------------------------------------------------------------- receipt

def load_receipt(root):
    path = os.path.join(root, RECEIPT_PATH)
    if not os.path.exists(path):
        return {"schema": RECEIPT_SCHEMA, "models": {}}
    try:
        with open(path, encoding="utf-8") as handle:
            receipt = json.load(handle)
    except ValueError:
        print("  ! the install receipt is unreadable; treating everything as new")
        return {"schema": RECEIPT_SCHEMA, "models": {}}
    receipt.setdefault("models", {})
    return receipt


def write_receipt(root, receipt, branch):
    receipt["schema"] = RECEIPT_SCHEMA
    receipt["repo"] = REPO
    receipt["branch"] = branch
    receipt["installed_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    path = os.path.join(root, RECEIPT_PATH)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(receipt, handle, indent="\t", ensure_ascii=False, sort_keys=True)
        handle.write("\n")


# ----------------------------------------------------------- mesh_overrides

def load_overrides(root):
    path = os.path.join(root, OVERRIDES_PATH)
    if not os.path.exists(path):
        # A checkout with no overrides file is fine - make one shaped the way
        # MeshOverrides.create() expects.
        return {"enabled": True, "by_kind": {}, "by_sheet": {}, "by_type": {}}
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save_overrides(root, data, trailing_newline=True):
    """Write it back the way the file's other writers do.

    Tabs, a .bak first, and every key preserved - including `_comment`,
    `_note_corners` and anything a later reader adds. This file is hand-edited
    and self-documenting; a save that reformatted it or dropped its own
    documentation would be a bad trade.

    The trailing newline is matched to whatever the file already had rather than
    imposed. The two existing writers disagree - the Blender add-on's
    overrides.py ends with one, Godot's MeshOverrides.save_overrides() does not -
    so picking either would show up as a spurious one-line diff in somebody's
    checkout the first time this ran. This tool has no business having an opinion
    about it.
    """
    path = os.path.join(root, OVERRIDES_PATH)
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent="\t", ensure_ascii=False)
        if trailing_newline:
            handle.write("\n")


def overrides_end_with_newline(root):
    path = os.path.join(root, OVERRIDES_PATH)
    if not os.path.exists(path):
        return True  # A file we are creating gets the POSIX-correct ending.
    with open(path, "rb") as handle:
        if handle.seek(0, os.SEEK_END) == 0:
            return True
        handle.seek(-1, os.SEEK_END)
        return handle.read(1) == b"\n"


# ------------------------------------------------------------------ bindings

def load_local_sprites(root):
    """Which sprites this checkout's own atlas actually has.

    Returns None when there is no manifest, which is the normal state of a fresh
    clone that has not run setup.bat yet - no warnings can be made, and none are.
    """
    path = os.path.join(root, MANIFEST_PATH)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            return set(json.load(handle).get("sprites", {}))
    except ValueError:
        return None


def warn_about_bindings(index, actions, local_sprites):
    """Say which models will render untextured, and why.

    A warning rather than a failure: the model is still better geometry than a
    flat quad, and the sprite may well appear the next time the atlas is
    exported. Being told up front beats wondering why one prop is grey.
    """
    if local_sprites is None:
        return
    unresolvable = {}
    for sprite_id, _ in actions:
        for binding in index["models"][sprite_id].get("texture_bindings", []):
            if binding not in local_sprites:
                unresolvable.setdefault(sprite_id, []).append(binding)

    if not unresolvable:
        return
    print()
    print(f"  Note: {len(unresolvable)} model(s) bind to sprites your atlas does not have.")
    print("  They will install and render, but in flat colours rather than PZ's art:")
    for sprite_id, missing in sorted(unresolvable.items())[:10]:
        print(f"    {sprite_id}  <- {', '.join(missing)}")
    if len(unresolvable) > 10:
        print(f"    ... and {len(unresolvable) - 10} more")
    print("  Re-export your atlas (build_world.bat) if you expected these to be present.")


# -------------------------------------------------------------------- install

def stale_import_path(model_path):
    """Godot's import sidecar for a model.

    Deleted whenever the .glb underneath changes, for the same reason
    ModelPlacementEditor._forget_stale_import() does it: the sidecar pins the
    previously imported resource, so without removing it the editor keeps
    handing back the OLD model from a path whose contents have changed.
    """
    return model_path + ".import"


# A local model this script is about to overwrite is set aside under this
# suffix rather than destroyed.
#
# assets/models/furniture/ is where people put their OWN models - dragged in,
# calibrated in game with the P editor, sometimes bought. It is gitignored, so
# there is no `git checkout` to undo an overwrite with. Preserving the file makes
# --prune able to put back what was there rather than leaving a restored rule
# pointing at a model that no longer exists.
REPLACED_SUFFIX = ".replaced"


def preserve_local(dest, receipt_record, dry_run):
    """Set aside a model this script did not install, before overwriting it.

    Returns True if something was preserved. A file whose hash matches what the
    receipt says this script last installed is ours, so it is simply overwritten.
    """
    if not os.path.exists(dest):
        return False
    if receipt_record and sha256_file(dest) == receipt_record.get("sha256"):
        return False  # Ours from a previous run - nothing of anyone's to keep.
    if dry_run:
        return True
    backup = dest + REPLACED_SUFFIX
    if not os.path.exists(backup):
        # Never overwrite an existing backup: the first one is the user's own
        # file, and a second run must not bury it under a community model.
        shutil.move(dest, backup)
        sidecar = stale_import_path(dest)
        if os.path.exists(sidecar):
            os.replace(sidecar, backup + ".import")
    return True


def download_model(url, dest, expected_sha, expected_size, dry_run):
    if dry_run:
        return
    data = fetch(url, binary=True)
    if data is None:
        raise InstallError(f"{url} is missing from the repository")
    if len(data) > MAX_MODEL_BYTES:
        raise InstallError(f"{url} is {len(data)} bytes, over the {MAX_MODEL_BYTES} limit")

    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha:
        # Verified BEFORE anything is written, the same way tools/pz_decompile.py
        # checks its download. A file that does not match the index is either a
        # truncated transfer or not the file the index is describing, and either
        # way it must not reach the game.
        raise InstallError(
            f"checksum mismatch for {os.path.basename(dest)}:\n"
            f"    index says {expected_sha}\n"
            f"    download is {digest}\n"
            "  Nothing was written. Try again; if it persists, report it."
        )
    if expected_size and len(data) != expected_size:
        raise InstallError(
            f"size mismatch for {os.path.basename(dest)}: expected {expected_size}, got {len(data)}"
        )

    os.makedirs(os.path.dirname(dest), exist_ok=True)
    # Written beside the target and moved into place, so an interrupted run
    # cannot leave a half-written .glb that hashes fine next time because the
    # receipt says it is already installed.
    handle, temp_path = tempfile.mkstemp(dir=os.path.dirname(dest), suffix=".part")
    try:
        with os.fdopen(handle, "wb") as out:
            out.write(data)
        os.replace(temp_path, dest)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    sidecar = stale_import_path(dest)
    if os.path.exists(sidecar):
        os.unlink(sidecar)


def plan(index, receipt, root, only):
    """What to do, per sprite: install / update / skip."""
    install, update, skip = [], [], []
    for sprite_id, entry in sorted(index["models"].items()):
        if only and only not in sprite_id:
            continue
        path = os.path.join(root, MODEL_DIR, f"{sprite_id}.glb")
        if not os.path.exists(path):
            install.append((sprite_id, entry))
            continue
        # Hashed rather than trusting the receipt: a file edited or replaced
        # locally should be noticed, and a receipt from an interrupted run
        # should not cause a missing update.
        if sha256_file(path) == entry["sha256"]:
            skip.append((sprite_id, entry))
        else:
            update.append((sprite_id, entry))
    return install, update, skip


def run_install(root, index, ref, branch, only, dry_run):
    receipt = load_receipt(root)
    install, update, skip = plan(index, receipt, root, only)
    actions = install + update

    print(f"  published : {len(index['models'])} model(s)")
    if only:
        print(f"  filter    : ids containing {only!r}")
    print(f"  to install: {len(install)}")
    print(f"  to update : {len(update)}")
    print(f"  up to date: {len(skip)}")

    if not actions:
        print("\n  Nothing to do.")
        return 0

    warn_about_bindings(index, actions, load_local_sprites(root))

    overrides = load_overrides(root)
    keep_newline = overrides_end_with_newline(root)
    by_type = overrides.setdefault("by_type", {})
    print()

    failures = []
    for sprite_id, entry in actions:
        verb = "install" if (sprite_id, entry) in install else "update "
        dest = os.path.join(root, MODEL_DIR, f"{sprite_id}.glb")
        url = f"{RAW_BASE}/{REPO}/{ref}/{entry['path']}"
        size_kb = entry.get("size", 0) / 1024.0
        preserved = preserve_local(dest, receipt["models"].get(sprite_id), dry_run)
        try:
            download_model(url, dest, entry["sha256"], entry.get("size"), dry_run)
        except InstallError as exc:
            print(f"  {verb} {sprite_id:<44} FAILED")
            print(f"    {exc}")
            failures.append(sprite_id)
            continue

        previous = by_type.get(sprite_id)
        rule = {
            "offset": entry.get("offset", [0, 0, 0]),
            "rotation": entry.get("rotation", 0),
            "scale": entry.get("scale", 1),
            "scene": f"res://assets/models/furniture/{sprite_id}.glb",
        }
        replaced = previous is not None and previous != rule
        by_type[sprite_id] = rule

        receipt["models"][sprite_id] = {
            "version": entry.get("version"),
            "sha256": entry["sha256"],
            "size": entry.get("size"),
            # Kept so --prune can put back a hand-authored rule rather than
            # deleting it, on the assumption that anything already there was
            # deliberate.
            "previous_override": previous if replaced else None,
            # A model of the user's own was moved aside to make room; --prune
            # puts it back.
            "preserved_local": preserved,
        }

        by = entry.get("author", "?")
        notes = []
        if replaced:
            notes.append("replaced a local rule")
        if preserved:
            notes.append(f"your own model kept as {sprite_id}.glb{REPLACED_SUFFIX}")
        print(f"  {verb} {sprite_id:<44} v{entry.get('version', '?')}  {size_kb:6.1f} KB  by {by}")
        if notes:
            print(f"          ({'; '.join(notes)})")

    if not dry_run:
        save_overrides(root, overrides, keep_newline)
        write_receipt(root, receipt, branch)

    print()
    if dry_run:
        print("  --dry-run: nothing was written.")
    else:
        installed = len(actions) - len(failures)
        print(f"  Wrote {installed} model(s) to {MODEL_DIR}")
        print(f"  Merged {installed} by_type entr{'y' if installed == 1 else 'ies'} into {OVERRIDES_PATH}")
        print(f"  (a .bak of the previous file is beside it)")

    credits = sorted({index["models"][s].get("author", "?") for s, _ in actions})
    if credits:
        print(f"\n  Models by: {', '.join(credits)}")
        print("  Each carries its own licence - see the entry files in the model repo.")

    if failures:
        print(f"\n  {len(failures)} model(s) failed: {', '.join(failures)}")
        return 1
    return 0


def run_prune(root, dry_run):
    """Undo what this script installed, and nothing else."""
    receipt = load_receipt(root)
    if not receipt["models"]:
        print("  Nothing recorded as installed; nothing to remove.")
        return 0

    overrides = load_overrides(root)
    keep_newline = overrides_end_with_newline(root)
    by_type = overrides.setdefault("by_type", {})
    removed = 0
    restored = 0

    for sprite_id, record in sorted(receipt["models"].items()):
        path = os.path.join(root, MODEL_DIR, f"{sprite_id}.glb")
        backup = path + REPLACED_SUFFIX
        if os.path.exists(path) and not dry_run:
            os.unlink(path)
            sidecar = stale_import_path(path)
            if os.path.exists(sidecar):
                os.unlink(sidecar)

        # If this script moved one of the user's own models aside to install
        # over it, put it back. Restoring the rule without the file it points at
        # would leave the game loading nothing.
        restored_file = False
        if os.path.exists(backup) and not dry_run:
            shutil.move(backup, path)
            if os.path.exists(backup + ".import"):
                os.replace(backup + ".import", stale_import_path(path))
            restored_file = True

        previous = record.get("previous_override")
        if previous is not None:
            # There was a hand-authored rule here before this script overwrote
            # it. Put it back rather than deleting it - it was somebody's work.
            by_type[sprite_id] = previous
            restored += 1
            print(f"  removed {sprite_id:<44} (restored the local rule it replaced)")
        else:
            by_type.pop(sprite_id, None)
            print(f"  removed {sprite_id}")
        if restored_file:
            print(f"          {'':<44} (put your own {sprite_id}.glb back)")
        removed += 1

    if not dry_run:
        save_overrides(root, overrides, keep_newline)
        receipt["models"] = {}
        write_receipt(root, receipt, receipt.get("branch", DEFAULT_BRANCH))

    print(f"\n  Removed {removed} model(s)" + (f", restored {restored} local rule(s)" if restored else ""))
    if dry_run:
        print("  --dry-run: nothing was written.")
    return 0


def run_list(index):
    print(f"  {len(index['models'])} model(s) published in {REPO}:\n")
    for sprite_id, entry in sorted(index["models"].items()):
        bindings = ", ".join(entry.get("texture_bindings", [])) or "no sprite bindings"
        print(f"  {sprite_id:<44} v{entry.get('version', '?'):<3} by {entry.get('author', '?'):<16} <- {bindings}")
    return 0


def main(argv):
    parser = argparse.ArgumentParser(
        description="Install community 3D models into this pz-godot checkout.",
    )
    parser.add_argument("--repo-root", help="the pz-godot checkout (default: found automatically)")
    parser.add_argument("--branch", default=DEFAULT_BRANCH, help="branch of the model repo")
    parser.add_argument("--only", help="only sprite ids containing this substring")
    parser.add_argument("--dry-run", action="store_true", help="say what would change, write nothing")
    parser.add_argument("--prune", action="store_true", help="remove what this script installed")
    parser.add_argument("--list", action="store_true", help="list what is published and exit")
    args = parser.parse_args(argv)

    try:
        root = find_repo_root(args.repo_root)
        print()
        print("  ================================================================")
        print("   PZ-GODOT  --  community model install")
        print("  ================================================================")
        print(f"  repo      : {REPO} ({args.branch})")
        print(f"  into      : {root}")

        if args.prune:
            return run_prune(root, args.dry_run)

        # One commit for the whole run - see resolve_commit().
        commit = resolve_commit(args.branch)
        ref = commit or args.branch
        if commit:
            print(f"  at commit : {commit[:10]}")
        else:
            print("  at commit : could not resolve; using the branch tip directly")
        print()

        index = fetch_index(ref, args.branch)
        if args.list:
            return run_list(index)
        return run_install(root, index, ref, args.branch, args.only, args.dry_run)
    except InstallError as exc:
        print(f"\n  ERROR: {exc}\n")
        return 1
    except KeyboardInterrupt:
        print("\n  Interrupted. Re-run to carry on - finished models are kept.\n")
        return 130


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
