# install/

`pz_models_install.py` is a copy of pz-godot's own `tools/install_models.py`,
for anyone who wants to install the models without cloning the game repo's
tooling.

**If you have a pz-godot checkout, use the copy in it instead** — run
`tools\install_models.bat`. That one is the original; this is a convenience
mirror and can lag behind it.

Run this copy against a checkout explicitly, since it cannot find one by walking
up from wherever you saved it:

```
python pz_models_install.py --repo-root C:\path\to\pz-godot
```

`--dry-run` says what it would change without writing, `--list` shows what is
published, and `--prune` removes what it installed — putting back any model and
any `mesh_overrides.json` rule of your own that it moved aside.
