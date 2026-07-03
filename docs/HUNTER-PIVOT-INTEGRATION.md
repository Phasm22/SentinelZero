# Hunter Pivot Engine × SentinelZero — Findings & Recommendations

*Investigation 2026-07-03 · SentinelZero repo · scope: owner's homelab (Lab `172.16.0.0/22`, Home `192.168.68.0/22`) — authorized security testing on infrastructure the owner controls.*

Companion to [`HUNTER-PREPLAN.md`](HUNTER-PREPLAN.md). Answers the Part A / Part B handoff: A1–A4 are investigation findings (answerable from code + one live test); B1–B4 are owner risk-tolerance calls with recommendations.

## TL;DR

- **A1 — Report contract:** A pivot *chain* does **not** fit today's `findings[]`/`fingerprint_diffs[]` shape without losing its structure — those become flat, unordered, edge-less events. Adding new top-level fields is safe (the normalizer ignores unknown keys, the test asserts a superset, the UI optional-chains everything), but the causal graph only surfaces if you plumb new fields through `normalize_report` + UI.
- **A2 — Invocation:** The current call blocks a **daemon worker thread** (not the request), holding a Flask `app_context` + DB session for the whole 3-stage run. Fire-and-forget missions must **detach** — `Popen` + status file, no parked thread — and leave the two narrative subprocess calls untouched.
- **A3 — Status surface:** Use a **sidecar status file** (`hunt-<mission>.status.json`) in the existing reports dir, surfaced by a new `/hunter/missions` endpoint. Matches the file-based seam, no DB migration, survives restarts.
- **A4 — Ollama contention:** **Live-tested** (exposure blocker resolved). Same-model calls serialize cleanly (~2s warm, FIFO queue); the real cost is **cross-model qwen↔nomic switching at ~9.6s per swap** under `MAX_LOADED_MODELS=1`. **Fix: set `MAX_LOADED_MODELS=2`** — both models co-resident for ~9.3GB, swap penalty gone.
- **B1–B4** are owner risk calls; recommendations: narrow separate mission trigger (start manual), run narrative stages in parallel (don't deprecate), Hunter POSTs embeddings directly (existing seam), phase approvals Hunter-side first.

---

## Part A — Investigation

### A1. Report contract — new top-level fields needed for the pivot chain

**How the contract works today.** `normalize_report` (`backend/src/services/hunter_reports.py:344`) is a pure projection: it reads a fixed set of raw keys (`mission_id`, `target_network`, `findings`, `fingerprint_diffs`, `worker_summaries`, `hosts_recommended_for_scan`, `scan_triggered`, …) and ignores everything else. `_build_events` (`hunter_reports.py:147`) flattens `findings[]` **and** `fingerprint_diffs[]` into one event list, assigning synthetic ids `"{source_field}:{idx}"`.

**Why the pivot chain doesn't fit the existing shape.** The current event model is structurally flat:

- **No ordering** beyond list insertion — no per-event timestamp or sequence number.
- **No edges** — events are grouped only by `ip` (`_host_rollups`, `hunter_reports.py:178`). There's no `parent_event_id`, no "pivot triggered by finding X," no task lineage.
- **`worker_summaries` is opaque** — passed through as strings, truncated `[:6]` into the context pack (`hunter_reports.py:327`). It can't carry a graph.

So you *can* cram pivot findings into `findings[]`/`fingerprint_diffs[]` and they'll render as flat, host-grouped rows — but the host→finding→pivot causal graph, the entire point of the pivot engine, is dropped.

**Additions are safe — confirmed downstream.** Nothing asserts a flat single-pass shape:

- The unit test uses `set(normalized.keys()) >= {...}` (`backend/tests/unit/test_hunter_reports.py:58`) — a **superset** check, so new top-level keys don't break it.
- `normalize_report` silently ignores unknown raw keys.
- The UI reads only the normalized projection, all optional-chained: `run.huntRun || {}`, `run.whatChanged?.eventTotal ?? …`, `run.deterministicNarrative || []` (`frontend/react-sentinelzero/src/components/hunter/hunterFormat.js:147`, `HunterNarrative.jsx:6`, `HunterTimeline.jsx:21`). `hunter_overview()` just wraps `list_normalized_runs` — no shape assumptions.

**Recommendation.** Add new top-level fields rather than overloading `findings[]`:

- `pivot_events[]` — `{event_id, seq, ts, task_id, parent_event_id, ip, type, description, action}` (the ordered, linked append-only log).
- `pivot_edges[]` (or fold parent refs into events) — the finding→pivot DAG.
- Keep emitting terminal findings into `findings[]`/`fingerprint_diffs[]` so **existing UI keeps working unchanged**.

Then extend `normalize_report` to emit a `huntPivotChain` section (mirroring `huntEvent`) and add a timeline/graph component. Because additions are backward-compatible, ship incrementally: contract + normalizer first, UI later.

### A2. Invocation mechanics — what blocks, and how to make missions async

**What actually blocks.** `backend/src/services/scanner.py:879` spawns a single `daemon=True` thread targeting `run_ai_pipeline` (`agent_service.py:38`). The scan HTTP request has **already returned** (`complete_scan` runs right after the spawn), so **the request thread is not blocked**. What's tied up is the **daemon worker thread**, which:

1. Enters `app.app_context()` and holds it for the whole run.
2. Runs verdicts → synthesis → scan_analyst **sequentially**, each a blocking `subprocess.run(..., timeout=…)` (`agent_service.py:267`; timeouts 120 / 90 / 180s).
3. Holds a DB session across all three (commits between stages).

**Why you can't reuse this pattern for a mission.** A mission is minutes-to-hours. You must not (a) park a thread on `subprocess.run` that long, or (b) hold a Flask `app_context`/SQLite session open for the duration — that's exactly the WAL/connection pressure the recent perf work fought.

**Concrete async design (fire-and-forget):**

1. New `agent_service.spawn_mission(seed)` uses **`subprocess.Popen`** (not `.run`), redirecting the child's output to the reports dir, writes a status file, and **returns immediately** — no waiting thread, no parked `app_context`.
2. Completion is detected by the **existing file-based mechanism**: Hunter writes `hunt-<mission>.json`, and `list_normalized_runs` already discovers reports by directory mtime (`hunter_reports.py:107`). No callback thread needed.
3. The two narrative stages (`_run_synthesis`, `_run_scan_analyst`) are **left exactly as-is** — separate subprocess invocations with their own timeouts.

Preserve `_agent_env()` (`agent_service.py:241`) and `_can_call_agent()` gating so missions honor the same local-mode/OpenAI-key config.

### A3. Status surface — recommend a sidecar status file

| Option | Fit | Cost |
|---|---|---|
| Sidecar status file in reports dir | Matches the file-based seam; Hunter already writes there | Atomic-write on Hunter's side + a read endpoint |
| DB row (`mission` table) | Queryable, joins to scans | Cross-process writer → WAL contention; migration; Hunter needs the model |
| Poll endpoint only | — | Still needs a backing store |

**Recommendation: a sidecar status file** — `hunt-<mission_id>.status.json`, written atomically (temp + `os.replace`) by Hunter, containing `{mission_id, state: queued|running|stalled|failed|done, started_at, updated_at, pid, last_task, error}`. Surface via a new `GET /hunter/missions` + `/hunter/missions/<id>` in `backend/src/routes/hunter_routes.py` that globs the reports dir like `_iter_report_files`. Hunter stays the sole writer (mirrors the incident-memory "Hunter POSTs, backend never reaches in" principle); survives restarts; "stalled" is derivable from `updated_at` staleness + `pid` liveness.

### A4. Ollama contention — LIVE TEST RESULTS

**Status change since first pass.** In the initial investigation this was **not testable** — `192.168.68.202` answered ICMP but refused `:11434`. Root cause (owner-confirmed): Ollama was running as a **user process bound to `127.0.0.1`** while the `ollama-lan.service` systemd unit (which sets `OLLAMA_HOST=0.0.0.0:11434`) was **inactive**. Owner killed the user process, started `ollama-lan.service` with `MAX_LOADED_MODELS=1`, `NUM_PARALLEL=1`, `KEEP_ALIVE=30m`, unloaded the 27B model, warmed `qwen2.5:14b`, and pulled `nomic-embed-text`. It's now reachable (Ollama 0.24.0, ~7ms), so the test below is **live, not inferred.**

**Environment:** run from the backend VM against `192.168.68.202:11434`. Models: `qwen2.5:14b` (8GB, narrative/mission reasoning) + `nomic-embed-text` (137M, incident-memory embeddings). Benchmark script: `scratchpad/ollama_contention.sh` (re-runnable).

| Test | Measures | Wall | Server detail |
|---|---|---|---|
| **T1** baseline 14B gen (warm) | single-call latency | **2.24s** | 110 tok @ 64.6 tok/s, load 104ms |
| **T2-A / T2-B** two concurrent 14B gens | same-model concurrency | **2.03s / 3.95s** | both 66 tok/s; **B waited for A** |
| **T3** embed (nomic) after gen | model-swap cost | **6.62s** | dim 768; qwen evicted from VRAM |
| **T4-gen / T4-emb** gen ∥ embed | cross-model contention | **11.57s / 0.06s** | gen **load=9637ms** (reloaded 8GB qwen) |
| **T5** 14B gen right after | warm-again check | **1.96s** | load 56ms |

**Finding 1 — same-model requests serialize cleanly (`NUM_PARALLEL=1`).** T2-A finished at 2.03s (= baseline); T2-B at 3.95s ≈ **2× baseline**. The second request queued FIFO for the full duration of the first, then ran at undiminished throughput (66 tok/s each). No errors, no drops — pure queueing. This is more benign than first estimated: a mission is many ~2s calls, so a concurrent narrative call slips into the gap between mission steps rather than waiting "hours." The only real risk is a *single* long mission generate blocking a short narrative call past its 90/180s timeout — bounded.

**Finding 2 — cross-model traffic forces a ~9.6s reload every switch (`MAX_LOADED_MODELS=1`).** This is the expensive one. After the embed (T3) evicted qwen, the next generate (T4-gen) paid **`load=9637ms`** to page the 8GB model back in — 11.57s vs. 2s warm. The embed itself, once nomic was resident, was **0.06s**. The cost is the **eviction/reload thrash**, not the embedding. `/api/ps` confirmed only one model resident at a time, flipping qwen↔nomic. (Single sample, but it's the server's own `load_duration` and the evict-on-load mechanism is deterministic — treated as solid.)

**Why it matters for the pivot engine.** Mission reasoning (qwen) and SentinelZero incident-memory embeddings (nomic, per B3) use **different models**. A mission that reasons over a finding → embeds it → reasons over the next thrashes the ~9.6s swap on **every step** — minutes of pure model-loading overhead, invisible until profiled.

**Recommendation (config, not code):**

- **Set `OLLAMA_MAX_LOADED_MODELS=2`, keep `NUM_PARALLEL=1`.** qwen (9GB) + nomic (0.3GB) co-resident ≈ **9.3GB total** eliminates the swap penalty — the single biggest win. Verify ≥~12GB VRAM (headroom exists after unloading the 27B). Keep `NUM_PARALLEL=1`: parallel decode on one GPU splits the KV cache and rarely helps.
- **Code-side (later):** have missions **batch embeddings** — accumulate findings, embed in one nomic pass at mission end.
- **`KEEP_ALIVE=30m`** is correct.
- **Verify the fix:** re-run `scratchpad/ollama_contention.sh` after the change — T4-gen's `load=` should drop from ~9600ms to ~50ms.

---

## Part B — Owner decisions (tradeoffs + recommendation)

### B1. Trigger policy — should "escalate" spawn a mission?

Today "escalate" is cheap (a narrative verdict); a mission is minutes-to-hours, GPU-bound, and can take active actions. Reusing the escalate threshold (`_apply_auto_verdicts`, `agent_service.py:163`, auto-escalates gap types on lab) would fire missions on inventory bookkeeping — far too broad. **Recommendation:** a **separate, narrower gate**, decoupled from escalate. Escalate stays "a human should look." Mission = "escalate **AND** pivot-worthy" (e.g. `new_host`/`new_port`/`service_change` on a **lab** host, or `new_vuln_critical/high`, excluding auto-escalated gap types). Start **manual-trigger-only** to calibrate cost/false-positives before any auto-spawn. The predicate is small — `type` + `verdict` + network label are already on the insight.

### B2. Scope of replacement — deprecate the existing synthesis stages?

The pivot engine's synthesis overlaps `_run_synthesis` and `_run_scan_analyst`, but those are **cheap, synchronous, run on every scan**, and the whole UI (`correlated` insights, `scan_analyst` summary, `backend/src/services/scan_analysis.py`) depends on them. Missions run rarely and cover only seeded targets. **Recommendation: run in parallel, don't deprecate** — different altitudes (per-scan coverage vs. occasional deep dives). If output overlaps noisily, dedupe at the **display** layer (tag mission-derived insights `source: mission`), not by removing a stage.

### B3. Incident-memory ownership — who embeds pivot findings?

`backend/src/routes/incident_routes.py` already sets the pattern: **the agent owns embeddings**, POSTs pre-computed vectors to `/api/incidents`; the backend only stores/ranks, never calls an embedding provider (`incident_memory.py:1–7`). **Recommendation: Hunter writes directly** via `POST /api/incidents` with `source: "mission"` (the model already allows arbitrary source strings, `backend/src/models/incident.py:15`). Zero new backend embedding code; immediately searchable via the same cosine recall; gate with the existing optional `SENSOR_API_KEY` header. *(Note: this is exactly the qwen↔nomic path that thrashes without the A4 `MAX_LOADED_MODELS=2` fix.)*

### B4. Approval-gate surfacing — SentinelZero UI or Hunter-owned?

Option 1 (SentinelZero "pending approval" UI + approve/deny endpoint) is centralized but forces Hunter to **block mid-mission** on an external callback and means building real blocking UI. Option 2 (Hunter owns its own control surface) is simple but splits operator attention. **Recommendation: phase it.** v1 — **Hunter owns approvals** on its own surface, or run missions in a pre-approved passive/read-only mode so no gate is needed. The A3 status file already gives visibility (`state: stalled`, `last_task: "awaiting approval"`). Build the SentinelZero "pending approval" UI as v2 **only if** missions routinely take active actions and you want approvals centralized.

---

## Two cross-cutting flags

1. **Ollama exposure blocker — now RESOLVED** (was the gate on the entire local-mode pivot engine). The remaining action is the `MAX_LOADED_MODELS=2` config tweak so cross-model thrash doesn't eat mission runtime.
2. **Daemon-thread `app_context`/DB-session lifetime (A2)** is the one place a naive "just make the timeout bigger" approach would quietly reintroduce the DB-contention problems the last perf pass fixed — the mission path must detach, not extend.

*No application code was changed — investigation + live testing only.*
