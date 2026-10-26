import streamlit as st
import os
from engine import extract_text_from_file, run_scrutiny_checks, detect_ela

st.set_page_config(page_title="AICTE Scrutiny Assistant", layout="wide")

st.title("AICTE EoA Scrutiny Decision-Support System")
st.caption("AI-Powered Pre-Screening, Document Authentication & Regulatory Compliance Checker")

uploaded_file = st.file_uploader("Upload Scrutiny File (.pdf, .txt, .png, .jpg)", type=["pdf", "txt", "png", "jpg"])

if uploaded_file:
    file_path = f"temp_{uploaded_file.name}"
    with open(file_path, "wb") as f:
        f.write(uploaded_file.read())

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Submitted Document Preview")
        if file_path.endswith((".pdf", ".txt")):
            text = extract_text_from_file(file_path)
            st.text_area("Extracted Digital Text (OCR / Stream)", text, height=420)
        else:
            st.image(file_path, caption="Uploaded File / Infrastructure Proof", use_container_width=True)

    with col2:
        st.subheader("Audit & Compliance Findings")
        if file_path.endswith((".pdf", ".txt")):
            findings = run_scrutiny_checks(text)
            for item in findings:
                if "FLAGGED" in item["status"]:
                    st.error(f"**[{item['status']}] {item['check']}**")
                else:
                    st.success(f"**[{item['status']}] {item['check']}**")
                st.write(f"- **Extracted Value:** `{item['extracted']}`")
                st.write(f"- **Statutory Clause:** {item['rule']}")
                st.write(f"- **Officer Note:** {item['observation']}")
                st.divider()
        else:
            st.write("Running Error Level Analysis (ELA) for image manipulation check...")
            ela_img = detect_ela(file_path)
            st.image(ela_img, caption="Forensic Compression Heatmap", use_container_width=True)
            st.warning("Advisory: Pixel brightness spikes highlight localized modification/pasted content.")