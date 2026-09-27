"""
Poddopaataa Autonomous Lead Conversion & Inbox Agent
1. Real-time Inbox Poller: Guarantees 0-latency replies (every 3 seconds).
2. Proactive Lead Nurturing & Multi-Touch Follow-Up Engine:
   - Stage 1 (~25-90 min silence): Literary sample couplet hook.
   - Stage 2 (~2-6 hrs silence): 1,000 BDT combo discount & WhatsApp phone collection hook.
   - Stage 3 (~18-22 hrs silence): Soft break-up & WhatsApp community invite.
3. Automatically identifies phone numbers and captures leads in leads.json/csv.
4. Detects rejection / not interested keywords and stops follow-ups.
5. 100% compliant with Meta 24-hour messaging policy and BST daytime hours.
"""

import os
import sys
import time
import json
import logging
import hmac
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
import requests
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [LOCAL-AGENT] %(message)s"
)
logger = logging.getLogger("local_inbox_agent")

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

import lead_manager
import webhook_server

PAGE_ID = os.getenv("PODDOPAATAA_PAGE_ID", "377657402757335")
USER_TOKEN = os.getenv("USER_ACCESS_TOKEN", "")
APP_SECRET = os.getenv("APP_SECRET", "")
GRAPH_URL = "https://graph.facebook.com/v20.0"

BST = timezone(timedelta(hours=6))

# Exclude owner / test PSIDs if any
EXCLUDED_PSIDS = {"4277400149005436"}


def get_page_token_and_proof():
    try:
        res = requests.get(f"{GRAPH_URL}/me/accounts", params={"access_token": USER_TOKEN}, timeout=10)
        pages = res.json().get("data", [])
        for p in pages:
            if p["id"] == PAGE_ID:
                ptoken = p["access_token"]
                proof = hmac.new(APP_SECRET.encode("utf-8"), ptoken.encode("utf-8"), hashlib.sha256).hexdigest()
                return ptoken, proof
    except Exception as e:
        logger.error(f"Error fetching page token: {e}")
    return "", ""


PAGE_TOKEN, APP_PROOF = get_page_token_and_proof()
processed_ids = set()


def send_messenger_message(recipient_id: str, text: str) -> bool:
    """Dispatches a message to a Facebook Messenger recipient."""
    global PAGE_TOKEN, APP_PROOF
    if not PAGE_TOKEN:
        PAGE_TOKEN, APP_PROOF = get_page_token_and_proof()
        if not PAGE_TOKEN:
            return False

    send_url = f"{GRAPH_URL}/me/messages"
    s_params = {"access_token": PAGE_TOKEN, "appsecret_proof": APP_PROOF}
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "messaging_type": "RESPONSE"
    }
    try:
        s_res = requests.post(send_url, params=s_params, json=payload, timeout=12)
        if s_res.status_code == 200:
            return True
        else:
            err_data = s_res.json().get("error", {})
            err_code = err_data.get("code")
            logger.error(f"Failed to send to {recipient_id}: {s_res.status_code} {s_res.text}")
            if err_code == 551:
                # User unavailable (blocked page or deactivated)
                lead = lead_manager.get_lead_by_psid(recipient_id)
                if lead:
                    lead_manager.update_lead_status(lead.get("id"), "Unavailable", "User unavailable / blocked")
                    lead_manager.record_followup(recipient_id, 99, "Unavailable (code 551)")
            return False
    except Exception as e:
        logger.error(f"Exception sending to {recipient_id}: {e}")
        return False


