import json
import shutil
import tempfile
import time
from pathlib import Path

import streamlit as st

from checker import check_doc
from feedback_server import start_feedback_server
from ui_components import (
    render_catalog_trigger_list,
    render_eval_results,
    render_status_banner,
    render_trigger_details_accordion,
)

BASE_DIR =  Path(__file__).parent.parent.parent # 14c-housing
# this directory contains rule catalogs available in the app dropdown
CATALOGS_DIR = BASE_DIR / "catalogs"
# uploaded family/bundle JSON are persisted here so the saved-feedback flow can copy them
UPLOADS_DIR = Path(tempfile.gettempdir()) / "ahaa_uploads"
# copies catalog files in this directory to simulate "generating" new llm-based rule catalogs
LLM_GEN_CATALOG_DIR = BASE_DIR / "catalog_templates" / "mco_maple_square_llm"
ENGINE_ID_ALLOWED_CHARS = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")

def get_catalog_options():
    if not CATALOGS_DIR.exists():
        return []
    return sorted(
        catalog_dir.name
        for catalog_dir in CATALOGS_DIR.iterdir()
        if catalog_dir.is_dir()
    )

def save_uploaded_json(uploaded_file, dest_name):
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    dest_path = UPLOADS_DIR / dest_name
    dest_path.write_bytes(uploaded_file.getvalue())
    return dest_path

def get_catalog_filepaths(catalog_version):
    catalog_dir = CATALOGS_DIR / catalog_version
    trigger_catalog_filepath = catalog_dir / 'trigger_catalog.json'
    req_catalog_filepath = catalog_dir / 'req_catalog.json'
    missing_files = [
        path.name
        for path in (trigger_catalog_filepath, req_catalog_filepath)
        if not path.exists()
    ]

    if missing_files:
        raise FileNotFoundError(
            f"Catalog '{catalog_version}' is missing: {', '.join(missing_files)}"
        )

    return trigger_catalog_filepath, req_catalog_filepath

def read_trigger_catalog(catalog_id):
    trigger_catalog_filepath = CATALOGS_DIR / catalog_id / "trigger_catalog.json"
    with trigger_catalog_filepath.open() as trigger_catalog_file:
        triggers = json.load(trigger_catalog_file)

    if not isinstance(triggers, list):
        raise ValueError(
            f"Expected {trigger_catalog_filepath} to contain a list of trigger objects."
        )

    return triggers

def get_compliance_engine_dir(engine_id):
    cleaned_engine_id = engine_id.strip()
    if not cleaned_engine_id:
        raise ValueError("Please enter a rule catalog id for your housing program.")
    if any(char not in ENGINE_ID_ALLOWED_CHARS for char in cleaned_engine_id):
        raise ValueError(
            "Catalog id can only contain letters, numbers, underscores, and hyphens."
        )

    return CATALOGS_DIR / cleaned_engine_id

def copy_llm_template_catalog(compliance_engine_dir):
    if not LLM_GEN_CATALOG_DIR.exists():
        raise FileNotFoundError(
            f"LLM template catalog directory not found: {LLM_GEN_CATALOG_DIR}"
        )

    shutil.copytree(
        LLM_GEN_CATALOG_DIR,
        compliance_engine_dir,
        dirs_exist_ok=True,
    )

def render_compliance_engine_loading():
    messages = [
        "Reading the fine print...",
        "Finding eligibility rules...",
        "Sorting documents from declarations...",
        "Assembling compliance checks...",
        "Polishing the rule catalog...",
    ]
    progress_bar = st.progress(0, text="Starting compliance engine build...")

    for index, message in enumerate(messages, start=1):
        time.sleep(1)
        progress_bar.progress(index * 20, text=message)

@st.cache_resource
def get_feedback_save_url():
    save_dir = Path(__file__).resolve().parent / "saved_feedback"
    return start_feedback_server(save_dir)

