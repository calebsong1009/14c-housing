import streamlit as st
from pathlib import Path
from checker import check_doc
from feedback_server import start_feedback_server
from ui_components import (
    render_eval_results,
    render_status_banner,
    render_trigger_details_accordion,
)


def get_test_filepaths(num):
    base_dir =  Path(__file__).parent.parent.parent # 14c-housing
    ex_num = num
    family_app_filepath = base_dir / f"evals/usecases/family_{ex_num}.json"
    doc_bundle_filepath = base_dir / f"evals/usecases/bundle_{ex_num}.json"
    trigger_catalog_filepath = base_dir / 'catalog_templates/trigger_catalog.json'
    req_catalog_filepath = base_dir / 'catalog_templates/req_catalog.json'
    return family_app_filepath, doc_bundle_filepath, trigger_catalog_filepath, req_catalog_filepath


def test_check_doc(num):
    filepaths = get_test_filepaths(num)
    return check_doc(*filepaths)

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

    check_col, spacer_col, eval_col = st.columns([1, 2, 1])
    with check_col:
        check_clicked = st.form_submit_button("Check")
    with spacer_col:
        st.empty()
    with eval_col:
        eval_mode = st.toggle("Eval Mode", value=False)


if check_clicked:
    if application_file is None:
        st.error("Please upload an application file before running the check.")
    elif bundle_files is None or len(bundle_files) == 0:
        st.error("Please upload required document files before running the check.")
    else:
        try:
            
            # overall_pass, triggers = dummy_check_doc(application_file, bundle_files or [])
            family_app_filepath, doc_bundle_filepath, trigger_catalog_filepath, req_catalog_filepath = (
                get_test_filepaths(3)
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
