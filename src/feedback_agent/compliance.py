"""
Minimal P2 compliance engine.

run_compliance       — returns (passed, failed_labels)  [lightweight check]
run_compliance_trace — returns a full trace dict the feedback agent passes to the LLM
"""

from __future__ import annotations
from typing import Any


def _get_nested(data: dict, path: str) -> Any:
    current = data
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _eval_condition(condition: dict, data: dict) -> bool:
    t = condition["type"]

    if t == "predicate":
        val    = _get_nested(data, condition["field"])
        op     = condition["operator"]
        target = condition.get("value")

        if op == "equals":       return val == target
        if op == "not_equals":   return val != target
        if op == "greater_than": return val is not None and val > target
        if op == "less_than":    return val is not None and val < target
        if op == "contains":     return target in (val or [])
        if op == "in":           return val in (target or [])
        if op == "exists":       return val is not None
        return False

    if t == "all": return all(_eval_condition(c, data) for c in condition["children"])
    if t == "any": return any(_eval_condition(c, data) for c in condition["children"])
    if t == "not": return not _eval_condition(condition["child"], data)

    raise ValueError(f"Unknown condition type: {t!r}")


def _eval_doc_spec(spec: dict, documents: list[str]) -> tuple[bool, dict]:
    """Returns (satisfied, {"all_of": [...], "any_of": [...]}) with missing document types."""
    t = spec["type"]

    if t == "document":
        hit = spec["document_type"] in documents
        return hit, ({"all_of": [], "any_of": []} if hit else {"all_of": [spec["document_type"]], "any_of": []})

    if t == "all_of":
        all_of_missing: list[str] = []
        any_of_missing: list[str] = []
        for child in spec["children"]:
            ok, child_missing = _eval_doc_spec(child, documents)
            if not ok:
                all_of_missing.extend(child_missing["all_of"])
                any_of_missing.extend(child_missing["any_of"])
        satisfied = not all_of_missing and not any_of_missing
        return satisfied, {"all_of": all_of_missing, "any_of": any_of_missing}

    if t == "one_of":
        for child in spec["children"]:
            ok, _ = _eval_doc_spec(child, documents)
            if ok:
                return True, {"all_of": [], "any_of": []}
        any_of_options: list[str] = []
        for child in spec["children"]:
            _, child_missing = _eval_doc_spec(child, documents)
            any_of_options.extend(child_missing["all_of"])
            any_of_options.extend(child_missing["any_of"])
        return False, {"all_of": [], "any_of": any_of_options}

    raise ValueError(f"Unknown document_spec type: {t!r}")


def _per_member_entries(trigger: dict, family: dict, req_map: dict, docs: list[str]) -> list[dict]:
    per_member_cond = trigger.get("per_member_scope")
    members = family.get("household", {}).get("members", [])
    entries = []
    for member in members:
        if per_member_cond is None or _eval_condition(per_member_cond, member):
            for req_id in trigger["emits_requirements"]:
                req = req_map.get(req_id)
                if req is None:
                    continue
                satisfied, missing = _eval_doc_spec(req["document_spec"], docs)
                label = f"{req_id}::{member.get('name', 'unknown')}"
                entries.append({
                    "requirement_id": req_id,
                    "instance_label": label,
                    "triggered_by": [trigger["trigger_id"]],
                    "applies_to_member": member.get("name"),
                    "satisfied": satisfied,
                    "missing_document_types": missing,
                })
    return entries


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_compliance(
    family: dict,
    bundle: dict,
    triggers: list[dict],
    reqs: list[dict],
) -> tuple[bool, list[str]]:
    """Lightweight check. Returns (passed, failed_instance_labels)."""
    trace = run_compliance_trace(family, bundle, triggers, reqs)
    failed = [r["instance_label"] for r in trace["requirement_trace"] if not r["satisfied"]]
    return len(failed) == 0, failed


def run_compliance_trace(
    family: dict,
    bundle: dict,
    triggers: list[dict],
    reqs: list[dict],
) -> dict:
    """
    Full compliance evaluation with audit trail.

    Returns:
    {
      "passed": bool,
      "trigger_trace": [
        {"trigger_id": str, "fired": bool, "emitted_requirements": [str]}
      ],
      "requirement_trace": [
        {
          "requirement_id": str,
          "instance_label": str,            # e.g. "req_pay_stubs" or "req_id::member_name"
          "triggered_by": [str],            # trigger_ids that emitted this
          "applies_to_member": str | null,
          "satisfied": bool,
          "missing_document_types": [str]   # empty when satisfied
        }
      ]
    }
    """
    req_map = {r["requirement_id"]: r for r in reqs}
    docs    = bundle["documents"]

    trigger_trace: list[dict] = []
    req_trace_map: dict[str, dict] = {}  # instance_label → entry

    for trigger in triggers:
        fired = _eval_condition(trigger["activation"], family)
        trigger_trace.append({
            "trigger_id": trigger["trigger_id"],
            "fired": fired,
            "emitted_requirements": trigger["emits_requirements"] if fired else [],
        })

        if not fired:
            continue

        scope = trigger.get("instance_scope", "household")

        if scope in ("household", "applicant", "co_applicant"):
            for req_id in trigger["emits_requirements"]:
                req = req_map.get(req_id)
                if req is None:
                    continue
                satisfied, missing = _eval_doc_spec(req["document_spec"], docs)
                label = req_id
                if label in req_trace_map:
                    req_trace_map[label]["triggered_by"].append(trigger["trigger_id"])
                    if satisfied:  # once satisfied by any trigger path, it's satisfied
                        req_trace_map[label]["satisfied"] = True
                        req_trace_map[label]["missing_document_types"] = {"all_of": [], "any_of": []}
                else:
                    req_trace_map[label] = {
                        "requirement_id": req_id,
                        "instance_label": label,
                        "triggered_by": [trigger["trigger_id"]],
                        "applies_to_member": None,
                        "satisfied": satisfied,
                        "missing_document_types": missing,
                    }

        elif scope == "per_member":
            for entry in _per_member_entries(trigger, family, req_map, docs):
                label = entry["instance_label"]
                if label not in req_trace_map:
                    req_trace_map[label] = entry
                else:
                    req_trace_map[label]["triggered_by"].append(trigger["trigger_id"])

    req_trace = list(req_trace_map.values())
    return {
        "passed": all(r["satisfied"] for r in req_trace),
        "trigger_trace": trigger_trace,
        "requirement_trace": req_trace,
    }
