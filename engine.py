import fitz  # PyMuPDF
import re
from datetime import datetime
from dateutil import parser
from rapidfuzz import fuzz
from PIL import Image, ImageChops, ImageEnhance

# Mock AICTE Central Database Record
AICTE_MASTER_DB = {
    "institution_name": "Apex Institute of Engineering & Technology",
    "sanctioned_intake": 180,
    "academic_year_start": "2026-08-01"
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

    # 2. Expiry Date Check
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
    
    return ImageEnhance.Brightness(diff).enhance(scale)