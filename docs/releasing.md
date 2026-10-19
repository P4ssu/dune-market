# Releasing a new version

Friends' copies of the program update themselves: they check GitHub for the newest release, download it in the
background, verify it and install it the next time they start the program. Nothing is uploaded by hand.

## Publish a new version

1. Make and test the change.
2. Raise the version in `src/dune_market/__init__.py` (and `version` in `pyproject.toml`), for example `1.2.1`.
3. Commit and push, then tag and push the tag. The tag message becomes the release notes; its first line is
   shown to friends in the game, so keep it short:

   ```
   git push
   git tag -a v1.2.1 -m "Armor popups now work for every item"
   git push origin v1.2.1
   ```

4. GitHub Actions (`.github/workflows/release.yml`) runs the tests, builds the program, checks it and publishes the
   release with `DuneMarket-update.zip` and its checksum. Follow it with `gh run watch`. It takes about 10 minutes.
5. Within about 6 hours (or at their next start) everyone with an older version gets a notice in the game, and the
   update installs the next time they start the program.

The workflow refuses to publish if the tag and `__version__` differ.

## What the update contains

Only the program (`DuneMarket.exe`, `_internal`, `start-solid.bat`). It never contains settings or keys, and installing
it never touches the friend's `config.toml` or `prices.db`. The shared database key is only in the installer zip
(`packaging\make-friend-zip.ps1`), which is shared privately.

Friends can turn automatic updates off with `auto_update = false` in `config.toml` (they are then only told).

## First installation of a new friend

Give them the installer zip built locally with `packaging\make-friend-zip.ps1` (see `packaging/README.md`). Even if it
is an older version, the program updates itself on its first start.

## If something goes wrong

* A broken release: publish a fixed one with a higher version. Friends who already got the broken one update again.
* Remove a release you do not want anyone to receive: delete it on the GitHub releases page; copies only update from
  the newest release.
* The updater is in `src/dune_market/update.py`; its installer script is written to `updates\apply.bat` next to the
  program when an update is applied.
