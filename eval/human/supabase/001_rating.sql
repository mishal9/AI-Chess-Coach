-- Human rating store for the GitHub Pages copy of the rating page.
--
-- Raters are anonymous to the database: each has an unguessable token, created by the
-- organiser, that travels in their personal link (#t=<token>). The tables sit in a private
-- schema that the API does not expose; the page can only call the two public functions
-- below, and they do nothing for a token that is not in rating.raters.

create schema if not exists rating;

create table rating.raters (
  token      uuid primary key default gen_random_uuid(),
  label      text not null,                -- organiser's note: who the link went to
  created_at timestamptz not null default now()
);

create table rating.sessions (
  token    uuid not null references rating.raters (token) on delete cascade,
  round    text not null,
  state    jsonb not null,                 -- the page's state as sent: tag, level, started, updated, scores
  saves    integer not null default 1,
  first_saved_at timestamptz not null default now(),
  saved_at timestamptz not null default now(),
  primary key (token, round)
);

alter table rating.raters enable row level security;
alter table rating.sessions enable row level security;
revoke all on schema rating from public, anon, authenticated;
revoke all on all tables in schema rating from public, anon, authenticated;

-- Load a rater's saved state. {known: false} for an unknown token, so the page can say so.
create function public.chess_load(p_token uuid, p_round text)
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select jsonb_build_object(
    'known', exists (select 1 from rating.raters r where r.token = p_token),
    'state', (select s.state from rating.sessions s where s.token = p_token and s.round = p_round)
  );
$$;

-- Save a rater's whole state (the page sends all of it each time). False for an unknown token.
create function public.chess_save(p_token uuid, p_round text, p_state jsonb)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not exists (select 1 from rating.raters r where r.token = p_token) then
    return false;
  end if;
  if length(p_round) > 20 or jsonb_typeof(p_state) <> 'object'
     or jsonb_typeof(p_state -> 'scores') <> 'object' or octet_length(p_state::text) > 300000 then
    raise exception 'bad state';
  end if;
  insert into rating.sessions as s (token, round, state)
  values (p_token, p_round, p_state)
  on conflict (token, round) do update
    set state = excluded.state, saves = s.saves + 1, saved_at = now();
  return true;
end;
$$;

revoke execute on function public.chess_load(uuid, text) from public;
revoke execute on function public.chess_save(uuid, text, jsonb) from public;
grant execute on function public.chess_load(uuid, text) to anon, authenticated;
grant execute on function public.chess_save(uuid, text, jsonb) to anon, authenticated;
