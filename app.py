import streamlit as st
import pandas as pd
import os
from engine import (
    extract_text_from_file,
    run_scrutiny_checks,
    detect_ela,
    scan_qr_and_barcodes,
    generate_scrutiny_pdf,
    create_self_contained_qr_url,
    decode_qr_report_param,
    generate_report_qr_code
)

# Your live Streamlit Cloud URL (never blocked by mobile carriers)
APP_PUBLIC_URL = "https://aicte-scrutiny-assistant-fyztjom2ndeysdummktxxn.streamlit.app"

st.set_page_config(page_title="AICTE Document Scanner & Scrutiny System", layout="wide")

# Check if opened via Mobile QR Code Scan
query_params = st.query_params
if "report" in query_params:
    try:
        findings, summary = decode_qr_report_param(query_params["report"])
        pdf_bytes = generate_scrutiny_pdf(findings, summary)
        pdf_filename = f"AICTE_Report_{summary['institution'].replace(' ', '_')}.pdf"

        st.title("📱 AICTE Mobile Report Portal")
        st.success(f"**Verified Audit Report for:** {summary['institution']}")
        st.metric("Compliance Score", f"{summary['compliance_score']}%", summary["verdict_status"])

        st.download_button(
            label="📥 TAP HERE TO DOWNLOAD PDF REPORT",
            data=pdf_bytes,
            file_name=pdf_filename,
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )
        st.divider()
        st.subheader("Summary Breakdown")
        for item in findings:
            st.write(f"**{item['check']}**: `{item['status']}` — {item['extracted']}")
        st.stop()
    except Exception as e:
        st.error("Invalid or expired QR report link.")

st.title("AICTE EoA Smart Document Scanner & Resultant Report System")
st.caption("AI-Powered Document Scanner, Authenticity Verifier & Automated APH Compliance Decision-Support")

tab1, tab2 = st.tabs(["📂 Upload Dossier Scanner (PDF / Image / TXT)", "📸 Live Camera Document / QR Scanner"])

with tab1:
    uploaded_file = st.file_uploader("Drop College Dossier or Certificate to Scan", type=["pdf", "txt", "png", "jpg", "jpeg"])

with tab2:
    camera_photo = st.camera_input("Scan Physical Certificate or QR Code via Webcam")

active_file = uploaded_file if uploaded_file is not None else camera_photo

if active_file:
    file_path = f"temp_{active_file.name}"
    with open(file_path, "wb") as f:
        f.write(active_file.read())

    try:
        if file_path.endswith((".pdf", ".txt")):
            text = extract_text_from_file(file_path)
            findings, summary = run_scrutiny_checks(text)

            st.subheader("1. Executive Scanner Resultant Report")
            if summary["badge_color"] == "success":
                st.success(f"### ✅ FINAL VERDICT: {summary['verdict_status']}")
            elif summary["badge_color"] == "warning":
                st.warning(f"### ⚠️ FINAL VERDICT: {summary['verdict_status']}")
            else:
                st.error(f"### 🚨 FINAL VERDICT: {summary['verdict_status']}")

            st.markdown(f"**Scrutiny Action Plan:** {summary['action_plan']}")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Institution Category", summary["programme"])
            c2.metric("Compliance Score", f"{summary['compliance_score']}%")
            c3.metric("Verified Parameters", f"{summary['verified_count']} / {summary['total_checks']}")
            c4.metric("Deficiencies Flagged", summary["flagged_count"])

            st.progress(summary["compliance_score"] / 100)
            st.divider()

            col1, col2 = st.columns([1, 1.2])

            with col1:
                st.subheader("2. Scanned Document & Mobile QR Download")
                st.info(f"**Target Institution:** {summary['institution']}")
                st.text_area("Extracted Digital Text", text, height=230)

                pdf_filename = f"AICTE_Resultant_Report_{summary['institution'].replace(' ', '_')}.pdf"
                pdf_report = generate_scrutiny_pdf(findings, summary)

                st.download_button(
                    label="📥 Download Resultant Scrutiny Report (PDF)",
                    data=pdf_report,
                    file_name=pdf_filename,
                    mime="application/pdf",
                    use_container_width=True
                )

                st.markdown("#### 📱 Scan QR Code to Download Report on Mobile")
                qr_url = create_self_contained_qr_url(APP_PUBLIC_URL, findings, summary)
                qr_img_buf = generate_report_qr_code(qr_url)

                qcol1, qcol2 = st.columns([1, 1.4])
                with qcol1:
                    st.image(qr_img_buf, caption="Scan with Phone", width=180)
                with qcol2:
                    st.success("**100% Carrier-Safe Mobile Link Ready!**")
                    st.write("Scan with any phone camera to open the mobile verification portal and download the official PDF.")

            with col2:
                st.subheader("3. Structured Parameter Breakdown")
                df = pd.DataFrame([
                    {
                        "Parameter": f["check"],
                        "Extracted Value": f["extracted"],
                        "Status": f["status"],
                        "Applicable Clause": f["rule"]
                    }
                    for f in findings
                ])
                st.dataframe(df, use_container_width=True, hide_index=True)

                st.subheader("4. Detailed Evidence-Linked Clause Audit")
                for item in findings:
                    if "FLAGGED" in item["status"]:
                        st.error(f"**[{item['status']}] {item['check']}**")
                    else:
                        st.success(f"**[{item['status']}] {item['check']}**")
                    st.write(f"- **Extracted Value:** `{item['extracted']}` | **Clause:** {item['rule']}")
                    st.write(f"- **Scanner Observation:** {item['observation']}")

        else:
            st.subheader("1. Forensic Image & QR Scanner Resultant Report")
            ela_img, max_diff = detect_ela(file_path)
            qr_codes = scan_qr_and_barcodes(file_path)

            col1, col2 = st.columns(2)
            with col1:
                st.image(file_path, caption="Original Scanned Document / Infrastructure Photo", use_container_width=True)
            with col2:
                st.image(ela_img, caption="Forensic Error Level Analysis (ELA) Map", use_container_width=True)

            st.divider()
            r1, r2 = st.columns(2)
            with r1:
                st.markdown("#### 🔍 Digital Tampering Verdict")
                if max_diff > 35:
                    st.error(f"**[FLAGGED - ANOMALY DETECTED]** High compression variance (Score: {max_diff}). Localized pixel editing or pasted text suspected.")
                else:
                    st.success(f"**[VERIFIED - CONSISTENT]** Uniform compression profile (Score: {max_diff}). No obvious pixel overlay anomalies.")

            with r2:
                st.markdown("#### 📱 Embedded QR / Digital Verification")
                if qr_codes:
                    st.success(f"**[QR VERIFIED]** Extracted Issuing-Authority Payload: `{qr_codes[0]}`")
                else:
                    st.warning("**[NO QR DETECTED]** No machine-readable QR code found on this image. Route for manual authority check.")

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)