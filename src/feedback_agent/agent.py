"""
Catalog Feedback Agent

Takes a failed compliance result, the full catalogs and application data, and
human feedback explaining what was wrong — then uses an LLM to reason about
the minimal fix and returns updated trigger and requirement catalogs.

Inputs:
  - trigger_catalog     : list[dict]  — full trigger catalog
  - req_catalog         : list[dict]  — full requirement catalog
  - bundle              : dict        — document bundle submitted by applicant
  - family              : dict        — household / application data
  - compliance_trace    : dict        — output of run_compliance_trace()
  - human_feedback      : str         — why the decision was wrong

Outputs:
  - updated trigger catalog (same format)
  - updated requirement catalog (same format)
  - analysis string explaining what was changed

Requires ANTHROPIC_API_KEY in the environment.

CLI usage:
    python agent.py \\
        --triggers  catalogs/trigger_catalog.json \\
        --reqs      catalogs/req_catalog.json \\
        --bundle    ../usecases/bundle_3.json \\
        --family    ../usecases/family_3.json \\
        --feedback  "The pay stubs rule needs only 3 stubs not 5" \\
        --out-triggers  updated_triggers.json \\
        --out-reqs      updated_reqs.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import os

import anthropic

from compliance import run_compliance_trace


def _load_dotenv() -> None:
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip())


_load_dotenv()


# ---------------------------------------------------------------------------
# Prompt (system portion is cached — it never changes across calls)
# ---------------------------------------------------------------------------

_SCHEMA = """\
## Trigger object schema
{
  "trigger_id": "string",
  "description": "string",
  "activation": <Condition>,
  "emits_requirements": ["requirement_id", ...],
  "instance_scope": "household" | "applicant" | "co_applicant" | "per_member",
  "per_member_scope": <Condition> | null,    // required iff instance_scope == "per_member"
  "source_reference": {"document": "str", "page": null, "section": "str|null", "quote": "str|null"}
}

## DocumentSetRequirement object schema
{
  "requirement_id": "string",
  "description": "string",
  "document_spec": <DocumentSpec>,
  "source_reference": {"document": "str", "page": null, "section": "str|null", "quote": "str|null"}
}

## Condition node types
{"type": "predicate", "field": "dotted.path", "operator": "equals|not_equals|contains|greater_than|less_than|in|exists", "value": <scalar|list|null>}
{"type": "all",  "children": [<Condition>, ...]}   // AND
{"type": "any",  "children": [<Condition>, ...]}   // OR
{"type": "not",  "child":    <Condition>}

## DocumentSpec node types
{"type": "document", "document_type": "filename.pdf", "notes": null}
{"type": "all_of",   "children": [<DocumentSpec>, ...]}   // every child required
{"type": "one_of",   "children": [<DocumentSpec>, ...]}   // at least one child required

## Household-level predicate field paths (dotted into the family JSON)
eligibility_checklist.<item>   — applicant self-attestation boolean (plain bool, e.g. eligibility_checklist.pay_stubs)
household.total_size
personal_information.<field>
employment.date_of_hire
assets.<category>
financials.<field>

## Per-member predicate field paths (inside per_member_scope, relative to member object)
age | relationship | name
"""

_SYSTEM = f"""\
You are a compliance catalog editor for the Maple Square affordable housing application system.

You will receive:
1. The full trigger catalog
2. The full requirement catalog
3. The document bundle the applicant submitted
4. The family/household application data
5. A compliance trace showing which triggers fired, which requirements were emitted, and which failed (including what documents were missing)
6. Human feedback explaining what was wrong with the compliance decision

Your job: reason about all of this and produce the minimum surgical change to the trigger and/or requirement catalogs that fixes the described problem. Do not touch anything unrelated to the feedback.

{_SCHEMA}

Respond with a single JSON object — no markdown, no text outside the JSON:
{{
  "analysis": "one or two sentences: what you changed and why",
  "trigger_changes": [
    {{
      "trigger_id": "...",
      "action": "update",
      "updated_trigger": {{ ...complete Trigger object... }}
    }}
  ],
  "req_changes": [
    {{
      "requirement_id": "...",
      "action": "update",
      "updated_req": {{ ...complete DocumentSetRequirement object... }}
    }}
  ]
}}

