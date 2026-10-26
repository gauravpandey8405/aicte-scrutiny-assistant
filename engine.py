import fitz  # PyMuPDF
import re
from datetime import datetime
from dateutil import parser
from rapidfuzz import fuzz, process
from PIL import Image, ImageChops, ImageEnhance
import os

# Multi-Institute AICTE Central Database Mock
AICTE_INSTITUTIONS_DIRECTORY = {
    "Apex Institute of Engineering & Technology": {
        "sanctioned_intake": 180,
        "academic_year_start": "2026-08-01",
        "min_carpet_area_sqm": 4500,
        "target_sfr": 20
    },
    "Prestige Institute of Engineering Management and Research": {
        "sanctioned_intake": 300,
        "academic_year_start": "2026-08-01",
        "min_carpet_area_sqm": 6000,
        "target_sfr": 20
    },
    "Indian Institute of Technology Indore": {
        "sanctioned_intake": 480,
        "academic_year_start": "2026-08-01",
        "min_carpet_area_sqm": 12000,
        "target_sfr": 15
    }
}

# Default statutory baseline applied if institution is newly applying
DEFAULT_REGULATORY_NORMS = {
    "sanctioned_intake": 120,
    "academic_year_start": "2026-08-01",
    "min_carpet_area_sqm": 3500,
    "target_sfr": 20
}

def extract_text_from_file(file_path):
    if file_path.endswith(".pdf"):
        doc = fitz.open(file_path)
        return "\n".join([page.get_text() for page in doc])
    elif file_path.endswith(".txt"):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def run_scrutiny_checks(extracted_text):
    audit_findings = []

    # 1. Dynamic Institution Name Resolution
    name_match = re.search(r'Institution Name[:\s]+(.+)', extracted_text, re.IGNORECASE)
    extracted_name = name_match.group(1).strip() if name_match else ""

    known_names = list(AICTE_INSTITUTIONS_DIRECTORY.keys())
    matched_profile = DEFAULT_REGULATORY_NORMS
    matched_institute_name = extracted_name

    if extracted_name:
        best_match = process.extractOne(extracted_name, known_names, scorer=fuzz.ratio)
        if best_match and best_match[1] >= 75:
            matched_institute_name = best_match[0]
            matched_profile = AICTE_INSTITUTIONS_DIRECTORY[matched_institute_name]
            audit_findings.append({
                "check": "Institution Identity Match",
                "status": "VERIFIED",
                "extracted": extracted_name,
                "rule": "AICTE Master Registry",
                "observation": f"Matched registered record '{matched_institute_name}' ({best_match[1]}% match)."
            })
        else:
            # If not in the mock database, treat as a newly registered applicant and apply default handbook norms
            audit_findings.append({
                "check": "Institution Identity Match",
                "status": "VERIFIED (NEW APPLICANT)",
                "extracted": extracted_name,
                "rule": "AICTE Central Portal",
                "observation": "Recognized new applicant identity. Baseline APH regulatory standards applied."
            })
    else:
        audit_findings.append({
            "check": "Institution Identity Match",
            "status": "FLAGGED (MISSING)",
            "extracted": "Not Found",
            "rule": "AICTE Mandatory Fields",
            "observation": "Institution Name header not detected in the uploaded document."
        })

    # 2. Expiry Date Check
    date_matches = re.findall(r'\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b', extracted_text)
    expiry_flagged = False
    for raw_date in date_matches:
        try:
            parsed_dt = parser.parse(raw_date, fuzzy=True, dayfirst=True)
            cutoff_dt = datetime.strptime(matched_profile["academic_year_start"], "%Y-%m-%d")
            if parsed_dt < cutoff_dt:
                audit_findings.append({
                    "check": "Safety NOC Validity",
                    "status": "FLAGGED (EXPIRED)",
                    "extracted": raw_date,
                    "rule": "AICTE APH Chapter II, Clause 2.4",
                    "observation": f"Validity expired on {raw_date}, prior to academic session start ({matched_profile['academic_year_start']})."
                })
                expiry_flagged = True
                break
        except Exception:
            continue
            
    if not expiry_flagged and date_matches:
        audit_findings.append({
            "check": "Safety NOC Validity",
            "status": "VERIFIED",
            "extracted": date_matches[-1],
            "rule": "AICTE APH Chapter II, Clause 2.4",
            "observation": "Document validity extends beyond the mandatory academic cutoff."
        })

    # 3. Sanctioned Intake Capacity Check
    intake_match = re.search(r'Intake[:\s]+(\d+)', extracted_text, re.IGNORECASE)
    if intake_match:
        val = int(intake_match.group(1))
        expected = matched_profile["sanctioned_intake"]
        if val <= expected:
            audit_findings.append({
                "check": "Sanctioned Seat Capacity",
                "status": "VERIFIED",
                "extracted": f"{val} seats",
                "rule": "Approved Seat Schedule",
                "observation": f"Within permitted sanctioned quota (Max: {expected})."
            })
        else:
            audit_findings.append({
                "check": "Sanctioned Seat Capacity",
                "status": "FLAGGED (DISCREPANCY)",
                "extracted": f"{val} seats",
                "rule": "Approved Seat Schedule",
                "observation": f"Discrepancy: File claims {val} seats; permitted quota is {expected}."
            })

    # 4. Built-Up Area Check (if present in doc)
    area_match = re.search(r'Carpet Area[:\s]+(\d+)', extracted_text, re.IGNORECASE)
    if area_match:
        extracted_area = int(area_match.group(1))
        req_area = matched_profile["min_carpet_area_sqm"]
        if extracted_area >= req_area:
            audit_findings.append({
                "check": "Infrastructure Built-Up Area",
                "status": "VERIFIED",
                "extracted": f"{extracted_area} Sq.m",
                "rule": "AICTE APH Appendix 4",
                "observation": f"Meets prescribed norms (Requirement: {req_area} Sq.m)."
            })
        else:
            audit_findings.append({
                "check": "Infrastructure Built-Up Area",
                "status": "FLAGGED (DEFICIENT)",
                "extracted": f"{extracted_area} Sq.m",
                "rule": "AICTE APH Appendix 4",
                "observation": f"Deficient by {req_area - extracted_area} Sq.m below {req_area} Sq.m."
            })

    # 5. Student to Faculty Ratio (SFR) Check (if present in doc)
    faculty_match = re.search(r'Faculty Count[:\s]+(\d+)', extracted_text, re.IGNORECASE)
    if faculty_match and intake_match:
        faculty_count = int(faculty_match.group(1))
        total_students = int(intake_match.group(1))
        ratio = round(total_students / (faculty_count if faculty_count > 0 else 1), 1)
        if ratio <= matched_profile["target_sfr"]:
            audit_findings.append({
                "check": "Student-to-Faculty Ratio (SFR)",
                "status": "VERIFIED",
                "extracted": f"{ratio}:1 ({faculty_count} faculty)",
                "rule": "AICTE APH Appendix 7",
                "observation": f"Complies with mandatory SFR threshold of {matched_profile['target_sfr']}:1."
            })
        else:
            audit_findings.append({
                "check": "Student-to-Faculty Ratio (SFR)",
                "status": "FLAGGED (HIGH SFR)",
                "extracted": f"{ratio}:1 ({faculty_count} faculty)",
                "rule": "AICTE APH Appendix 7",
                "observation": f"Exceeds prescribed faculty workload norm of {matched_profile['target_sfr']}:1."
            })

    return audit_findings