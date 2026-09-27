-- Run once in the Supabase SQL Editor before deploying account-scoped balance history.
alter table public.balance_snapshots
  add column if not exists account_key text;

create index if not exists balance_snapshots_user_account_created_idx
  on public.balance_snapshots (user_id, account_key, created_at desc);
