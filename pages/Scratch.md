- The cloud-infrastructure node types (`vm`, `function`, `cluster`, …) and the `runs_on`/`belongs_to` relations are left out of the DSL as not directly relevant yet.
- `latency`, `jitter` and `error_rate` (resolved into a `CallProfile`) shape the RTI (service→database) emission: each RTI payload carries a `duration`
  summary-stats measure (in microseconds) whose own count is the number of latency samples, each jittered by ±`jitter` and floored at zero, plus an `error`
  boolean dimension (a Bernoulli draw against `error_rate`), so the `dt.service.database.query.response_time` metric has data locally. Resolution order is
  request-level `overrides` > per-node value > global `defaults`; `jitter` has no request-level override.
- Because one Bernoulli draw covers all samples in the summary, a `true` draw marks the whole summary as failed (bursty compared to real split-by-error records,
  but ~`error_rate` on average).
- RTR (service→service) edges carry no timing - no customer metric reads duration or error off the RTR path. The DSL still accepts `latency`/`jitter`/`error_rate`
  on services uniformly; those values are simply not emitted to Kafka (yet).
-