# Monoegde

**Mono Edge–style rolling-mill signal analytics:** synthetic PLC-like streams, historical exploration, and live cobble-precursor detection in a Streamlit operator console.

---

## Authorship & how this project was built

**Product idea, architecture, and design decisions are mine (Pranav Joshi).**  
I defined the problem (rolling-mill cobble vs false-issue load changes), the data model, the offline → online workflow, the choice of detectors, and how the UI should feel for an operator demo.

**Implementation code was largely generated with an AI coding agent (Cursor),** directed through iterative prompts: scaffolding the simulator, wiring Supabase, building the Streamlit UI, fitting detectors, and hardening auth, logging, and deploy-oriented storage. I reviewed, steered, and accepted the design at each step; the agent wrote and refactored the bulk of the source.

In short:

| Role | Who |
|------|-----|
| Problem framing, architecture, UX intent, algorithm *choice* | Author (human) |
| Implementation, refactors, glue code | AI agent under human direction |

This README documents both the **thinking** and the **resulting system**.

---

## What the app does

1. **Simulate** high-rate mill signals (RS-01 / FS-01, ~50 Hz / 20 ms ticks).
2. **Store** historical wide-format readings in **Supabase Postgres** (not local CSV for the hosted demo path).
3. **Sign in** with local accounts (PBKDF2 hashes) stored in the same database.
4. **Explore history** — filter by mill, signal, time, and pass profile (NORMAL / FALSE_ISSUE / COBBLE).
5. **Live monitor** — run an in-process simulator stream anytime; optionally fit a detector and score ticks online.

Live ticks are **simulated in-process**. Persistence is for **training / analytics / accounts**, not for writing every live sample.

---

## Brainstorm: detection approach

Cobble incidents are rare; operators also see **false issues** (hard billets / load changes) that look energetic but are not cobbles. Labels exist in the **offline** simulator (`ground_truth_state`, `pass_profile`). At **runtime** we assume we do not get those labels — only the six signals.

### Why a sliding statistical window?

- Cobble precursors show up as short bursts of abnormal multi-signal behaviour, not as a single wild sample.
- A **ring buffer of ~4 s** (e.g. 200 ticks × 20 ms) matches “look at the last few seconds of rolling.”
- Per-mill **NORMAL LOAD** mean/std → per-tick \|z\| → window mean score → flag above a quantile of NORMAL scores.
- Interpretable, fast, no heavy model for the first demo path.

### Why Isolation Forest as a second algorithm?

- Same window idea, but features are **mean \|z\| per signal over the window** (a small feature vector).
- Train only on **NORMAL LOAD** windows from historical data; score live windows; threshold from the NORMAL score distribution.
- Useful to compare a classical ML anomaly model against the pure statistical window in the same UI.

### Workflow I wanted (then had the agent implement)

```text
Offline: generate labeled history → store in DB
         → fit detector (μ/σ, threshold, optional IF model)
         → review FitReport metrics (precursor vs false-issue flag rates)
         → optionally “Save as best” for reuse

Online:  start live stream (no fit required)
         → after accepted fit → start detection on each tick batch
```

---

## Architecture (high level)

```text
src/
  data_simulation/     # FSM + physical-ish signal generator
  detection/           # sliding window + Isolation Forest + FitReport
  frontend/            # Streamlit UI (auth, home, live, history)
  db.py                # Supabase Postgres helpers
  logging_setup.py     # console + logs/monoegde.log
```

| Concern | Storage / runtime |
|---------|-------------------|
| Users | Supabase `users` |
| Historical mill rows | Supabase `sensor_readings` |
| Saved best detector | Supabase `saved_fits` (pickle + report JSON) |
| Live stream | In-memory `RollingMillSimulationEngine` |

---

## Prerequisites

