-- Shared price table for Dune Market (Supabase: SQL Editor -> New query -> paste -> Run).
-- Friends use the project's "anon" key. With the policies below that key can read and add rows,
-- but nobody can change or delete rows.

create table if not exists public.observations (
    uid          text primary key,          -- unique id made by the program, so repeats never duplicate
    world        text not null,             -- prices are per World
    name         text not null,
    category     text not null,
    grade        text not null,
    kind         text not null check (kind in ('sell', 'buy')),
    observed_at  timestamptz not null,
    contributor  text not null,
    avg          bigint,
    low          bigint,
    price        bigint,
    expires_in_s bigint,
    created_at   timestamptz not null default now()  -- used by the programs to download only new rows
);

create index if not exists observations_world_created on public.observations (world, created_at);

alter table public.observations enable row level security;

create policy "friends can read prices" on public.observations
    for select to anon using (true);

create policy "friends can add prices" on public.observations
    for insert to anon with check (true);
-- No update or delete policy on purpose.
