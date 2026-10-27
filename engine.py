import fitz
import re
import cv2
import numpy as np
from datetime import datetime
from dateutil import parser
from PIL import Image, ImageChops, ImageEnhance
import os

AICTE_APH_NORMS = {
    "Engineering": {
        "division_size": 60,
        "max_intake": 360,
        "sfr_limit": 20.0,
        "area_per_student_sqm": 12.5
    },
    "Management": {
        "division_size": 60,
        "max_intake": 300,
        "sfr_limit": 20.0,
        "area_per_student_sqm": 10.0
    },
    "Pharmacy": {
        "division_size": 60,
        "max_intake": 120,
        "sfr_limit": 15.0,
        "area_per_student_sqm": 14.0
    },
    "Computer Applications": {
        "division_size": 60,
        "max_intake": 180,
        "sfr_limit": 20.0,
        "area_per_student_sqm": 10.0
    }
}

ACADEMIC_SESSION_START = "2026-08-01"

def extract_text_from_file(file_path):
    if file_path.endswith(".pdf"):
        doc = fitz.open(file_path)
        return "\n".join([page.get_text() for page in doc])
    elif file_path.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def scan_qr_and_barcodes(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return []
    detector = cv2.QRCodeDetector()
    data, bbox, _ = detector.detectAndDecode(img)
    if data:
        return [data]
    return []

def detect_programme_category(text):
    text_lower = text.lower()
    if "pharmacy" in text_lower or "b.pharm" in text_lower:
        return "Pharmacy"
    elif "management" in text_lower or "mba" in text_lower or "pgdm" in text_lower:
        return "Management"
    elif "mca" in text_lower or "computer application" in text_lower:
        return "Computer Applications"
    return "Engineering"

def evaluate_overall_verdict(findings, detected_college, programme):
    total = len(findings)
    flagged = [f for f in findings if "FLAGGED" in f["status"]]
    verified = total - len(flagged)
    score = int(round((verified / max(total, 1)) * 100))

    if len(flagged) == 0:
        verdict_status = "RECOMMENDED FOR EOA APPROVAL"
        badge_color = "success"
        action_plan = "All statutory parameters match AICTE Approval Process Handbook norms. Forward dossier to Regional Committee for final EoA issuance."
    elif len(flagged) <= 2:
        verdict_status = "CONDITIONAL / RECTIFICATION REQUIRED"
        badge_color = "warning"
        action_plan = f"{len(flagged)} minor compliance gap(s) detected. Issue automated deficiency alert to {detected_college} for document re-upload within 15 days."
    else:
        verdict_status = "CRITICAL DEFICIENCY / EVC INSPECTION RECOMMENDED"
        badge_color = "error"
        action_plan = f"Multiple statutory breaches ({len(flagged)} flags) identified across core norms. Route application to Expert Visit Committee (EVC) for physical verification."

    return {
        "institution": detected_college,
        "programme": programme,
        "total_checks": total,
        "verified_count": verified,
        "flagged_count": len(flagged),
        "compliance_score": score,
        "verdict_status": verdict_status,
        "badge_color": badge_color,
        "action_plan": action_plan,
        "timestamp": datetime.now().strftime("%d-%b-%Y %H:%M:%S")
    }

def run_scrutiny_checks(extracted_text):
    audit_findings = []
    programme = detect_programme_category(extracted_text)
    norms = AICTE_APH_NORMS[programme]

    name_match = re.search(r'(?:Institution Name|College Name|Institute)[:\s]+([^\n\r]+)', extracted_text, re.IGNORECASE)
    pid_match = re.search(r'(?:Permanent Institute ID|AICTE ID|PID)[:\s]*(1-\d{7,12})', extracted_text, re.IGNORECASE)
    extracted_name = name_match.group(1).strip() if name_match else "Unspecified Applicant Institution"

    if name_match and len(extracted_name) > 4:
        pid_str = f" (PID: {pid_match.group(1)})" if pid_match else ""
        audit_findings.append({
            "check": f"Institution Registration & Category [{programme}]",
            "status": "VERIFIED",
            "extracted": f"{extracted_name}{pid_str}",
            "rule": "AICTE APH Chapter I (Institutional Eligibility)",
            "observation": f"Valid entity parsed under {programme} regulatory norms."
        })
    else:
        audit_findings.append({
            "check": "Institution Identity Header",
            "status": "FLAGGED (MISSING)",
            "extracted": "Not Found",
            "rule": "AICTE APH Chapter I (Mandatory Disclosures)",
            "observation": "Document is missing a valid 'Institution Name:' field."
        })

    intake_match = re.search(r'(?:Sanctioned Student Intake|Approved Intake|Intake)[:\s]+(\d+)', extracted_text, re.IGNORECASE)
    intake_val = int(intake_match.group(1)) if intake_match else None

    if intake_val is not None:
        if intake_val > 0 and intake_val % 30 == 0 and intake_val <= norms["max_intake"]:
            audit_findings.append({
                "check": "Sanctioned Intake Division Norms",
                "status": "VERIFIED",
                "extracted": f"{intake_val} Seats",
                "rule": f"AICTE APH Appendix 1 ({programme} Division Size)",
                "observation": f"Complies with standard division multiples of 30/60 (Max allowed: {norms['max_intake']})."
            })
        else:
            audit_findings.append({
                "check": "Sanctioned Intake Division Norms",
                "status": "FLAGGED (NON-STANDARD INTAKE)",
                "extracted": f"{intake_val} Seats",
                "rule": f"AICTE APH Appendix 1 ({programme} Division Size)",
                "observation": f"Intake {intake_val} violates standard division multiples of 30/60 or exceeds max cap ({norms['max_intake']})."
            })
    else:
        audit_findings.append({
            "check": "Sanctioned Intake Declaration",
            "status": "FLAGGED (MISSING)",
            "extracted": "Not Found",
            "rule": "AICTE APH Appendix 1",
            "observation": "Mandatory student intake figure not detected in document."
        })

    area_match = re.search(r'(?:Carpet Area|Built-up Area|Total Area)[:\s]+(\d+)', extracted_text, re.IGNORECASE)
    if area_match:
        actual_area = int(area_match.group(1))
        baseline_students = intake_val if intake_val else 180
        required_area = int(baseline_students * norms["area_per_student_sqm"])

        if actual_area >= required_area:
            audit_findings.append({
                "check": "Instructional & Admin Carpet Area",
                "status": "VERIFIED",
                "extracted": f"{actual_area} Sq.m",
                "rule": "AICTE APH Appendix 4 (Land & Built-up Area Norms)",
                "observation": f"Meets area requirement for {baseline_students} intake (Min: {required_area} Sq.m)."
            })
        else:
            shortfall = required_area - actual_area
            audit_findings.append({
                "check": "Instructional & Admin Carpet Area",
                "status": "FLAGGED (DEFICIENCY)",
                "extracted": f"{actual_area} Sq.m",
                "rule": "AICTE APH Appendix 4 (Land & Built-up Area Norms)",
                "observation": f"Shortfall of {shortfall} Sq.m below required {required_area} Sq.m for {baseline_students} seats."
            })

    faculty_match = re.search(r'(?:Faculty Count|Total Faculty|Faculty)[:\s]+(\d+)', extracted_text, re.IGNORECASE)
    if faculty_match and intake_val:
        faculty_count = int(faculty_match.group(1))
        min_required_faculty = int(intake_val / norms["sfr_limit"])
        actual_sfr = round(intake_val / max(faculty_count, 1), 1)

        if actual_sfr <= norms["sfr_limit"]:
            audit_findings.append({
                "check": "Faculty Cadre & SFR Compliance",
                "status": "VERIFIED",
                "extracted": f"1:{actual_sfr} ({faculty_count} Faculty)",
                "rule": "AICTE APH Appendix 7 (Faculty Norms)",
                "observation": f"Meets prescribed 1:{int(norms['sfr_limit'])} ratio (Min required: {min_required_faculty} faculty)."
            })
        else:
            audit_findings.append({
                "check": "Faculty Cadre & SFR Compliance",
                "status": "FLAGGED (FACULTY SHORTAGE)",
                "extracted": f"1:{actual_sfr} ({faculty_count} Faculty)",
                "rule": "AICTE APH Appendix 7 (Faculty Norms)",
                "observation": f"Violates 1:{int(norms['sfr_limit'])} norm. Needs at least {min_required_faculty} faculty for {intake_val} seats."
            })

    date_matches = re.findall(r'\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b', extracted_text)
    if date_matches:
        expiry_raw = date_matches[-1]
        try:
            parsed_dt = parser.parse(expiry_raw, fuzzy=True, dayfirst=True)
            cutoff_dt = datetime.strptime(ACADEMIC_SESSION_START, "%Y-%m-%d")
            if parsed_dt >= cutoff_dt:
                audit_findings.append({
                    "check": "Fire & Building Safety NOC Validity",
                    "status": "VERIFIED",
                    "extracted": expiry_raw,
                    "rule": "AICTE APH Chapter II, Clause 2.4",
                    "observation": f"Active validity confirmed beyond session commencement ({ACADEMIC_SESSION_START})."
                })
            else:
                audit_findings.append({
                    "check": "Fire & Building Safety NOC Validity",
                    "status": "FLAGGED (EXPIRED)",
                    "extracted": expiry_raw,
                    "rule": "AICTE APH Chapter II, Clause 2.4",
                    "observation": f"Certificate expired on {expiry_raw}, prior to mandatory academic session cutoff."
                })
        except Exception:
            pass
    else:
        audit_findings.append({
            "check": "Fire & Building Safety NOC Validity",
            "status": "FLAGGED (MISSING DATE)",
            "extracted": "No Valid Date",
            "rule": "AICTE APH Chapter II, Clause 2.4",
            "observation": "Could not locate mandatory validity/expiry date on the certificate."
        })

    nba_match = re.search(r'(?:NBA Accreditation|Accreditation)[:\s]+(Valid|Active|Approved|Expired|Pending|None)', extracted_text, re.IGNORECASE)
    if nba_match:
        status_word = nba_match.group(1).title()
        if status_word in ["Valid", "Active", "Approved"]:
            audit_findings.append({
                "check": "Quality Accreditation Status",
                "status": "VERIFIED",
                "extracted": status_word,
                "rule": "AICTE Quality Mandate",
                "observation": "Institution holds valid statutory accreditation."
            })
        else:
            audit_findings.append({
                "check": "Quality Accreditation Status",
                "status": "FLAGGED (DEFICIENT)",
                "extracted": status_word,
                "rule": "AICTE Quality Mandate",
                "observation": f"Accreditation status reported as '{status_word}'. Flagged for committee review."
            })

    summary_report = evaluate_overall_verdict(audit_findings, extracted_name, programme)
    return audit_findings, summary_report

def detect_ela(image_path, quality=90):
    original = Image.open(image_path).convert('RGB')
    resaved_path = "temp_ela_buffer.jpg"
    original.save(resaved_path, 'JPEG', quality=quality)
    resaved = Image.open(resaved_path)

    diff = ImageChops.difference(original, resaved)
    extrema = diff.getextrema()
    max_diff = max([ex[1] for ex in extrema])
    scale = 255.0 / (max_diff if max_diff != 0 else 1)

    result = ImageEnhance.Brightness(diff).enhance(scale)
    if os.path.exists(resaved_path):
        os.remove(resaved_path)
    return result, max_diff

def generate_scrutiny_pdf(findings, summary):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    page.insert_text((50, 45), "ALL INDIA COUNCIL FOR TECHNICAL EDUCATION", fontsize=14, fontname="helv", color=(0.1, 0.2, 0.5))
    page.insert_text((50, 62), "Resultant Document Scanner & Regulatory Scrutiny Report", fontsize=10, fontname="helv", color=(0.3, 0.3, 0.3))
    page.draw_line(fitz.Point(50, 72), fitz.Point(545, 72), color=(0.1, 0.2, 0.5), width=1.5)

    page.insert_text((50, 95), f"Institution: {summary['institution']}", fontsize=11, fontname="helv")
    page.insert_text((50, 112), f"Programme Category: {summary['programme']}  |  Compliance Score: {summary['compliance_score']}%", fontsize=10, fontname="helv")
    page.insert_text((50, 129), f"Resultant Scanner Verdict: {summary['verdict_status']}", fontsize=11, fontname="helv", color=(0.8, 0, 0) if summary['flagged_count'] > 0 else (0, 0.5, 0))
    page.insert_text((50, 145), f"Recommended Action: {summary['action_plan']}", fontsize=8.5, fontname="helv", color=(0.25, 0.25, 0.25))
    page.draw_line(fitz.Point(50, 156), fitz.Point(545, 156), color=(0.8, 0.8, 0.8), width=1)

    y = 178
    for idx, item in enumerate(findings, 1):
        status_color = (0.8, 0, 0) if "FLAGGED" in item["status"] else (0, 0.5, 0)
        page.insert_text((50, y), f"{idx}. {item['check']}  [{item['status']}]", fontsize=10.5, fontname="helv", color=status_color)
        page.insert_text((65, y + 14), f"Extracted Value: {item['extracted']}", fontsize=9, fontname="helv", color=(0.2, 0.2, 0.2))
        page.insert_text((65, y + 27), f"Statutory Rule: {item['rule']}", fontsize=9, fontname="helv", color=(0.2, 0.2, 0.2))
        page.insert_text((65, y + 40), f"Scanner Observation: {item['observation']}", fontsize=9, fontname="helv", color=(0.3, 0.3, 0.3))
        y += 60

        if y > 760:
            page = doc.new_page(width=595, height=842)
            y = 50

    page.draw_line(fitz.Point(50, 785), fitz.Point(545, 785), color=(0.7, 0.7, 0.7), width=1)
    page.insert_text((50, 802), f"Generated: {summary['timestamp']} | Decision-Support Advisory Output Only.", fontsize=8, fontname="helv", color=(0.5, 0.5, 0.5))

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes