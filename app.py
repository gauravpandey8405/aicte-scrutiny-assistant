import streamlit as st
import pandas as pd
import os
from engine import (
    extract_text_from_file,
    run_scrutiny_checks,
    detect_ela,
    scan_qr_and_barcodes,
    generate_scrutiny_pdf,
    upload_pdf_for_qr_download,
    generate_report_qr_code
)

st.set_page_config(page_title="AICTE Document Scanner & Scrutiny System", layout="wide")

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
                st.subheader("2. Scanned Document & Instant QR Download")
                st.info(f"**Target Institution:** {summary['institution']}")
                st.text_area("Extracted Digital Text", text, height=250)

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
                with st.spinner("Generating direct mobile download QR code..."):
                    dl_url = upload_pdf_for_qr_download(pdf_report, filename=pdf_filename)
                    if dl_url:
                        qr_img_buf = generate_report_qr_code(dl_url)
                        qcol1, qcol2 = st.columns([1, 1.5])
                        with qcol1:
                            st.image(qr_img_buf, caption="Scan to Download PDF", width=180)
                        with qcol2:
                            st.success("**Mobile Download Ready!**")
                            st.write("Point any smartphone camera at this QR code to immediately download the PDF report.")
                            st.markdown(f"🔗 [Direct PDF Link]({dl_url})")
                    else:
                        fallback_summary = (
                            f"AICTE SCRUTINY AUDIT REPORT\n"
                            f"Institution: {summary['institution']}\n"
                            f"Category: {summary['programme']}\n"
                            f"Score: {summary['compliance_score']}%\n"
                            f"Verdict: {summary['verdict_status']}\n"
                            f"Verified: {summary['verified_count']}/{summary['total_checks']}\n"
                            f"Timestamp: {summary['timestamp']}"
                        )
                        qr_img_buf = generate_report_qr_code(fallback_summary)
                        st.image(qr_img_buf, caption="Scan for Instant Digital Verification Summary", width=180)

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