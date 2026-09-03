# pz-godot community model database

Community-made 3D models for [pz-godot](https://github.com/DevelopmentStatus/pz-godot),
which renders Project Zomboid's world in Godot. PZ draws everything as flat
isometric sprites; some objects read badly that way no matter how the texture is
treated. This is where the replacements live.

**Everything here is claimed, reviewed and voted on through Discord.** The bot is
the only thing that writes to this repo.

---

## There is no game art in this repository

Every `.glb` here contains geometry, normals and UVs — and **no texture data at
all**. A model says which sprite it wants pixels from by *naming its material*:

```
pz:fixtures_counters_01_67
```

At load time the game resolves that name against the atlas **you** generated from
**your own** Project Zomboid Build 42 install, and maps the model's UVs onto that
sprite's slice of it. A model with several materials can pull from several
sprites.

This is deliberate and non-negotiable. Project Zomboid's art belongs to The Indie
Stone and is not ours to redistribute; pz-godot's position is to ship the tools,
not the output. Coordinates and a string break nobody's licence. A baked-in
texture crop would republish their art a few thousand times over.

The rule is enforced mechanically, not on the honour system. Any submission whose
`.glb` contains a non-empty `images` or `textures` array is rejected before it is
ever staged, and CI re-checks every file in this repo on every push. See
[`tools/glb_check.py`](tools/glb_check.py) — that file *is* the specification.

An author's own original texture can be admitted by an admin on a case-by-case
basis, recorded in the entry as `embedded_textures` with who approved it and why.
Even then, an image whose name collides with a PZ sheet or sprite id is refused
outright.

---

## Installing the models

From a pz-godot checkout:

```bash
tools/install_models.bat
```

It downloads only what changed, verifies each file against the SHA-256 in
`index.json` before writing it, and merges the `by_type` entries into your
`data/mesh_overrides.json` without touching anything you authored by hand.

If a model binds to a sprite your own export doesn't have, the installer says so
and the model renders in its fallback colour rather than failing.

---

## Layout

| Path | What it is |
|---|---|
| `index.json` | The whole database in one file — what the installer fetches. Derived; regenerated on every publish. |
| `models/<sprite_id>.glb` | The current approved model for a sprite. One file, always the latest. |
| `entries/<sprite_id>.json` | That sprite's metadata and full version history. |
| `catalog/sprites.json` | Every PZ sprite id a model may be submitted for. Ids and kinds only — no art, no atlas layout. |
| `schema/entry.schema.json` | The shape of an entry file. |
| `tools/glb_check.py` | The no-textures rule, as runnable code. Used by CI. |
| `install/` | A standalone copy of the installer, for people without a pz-godot checkout. |

### Version history without duplicate files

`models/<sprite_id>.glb` only ever holds the current version. Older ones are not
deleted — every version is a git blob, and a blob reachable from history is never
garbage-collected. Each entry records the `blob_sha` of every version it has ever
had, so any of them can be fetched forever:

```
GET /repos/DevelopmentStatus/pz-godot-models/git/blobs/<blob_sha>
```

History is append-only. Reverting to an old model re-commits that blob as a *new*
version rather than rewriting the past.

---

## Contributing

Through the Discord, not through pull requests — the claim system exists so that
twenty people don't independently model the same chair.

1. Claim a sprite with `/task claim`. You have 24 hours before it returns to the
   pool for someone else.
2. Model it. In Blender, use the **PZ Tile Viewer** add-on's *Export for
   Community* — it strips the textures and names your materials for you.
3. `/task submit` with the `.glb`. It is checked immediately and staged; nothing
   reaches this repo until an admin approves it.
4. Think an existing model can be beaten? `/model challenge` with yours. Both go
   head-to-head in a community vote, and the loser stays in the version history.

Authoring rules — pivot, scale, orientation — are in pz-godot's
[`docs/project/pipeline/model_authoring.md`](https://github.com/DevelopmentStatus/pz-godot/blob/main/docs/project/pipeline/model_authoring.md).
Get the pivot wrong and no calibration can rescue it.

---

## Licence

The tooling, schema and metadata in this repository are MIT (see `LICENSE`).

**Models are not covered by that.** Each carries its own `license` field, chosen
by its author, recorded in its entry and repeated in `index.json`. Check the
entry before reusing a model outside pz-godot.
