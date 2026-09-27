-- Run once in the Supabase SQL Editor for existing deployments.
alter table public.custom_strategies enable row level security;

drop policy if exists custom_strategies_owner_all on public.custom_strategies;
create policy custom_strategies_owner_all
  on public.custom_strategies
  for all
  to authenticated
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);
