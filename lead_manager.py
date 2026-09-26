"""
Poddopaataa Lead Capture & CRM Engine
Extracts, validates, and stores leads from Facebook Messenger conversations.
Saves data into leads.json and leads.csv (Excel compatible with UTF-8 BOM).
"""

import os
import re
import csv
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple

logger = logging.getLogger("poddopaataa_leads")

BASE_DIR = Path(__file__).resolve().parent
LEADS_JSON = BASE_DIR / "leads.json"
LEADS_CSV = BASE_DIR / "leads.csv"
PAGE_ID = os.getenv("PODDOPAATAA_PAGE_ID", "377657402757335")

# Bangladesh Standard Time (UTC+6)
BST = timezone(timedelta(hours=6))

BENGALI_DIGITS = {
    '০': '0', '১': '1', '২': '2', '৩': '3', '৪': '4',
    '৫': '5', '৬': '6', '৭': '7', '৮': '8', '৯': '9'
}

EN_TO_BN = str.maketrans('0123456789', '০১২৩৪৫৬৭৮৯')


def normalize_digits(text: str) -> str:
    """Converts Bengali numerals to standard English numerals."""
    if not text:
        return ""
    res = []
    for ch in text:
        res.append(BENGALI_DIGITS.get(ch, ch))
    return "".join(res)


def extract_phone_number(text: str) -> Optional[str]:
    """
    Extracts Bangladeshi 11-digit mobile number from text.
    Handles +8801..., 8801..., 01..., with dashes, spaces, brackets, and Bengali digits.
    Supported prefixes: 013, 014, 015, 016, 017, 018, 019.
    """
    if not text:
        return None
    
    clean_text = normalize_digits(text)
    
    # 1. Direct standard match
    match = re.search(r'(?:\+?880|880|0)(1[3-9]\d{8})\b', clean_text)
    if match:
        return f"0{match.group(1)}"
    
    # 2. Stripping hyphens, spaces, dots, parens from phone-like candidate strings
    candidates = re.findall(r'(?:(?:\+?880|880|0)[\d\s\-\.()]{9,16}\d)', clean_text)
    for cand in candidates:
        digits_only = re.sub(r'\D', '', cand)
        if digits_only.startswith('880'):
            digits_only = digits_only[2:]
        if digits_only.startswith('0') and len(digits_only) == 11 and digits_only[1] in '13456789':
            return digits_only
        elif len(digits_only) == 10 and digits_only[0] in '3456789':
            return f"01{digits_only}"

    return None


def extract_duration_and_budget(text: str) -> Tuple[str, int]:
    """
    Infers duration and estimated budget from user message.
    Base price: 1 min = 1500 BDT, subsequent mins = 1000 BDT.
    Defaults to 1 min (1500 BDT) as minimum package.
    """
    clean_text = normalize_digits(text or "")
    
    # Check for minutes
    min_match = re.search(r'(\d+)\s*(?:মিনিট|min)', clean_text, re.IGNORECASE)
    if min_match:
        mins = int(min_match.group(1))
        mins = max(1, mins)
        cost = 1500 if mins == 1 else 1500 + ((mins - 1) * 1000)
        return f"{mins} মিনিট", cost
    
    # Check for word count
    word_match = re.search(r'(\d+)\s*(?:শব্দ|word)', clean_text, re.IGNORECASE)
    if word_match:
        words = int(word_match.group(1))
        mins = max(1, round(words / 160))
        cost = 1500 if mins == 1 else 1500 + ((mins - 1) * 1000)
        return f"{mins} মিনিট ({words} শব্দ)", cost
    
    # Default minimum
    return "১ মিনিট (নূন্যতম)", 1500