st.set_page_config(
    page_title="HAHA",
    page_icon="🏠",
    layout="centered",
)

st.title("🏠 Help for Affordable Housing Applications")

eval_mode = st.toggle("⚙️ Housing Provider Admin View", value=False)

tab_labels = ["📋 Check My Application"]
if eval_mode:
    tab_labels.extend(["⚙️ Compliance Engine Config", "🛠️ Update Rule Catalog"])

tabs = st.tabs(tab_labels)
check_tab = tabs[0]
if eval_mode:
    build_tab, update_tab = tabs[1], tabs[2]

with check_tab:
    st.write(
        "Check whether your Affordable Housing Application is complete. \n\n"
        "Upload your application file and supporting document bundle, then run the "
        "check to see whether any required documents may be missing."
    )

    with st.container(border=True):
        catalog_options = get_catalog_options()
        selected_catalog = st.selectbox(
            "Select the Housing Program Rule Catalog.",
            options=catalog_options,
            index=0 if catalog_options else None,
            placeholder="No housing problem rule catalogs available",
        )

    with st.form("eligibility_form"):
        st.subheader("Application Upload")
        application_file = st.file_uploader(
            "Upload the family application JSON",
            type=["json"],
            accept_multiple_files=False,
            key="application_upload",
        )

        st.subheader("Document Bundle Upload")
        bundle_file = st.file_uploader(
            "Upload the document bundle JSON",
            type=["json"],
            accept_multiple_files=False,
            key="bundle_upload",
        )

        check_clicked = st.form_submit_button("Check")

    if check_clicked:
        if selected_catalog is None:
            st.error("Please choose a catalog before running the check.")
        elif application_file is None:
            st.error("Please upload an application JSON before running the check.")
        elif bundle_file is None:
            st.error("Please upload a document bundle JSON before running the check.")
        else:
            try:
                family_app_filepath = save_uploaded_json(application_file, "family_application.json")
                doc_bundle_filepath = save_uploaded_json(bundle_file, "document_bundle.json")
                trigger_catalog_filepath, req_catalog_filepath = get_catalog_filepaths(selected_catalog)
                overall_pass, triggers, total_missing_docs = check_doc(
                    family_app_filepath,
                    doc_bundle_filepath,
                    trigger_catalog_filepath,
                    req_catalog_filepath,
                )

                st.divider()
                if eval_mode:
                    render_eval_results(
                        overall_pass,
                        triggers,
                        total_missing_docs,
                        get_feedback_save_url(),
                        family_app_filepath,
                        doc_bundle_filepath,
                    )
                else:
                    render_status_banner(overall_pass, total_missing_docs)

                    if not triggers:
                        st.info("No triggers were returned.")
                    else:
                        render_trigger_details_accordion(triggers)

            except Exception as exc:
                st.exception(exc)
    else:
        st.caption("Nothing has been checked yet.")

