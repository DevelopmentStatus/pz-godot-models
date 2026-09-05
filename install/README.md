# install/

Installs the community models into a pz-godot checkout, for anyone who wants
them without cloning the game repo's tooling.

`install-models.bat` is the way in on Windows. Three ways to use it:

1. **Drag your pz-godot folder onto `install-models.bat`.**
2. Run it with the path: `install-models.bat C:\path\to\pz-godot`
3. Drop this whole `install/` folder inside a pz-godot checkout and
   double-click. It finds the checkout by walking up from where it sits.

Or call the script directly, on any platform:

```
python pz_models_install.py --repo-root /path/to/pz-godot
```

**If you have a pz-godot checkout, its own `tools/install_models.bat` is the
better entry point**: it needs no path at all. That copy is the original;
`pz_models_install.py` here is a convenience mirror and can lag behind it.

`--dry-run` says what it would change without writing, `--list` shows what is
published, and `--prune` removes what it installed, putting back any model and
any `mesh_overrides.json` rule of your own that it moved aside.
