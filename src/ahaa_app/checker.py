from __future__ import annotations
from typing import Dict, List, Tuple, Any
import sys
from pathlib import Path
import json
# Support running from the project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from compliance_checker.compliance_check import build_report

TriggerDict = Dict[str, Dict[str, Any]]

def get_missing_documents(instance):
    missing_documents = list(instance.get("missing_documents", []))
    missing_documents_type = instance.get("missing_documents_type", {})

    missing_documents.extend(missing_documents_type.get("missing_all_of", []))

    missing_any_of = missing_documents_type.get("missing_any_of", [])
    if len(missing_any_of) == 1:
        missing_documents.append(missing_any_of[0])
    elif len(missing_any_of) > 1:
        missing_documents.append(f"one of: {', '.join(missing_any_of)}")

    return missing_documents

def dummy_check_doc(application_file, document_bundle_files) -> Tuple[bool, TriggerDict]:
    """
    Runs dummy document eligibility checks.

    Parameters
    ----------
    application_file:
        A single uploaded file object from Streamlit.
    document_bundle_files:
        A list of uploaded file objects from Streamlit.

    Returns
    -------
    tuple
        (overall_pass, triggers)
        - overall_pass: bool
        - triggers: dict shaped like
          {
              trigger_id: {
                  "pass": bool,
                  "description": str,
                  "document_requirement_id": list,
              }
          }
    """
    bundle_count = len(document_bundle_files)

    triggers: TriggerDict = {
        "trigger_001": {
            "pass": application_file is not None,
            "description": "Application file was provided.",
            "document_requirement_id": ["app_required"],
        },
        "trigger_002": {
            "pass": bundle_count > 0,
            "description": "At least one supporting document was uploaded.",
            "document_requirement_id": ["bundle_required"],
        },
        "trigger_003": {
            "pass": bundle_count >= 2,
            "description": "Bundle contains at least two documents for demonstration purposes.",
            "document_requirement_id": ["demo_multi_doc_rule"],
        },
    }

    overall_pass = all(trigger["pass"] for trigger in triggers.values())
    return overall_pass, triggers


realistic_example_triggers = """
{
      "trigger_id": "trig_household_member_id",
      "description": "Every household member needs identification",
      "fired": true,
      "source_reference": {
        "document": "Maple Square FCFS Application 2026",
        "page": 18,
        "section": "Required Documents item 1",
        "quote": null
      },
      "requirement_fulfilled": true,
      "instances": [
        {
          "instance_label": "req_household_member_id::Marcus Webb",
          "requirement_id": "req_household_member_id",
          "applies_to_member": "Marcus Webb",
          "fulfilled": true,
          "missing_documents": []
        },
        {
          "instance_label": "req_household_member_id::Tina Webb",
          "requirement_id": "req_household_member_id",
          "applies_to_member": "Tina Webb",
          "fulfilled": true,
          "missing_documents": []
        },
        {
          "instance_label": "req_household_member_id::Leo Webb",
          "requirement_id": "req_household_member_id",
          "applies_to_member": "Leo Webb",
          "fulfilled": true,
          "missing_documents": []
        }
      ]
    },
    {
      "trigger_id": "trig_section_8_voucher_checklist",
      "description": "Self-attested Section 8 / voucher \u2192 require voucher proof",
      "fired": false,
      "source_reference": {
        "document": "Maple Square FCFS Application 2026",
        "page": 18,
        "section": "Required Documents item 2",
        "quote": null
      },
      "requirement_fulfilled": null,
      "instances": []
    },
"""

def check_doc(family_app_filepath, doc_bundle_filepath, 
              trigger_catalog_filepath, req_catalog_filepath) -> Tuple[bool, TriggerDict]:
    """
    Runs document eligibility checks.

    Replace the body of this function with your real external checker call.

    Parameters
    ----------
    application_file:
        A single uploaded file object from Streamlit.
    document_bundle_files:
        A list of uploaded file objects from Streamlit.

    Returns
    -------
    tuple
        (overall_pass, triggers)
        - overall_pass: bool
        - triggers: dict shaped like
          {
              trigger_id: {
                  "pass": bool,
                  "description": str,
                  "document_requirement_id": list,
              }
          }
    """
    family = json.loads(Path(family_app_filepath).read_text(encoding="utf-8"))
    bundle = json.loads(Path(doc_bundle_filepath).read_text(encoding="utf-8"))
    triggers = json.loads(Path(trigger_catalog_filepath).read_text(encoding="utf-8"))
    reqs = json.loads(Path(req_catalog_filepath).read_text(encoding="utf-8"))

    report = build_report(family, bundle, triggers, reqs)
    
    overall_pass = report['passed']
    # only keep triggers that were fired by the family application
    fired_triggers = [trig for trig in report['triggers'] if bool(trig['fired'])==True]
    
    # store total missing docs for easy display
    # also add "overall_missing_docs" to each trigger (concats applies_to_member + missing_doc)
    total_missing_docs = []
    for trig in fired_triggers:
        missing_docs = []
        if not bool(trig['requirement_fulfilled']):
            for instance in trig.get('instances', []):
                if bool(instance['fulfilled']) == False:
                    member = instance.get("applies_to_member", "")
                    member = "" if member in (None, "null", "") else f"{member} - "
                    missing_docs.extend(
                        f"{member}{doc}" for doc in get_missing_documents(instance)
                    )
        trig['all_missing_docs'] = missing_docs
        total_missing_docs.extend(missing_docs)
    
    # remove duplicates
    total_missing_docs = list(dict.fromkeys(total_missing_docs))
        
    return overall_pass, fired_triggers, total_missing_docs

if __name__ == "__main__":

    base_dir =  Path(__file__).parent.parent.parent # 14c-housing
    ex_num = 1
    print('base_dir', base_dir)
    family_app_filepath = base_dir / f'evals/usecases/family_{ex_num}.json'
    doc_bundle_filepath = base_dir / f'evals/usecases/bundle_{ex_num}.json'
    trigger_catalog_filepath = base_dir / 'catalog_templates/trigger_catalog.json'
    req_catalog_filepath = base_dir / 'catalog_templates/req_catalog.json'