if eval_mode:
    with build_tab:
        st.write(
            "Hello, Housing Provider! Convert your program’s existing guidelines into a structured rule catalog"
            " that powers our compliance engine, which will allow families to check their application completeness for your housing program."
        )

        if "compliance_engine_created_message" in st.session_state:
            st.success(st.session_state.pop("compliance_engine_created_message"))

        with st.form("guidelines_form"):
            compliance_engine_id = st.text_input(
                "Program Rule Catalog ID",
                max_chars=64,
                placeholder="Enter an identifier for your housing program's rule catalog.",
                key="compliance_engine_id",
            )

            st.subheader("Program Guidelines Upload")
            guideline_files = st.file_uploader(
                "Upload one or more application guideline documents for your program",
                type=None,
                accept_multiple_files=True,
                key="guidelines_upload",
            )

            build_rules_clicked = st.form_submit_button("🤖 Build Compliance Rules")

        if build_rules_clicked:
            try:
                compliance_engine_dir = get_compliance_engine_dir(compliance_engine_id)
                if compliance_engine_dir.exists():
                    raise FileExistsError

                render_compliance_engine_loading()
                CATALOGS_DIR.mkdir(parents=True, exist_ok=True)
                compliance_engine_dir.mkdir()
                copy_llm_template_catalog(compliance_engine_dir)
                st.session_state.compliance_engine_created_message = (
                    f"Created rule catalog for compliance engine: {compliance_engine_dir.name}"
                )
                st.session_state.latest_built_compliance_engine_id = compliance_engine_dir.name
                st.rerun()
            except FileExistsError:
                st.error("A compliance engine with that id already exists.")
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.exception(exc)

        built_engine_id = st.session_state.get("latest_built_compliance_engine_id")
        if built_engine_id:
            try:
                built_triggers = read_trigger_catalog(built_engine_id)
                st.subheader("Generated Compliance Triggers")
                st.caption(f"Program Rule Catalog ID: {built_engine_id}")
                render_catalog_trigger_list(built_triggers)
            except FileNotFoundError:
                st.info(
                    f"No trigger_catalog.json found yet for {built_engine_id}. "
                    "Once the catalog builder writes that file, generated triggers will appear here."
                )
            except Exception as exc:
                st.exception(exc)

    with update_tab:
        st.write("Hello, Housing Provider! Update your existing rule catalog using flagged feedback from user applications.")

        with st.container(border=True):
            catalog_options = get_catalog_options()
            selected_update_catalog = st.selectbox(
                "Select the Housing Program Rule Catalog.",
                options=catalog_options,
                index=0 if catalog_options else None,
                placeholder="No housing problem rule catalogs available",
                key="update_catalog_select",
            )

        saved_feedback_dir = Path(__file__).resolve().parent / "saved_feedback"

        # Auto-refreshing fragment: polls saved_feedback/ every 2s so newly-saved
        # sessions appear in the dropdown without the user having to interact.
        # Lives outside the form because st.form widgets don't update mid-form.
        @st.fragment(run_every="2s")
        def render_feedback_session_selector():
            folders = sorted(
                [d.name for d in saved_feedback_dir.iterdir() if d.is_dir()]
            ) if saved_feedback_dir.exists() else []
            if folders:
                st.selectbox(
                    "Select a feedback session to apply.",
                    options=folders,
                    key="selected_feedback_session",
                )
            else:
                st.info("No saved feedback sessions found. Run a compliance check in admin view and save feedback first.")
                st.session_state.pop("selected_feedback_session", None)

        st.subheader("Saved Feedback Sessions")
        render_feedback_session_selector()

        with st.form("update_rule_catalog_form"):
            update_rules_clicked = st.form_submit_button("🤖 Update Rule Catalog")

        if update_rules_clicked:
            selected_feedback = st.session_state.get("selected_feedback_session")
            if selected_update_catalog is None:
                st.error("Please choose a rule catalog before updating.")
            elif not selected_feedback:
                st.error("No feedback sessions available to apply.")
            else:
                try:
                    import sys
                    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
                    from feedback_agent.agent import run_from_saved_feedback

                    trigger_path, req_path = get_catalog_filepaths(selected_update_catalog)
                    triggers = json.loads(trigger_path.read_text(encoding="utf-8"))
                    reqs = json.loads(req_path.read_text(encoding="utf-8"))
                    folder = saved_feedback_dir / selected_feedback

                    with st.spinner("Running feedback agent..."):
                        updated_triggers, updated_reqs, analysis = run_from_saved_feedback(
                            feedback_dir=folder,
                            trigger_catalog=triggers,
                            req_catalog=reqs,
                        )

                    trigger_path.write_text(json.dumps(updated_triggers, indent=2), encoding="utf-8")
                    req_path.write_text(json.dumps(updated_reqs, indent=2), encoding="utf-8")

                    st.success(f"Rule catalog '{selected_update_catalog}' updated.")
                    st.write(f"**What changed:** {analysis}")
                except Exception as exc:
                    st.exception(exc)
