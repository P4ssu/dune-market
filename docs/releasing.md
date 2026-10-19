# Releasing a new version

Friends are told about new versions by an in-game notice (and a console line). Nothing is installed
automatically; they download the new zip and run `Install.bat` again.

1. Change the version in `src/dune_market/__init__.py` (and `version` in `pyproject.toml`), for example `1.1.1`.
   The notice only appears for people whose version is lower than the newest `releases` row.
2. Run the tests, then build the program and the zip (see `packaging/README.md`).
3. Upload `dist\DuneMarket-Setup.zip` (replace the old file on the same share link, or make a new link).
4. Publish the release: Supabase dashboard -> SQL Editor -> run

   ```sql
   insert into public.releases (version, download_url, notes)
   values ('1.1.1', 'https://<download link>', 'Short note: what is new');
   ```

   Within a few hours (and on the next start) everyone with an older version sees the notice.
5. Update the pinned Discord message if the link changed.

The table is created once with `docs/remote-schema-releases.sql`.