def get_all_leads() -> List[Dict]:
    """Loads all leads from leads.json."""
    if not LEADS_JSON.exists():
        return []
    try:
        with open(LEADS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading {LEADS_JSON}: {e}")
        return []


def sync_leads_to_csv(leads: List[Dict]):
    """Writes leads to leads.csv with UTF-8 BOM for perfect Excel compatibility."""
    fieldnames = [
        "lead_id", "timestamp_bst", "name", "phone", "duration_est", 
        "estimated_bdt", "status", "psid", "whatsapp_link", "messenger_link", "last_message", "notes"
    ]
    try:
        with open(LEADS_CSV, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for lead in leads:
                writer.writerow({
                    "lead_id": lead.get("id", ""),
                    "timestamp_bst": lead.get("timestamp_bst", ""),
                    "name": lead.get("name", ""),
                    "phone": lead.get("phone", ""),
                    "duration_est": lead.get("duration_est", ""),
                    "estimated_bdt": lead.get("estimated_bdt", 0),
                    "status": lead.get("status", "New"),
                    "psid": lead.get("psid", ""),
                    "whatsapp_link": lead.get("whatsapp_url", ""),
                    "messenger_link": lead.get("messenger_url", ""),
                    "last_message": lead.get("last_message", "").replace("\n", " "),
                    "notes": lead.get("notes", "")
                })
    except Exception as e:
        logger.error(f"Error writing to CSV: {e}")


def save_or_update_lead(
    psid: str,
    name: str,
    phone: Optional[str] = None,
    message: str = "",
    duration_est: Optional[str] = None,
    estimated_bdt: Optional[int] = None,
    notes: str = ""
) -> Dict:
    """
    Saves a new lead or updates existing lead if PSID or phone matches.
    Ensures persistent storage in both JSON and CSV.
    """
    leads = get_all_leads()
    now_bst = datetime.now(BST)
    timestamp_str = now_bst.strftime("%Y-%m-%d %I:%M %p (BST)")
    iso_time = now_bst.isoformat()
    
    # If phone was not explicitly passed, attempt extraction from message
    if not phone:
        phone = extract_phone_number(message)
    
    # Infer duration and budget if not provided
    if not duration_est or not estimated_bdt:
        d_est, b_est = extract_duration_and_budget(message)
        duration_est = duration_est or d_est
        estimated_bdt = estimated_bdt or b_est

    # Look for existing lead by PSID or phone
    existing_lead = None
    for item in leads:
        if (phone and item.get("phone") == phone) or (psid and item.get("psid") == psid):
            existing_lead = item
            break
            
    messenger_url = f"https://business.facebook.com/latest/inbox/messenger?asset_id={PAGE_ID}"
    whatsapp_url = f"https://wa.me/88{phone}" if phone else "https://wa.me/8801409350858"

    if existing_lead:
        # Update existing record
        if name and name != "কবি" and existing_lead.get("name") in ["", "কবি", "Facebook User"]:
            existing_lead["name"] = name
        if phone:
            existing_lead["phone"] = phone
            existing_lead["whatsapp_url"] = f"https://wa.me/88{phone}"
            if existing_lead.get("status") in ["Inquiry", "Pending", ""]:
                existing_lead["status"] = "New"
        if message:
            existing_lead["last_message"] = message
        existing_lead["updated_at"] = iso_time
        if duration_est != "১ মিনিট (নূন্যতম)":
            existing_lead["duration_est"] = duration_est
            existing_lead["estimated_bdt"] = estimated_bdt
        if notes:
            existing_lead["notes"] = f"{existing_lead.get('notes', '')} | {notes}".strip(" |")
        lead_data = existing_lead
        logger.info(f"Updated existing lead ID: {existing_lead.get('id')} with phone: {phone}")
    else:
        # Create brand new lead
        lead_id = f"PL-{now_bst.strftime('%Y%m%d%H%M%S')}"
        lead_data = {
            "id": lead_id,
            "created_at": iso_time,
            "timestamp_bst": timestamp_str,
            "name": name if name else "কবি",
            "phone": phone or "পেন্ডিং",
            "psid": psid,
            "duration_est": duration_est,
            "estimated_bdt": estimated_bdt,
            "status": "New" if phone else "Inquiry",
            "source": "Facebook Messenger",
            "last_message": message,
            "notes": notes,
            "whatsapp_url": whatsapp_url,
            "messenger_url": messenger_url
        }
        leads.insert(0, lead_data)  # newest first
        logger.info(f"Created new lead ID: {lead_id} ({name} - {phone})")

    # Save to JSON
    try:
        with open(LEADS_JSON, "w", encoding="utf-8") as f:
            json.dump(leads, f, ensure_ascii=False, indent=2)
        # Sync to CSV
        sync_leads_to_csv(leads)
    except Exception as e:
        logger.error(f"Failed to persist leads: {e}")

    return lead_data


def update_lead_status(lead_id: str, new_status: str, notes: str = "") -> bool:
    """Updates status of a lead ('New', 'Contacted', 'Confirmed', 'Completed', 'Cancelled')."""
    leads = get_all_leads()
    updated = False
    for lead in leads:
        if lead.get("id") == lead_id:
            lead["status"] = new_status
            if notes:
                lead["notes"] = notes
            lead["updated_at"] = datetime.now(BST).isoformat()
            updated = True
            break
            
    if updated:
        try:
            with open(LEADS_JSON, "w", encoding="utf-8") as f:
                json.dump(leads, f, ensure_ascii=False, indent=2)
            sync_leads_to_csv(leads)
            return True
        except Exception as e:
            logger.error(f"Error updating lead status: {e}")
    return False


def get_lead_stats() -> Dict:
    """Returns analytics data for dashboard cards."""
    leads = get_all_leads()
    now_bst = datetime.now(BST)
    today_str = now_bst.strftime("%Y-%m-%d")
    
    total_leads = len(leads)
    leads_with_phone = sum(1 for l in leads if l.get("phone") and l.get("phone") != "পেন্ডিং")
    today_leads = sum(1 for l in leads if l.get("created_at", "").startswith(today_str))
    
    total_potential_bdt = sum(l.get("estimated_bdt", 1500) for l in leads)
    confirmed_bdt = sum(l.get("estimated_bdt", 1500) for l in leads if l.get("status") in ["Confirmed", "In Production", "Completed"])
    
    status_counts = {}
    for l in leads:
        st = l.get("status", "New")
        status_counts[st] = status_counts.get(st, 0) + 1

    return {
        "total_leads": total_leads,
        "leads_with_phone": leads_with_phone,
        "today_leads": today_leads,
        "total_potential_bdt": total_potential_bdt,
        "confirmed_bdt": confirmed_bdt,
        "status_counts": status_counts
    }


def sync_leads_from_facebook(page_access_token: str, page_id: str = PAGE_ID, limit: int = 25) -> int:
    """
    Fetches recent conversations from Facebook Graph API and automatically
    populates or updates the leads database.
    """
    import requests
    if not page_access_token:
        return 0
    try:
        url = f"https://graph.facebook.com/v20.0/{page_id}/conversations"
        params = {
            "fields": "id,updated_time,participants,messages.limit(10){id,message,from,created_time}",
            "limit": limit,
            "access_token": page_access_token
        }
        res = requests.get(url, params=params, timeout=10)
        if res.status_code != 200:
            logger.error(f"Failed to fetch FB conversations: {res.status_code} {res.text}")
            return 0
            
        convs = res.json().get("data", [])
        synced_count = 0
        for c in convs:
            parts = c.get("participants", {}).get("data", [])
            user_part = [p for p in parts if p["id"] != page_id]
            if not user_part:
                continue
            user_name = user_part[0]["name"]
            user_psid = user_part[0]["id"]
            msgs = c.get("messages", {}).get("data", [])
            
            found_phone = None
            latest_msg = ""
            for m in msgs:
                if m.get("from", {}).get("id") != page_id:
                    txt = m.get("message", "")
                    if not latest_msg:
                        latest_msg = txt
                    p = extract_phone_number(txt)
                    if p:
                        found_phone = p
                        break
                        
            save_or_update_lead(
                psid=user_psid,
                name=user_name,
                phone=found_phone,
                message=latest_msg
            )
            synced_count += 1
            
        logger.info(f"Successfully synced {synced_count} leads from Facebook inbox.")
        return synced_count
    except Exception as e:
        logger.error(f"Error in sync_leads_from_facebook: {e}")
        return 0

