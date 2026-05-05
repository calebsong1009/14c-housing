#!/usr/bin/env python3
"""
compliance_check.py — Evaluates whether a family + document bundle satisfy
all requirements triggered for that family by the trigger catalog.

Usage:
    python compliance_checker/compliance_check.py <family.json> <bundle.json> <trigger_catalog.json> <req_catalog.json>
    python compliance_checker/compliance_check.py <family.json> <bundle.json> <trigger_catalog.json> <req_catalog.json> -o <result.json>

Output JSON shape:
{
  "family_id": str,
  "bundle_id": str,
  "passed": bool,
  "triggers": [
    {
      "trigger_id": str,
      "description": str,
      "fired": bool,
      "source_reference": { "document": str, "page": int, "section": str },
      "requirement_fulfilled": bool | null,   // null when not fired
      "instances": [
        {
          "instance_label": str,
          "requirement_id": str,
          "applies_to_member": str | null,
          "fulfilled": bool,
          "missing_documents_type": {         // empty lists when fulfilled
            "missing_all_of": [str],          // every listed doc is individually required
            "missing_any_of": [str]           // at least one of the listed docs is required
          }
        }
      ]
    }
  ]
}
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

# Support running from the project root
# sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from feedback_agent.compliance import run_compliance_trace


def build_report(
    family: dict,
    bundle: dict,
    triggers_catalog: list[dict],
    req_catalog: list[dict],
) -> dict:
    trace = run_compliance_trace(family, bundle, triggers_catalog, req_catalog)

    # Index the full trigger definitions for description + source_reference
    trigger_by_id = {t["trigger_id"]: t for t in triggers_catalog}

    # Group requirement-trace entries by each trigger that emitted them.
    # Each entry carries triggered_by: [trigger_id, ...] so one entry can
    # appear under multiple triggers (dedup / sanity-overlay pairs).
    instances_by_trigger: dict[str, list[dict]] = defaultdict(list)
    for req_entry in trace["requirement_trace"]:
        for tid in req_entry["triggered_by"]:
            instances_by_trigger[tid].append(req_entry)

    trigger_results = []
    for t_entry in trace["trigger_trace"]:
        trigger_id = t_entry["trigger_id"]
        trig = trigger_by_id.get(trigger_id, {})

        result: dict = {
            "trigger_id": trigger_id,
            "description": trig.get("description", ""),
            "fired": t_entry["fired"],
            "source_reference": trig.get("source_reference", {}),
            "requirement_fulfilled": None,
            "instances": [],
        }

        if not t_entry["fired"]:
            trigger_results.append(result)
            continue

        instances = [
            {
                "instance_label": e["instance_label"],
                "requirement_id": e["requirement_id"],
                "applies_to_member": e.get("applies_to_member"),
                "fulfilled": e["satisfied"],
                "missing_documents_type": {
                    "missing_all_of": e["missing_document_types"]["all_of"],
                    "missing_any_of": e["missing_document_types"]["any_of"],
                },
            }
            for e in instances_by_trigger.get(trigger_id, [])
        ]

        result["instances"] = instances
        # A fired trigger is fulfilled only when every instance it produced is satisfied.
        # An empty instance list means the trigger fired but scoped to zero members → no
        # outstanding requirement, treat as fulfilled.
        result["requirement_fulfilled"] = all(i["fulfilled"] for i in instances) if instances else True

        trigger_results.append(result)

    return {
        "family_id": family.get("family_id"),
        "bundle_id": bundle.get("bundle_id"),
        "passed": trace["passed"],
        "triggers": trigger_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check if a family + bundle satisfy all triggered compliance requirements."
    )
    parser.add_argument("family", help="Path to family JSON file")
    parser.add_argument("bundle", help="Path to bundle JSON file")
    parser.add_argument("trigger_catalog", help="Path to trigger_catalog.json")
    parser.add_argument("req_catalog", help="Path to req_catalog.json")
    parser.add_argument("--output", "-o", help="Write JSON report to this path (default: stdout)")
    args = parser.parse_args()

    family = json.loads(Path(args.family).read_text(encoding="utf-8"))
    bundle = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
    triggers = json.loads(Path(args.trigger_catalog).read_text(encoding="utf-8"))
    reqs = json.loads(Path(args.req_catalog).read_text(encoding="utf-8"))

    report = build_report(family, bundle, triggers, reqs)
    output_text = json.dumps(report, indent=2)

    if args.output:
        Path(args.output).write_text(output_text, encoding="utf-8")
        print(f"Report written to {args.output}", file=sys.stderr)
    else:
        print(output_text)


if __name__ == "__main__":
    main()
