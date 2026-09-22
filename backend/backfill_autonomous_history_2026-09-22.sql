-- One-time correction for the Bitget history imported while the worker was offline.
-- Run once in the Supabase SQL Editor, then do not rerun as part of deployments.

update public.agent_cycles
set mode = 'autonomous'
where mode = 'imported'
  and created_at >= timestamptz '2026-09-17 00:00:00+00'
  and created_at < timestamptz '2026-09-23 00:00:00+00';

-- Repair runtime closes recorded before exit_price was stored separately.
update public.agent_cycles
set order_result = jsonb_set(
  coalesce(order_result, '{}'::jsonb),
  '{exit_price}',
  to_jsonb((ticker->>'last_price')::numeric),
  true
)
where status = 'closed'
  and mode = 'strategy'
  and not (coalesce(order_result, '{}'::jsonb) ? 'exit_price')
  and ticker->>'last_price' is not null;
