import streamlit as st

from checker import check_doc
from ui_components import (
    render_eval_results,
    render_status_banner,
    render_trigger_details_accordion,
)


st.set_page_config(
    page_title="Document Eligibility Checker",
    page_icon="📄",
    layout="centered",
)

st.title("AHAA: Affordable Housing Application Assistant")
st.write(
    "Upload the application file and supporting document bundle, then run the "
    "check to verify whether all necessary documents for application requirements "
    "are present."
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
            overall_pass, triggers = check_doc(application_file, bundle_files or [])

            st.divider()
            if eval_mode:
                render_eval_results(overall_pass, triggers)
            else:
                render_status_banner("Document bundle passed", overall_pass)

                if not triggers:
                    st.info("No triggers were returned.")
                else:
                    render_trigger_details_accordion(triggers)

        except Exception as exc:
            st.exception(exc)
else:
    st.caption("Nothing has been checked yet.")
