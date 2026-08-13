# CLAUDE.md

Airport Investment Intelligence Agent  — an AI agent that helps analysts
find US airports where terminal renovation would pay off, based on flight and
passenger capacity signals. Built fresh in this folder.

## Reference repo — read-only

`../airport-investment-agent/` is a previous implementation. **Treat it as
reference only: never edit it.** Reuse its ideas and data-access patterns
(especially `data_extractor_by_kpi/bts.py`, the shared BTS query layer, and
`kpis.py`, the deterministic signal calculations), but write new code here.

## Stack

- **Backend:** Python 3.
- **Frontend:** React web app with a chat interface.
- **LLM provider:** not decided yet — keep the LLM behind a thin abstraction so
  the provider is swappable. Ask the user before committing to one.
- **Data:** BTS Socrata table `r495-tyji` (T-100 Segment Summary by Origin
  Airport, monthly, 2014–present, live JSON, no key) — same source as the
  reference repo's `bts.py`.

## Design rules (from the assignment)

- **Scoring/ranking must be deterministic code**, not LLM output. The LLM's job
  is tool selection, mapping place names to airport codes, and explaining
  results in plain English.
- The agent must support conversational follow-ups.
- Answers must clearly state assumptions, uncertainty, and scope limits; refuse
  questions the data can't answer (delays, gate counts, fares, route-level
  detail are not in the T-100 summary table).
- Deliverables include source code and a short design/architecture doc covering
  scoring methodology, tradeoffs, and where/how AI is used.

## Conventions

- Keep KPI/scoring functions pure (rows in, dict out, no I/O) so they can be
  tested against live data with invariant checks rather than fixed numbers.
- All BTS access through one query module; cache by URL within a process.
