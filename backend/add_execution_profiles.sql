-- Run once in the Supabase SQL Editor for existing deployments.
alter table public.user_agent_settings
  add column if not exists execution_profiles jsonb not null default '["autonomous:futures"]'::jsonb;

alter table public.balance_snapshots
  add column if not exists futures_equity numeric,
  add column if not exists spot_equity numeric;