- Python **≥ 3.12**
- [uv](https://docs.astral.sh/uv/)
- A **Supabase** (or any Postgres) project with connection URI

---

## Setup

```bash
uv sync
```

Create `.env` (see `.env.example`):

```bash
DATABASE_URL=postgresql://postgres:YOUR_PASSWORD@db.YOUR_PROJECT.supabase.co:5432/postgres
```

If the password contains `@`, URL-encode it (`@` → `%40`). The app connects with `sslmode=require`.

### Tables

On first use the app / helpers create what they need (e.g. `saved_fits`). Core tables:

**`users`** — username, salt, password_hash, created_at  

**`sensor_readings`** — mill_id, timestamp, six signals, ground_truth_state, pass_profile  

**`saved_fits`** — algorithm, hparams, report, pickled detector  

You can also create `users` / `sensor_readings` once in the Supabase SQL editor if you prefer.

---

## Generate signal data (offline)

Historical data is **not** produced from the Streamlit UI. Run the generator offline; it writes straight to Supabase:

```bash
uv run python -m data_simulation.generate_historical_data --hours 2
```

What this does:

- Runs the mill FSM / physical simulation at **50 ticks/s** of simulated time.
- Emits long wire payloads, pivots to **wide** rows (one row per mill per tick).
- Clears existing `sensor_readings`, then **COPY**-inserts in batches.
- Example: 2 simulated hours × 2 mills ≈ **720,000** rows.

Optional console stream (debug the simulator without the UI):

```bash
uv run python -m data_simulation.run_simulator
```

---

## Run the web UI

```bash
uv run streamlit run src/frontend/app.py
```

### Auth

1. Open the app → **Sign up** / **Sign in**.
2. Accounts are hashed (PBKDF2) and stored in Supabase `users`.
3. Until signed in, only the auth screen is shown.

### Home

Landing / navigation into Live and Historical analytics.

### Historical analytics

- Loads from `sensor_readings` (not CSV).
- **Fast sample** (~25k evenly spaced rows) vs **Full mill data**.
- Event browser for COBBLE / FALSE_ISSUE / NORMAL episodes, timelines, and multi-signal comparisons.

### Live monitoring

1. **Start live stream** anytime (no fit required) — in-process simulator, charts update.
2. **Fit** on historical Supabase data, or **Load saved best**.
3. Review the **FitReport** (threshold, NORMAL vs precursor vs false-issue metrics).
4. **Accept** the fit → unlocks **Start detection**.
5. Optionally **Save as best** so the next session can skip retraining.

Algorithms exposed in the UI:

- Statistical window (\|z\|)
- Isolation Forest

---

## Logging

Logs go to the terminal and `logs/monoegde.log` (gitignored).

```bash
uv run streamlit run src/frontend/app.py
LOG_LEVEL=DEBUG uv run streamlit run src/frontend/app.py
tail -f logs/monoegde.log
```

Useful for: DB connect/read failures, fit start/finish, login attempts (no passwords logged), save/load best fit.

---

## Project layout (detail)

| Path | Role |
|------|------|
| `src/data_simulation/simulator/` | Mill stands, FSM, signal generation |
| `src/data_simulation/generate_historical_data.py` | Offline DB seed |
| `src/detection/common.py` | Shared baselines, constants, training-frame load |
| `src/detection/slide_window.py` | Statistical window fit + online detector |
| `src/detection/isolation_forest.py` | IF fit + online detector |
| `src/detection/fit_report.py` | Structured offline fit summary for the UI |
| `src/frontend/pages/` | home, live, history |
| `src/frontend/auth.py` | Sign-in / sign-up |
| `src/db.py` | Postgres access |

---

## Design notes & limitations

- Demo-oriented: **synthetic** mills, not a live plant PLC feed.
- Detection is **precursor-oriented** scoring, not a certified safety system.
- Fitting on full history can be slow over the network; prefer **saved best** after one good fit.
- History **fast sample** trades density for latency while keeping the full time span.

---

## License / credit

© Pranav Joshi — architecture and product direction.  
Substantial portions of the codebase were produced with AI assistance under that direction.
