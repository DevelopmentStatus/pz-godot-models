# pz-godot community model database

Community-made 3D models for [pz-godot](https://github.com/DevelopmentStatus/pz-godot),
which renders Project Zomboid's world in Godot. PZ draws everything as flat
isometric sprites, and some objects just don't read well that way. This is
where the 3D replacements live.

**Everything here is claimed, reviewed, and voted on through Discord.** The
bot is the only thing that writes to this repo.

Browse the models in 3D at
**[developmentstatus.github.io/pz-godot-models](https://developmentstatus.github.io/pz-godot-models/)**.

## There's no game art in this repository

Every `.glb` here contains geometry, normals, and UVs. No texture data at
all. A model says which sprite it wants pixels from by naming its material:

```
pz:fixtures_counters_01_67
```

At load time, the game resolves that name against the atlas you generated
from your own Project Zomboid Build 42 install, and maps the model's UVs
onto that sprite's slice of it. A model with several materials can pull
from several sprites.

This is deliberate. Project Zomboid's art belongs to The Indie Stone, not
to us, and pz-godot's job is to ship the tools, not the output. Coordinates
and a string don't infringe anyone's licence; a baked-in texture crop would
republish that art a few thousand times over.

The rule is enforced mechanically, not on trust. Any submission whose
`.glb` contains a non-empty `images` or `textures` array is rejected before
it's ever staged, and CI re-checks every file in the repo on every push.
[`tools/glb_check.py`](tools/glb_check.py) is the actual specification.

An author's own original texture can be admitted by an admin on a
case-by-case basis. It gets recorded in the entry as `embedded_textures`,
along with who approved it and why. Even then, an image whose name
collides with a PZ sheet or sprite id is refused outright.

## Installing the models

The [install page](https://developmentstatus.github.io/pz-godot-models/#/install)
hands you the two files directly. Otherwise download this repository's
[`install/`](install/) folder, then either drag your pz-godot folder onto
`install-models.bat`, or run it with the path:

```
install-models.bat C:\path\to\pz-godot
```

Dropping the whole `install/` folder inside a pz-godot checkout also
works; it finds the checkout on its own.

pz-godot also ships its own copy as `tools/install_models.bat`, which
needs no arguments. Use that one if you already have the game repo cloned.

Either way, the installer downloads only what changed, verifies each file
against the SHA-256 in `index.json` before writing it, and merges the
`by_type` entries into your `data/mesh_overrides.json` without touching
anything you wrote by hand. `--prune` undoes all of it, restoring any
model or rule of your own that it displaced.

If a model binds to a sprite your own export doesn't have, the installer
says so, and the model just renders in its fallback colour instead of
failing.

## The website

[`index.html`](index.html) is the whole site: the model browser, the 3D viewer,
the install page, and this README. GitHub Pages serves it straight off `main`,
so a push publishes it. There is no build step and nothing to regenerate.

It reads the same files everything else does. The grid comes from `index.json`,
each model's page from its `entries/` file, and the Install and Readme tabs are
`install/README.md` and this file, fetched and rendered. Edit a README and the
site changes with it; publish a model and it appears without anyone touching
the page. `.nojekyll` is there so Pages publishes the repository verbatim
instead of running it through Jekyll.

The Discord bot's viewer links keep working unchanged:

```
?a=<glb url>&b=<glb url>&a_label=Current&b_label=Challenger&sprite=<sprite_id>
```

`a` alone shows one model, `a` and `b` show a side-by-side compare with linked
cameras for challenge votes, and `?sprite=<id>` on its own opens that sprite's
page. Model URLs are only loaded from this site, GitHub, or Discord's CDN, so a
hand-crafted link cannot use the site to show something this project never
approved.

## Layout

| Path | What it is |
|---|---|
| `index.html` | The website: model viewer, install page, and this README. Served by GitHub Pages from `main`. |
| `index.json` | The whole database in one file. What the installer fetches. Derived, regenerated on every publish. |
| `models/<sprite_id>.glb` | The current approved model for a sprite. One file, always the latest. |
| `entries/<sprite_id>.json` | That sprite's metadata and full version history. |
| `catalog/sprites.json` | Every PZ sprite id a model may be submitted for. Ids and kinds only, no art, no atlas layout. |
| `schema/entry.schema.json` | The shape of an entry file. |
| `tools/glb_check.py` | The no-textures rule, as runnable code. Used by CI. |
| `install/` | A standalone copy of the installer, for people without a pz-godot checkout. |

### Version history without duplicate files

`models/<sprite_id>.glb` only ever holds the current version. Older ones
aren't deleted: every version is a git blob, and a blob reachable from
history is never garbage-collected. Each entry records the `blob_sha` of
every version it has ever had, so any of them can be fetched forever:

```
GET /repos/DevelopmentStatus/pz-godot-models/git/blobs/<blob_sha>
```

History is append-only. Reverting to an old model re-commits that blob as
a new version instead of rewriting the past.

## Contributing

Through the Discord, not through pull requests. The claim system exists so
twenty people don't independently model the same chair.

1. Claim a sprite with `/task claim`. You have 24 hours before it returns
   to the pool for someone else.
2. Model it. In Blender, use the PZ Tile Viewer add-on's *Export for
   Community*; it strips the textures and names your materials for you.
3. `/task submit` with the `.glb`. It's checked immediately and staged;
   nothing reaches this repo until an admin approves it.
4. Think an existing model can be beaten? `/model challenge` with yours.
   Both go head-to-head in a community vote, and the loser stays in the
   version history.

Authoring rules for pivot, scale, and orientation are in pz-godot's
[`docs/project/pipeline/model_authoring.md`](https://github.com/DevelopmentStatus/pz-godot/blob/main/docs/project/pipeline/model_authoring.md).
Get the pivot wrong and no calibration can rescue it.

## Licence

The tooling, schema, and metadata in this repository are MIT (see
`LICENSE`).

Models are not covered by that. Each carries its own `license` field,
chosen by its author, recorded in its entry and repeated in `index.json`.
Check the entry before reusing a model outside pz-godot.
