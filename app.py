import streamlit as st
import os
from engine import extract_text_from_file, run_scrutiny_checks, detect_ela, generate_scrutiny_pdf

st.set_page_config(page_title="AICTE Scrutiny Assistant", layout="wide")

st.title("AICTE EoA Scrutiny Decision-Support System")
st.caption("Universal AI Pre-Screening, Document Authentication & APH Regulatory Compliance Engine")

uploaded_file = st.file_uploader("Upload Any College Scrutiny Dossier (.pdf, .txt, .png, .jpg)", type=["pdf", "txt", "png", "jpg"])

if uploaded_file:
    file_path = f"temp_{uploaded_file.name}"
    with open(file_path, "wb") as f:
        f.write(uploaded_file.read())

    try:
        col1, col2 = st.columns([1, 1])

        with col1:
            st.subheader("Submitted Document Preview")
            if file_path.endswith((".pdf", ".txt")):
                text = extract_text_from_file(file_path)
                st.text_area("Extracted Digital Text (OCR / Stream)", text, height=450)
            else:
                st.image(file_path, caption="Uploaded File / Infrastructure Proof", use_container_width=True)

        with col2:
            st.subheader("Universal AICTE Handbook Audit Findings")
            if file_path.endswith((".pdf", ".txt")):
                findings, detected_college = run_scrutiny_checks(text)
                
                total_checks = len(findings)
                flagged_count = sum(1 for f in findings if "FLAGGED" in f["status"])
                verified_count = total_checks - flagged_count
                
                st.info(f"**Evaluated Entity:** {detected_college}")
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Checks", total_checks)
                m2.metric("Compliant", verified_count)
                m3.metric("Flagged Deficiencies", flagged_count)
                st.divider()

                for item in findings:
                    if "FLAGGED" in item["status"]:
                        st.error(f"**[{item['status']}] {item['check']}**")
                    else:
                        st.success(f"**[{item['status']}] {item['check']}**")
                    st.write(f"- **Extracted Value:** `{item['extracted']}`")
                    st.write(f"- **Statutory Clause:** {item['rule']}")
                    st.write(f"- **Officer Note:** {item['observation']}")
                    st.divider()

                pdf_report = generate_scrutiny_pdf(findings, institution_name=detected_college)
                st.download_button(
                    label="📄 Download Official Scrutiny Audit Report (PDF)",
                    data=pdf_report,
                    file_name=f"AICTE_Audit_{detected_college.replace(' ', '_')}.pdf",
                    mime="application/pdf"
                )
            else:
                st.write("Running Error Level Analysis (ELA) for image manipulation check...")
                ela_img = detect_ela(file_path)
                st.image(ela_img, caption="Forensic Compression Heatmap", use_container_width=True)
                st.warning("Advisory: Pixel brightness spikes highlight localized modification/pasted content.")
                
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)