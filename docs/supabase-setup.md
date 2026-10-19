# Shared price database (Supabase) setup

Done once by the project owner. Friends never see any of this: they only get the zip.

1. Create a free account at supabase.com and a **New project** (any name, a strong database password, a region close
   to Europe, for example Frankfurt). Wait until it says the project is ready.
2. Open **SQL Editor -> New query**, paste the whole of `docs/remote-schema.sql`, press **Run**. Under
   **Table Editor** there is now a table `observations`.
3. Open **Project Settings -> API**. Copy:
   - **Project URL** (looks like `https://xxxx.supabase.co`)
   - the **anon public** key.

   Never share or use the `service_role` key.
4. Put the same values in your own `config.toml`:

   ```toml
   contributor = "YourName"

   [remote]
   url = "https://xxxx.supabase.co"
   key = "<anon public key>"
   world = "Andromeda"
   ```

   Start `python -m dune_market run`; the console line should say "Sharing prices with friends".
5. Build the friends' zip (see `packaging/README.md`) with the same URL and key.

Notes
- The anon key is meant to be public; the table's policies let it read and add rows but never change or delete them.
  Anyone holding the zip can read and add prices, so share it only with friends you trust.
- Free tier: 500 MB. A price row is roughly 200 bytes, so this lasts a long time. Check the dashboard now and then.
- To see who uploaded what, open the table in **Table Editor**; to remove bad rows, use the dashboard (owner only).
