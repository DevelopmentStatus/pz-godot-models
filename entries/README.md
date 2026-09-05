# entries/

One `.json` per sprite: its current model, and every version it has ever had.

Shaped by `../schema/entry.schema.json`, enforced by `../tools/validate_repo.py`
in CI. `history` is append-only. Reverting to an old model re-publishes that
blob as a *new* version rather than rewriting the past, so the record of what was
live and when is never lost.

`texture_bindings` is read out of the `.glb` itself at validation time rather
than declared by the author, so it cannot disagree with the file.

Written by the Discord bot. Not edited by hand.
