"""
Feedback Agent — integration tests.

Each test:
  1. Runs compliance_trace on a (family, bundle) pair — confirms it FAILS.
  2. Passes the trace + human feedback to run_feedback_agent.
  3. Runs compliance again with updated catalogs — confirms PASS.
  4. Checks the edit was surgical.

Requires ANTHROPIC_API_KEY (in .env at repo root or in environment).
Run: python tests/test_feedback_agent.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from compliance import run_compliance, run_compliance_trace
from agent import run_feedback_agent

USECASES = Path(__file__).parent.parent.parent.parent / "evals" / "usecases"


def _family(n: int) -> dict:
    return json.loads((USECASES / f"family_{n}.json").read_text())


def _bundle(n: int) -> dict:
    return json.loads((USECASES / f"bundle_{n}.json").read_text())


# ---------------------------------------------------------------------------
# Test 1 — req_pay_stubs requires 5 stubs; bundle_3 only has 3.
#
# family_3 (Marcus Webb): eligibility_checklist.pay_stubs = true (plain bool,
# matches updated family format) → trigger fires.
# bundle_3 has pay_stub_1, pay_stub_2, pay_stub_3 only.
# Buggy catalog requires all_of[5] → FAIL.
# Human feedback: regulation only requires 3.
# Expected fix: document_spec shrinks to all_of[3].
# ---------------------------------------------------------------------------

TRIGGERS_T1 = [
    {
        "trigger_id": "trig_pay_stubs_checklist",
        "description": "Self-attested wage income → require consecutive pay stubs",
        "activation": {
            "type": "predicate",
            "field": "eligibility_checklist.pay_stubs",
            "operator": "equals",
            "value": True,
        },
        "emits_requirements": ["req_pay_stubs"],
        "instance_scope": "household",
        "per_member_scope": None,
        "source_reference": {
            "document": "Maple Square FCFS Application 2026",
            "page": 18,
            "section": "Required Documents item 5",
            "quote": None,
        },
    }
]

REQS_T1 = [
    {
        "requirement_id": "req_pay_stubs",
        "description": "Five consecutive pay stubs (bug: should be 3)",
        "document_spec": {
            "type": "all_of",
            "children": [
                {"type": "document", "document_type": "pay_stub_1.pdf", "notes": None},
                {"type": "document", "document_type": "pay_stub_2.pdf", "notes": None},
                {"type": "document", "document_type": "pay_stub_3.pdf", "notes": None},
                {"type": "document", "document_type": "pay_stub_4.pdf", "notes": None},
                {"type": "document", "document_type": "pay_stub_5.pdf", "notes": None},
            ],
        },
        "source_reference": {
            "document": "Maple Square FCFS Application 2026",
            "page": 18,
            "section": "Required Documents item 5",
            "quote": None,
        },
    }
]

FEEDBACK_T1 = (
    "The pay stubs requirement failed because pay_stub_4.pdf and pay_stub_5.pdf were missing. "
    "However the regulation only requires 3 consecutive pay stubs, not 5. "
    "Marcus Webb submitted pay_stub_1.pdf, pay_stub_2.pdf, and pay_stub_3.pdf which is sufficient. "
    "Please update req_pay_stubs to only require 3 pay stubs."
)


def test_pay_stubs_requirement_fix() -> None:
    family = _family(3)
    bundle = _bundle(3)

    trace = run_compliance_trace(family, bundle, TRIGGERS_T1, REQS_T1)
    assert not trace["passed"], "Expected pre-fix failure"
    assert any(
        r["requirement_id"] == "req_pay_stubs" and not r["satisfied"]
        for r in trace["requirement_trace"]
    )

    updated_triggers, updated_reqs, analysis = run_feedback_agent(
        trigger_catalog=TRIGGERS_T1,
        req_catalog=REQS_T1,
        bundle=bundle,
        family=family,
        compliance_trace=trace,
        human_feedback=FEEDBACK_T1,
    )
    print(f"\n[T1] Analysis: {analysis}")

    passed_after, failed_after = run_compliance(family, bundle, updated_triggers, updated_reqs)
    assert passed_after, f"Expected post-fix pass, still failing: {failed_after}"

    assert updated_triggers == TRIGGERS_T1, "Triggers should not have changed"

    updated_spec = next(
        r["document_spec"] for r in updated_reqs if r["requirement_id"] == "req_pay_stubs"
    )
    assert updated_spec != REQS_T1[0]["document_spec"], "document_spec should have changed"

    print("[T1] PASS")


# ---------------------------------------------------------------------------
# Test 2 — trig_irs_non_filing fires for every applicant (bug: household.total_size > 0);
#           should only fire when eligibility_checklist.irs_non_filing_verification = true.
#
# family_4 (Priya Patel): total_size=1 > 0 → trigger fires.
# eligibility_checklist.irs_non_filing_verification = false.
# bundle_4 has no irs_non_filing_verification.pdf → FAIL.
# Human feedback: trigger should use the checklist field.
# After fix: checklist=false → trigger doesn't fire → PASS.
# ---------------------------------------------------------------------------

TRIGGERS_T2 = [
    {
        "trigger_id": "trig_irs_non_filing",
        "description": "IRS non-filing verification — bug: fires for all applicants",
        "activation": {
            "type": "predicate",
            "field": "household.total_size",
            "operator": "greater_than",
            "value": 0,
        },
        "emits_requirements": ["req_irs_non_filing"],
        "instance_scope": "household",
        "per_member_scope": None,
        "source_reference": {
            "document": "Maple Square FCFS Application 2026",
            "page": 19,
            "section": "Required Documents item 9",
            "quote": None,
        },
    }
]

REQS_T2 = [
    {
        "requirement_id": "req_irs_non_filing",
        "description": "IRS verification of non-filing letter",
        "document_spec": {
            "type": "document",
            "document_type": "irs_non_filing_verification.pdf",
            "notes": None,
        },
        "source_reference": {
            "document": "Maple Square FCFS Application 2026",
            "page": 19,
            "section": "Required Documents item 9",
            "quote": None,
        },
    }
]

FEEDBACK_T2 = (
    "The IRS non-filing verification trigger is incorrectly firing for Priya Patel. "
    "The trigger fires for every applicant (household.total_size > 0) which is wrong — "
    "it should only fire when the applicant checked the irs_non_filing_verification box "
    "on their eligibility checklist (eligibility_checklist.irs_non_filing_verification equals true). "
    "Priya did not check that box so the trigger should not have fired. "
    "Please fix the trigger activation to use the checklist field."
)


def test_irs_non_filing_trigger_fix() -> None:
    family = _family(4)
    bundle = _bundle(4)

    trace = run_compliance_trace(family, bundle, TRIGGERS_T2, REQS_T2)
    assert not trace["passed"], "Expected pre-fix failure"
    assert any(
        t["trigger_id"] == "trig_irs_non_filing" and t["fired"]
        for t in trace["trigger_trace"]
    )

    updated_triggers, updated_reqs, analysis = run_feedback_agent(
        trigger_catalog=TRIGGERS_T2,
        req_catalog=REQS_T2,
        bundle=bundle,
        family=family,
        compliance_trace=trace,
        human_feedback=FEEDBACK_T2,
    )
    print(f"\n[T2] Analysis: {analysis}")

    passed_after, failed_after = run_compliance(family, bundle, updated_triggers, updated_reqs)
    assert passed_after, f"Expected post-fix pass, still failing: {failed_after}"

    assert updated_reqs == REQS_T2, "Requirements should not have changed"

    updated_activation = next(
        t["activation"] for t in updated_triggers if t["trigger_id"] == "trig_irs_non_filing"
    )
    assert "irs_non_filing_verification" in json.dumps(updated_activation), (
        f"Updated activation should reference checklist field, got: {updated_activation}"
    )

    print("[T2] PASS")


# ---------------------------------------------------------------------------
# Test 3 — trig_household_member_id is per_member scope (matches real catalog).
#           req only accepts birth_certificate.pdf (bug).
#           Bundle has driver_license.pdf but no birth_certificate → FAIL per member.
#           Human feedback: driver_license should also be accepted.
#           After fix: one_of spec → driver_license satisfies for all members → PASS.
# ---------------------------------------------------------------------------

TRIGGERS_T3 = [
    {
        "trigger_id": "trig_household_member_id",
        "description": "Every household member needs identification",
        "activation": {
            "type": "predicate",
            "field": "household.total_size",
            "operator": "greater_than",
            "value": 0,
        },
        "emits_requirements": ["req_household_member_id"],
        "instance_scope": "per_member",
        "per_member_scope": {
            "type": "predicate",
            "field": "name",
            "operator": "exists",
            "value": None,
        },
        "source_reference": {
            "document": "Maple Square FCFS Application 2026",
            "page": 18,
            "section": "Required Documents item 1",
            "quote": None,
        },
    }
]

REQS_T3 = [
    {
        "requirement_id": "req_household_member_id",
        "description": "Government-issued photo ID — bug: only accepts birth certificate",
        "document_spec": {
            "type": "document",
            "document_type": "birth_certificate.pdf",
            "notes": None,
        },
        "source_reference": {
            "document": "Maple Square FCFS Application 2026",
            "page": 18,
            "section": "Required Documents item 1",
            "quote": None,
        },
    }
]

BUNDLE_T3 = {
    "bundle_id": "bundle_test3",
    "documents": [
        "driver_license.pdf",
        "pay_stub_1.pdf",
        "pay_stub_2.pdf",
        "pay_stub_3.pdf",
        "pay_stub_4.pdf",
        "pay_stub_5.pdf",
        "federal_tax_return_2024.pdf",
        "checking_statement_march2025.pdf",
    ],
}

FEEDBACK_T3 = (
    "The household member ID requirement failed for Carlos and Maria Rivera because "
    "the bundle contained driver_license.pdf but the requirement only accepts birth_certificate.pdf. "
    "The Maple Square application accepts any government-issued photo ID — "
    "a driver's license is valid identification. "
    "Please update req_household_member_id to also accept driver_license.pdf and passport.pdf."
)


def test_household_id_requirement_fix() -> None:
    family = _family(5)
    bundle = BUNDLE_T3

    trace = run_compliance_trace(family, bundle, TRIGGERS_T3, REQS_T3)
    assert not trace["passed"], "Expected pre-fix failure"
    assert any(
        r["requirement_id"] == "req_household_member_id" and not r["satisfied"]
        for r in trace["requirement_trace"]
    )

    updated_triggers, updated_reqs, analysis = run_feedback_agent(
        trigger_catalog=TRIGGERS_T3,
        req_catalog=REQS_T3,
        bundle=bundle,
        family=family,
        compliance_trace=trace,
        human_feedback=FEEDBACK_T3,
    )
    print(f"\n[T3] Analysis: {analysis}")

    passed_after, failed_after = run_compliance(family, bundle, updated_triggers, updated_reqs)
    assert passed_after, f"Expected post-fix pass, still failing: {failed_after}"

    assert updated_triggers == TRIGGERS_T3, "Triggers should not have changed"

    updated_spec = next(
        r["document_spec"] for r in updated_reqs if r["requirement_id"] == "req_household_member_id"
    )
    assert updated_spec["type"] == "one_of", f"Expected one_of, got {updated_spec['type']!r}"
    doc_types = {c["document_type"] for c in updated_spec["children"]}
    assert "driver_license.pdf" in doc_types

    print("[T3] PASS")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        ("Test 1 — pay_stubs req (5→3 stubs, family_3/bundle_3)",              test_pay_stubs_requirement_fix),
        ("Test 2 — irs_non_filing trigger (always-on→checklist, family_4)",    test_irs_non_filing_trigger_fix),
        ("Test 3 — household_id per_member req (birth_cert→one_of, family_5)", test_household_id_requirement_fix),
    ]

    passed = failed = 0
    for name, fn in tests:
        print(f"\n{'='*60}\n{name}\n{'='*60}")
        try:
            fn()
            passed += 1
        except Exception as exc:
            import traceback
            print(f"FAILED: {exc}")
            traceback.print_exc()
            failed += 1

    print(f"\n{'='*60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)}")
    print("=" * 60)
    sys.exit(0 if failed == 0 else 1)