def poll_and_reply_cycle():
    """Polls recent conversations for newly arrived user messages and responds immediately."""
    global PAGE_TOKEN, APP_PROOF
    if not PAGE_TOKEN:
        PAGE_TOKEN, APP_PROOF = get_page_token_and_proof()
        if not PAGE_TOKEN:
            return

    try:
        url = f"{GRAPH_URL}/{PAGE_ID}/conversations"
        params = {
            "fields": "id,updated_time,participants,messages.limit(6){id,message,from,created_time,attachments}",
            "limit": 10,
            "access_token": PAGE_TOKEN,
            "appsecret_proof": APP_PROOF
        }
        res = requests.get(url, params=params, timeout=10)
        if res.status_code != 200:
            logger.warning(f"Graph API error: {res.status_code} {res.text}")
            return

        convs = res.json().get("data", [])
        for c in convs:
            parts = [p for p in c.get("participants", {}).get("data", []) if p.get("id") != PAGE_ID]
            if not parts:
                continue
            user_name = parts[0].get("name", "কবি")
            user_psid = parts[0].get("id")

            if user_psid in EXCLUDED_PSIDS:
                continue

            msgs = c.get("messages", {}).get("data", [])
            if not msgs:
                continue

            user_texts = []
            user_msg_ids = []
            has_attachments = False

            for m in msgs:
                sender_id = m.get("from", {}).get("id")
                m_text = m.get("message", "").strip()
                m_id = m.get("id")

                if sender_id == PAGE_ID:
                    # Ignore Meta's automated instant ad welcome greetings
                    if "Please let us know how we can help you" in m_text or "replied to an ad" in m_text or "replied to a post" in m_text:
                        continue
                    # A real human or bot reply exists, so earlier messages were already answered
                    break

                if m_id not in processed_ids:
                    user_msg_ids.append(m_id)
                    if m_text:
                        user_texts.insert(0, m_text)
                    if m.get("attachments", {}).get("data", []):
                        has_attachments = True

            if user_msg_ids:
                for mid in user_msg_ids:
                    processed_ids.add(mid)

                combined_text = " \n".join(user_texts).strip()
                logger.info(f"✨ NEW INCOMING MESSAGE from {user_name} ({user_psid}): '{combined_text}'")

                # 1. Check if user sent a phone number
                phone = lead_manager.extract_phone_number(combined_text)
                # 2. Check if user is rejecting / declining
                is_rejection = lead_manager.is_rejection_message(combined_text)

                if phone:
                    # Lead successfully converted / captured!
                    logger.info(f"🎯 LEAD CAPTURED! Phone extracted: {phone} from {user_name}")
                    lead_manager.save_or_update_lead(
                        psid=user_psid,
                        name=user_name,
                        phone=phone,
                        message=combined_text,
                        notes="Phone captured automatically by Local Agent"
                    )
                    reply = (
                        f"অসংখ্য ধন্যবাদ প্রিয় কবি {user_name}! 🌸\n"
                        f"আপনার মোবাইল নম্বরটি ({phone}) পেয়েছি। আমাদের স্টুডিও প্রোডাকশন টিম খুব শীঘ্রই আপনার সাথে সরাসরি ফোনে কথা বলে কবিতার রেকর্ডিং, কণ্ঠ নির্বাচন ও ভিজ্যুয়াল পরিকল্পনা চূড়ান্ত করবে।\n\n"
                        "আপনার কবিতাটি ছবি বা টেক্সট আকারে আমাদের অফিসিয়াল হোয়াটসঅ্যাপেও পাঠিয়ে রাখতে পারেন: 01409350858 (https://wa.me/8801409350858)। শুভকামনা!"
                    )
                elif is_rejection:
                    # Lead disqualified
                    logger.info(f"🛑 REJECTION DETECTED from {user_name} ({user_psid})")
                    lead_manager.save_or_update_lead(
                        psid=user_psid,
                        name=user_name,
                        message=combined_text
                    )
                    lead = lead_manager.get_lead_by_psid(user_psid)
                    if lead:
                        lead_manager.update_lead_status(lead.get("id"), "Not Interested", "User declined offer")
                    reply = (
                        f"ধন্যবাদ প্রিয় কবি {user_name}। আপনার সিদ্ধান্তকে আমরা সম্মান জানাই।\n"
                        "ভবিষ্যতে কখনো আপনার কবিতার জন্য সিনেম্যাটিক আবৃত্তি বা ভিডিও নির্মাণের প্রয়োজন হলে পদ্যপাতা সবসময় পাশে আছে। আপনার সৃষ্টিশীল পথচলার জন্য শুভকামনা রইল! 🌸"
                    )
                else:
                    # Standard inquiry or poem submission
                    lead_manager.save_or_update_lead(
                        psid=user_psid,
                        name=user_name,
                        message=combined_text or "অ্যাটাচমেন্ট পাঠানো হয়েছে"
                    )

                    if has_attachments and not combined_text:
                        reply = (
                            f"প্রিয় কবি {user_name},\n"
                            "আপনার পাঠানো কবিতা/ছবির ফাইলটি পেয়েছি। আপনার এই কবিতা দিয়ে চমৎকার আবৃত্তি ও সিনেম্যাটিক ভিজ্যুয়াল সহ কাব্যনাট্য তৈরি করা সম্ভব।\n\n"
                            "• ব্যয়: ১ম মিনিট ১,৫০০ টাকা, অতিরিক্ত প্রতি মিনিট ১,০০০ টাকা\n"
                            "• ৩টি কবিতা দিলে ১,০০০ টাকা নগদ ছাড়!\n"
                            "• সময়: ৩–৫ দিন\n\n"
                            "কবিতাটি টেক্সট আকারে ছবি ও পরিচিতি সহ হোয়াটসঅ্যাপেও পাঠাতে পারেন: 01409350858 (https://wa.me/8801409350858)"
                        )
                    else:
                        reply = webhook_server.generate_ai_response(combined_text, user_name)

                if send_messenger_message(user_psid, reply):
                    logger.info(f"🚀 REPLIED INSTANTLY to {user_name} ({user_psid})!")

    except Exception as e:
        logger.error(f"Error in poll_and_reply_cycle: {e}")


