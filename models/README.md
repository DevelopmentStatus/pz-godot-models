# models/

One `.glb` per sprite, named for the sprite it replaces, always holding the
current approved version.

Old versions are not kept here. Every version ever published is still a git blob
reachable from history, and each entry in `entries/` records the `blob_sha` of
every version it has had, so any of them can be fetched by SHA forever. See the
repository README.

Files here are written by the Discord bot. Nothing in this folder is edited by
hand.
