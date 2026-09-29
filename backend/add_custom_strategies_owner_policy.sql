-- Run once in the Supabase SQL Editor for existing deployments.
alter table public.user_agent_settings
  add column if not exists position_mode text;

alter table public.custom_strategies enable row level security;

drop policy if exists custom_strategies_owner_all on public.custom_strategies;
create policy custom_strategies_owner_all
  on public.custom_strategies
  for all
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

alter table public.user_bitget_credentials enable row level security;
alter table public.user_agent_settings enable row level security;
alter table public.agent_cycles enable row level security;
alter table public.balance_snapshots enable row level security;

drop policy if exists user_bitget_credentials_owner_all on public.user_bitget_credentials;
create policy user_bitget_credentials_owner_all
  on public.user_bitget_credentials
  for all
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists user_agent_settings_owner_all on public.user_agent_settings;
create policy user_agent_settings_owner_all
  on public.user_agent_settings
  for all
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists agent_cycles_owner_all on public.agent_cycles;
create policy agent_cycles_owner_all
  on public.agent_cycles
  for all
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

drop policy if exists balance_snapshots_owner_all on public.balance_snapshots;
create policy balance_snapshots_owner_all
  on public.balance_snapshots
  for all
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