def run_followup_cycle():
    """
    Proactively checks silent leads and sends multi-stage follow-ups:
    - Stage 1 (~25-90 min): Literary couplet request hook
    - Stage 2 (~2-6 hours): 1,000 BDT 3-poem discount & WhatsApp hook
    - Stage 3 (~18-22 hours): Soft break-up & WhatsApp community invite
    """
    global PAGE_TOKEN, APP_PROOF
    if not PAGE_TOKEN:
        PAGE_TOKEN, APP_PROOF = get_page_token_and_proof()
        if not PAGE_TOKEN:
            return

    # Check BST time: only follow up during waking hours (08:30 AM to 10:30 PM BST)
    now_bst = datetime.now(BST)
    current_hour_bst = now_bst.hour + (now_bst.minute / 60.0)
    if current_hour_bst < 8.5 or current_hour_bst > 22.5:
        logger.info(f"🌙 BST night time ({now_bst.strftime('%I:%M %p')}). Skipping follow-up pokes until morning.")
        return

    now_utc = datetime.now(timezone.utc)

    try:
        url = f"{GRAPH_URL}/{PAGE_ID}/conversations"
        params = {
            "fields": "id,updated_time,participants,messages.limit(5){id,message,from,created_time}",
            "limit": 25,
            "access_token": PAGE_TOKEN,
            "appsecret_proof": APP_PROOF
        }
        res = requests.get(url, params=params, timeout=12)
        if res.status_code != 200:
            logger.warning(f"Follow-up fetch error: {res.status_code} {res.text}")
            return

        convs = res.json().get("data", [])
        for c in convs:
            parts = [p for p in c.get("participants", {}).get("data", []) if p.get("id") != PAGE_ID]
            if not parts:
                continue
            user_name = parts[0].get("name", "কবি")
            user_psid = parts[0].get("id")

            if user_psid in EXCLUDED_PSIDS:
                continue

            # Look up lead record
            lead = lead_manager.get_lead_by_psid(user_psid)
            if not lead:
                continue

            # 1. Skip if phone already collected!
            phone = lead.get("phone")
            if phone and phone != "পেন্ডিং":
                continue

            # 2. Skip if disqualified or confirmed
            status = lead.get("status", "")
            if status in ["Not Interested", "Confirmed", "Completed", "Cancelled"]:
                continue

            msgs = c.get("messages", {}).get("data", [])
            if not msgs:
                continue

            # Check if Page was the last sender
            last_msg = msgs[0]
            if last_msg.get("from", {}).get("id") != PAGE_ID:
                # User sent the last message! They shouldn't receive a follow-up, they need an answer!
                continue

            # Check user's last message time to respect Meta 24-hr window
            user_msgs = [m for m in msgs if m.get("from", {}).get("id") != PAGE_ID]
            if not user_msgs:
                continue

            try:
                user_last_time = datetime.strptime(user_msgs[0]["created_time"], "%Y-%m-%dT%H:%M:%S%z")
                hours_since_user = (now_utc - user_last_time).total_seconds() / 3600.0

                page_last_time = datetime.strptime(last_msg["created_time"], "%Y-%m-%dT%H:%M:%S%z")
                mins_since_page = (now_utc - page_last_time).total_seconds() / 60.0
            except Exception as te:
                logger.warning(f"Timestamp parse error: {te}")
                continue

            # Meta 24-Hour Policy: Must be strictly within 23 hours of user's last message
            if hours_since_user > 23.0 or hours_since_user < 0:
                continue

            followup_stage = lead.get("followup_stage", 0)

            # Determine appropriate stage
            target_stage = 0
            nudge_msg = ""

            if followup_stage < 1 and 25.0 <= mins_since_page <= 120.0:
                # Stage 1: Literary hook - ask for couplet
                target_stage = 1
                nudge_msg = (
                    f"প্রিয় কবি {user_name},\n"
                    "আপনার পছন্দের কবিতার প্রথম ২–৪টি লাইন কি এখানে একটু শেয়ার করবেন? "
                    "আপনার কবিতার মেজাজ ও ছন্দ অনুযায়ী কোন ধরনের আবৃত্তি ও আবহ সঙ্গীত সবচেয়ে মানাবে, "
                    "আমরা একটু দেখে সুন্দর একটি পরিকল্পনা সাজিয়ে দিতে পারতাম! ✨"
                )

            elif followup_stage < 2 and (mins_since_page >= 120.0 or hours_since_user >= 2.0) and hours_since_user <= 16.0:
                # Stage 2: Value hook - Combo discount & lock slot
                target_stage = 2
                nudge_msg = (
                    f"প্রিয় কবি {user_name},\n"
                    "একটি দারুণ খবর জানিয়ে রাখি—পদ্যপাতার বিশেষ প্যাকেজে ৩টি কবিতা একসাথে দিলে পাচ্ছেন সরাসরি নগদ ১,০০০ টাকা ছাড়! (৪,৫০০ টাকার প্যাকেজ মাত্র ৩,৫০০ টাকায়)।\n\n"
                    "আপনার সৃষ্টিকে নান্দনিক আবৃত্তি ও ভিজ্যুয়ালে রূপ দিতে প্রস্তুত থাকলে আপনার মোবাইল/হোয়াটসঅ্যাপ নম্বরটি লিখে দিতে পারেন। আমাদের টিম আপনার সাথে যোগাযোগ করে নেবে। 🌿"
                )

            elif followup_stage < 3 and 18.0 <= hours_since_user <= 23.0:
                # Stage 3: Soft break-up & WhatsApp community invite
                target_stage = 3
                nudge_msg = (
                    f"কবি {user_name},\n"
                    "আশা করি ভালো আছেন। হয়তো ব্যস্ততার কারণে উত্তর দেওয়া হয়নি, কোনো তাড়া নেই। আপনি প্রস্তুত হলে যেকোনো সময় আমাদের জানাতে পারেন।\n\n"
                    "আপনার সুবিধার্থে আমাদের স্টুডিও হোয়াটসঅ্যাপ লিংক দিয়ে রাখছি: https://wa.me/8801409350858 (01409350858)। আপনার প্রতিটি পঙ্‌ক্তি সুরের মূর্ছনায় অমর হয়ে থাকুক! আন্তরিক শুভকামনা। 🌸"
                )

            if target_stage > 0 and nudge_msg:
                logger.info(f"🔔 TRIGGERING FOLLOW-UP STAGE {target_stage} to {user_name} ({user_psid})...")
                if send_messenger_message(user_psid, nudge_msg):
                    lead_manager.record_followup(user_psid, target_stage, f"Follow-up Stage {target_stage} sent")
                    logger.info(f"✅ Follow-up Stage {target_stage} delivered to {user_name}!")
                    # Small delay between multiple sends to be courteous with rate limits
                    time.sleep(2)

    except Exception as e:
        logger.error(f"Error in run_followup_cycle: {e}")


