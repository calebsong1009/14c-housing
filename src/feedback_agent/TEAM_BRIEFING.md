# Feedback Agent — Team Briefing

## What this is

The last stage of the AHAA/HAVEN pipeline. After the compliance engine evaluates an application and fails it, a human evaluator reads the output and says what was wrong. The feedback agent takes that explanation and automatically updates the trigger catalog and/or requirement catalog so the system gets it right next time.

No manual JSON editing. The agent uses an LLM (Claude) to reason about what needs to change and makes only the minimum surgical fix.

---

## How it fits in the pipeline

```
P1: Catalog Authoring       → trigger_catalog.json, req_catalog.json
         ↓
P2: Compliance Engine       → evaluates (family + bundle) against catalogs
         ↓
     [application FAILS]
         ↓
     Human Evaluator         → reads compliance output, explains what was wrong
         ↓
     Feedback Agent          → updates catalogs
         ↓
     Updated catalogs        → fed back into P2 on next run → application PASSES
```

---

## What I built

### `agent.py` — the feedback agent

Core function:
```python
run_feedback_agent(
    trigger_catalog,     # full trigger catalog
    req_catalog,         # full requirement catalog
    bundle,              # documents the applicant submitted
    family,              # household / application data
    compliance_trace,    # what fired, what failed, what docs were missing
    human_feedback,      # plain English explanation of what was wrong
) → (updated_triggers, updated_reqs, analysis)
```

The LLM sees everything — both full catalogs, the bundle, the family data, and the compliance trace showing exactly which triggers fired, which requirements were emitted, and what documents were missing. It reasons about the human's explanation and produces the minimum change.

Also has a CLI so you can run it directly:
```bash
python agent.py \
    --triggers catalogs/trigger_catalog.json \
    --reqs     catalogs/req_catalog.json \
    --bundle   ../usecases/bundle_3.json \
    --family   ../usecases/family_3.json \
    --feedback "The pay stubs rule only needs 3 stubs not 5" \
    --out-triggers updated_triggers.json \
    --out-reqs     updated_reqs.json
```

---

### `compliance.py` — minimal compliance engine

Written to support the feedback agent. Implements the engine logic described in `catalog_templates/README.md`.

Two functions:

**`run_compliance(family, bundle, triggers, reqs)`** → `(passed: bool, failed_labels: list)`
Simple pass/fail check.

**`run_compliance_trace(family, bundle, triggers, reqs)`** → full audit dict
Richer output — shows every trigger that fired, every requirement that was emitted, whether it was satisfied, and what documents were missing. This is what gets passed to the LLM as context.

Example trace:
```json
{
  "passed": false,
  "trigger_trace": [
    {"trigger_id": "trig_pay_stubs", "fired": true, "emitted_requirements": ["req_pay_stubs"]}
  ],
  "requirement_trace": [
    {
      "requirement_id": "req_pay_stubs",
      "satisfied": false,
      "missing_document_types": ["pay_stub_4.pdf", "pay_stub_5.pdf"]
    }
  ]
}
```

---

### `catalogs/trigger_catalog.json` + `catalogs/req_catalog.json`

**Sample catalogs written for development and testing.** These are NOT the real production catalogs — P1 owns those. These cover 11 triggers and 11 requirements based on the Maple Square FCFS Application checklist items, and are accurate to the schema. They exist so the feedback agent has something real to work against during development.

They contain deliberate bugs matching the 3 test cases below.

---

### `tests/test_feedback_agent.py` — 3 integration tests, all passing ✓

| Test | Family / Bundle | What was wrong | Human says | Fix applied |
|------|----------------|----------------|------------|-------------|
| T1 | family_3 / bundle_3 | `req_pay_stubs` requires 5 stubs; Marcus only submitted 3 | "Regulation only requires 3" | `document_spec` shrinks from `all_of[5]` to `all_of[3]` |
| T2 | family_4 / bundle_4 | `trig_federal_tax_returns` fires based on employment, not checklist; Priya didn't check that box | "Trigger should use the checklist field" | Trigger `activation` changes to `eligibility_checklist.federal_tax_returns_2024.checked == true` |
| T3 | family_5 / custom bundle | `req_household_member_id` only accepts `birth_certificate.pdf`; Carlos submitted a driver's license | "Driver's license is valid ID" | `document_spec` becomes `one_of[birth_certificate, driver_license, passport]` |

Each test asserts:
- Compliance **fails** before the fix (pre-condition)
- Compliance **passes** after the fix (post-condition)
- Only the described item changed (surgical edit)

Family and bundle data comes from real files in `usecases/`. Trigger/req catalogs in the tests are inline with deliberate bugs.

---

## What's needed to go further

### From P1
The feedback agent is ready to receive real catalog content. Right now it's using sample catalogs I wrote. Once P1 delivers the actual `trigger_catalog.json` and `req_catalog.json` for the Maple Square form, plug those in — the agent interface doesn't change.

### From P2
The compliance engine in `compliance.py` is a working minimal implementation, not the full P2. It correctly evaluates triggers and requirements against the Pydantic schema in `catalog_templates/templates.py`. If P2 builds a richer engine, the feedback agent just needs `run_compliance_trace()` to produce the same output format — or P2 can import from `compliance.py` directly.

### API key
The feedback agent calls Claude (claude-sonnet-4-6). Requires `ANTHROPIC_API_KEY` in a `.env` file at the repo root (gitignored). Cost is ~2–3 cents per call.

---

## What's solid, what's a placeholder

| Thing | Status |
|-------|--------|
| `agent.py` — core logic, LLM integration, apply changes | ✅ Done |
| `compliance.py` — engine + trace | ✅ Done |
| `tests/` — 3 tests, all passing | ✅ Done |
| Data formats — matches `catalog_templates/templates.py` exactly | ✅ Done |
| `.env` / `.gitignore` — key management | ✅ Done |
| `catalogs/*.json` — sample catalogs with bugs | ⚠️ Placeholder — real content comes from P1 |
| Integration with real P2 engine | ⏳ Pending P2 |
| Testing against real production catalogs | ⏳ Pending P1 |

---

## Running it

```bash
cd feedback_agent

# Run the tests
python3 tests/test_feedback_agent.py

# Run the CLI on a real case
python3 agent.py \
    --triggers  catalogs/trigger_catalog.json \
    --reqs      catalogs/req_catalog.json \
    --bundle    ../usecases/bundle_3.json \
    --family    ../usecases/family_3.json \
    --feedback  "The pay stubs rule only needs 3 not 5" \
    --out-triggers updated_triggers.json \
    --out-reqs     updated_reqs.json
```

Requires: Python 3.10+, `anthropic` package (`pip install anthropic`), `ANTHROPIC_API_KEY` in `.env`.
