import streamlit as st
from pathlib import Path
from checker import check_doc
from feedback_server import start_feedback_server
from ui_components import (
    render_eval_results,
    render_status_banner,
    render_trigger_details_accordion,
)

BASE_DIR =  Path(__file__).parent.parent.parent # 14c-housing
CATALOGS_DIR = BASE_DIR / "catalogs"

def get_catalog_options():
    if not CATALOGS_DIR.exists():
        return []
    return sorted(
        catalog_dir.name
        for catalog_dir in CATALOGS_DIR.iterdir()
        if catalog_dir.is_dir()
    )

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

def get_test_filepaths(fam_id, bun_id, catalog_version='mco_maple_square_v0'):
    family_app_filepath = BASE_DIR / f"evals/usecases/family_{fam_id}.json"
    doc_bundle_filepath = BASE_DIR / f"evals/usecases/bundle_{bun_id}.json"
    trigger_catalog_filepath, req_catalog_filepath = get_catalog_filepaths(catalog_version)
    return family_app_filepath, doc_bundle_filepath, trigger_catalog_filepath, req_catalog_filepath

@st.cache_resource
def get_feedback_save_url():
    save_dir = Path(__file__).resolve().parent / "saved_feedback"
    return start_feedback_server(save_dir)

st.set_page_config(
    page_title="HAHA",
    page_icon="🏠",
    layout="centered",
)

st.title("HAHA: Help for Affordable Housing Applications.")
st.write(
    "Check whether your Affordable Housing Application is complete! \n\n"
    "Upload your application file and supporting document bundle, then run the "
    "check to see whether any required documents may be missing."
)

with st.container(border=True):
    eval_mode = st.toggle("Eval Mode", value=False)
    catalog_options = get_catalog_options()
    selected_catalog = st.selectbox(
        "Catalog",
        options=catalog_options,
        index=0 if catalog_options else None,
        placeholder="No catalogs available",
    )

with st.form("eligibility_form"):
    st.subheader("Application Upload")
    application_file = st.file_uploader(
        "Upload a single application file",
        type=None,
        accept_multiple_files=False,
        key="application_upload",
    )

    st.subheader("Document Bundle Upload")
    bundle_files = st.file_uploader(
        "Upload one or more supporting documents",
        type=None,
        accept_multiple_files=True,
        key="bundle_upload",
    )

    check_clicked = st.form_submit_button("Check")


if check_clicked:
    if selected_catalog is None:
        st.error("Please choose a catalog before running the check.")
    elif application_file is None:
        st.error("Please upload an application file before running the check.")
    elif bundle_files is None or len(bundle_files) == 0:
        st.error("Please upload required document files before running the check.")
    else:
        try:
            
            family_app_filepath, doc_bundle_filepath, trigger_catalog_filepath, req_catalog_filepath = (
                get_test_filepaths(4, 4, selected_catalog)
            )
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