def main():
    logger.info("Initializing cache with past messages...")
    try:
        url = f"{GRAPH_URL}/{PAGE_ID}/conversations"
        params = {
            "fields": "messages.limit(2){id,from}",
            "limit": 20,
            "access_token": PAGE_TOKEN,
            "appsecret_proof": APP_PROOF
        }
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            for c in res.json().get("data", []):
                msgs = c.get("messages", {}).get("data", [])
                if msgs:
                    # ONLY cache as processed if the PAGE was the last sender (already answered!)
                    if msgs[0].get("from", {}).get("id") == PAGE_ID:
                        processed_ids.add(msgs[0]["id"])
            logger.info(f"Cache loaded with {len(processed_ids)} already-answered message IDs.")
    except Exception as e:
        logger.warning(f"Cache init warning: {e}")

    logger.info("🟢 Poddopaataa Local Conversion Agent is ACTIVE!")
    logger.info("⚡ Real-time inbox polling: every 3s | Proactive follow-up cycle: every 60s")

    loop_count = 0
    while True:
        poll_and_reply_cycle()

        loop_count += 1
        # Run proactive follow-up cycle every 20 iterations (~60 seconds)
        if loop_count % 20 == 0:
            run_followup_cycle()

        time.sleep(3)


if __name__ == "__main__":
    main()
