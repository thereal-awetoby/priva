-- Run once in the Supabase SQL Editor for existing deployments.
alter table public.user_agent_settings
  add column if not exists execution_profiles jsonb not null default '["autonomous:futures"]'::jsonb;
