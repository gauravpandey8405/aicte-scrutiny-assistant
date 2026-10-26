import fitz  # PyMuPDF
import re
from datetime import datetime
from dateutil import parser
from rapidfuzz import fuzz
from PIL import Image, ImageChops, ImageEnhance
import os

# Configurable AICTE Master Standards and Institution Record
AICTE_MASTER_DB = {
    "institution_name": "Apex Institute of Engineering & Technology",
    "sanctioned_intake": 180,
    "academic_year_start": "2026-08-01",
    "min_carpet_area_sqm": 4500,     # Prescribed minimum instructional + administrative area
    "target_sfr": 20,                # Prescribed Student-to-Faculty Ratio (Max 20:1)
    "nba_mandate": True              # Requires active NBA accreditation for Tier-1 approvals
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

    # 1. Institution Name Check
    name_match = re.search(r'Institution Name[:\s]+(.+)', extracted_text, re.IGNORECASE)
    extracted_name = name_match.group(1).strip() if name_match else "Unknown"
    sim_score = fuzz.ratio(extracted_name.lower(), AICTE_MASTER_DB["institution_name"].lower())
    
    if sim_score >= 85:
        audit_findings.append({
            "check": "Institution Identity Match",
            "status": "VERIFIED",
            "extracted": extracted_name,
            "rule": "AICTE Master Registry",
            "observation": f"Matched official records ({sim_score}% confidence)."
        })
    else:
        audit_findings.append({
            "check": "Institution Identity Match",
            "status": "FLAGGED (MISMATCH)",
            "extracted": extracted_name,
            "rule": "AICTE Master Registry",
            "observation": f"Name mismatch. AICTE record expects: '{AICTE_MASTER_DB['institution_name']}'."
        })

    # 2. Safety NOC Expiry Date Check
    date_matches = re.findall(r'\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b', extracted_text)
    expiry_flagged = False
    for raw_date in date_matches:
        try:
            parsed_dt = parser.parse(raw_date, fuzzy=True, dayfirst=True)
            cutoff_dt = datetime.strptime(AICTE_MASTER_DB["academic_year_start"], "%Y-%m-%d")
            if parsed_dt < cutoff_dt:
                audit_findings.append({
                    "check": "Safety NOC Validity",
                    "status": "FLAGGED (EXPIRED)",
                    "extracted": raw_date,
                    "rule": "AICTE APH Chapter II, Clause 2.4",
                    "observation": f"Validity expired on {raw_date}, prior to academic session start."
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
            "observation": "Document validity extends beyond the required regulatory period."
        })

    # 3. Sanctioned Intake Capacity Check
    intake_match = re.search(r'Intake[:\s]+(\d+)', extracted_text, re.IGNORECASE)
    if intake_match:
        val = int(intake_match.group(1))
        expected = AICTE_MASTER_DB["sanctioned_intake"]
        if val == expected:
            audit_findings.append({
                "check": "Sanctioned Seat Capacity",
                "status": "VERIFIED",
                "extracted": str(val),
                "rule": "Approved Seat Schedule",
                "observation": "Declared seats match AICTE sanctioned quota."
            })
        else:
            audit_findings.append({
                "check": "Sanctioned Seat Capacity",
                "status": "FLAGGED (DISCREPANCY)",
                "extracted": str(val),
                "rule": "Approved Seat Schedule",
                "observation": f"Discrepancy: File claims {val} seats; permitted quota is {expected}."
            })

    # 4. Built-Up Carpet Area Verification
    area_match = re.search(r'Carpet Area[:\s]+(\d+)', extracted_text, re.IGNORECASE)
    if area_match:
        extracted_area = int(area_match.group(1))
        req_area = AICTE_MASTER_DB["min_carpet_area_sqm"]
        if extracted_area >= req_area:
            audit_findings.append({
                "check": "Infrastructure Built-Up Area",
                "status": "VERIFIED",
                "extracted": f"{extracted_area} Sq.m",
                "rule": "AICTE APH Appendix 4 (Norms for Land & Built-up Area)",
                "observation": f"Meets minimum threshold of {req_area} Sq.m."
            })
        else:
            audit_findings.append({
                "check": "Infrastructure Built-Up Area",
                "status": "FLAGGED (DEFICIENT)",
                "extracted": f"{extracted_area} Sq.m",
                "rule": "AICTE APH Appendix 4 (Norms for Land & Built-up Area)",
                "observation": f"Deficient by {req_area - extracted_area} Sq.m below mandatory {req_area} Sq.m."
            })

    # 5. Student to Faculty Ratio (SFR) Check
    faculty_match = re.search(r'Faculty Count[:\s]+(\d+)', extracted_text, re.IGNORECASE)
    if faculty_match and intake_match:
        faculty_count = int(faculty_match.group(1))
        total_students = int(intake_match.group(1))
        ratio = round(total_students / (faculty_count if faculty_count > 0 else 1), 1)
        if ratio <= AICTE_MASTER_DB["target_sfr"]:
            audit_findings.append({
                "check": "Student-to-Faculty Ratio (SFR)",
                "status": "VERIFIED",
                "extracted": f"{ratio}:1 ({faculty_count} faculty)",
                "rule": "AICTE APH Appendix 7 (Faculty Cadre Norms)",
                "observation": f"Complies with mandatory SFR upper bound of {AICTE_MASTER_DB['target_sfr']}:1."
            })
        else:
            audit_findings.append({
                "check": "Student-to-Faculty Ratio (SFR)",
                "status": "FLAGGED (HIGH SFR)",
                "extracted": f"{ratio}:1 ({faculty_count} faculty)",
                "rule": "AICTE APH Appendix 7 (Faculty Cadre Norms)",
                "observation": f"Adverse SFR detected. Exceeds prescribed norm of {AICTE_MASTER_DB['target_sfr']}:1."
            })

    # 6. Accreditation (NBA / NAAC) Check
    nba_match = re.search(r'NBA Accreditation[:\s]+(Valid|Active|Expired|None)', extracted_text, re.IGNORECASE)
    if nba_match:
        nba_status = nba_match.group(1).title()
        if nba_status in ["Valid", "Active"]:
            audit_findings.append({
                "check": "Programme Accreditation Status",
                "status": "VERIFIED",
                "extracted": nba_status,
                "rule": "AICTE Regulation on Quality Mandate",
                "observation": "Active NBA accreditation confirmed."
            })
        else:
            audit_findings.append({
                "check": "Programme Accreditation Status",
                "status": "FLAGGED (INACTIVE)",
                "extracted": nba_status,
                "rule": "AICTE Regulation on Quality Mandate",
                "observation": "Accreditation expired or missing for eligible programmes."
            })

    return audit_findings

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
    return result

def generate_scrutiny_pdf(findings, institution_name="Apex Institute of Engineering & Technology"):
    """Generates an official AICTE Scrutiny Deficiency & Audit Report PDF"""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)

    # Title & Official Header
    page.insert_text((50, 50), "ALL INDIA COUNCIL FOR TECHNICAL EDUCATION", fontsize=14, fontname="helv", color=(0.1, 0.2, 0.5))
    page.insert_text((50, 68), "Preliminary Regulatory Scrutiny Audit Report (Decision Support)", fontsize=10, fontname="helv", color=(0.3, 0.3, 0.3))
    page.insert_line((50, 80), (545, 80), color=(0.1, 0.2, 0.5), width=1.5)

    page.insert_text((50, 105), f"Target Institution: {institution_name}", fontsize=11, fontname="helv")
    page.insert_text((50, 122), f"Generated Date: {datetime.now().strftime('%d-%b-%Y %H:%M:%S')}", fontsize=9, fontname="helv", color=(0.4, 0.4, 0.4))

    y = 150
    for idx, item in enumerate(findings, 1):
        status_color = (0.8, 0, 0) if "FLAGGED" in item["status"] else (0, 0.5, 0)
        page.insert_text((50, y), f"{idx}. {item['check']}  [{item['status']}]", fontsize=11, fontname="helv", color=status_color)
        page.insert_text((65, y + 15), f"Extracted Value: {item['extracted']}", fontsize=9, fontname="helv", color=(0.2, 0.2, 0.2))
        page.insert_text((65, y + 28), f"Statutory Rule: {item['rule']}", fontsize=9, fontname="helv", color=(0.2, 0.2, 0.2))
        page.insert_text((65, y + 41), f"Scrutiny Finding: {item['observation']}", fontsize=9, fontname="helv", color=(0.3, 0.3, 0.3))
        y += 65

        if y > 760:
            page = doc.new_page(width=595, height=842)
            y = 50

    page.insert_line((50, 780), (545, 780), color=(0.7, 0.7, 0.7), width=1)
    page.insert_text((50, 800), "Advisory Notice: Generated by AICTE Decision-Support System. Final action remains with Scrutiny Committee.", fontsize=8, fontname="helv", color=(0.5, 0.5, 0.5))

    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes