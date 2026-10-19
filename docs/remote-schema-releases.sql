-- Release notices for Dune Market (Supabase: SQL Editor -> New query -> paste -> Run).
-- Running copies read the newest row and tell the user when it is newer than themselves.
-- The shared (anon) key can only READ this table; the owner adds rows in the dashboard.

create table if not exists public.releases (
    id           bigint generated always as identity primary key,
    version      text not null,                 -- e.g. 1.1.1
    download_url text not null default '',      -- where the new zip can be downloaded
    notes        text not null default '',      -- one short line: what is new
    created_at   timestamptz not null default now()
);

alter table public.releases enable row level security;

create policy "everyone can read releases" on public.releases
    for select to anon using (true);
-- No insert/update/delete policy on purpose.