Set trigger_changes to [] if no triggers need changing.
Set req_changes to [] if no requirements need changing.
"""


# ---------------------------------------------------------------------------
# Core function
# ---------------------------------------------------------------------------

def run_feedback_agent(
    trigger_catalog: list[dict],
    req_catalog: list[dict],
    bundle: dict,
    family: dict,
    compliance_trace: dict,
    human_feedback: str,
    model: str = "claude-sonnet-4-6",
) -> tuple[list[dict], list[dict], str]:
    """
    Apply LLM reasoning to update catalogs based on a failed compliance result
    and human feedback explaining what was wrong.

    Returns (updated_triggers, updated_reqs, analysis).
    """
    client = anthropic.Anthropic()

    user_content = f"""\
=== TRIGGER CATALOG ===
{json.dumps(trigger_catalog, indent=2)}

=== REQUIREMENT CATALOG ===
{json.dumps(req_catalog, indent=2)}

=== DOCUMENT BUNDLE ===
{json.dumps(bundle, indent=2)}

=== FAMILY / APPLICATION DATA ===
{json.dumps(family, indent=2)}

=== COMPLIANCE TRACE (what fired, what failed, what was missing) ===
{json.dumps(compliance_trace, indent=2)}

=== HUMAN FEEDBACK (why the decision was wrong) ===
{human_feedback}"""

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": _SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_content}],
    )

    u = response.usage
    print(f"  [usage] input={u.input_tokens} output={u.output_tokens} "
          f"cache_created={getattr(u, 'cache_creation_input_tokens', 0)} "
          f"cache_read={getattr(u, 'cache_read_input_tokens', 0)}")

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        result: dict = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned non-JSON:\n{raw}") from exc

    # Apply trigger changes
    trigger_map = {t["trigger_id"]: t for t in trigger_catalog}
    for change in result.get("trigger_changes", []):
        action = change["action"]
        tid    = change["trigger_id"]
        if action == "update":
            trigger_map[tid] = change["updated_trigger"]
        elif action == "delete":
            trigger_map.pop(tid, None)

    # Apply requirement changes
    req_map = {r["requirement_id"]: r for r in req_catalog}
    for change in result.get("req_changes", []):
        action = change["action"]
        rid    = change["requirement_id"]
        if action == "update":
            req_map[rid] = change["updated_req"]
        elif action == "delete":
            req_map.pop(rid, None)

    return (
        list(trigger_map.values()),
        list(req_map.values()),
        result.get("analysis", ""),
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _load(path: str) -> dict | list:
    return json.loads(Path(path).read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description="Catalog Feedback Agent")
    parser.add_argument("--triggers",     required=True)
    parser.add_argument("--reqs",         required=True)
    parser.add_argument("--bundle",       required=True)
    parser.add_argument("--family",       required=True)
    parser.add_argument("--feedback",     required=True, help="Human feedback string or @path/to/file.txt")
    parser.add_argument("--out-triggers", default="updated_trigger_catalog.json")
    parser.add_argument("--out-reqs",     default="updated_req_catalog.json")
    parser.add_argument("--model",        default="claude-sonnet-4-6")
    args = parser.parse_args()

    triggers = _load(args.triggers)
    reqs     = _load(args.reqs)
    bundle   = _load(args.bundle)
    family   = _load(args.family)

    feedback = args.feedback
    if feedback.startswith("@"):
        feedback = Path(feedback[1:]).read_text().strip()

    trace = run_compliance_trace(family, bundle, triggers, reqs)

    print(f"Compliance result: {'PASS' if trace['passed'] else 'FAIL'}")
    failed = [r["instance_label"] for r in trace["requirement_trace"] if not r["satisfied"]]
    if failed:
        print(f"Failed requirements: {failed}")

    print("\nRunning feedback agent...", flush=True)
    updated_triggers, updated_reqs, analysis = run_feedback_agent(
        trigger_catalog=triggers,
        req_catalog=reqs,
        bundle=bundle,
        family=family,
        compliance_trace=trace,
        human_feedback=feedback,
        model=args.model,
    )

    Path(args.out_triggers).write_text(json.dumps(updated_triggers, indent=2))
    Path(args.out_reqs).write_text(json.dumps(updated_reqs, indent=2))

    print(f"\nAnalysis: {analysis}")
    print(f"\nUpdated catalogs written to:\n  {args.out_triggers}\n  {args.out_reqs}")


if __name__ == "__main__":
    main()
