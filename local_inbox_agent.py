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
ai_sent_msg_ids = set()
human_takeover_until = {}  # user_psid -> timestamp when takeover expires

PROCESSED_COMMENTS_FILE = BASE_DIR / "processed_comments.json"
processed_comment_ids = set()


def load_processed_comments():
    """Loads previously handled comment IDs from file."""
    global processed_comment_ids
    if PROCESSED_COMMENTS_FILE.exists():
        try:
            with open(PROCESSED_COMMENTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                processed_comment_ids = set(data)
                logger.info(f"Loaded {len(processed_comment_ids)} processed comment IDs from cache.")
        except Exception as e:
            logger.warning(f"Error loading processed comments cache: {e}")


def save_processed_comment(c_id: str):
    """Saves a comment ID to the persisted processed comments file."""
    try:
        processed_comment_ids.add(c_id)
        with open(PROCESSED_COMMENTS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(processed_comment_ids), f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Error saving processed comment {c_id}: {e}")


def send_private_reply_to_comment(comment_id: str, text: str) -> str:
    """Dispatches a 1-on-1 private Messenger DM to a commenter. Returns recipient PSID if successful."""
    global PAGE_TOKEN, APP_PROOF
    if not PAGE_TOKEN:
        PAGE_TOKEN, APP_PROOF = get_page_token_and_proof()
        if not PAGE_TOKEN:
            return ""

    url = f"{GRAPH_URL}/me/messages"
    params = {"access_token": PAGE_TOKEN, "appsecret_proof": APP_PROOF}
    payload = {
        "recipient": {"comment_id": comment_id},
        "message": {"text": text}
    }
    try:
        res = requests.post(url, params=params, json=payload, timeout=12)
        if res.status_code == 200:
            data = res.json()
            psid = data.get("recipient_id", "")
            msg_id = data.get("message_id")
            if msg_id:
                ai_sent_msg_ids.add(msg_id)
            logger.info(f"💌 Private Messenger DM delivered to commenter for comment {comment_id} (PSID: {psid})")
            return psid
        else:
            logger.warning(f"Private DM skipped/failed for comment {comment_id}: {res.status_code} {res.text}")
    except Exception as e:
        logger.error(f"Error sending private reply to comment {comment_id}: {e}")
    return ""


def like_comment(comment_id: str) -> bool:
    """Likes a public comment as Page."""
    global PAGE_TOKEN, APP_PROOF
    try:
        url = f"{GRAPH_URL}/{comment_id}/likes"
        payload = {"access_token": PAGE_TOKEN, "appsecret_proof": APP_PROOF}
        res = requests.post(url, data=payload, timeout=8)
        return res.status_code == 200
    except Exception as e:
        logger.error(f"Error liking comment {comment_id}: {e}")
        return False


def reply_public_comment(comment_id: str, text: str) -> bool:
    """Posts a public threaded reply to a comment."""
    global PAGE_TOKEN, APP_PROOF
    try:
        url = f"{GRAPH_URL}/{comment_id}/comments"
        payload = {
            "message": text,
            "access_token": PAGE_TOKEN,
            "appsecret_proof": APP_PROOF
        }
        res = requests.post(url, data=payload, timeout=12)
        if res.status_code == 200:
            return True
        else:
            logger.warning(f"Public reply failed for comment {comment_id}: {res.status_code} {res.text}")
            return False
    except Exception as e:
        logger.error(f"Error in reply_public_comment: {e}")
        return False


def generate_comment_response(comment_text: str, user_name: str) -> str:
    """Generates an engaging, literary, and conversion-focused response for a comment."""
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            from google import genai
            client = genai.Client(api_key=gemini_key)
            prompt = (
                f"You are the literary voice and warm host for 'পদ্যপাতা' (Poddopaataa), "
                f"a premier audio-visual poetry production house that turns written poems into cinematic 'কাব্যনাট্য' "
                f"(professional voice recitation, custom emotive background score, and HD cinematic visuals).\n\n"
                f"Commenter Name: {user_name}\n"
                f"Comment: \"{comment_text}\"\n\n"
                f"Strict Guidelines for Response in Bengali:\n"
                f"১. অত্যন্ত আন্তরিক, বিনম্র, মার্জিত ও সৃষ্টিশীল সাহিত্যিক ভঙ্গিতে কথা বলুন। কোনো কৃত্রিম রোবটের মতো লাগা চলবে না।\n"
                f"২. যদি ব্যবহারকারী 'কাব্যনাট্য কি' বা এর অর্থ/প্রক্রিয়া সম্পর্কে জানতে চান:\n"
                f"   - কাব্যনাট্যের রূপ বুঝিয়ে বলুন: কবিতার প্রতিটি পঙ্‌ক্তিকে পেশাদার আবৃত্তি, সুরের মূর্ছনা ও সিনেমার মতো জীবন্ত এইচডি ভিজ্যুয়ালের নিখুঁত মেলবন্ধন।\n"
                f"   - সিদ্ধান্ত নেওয়ার আগে আমাদের পূর্ববর্তী প্রোডাকশন ও কাজের মান দেখে ভালো করে বুঝতে আমাদের অফিশিয়াল ইউটিউব চ্যানেলে ঢুঁ মারার আমন্ত্রণ জানান:\n"
                f"     👉 https://www.youtube.com/@Poddopaataa — আগে ভালো করে দেখুন ও বুঝুন, তারপর সিদ্ধান্ত নিন!\n"
                f"৩. যদি খরচ বা কবিতা পাঠানোর নিয়ম জানতে চান:\n"
                f"   - স্বচ্ছ রেট: ১ম মিনিট ১,৫০০ টাকা, পরবর্তী প্রতি অতিরিক্ত মিনিট ১,০০০ টাকা। একসাথে ৩টি কবিতার প্যাকেজে ১,০০০ টাকা নগদ ছাড় (মাত্র ৩,৫০০ টাকা)!\n"
                f"   - বিশেষ আশ্বাস: কোনো অগ্রিম বা আগে টাকা দিতে হবে না! কাজ সম্পূর্ণ তৈরি হওয়ার পর পেমেন্ট করবেন।\n"
                f"   - কাজের মান দেখতে ইউটিউব লিংক দিন: https://www.youtube.com/@Poddopaataa\n"
                f"   - কবিতা জমা দিতে ইনবক্সে অথবা সরাসরি হোয়াটসঅ্যাপে যুক্ত হতে বলুন: 01409350858 (https://wa.me/8801409350858)।\n"
                f"৪. যদি সাধারণ প্রশংসা বা ভালো লাগার মন্তব্য হয় (যেমন: সুন্দর, অসাধারণ, ধন্যবাদ, nice, wow, শুভকামনা ইত্যাদি):\n"
                f"   - গভীর আন্তরিক কৃতজ্ঞতা ও ভালোবাসা জানান।\n"
                f"   - নিয়মিত কাব্যনাট্য ও আবৃত্তি উপভোগ করতে পদ্যপাতার অফিশিয়াল ইউটিউব চ্যানেল (https://www.youtube.com/@Poddopaataa) ঘুরে আসার আমন্ত্রণ জানান।\n"
                f"   - তিনি কবিতা লিখলে বা তার পছন্দের কবিতা থাকলে ইনবক্স বা হোয়াটসঅ্যাপে (01409350858) পাঠানোর আমন্ত্রণ জানান।\n"
                f"৫. আকার: পরিমিত ও আকর্ষণীয় (২ থেকে ৪টি অর্থপূর্ণ বাক্যের মধ্যে)।"
            )
            response = client.models.generate_content(
                model="gemini-flash-lite-latest",
                contents=prompt
            )
            if response and response.text:
                return response.text.strip()
        except Exception as e:
            logger.warning(f"Gemini comment generation error: {e}")

    # Fallback response
    c_lower = comment_text.lower()
    if any(w in c_lower for w in ["কাব্যনাট্য", "কি", "কাকে বলে", "বুঝিনি", "দাম", "খরচ", "টাকা", "price", "cost", "info", "পাঠাব"]):
        return (
            f"প্রিয় {user_name}, আন্তরিক শুভেচ্ছা ও ভালোবাসা! 🌸\n\n"
            "কাব্যনাট্য হলো আপনার কবিতার প্রতিটি অনুভূতিকে পেশাদার আবৃত্তি শিল্পীর ভরাট কণ্ঠ, মন ছোঁয়া সুর ও সিনেমার মতো আকর্ষণীয় এইচডি ভিজ্যুয়ালের মেলবন্ধনে রূপ দেওয়া একটি দৃশ্যকাব্য।\n\n"
            "আমাদের কাজের মান ও আগের সৃষ্টিগুলো দেখে ভালো করে বুঝতে আপনার সুবিধার্থে অফিশিয়াল ইউটিউব চ্যানেলটি ঘুরে আসার অনুরোধ রইল:\n"
            "👉 https://www.youtube.com/@Poddopaataa — আগে দেখুন ও বুঝুন, তারপর সিদ্ধান্ত নিন!\n\n"
            "১ম মিনিট ১,৫০০ টাকা, পরবর্তী প্রতি অতিরিক্ত মিনিট ১,০০০ টাকা। ৩টি কবিতার প্যাকেজে সরাসরি ১,০০০ টাকা নগদ ছাড় (মাত্র ৩,৫০০ টাকা)! সবচেয়ে বড় বিষয়—কবিতা সম্পূর্ণ তৈরি ও আবৃত্তি হওয়ার আগে কোনো অগ্রিম টাকা দিতে হবে না। বিস্তারিত জানতে আমাদের ইনবক্সে মেসেজ দিন অথবা হোয়াটসঅ্যাপে যোগাযোগ করুন: 01409350858 (https://wa.me/8801409350858)। 🌿"
        )
    else:
        return (
            f"অসংখ্য ধন্যবাদ ও বিনম্র কৃতজ্ঞতা প্রিয় {user_name}! 🌸\n"
            "আপনার এমন আন্তরিক অনুপ্রেরণাই আমাদের পথচলার মূল প্রেরণা। পদ্যপাতার নিয়মিত আবৃত্তি ও সিনেম্যাটিক কাব্যনাট্য উপভোগ করতে আমাদের ইউটিউব চ্যানেলে যুক্ত থাকার আমন্ত্রণ রইল: https://www.youtube.com/@Poddopaataa। আপনার প্রতিটি দিন সাহিত্যের সুর ও স্নিগ্ধতায় ভরে উঠুক! ✨"
        )


def get_monitored_post_ids() -> list:
    """Collects all active content IDs to monitor for comments: feed posts, videos, and active ad stories."""
    targets = set()
    # Always include known running ad stories
    targets.add("377657402757335_1655127473279582")

    # 1. Feed posts
    try:
        url = f"{GRAPH_URL}/{PAGE_ID}/feed"
        params = {"fields": "id", "limit": 10, "access_token": PAGE_TOKEN, "appsecret_proof": APP_PROOF}
        res = requests.get(url, params=params, timeout=8)
        if res.status_code == 200:
            for p in res.json().get("data", []):
                if p.get("id"):
                    targets.add(p["id"])
    except Exception as e:
        logger.warning(f"Error fetching feed posts for comment monitoring: {e}")

    # 2. Videos / Reels
    try:
        v_url = f"{GRAPH_URL}/{PAGE_ID}/videos"
        v_params = {"fields": "id", "limit": 10, "access_token": PAGE_TOKEN, "appsecret_proof": APP_PROOF}
        v_res = requests.get(v_url, params=v_params, timeout=8)
        if v_res.status_code == 200:
            for v in v_res.json().get("data", []):
                if v.get("id"):
                    targets.add(v["id"])
    except Exception as e:
        logger.warning(f"Error fetching videos for comment monitoring: {e}")

    # 3. Active Ad stories from Meta Ads Manager
    try:
        for act in ["act_743060607284727", "act_201853775777524"]:
            ad_url = f"{GRAPH_URL}/{act}/ads"
            ad_params = {
                "fields": "creative{effective_object_story_id}",
                "effective_status": '["ACTIVE"]',
                "access_token": USER_TOKEN
            }
            ad_res = requests.get(ad_url, params=ad_params, timeout=8)
            if ad_res.status_code == 200:
                for a in ad_res.json().get("data", []):
                    sid = a.get("creative", {}).get("effective_object_story_id")
                    if sid:
                        targets.add(sid)
    except Exception as e:
        logger.warning(f"Error fetching active ad stories: {e}")

    return list(targets)


def poll_and_reply_comments():
    """Polls all active posts, videos, and ads for unreplied comments, likes them, and posts public replies."""
    global PAGE_TOKEN, APP_PROOF
    if not PAGE_TOKEN:
        PAGE_TOKEN, APP_PROOF = get_page_token_and_proof()
        if not PAGE_TOKEN:
            return

    target_ids = get_monitored_post_ids()

    for post_id in target_ids:
        try:
            url = f"{GRAPH_URL}/{post_id}/comments"
            params = {
                "fields": "id,from,message,created_time,like_count,user_likes,comments{id,from,message}",
                "limit": 15,
                "access_token": PAGE_TOKEN,
                "appsecret_proof": APP_PROOF
            }
            res = requests.get(url, params=params, timeout=10)
            if res.status_code != 200:
                continue

            comments_data = res.json().get("data", [])
            for c in comments_data:
                c_id = c.get("id")
                if not c_id or c_id in processed_comment_ids:
                    continue

                c_from = c.get("from")
                if c_from and c_from.get("id") == PAGE_ID:
                    save_processed_comment(c_id)
                    continue

                # Check if page already replied to this comment in threads
                child_replies = c.get("comments", {}).get("data", [])
                page_already_replied = any(r.get("from", {}).get("id") == PAGE_ID for r in child_replies)
                if page_already_replied:
                    save_processed_comment(c_id)
                    continue

                c_text = c.get("message", "").strip()
                user_name = c_from.get("name", "প্রিয় সুহৃদ") if c_from else "প্রিয় সুহৃদ"

                if not c_text:
                    like_comment(c_id)
                    save_processed_comment(c_id)
                    continue

                logger.info(f"💬 NEW UNREPLIED COMMENT on post {post_id} from {user_name}: '{c_text}'")

                # Generate tailored literary response
                reply_text = generate_comment_response(c_text, user_name)

                # 1. Like the comment
                liked = like_comment(c_id)
                if liked:
                    logger.info(f"❤️ Liked comment {c_id}")

                # 2. Post public threaded reply
                pub_ok = reply_public_comment(c_id, reply_text)
                if pub_ok:
                    logger.info(f"✅ Public reply posted on comment {c_id}")

                # 3. Direct Private Messenger DM (if permitted)
                user_psid = send_private_reply_to_comment(c_id, reply_text)

                # 4. Save/Update lead in CRM ONLY if we have a real user profile or PSID
                if user_psid or (user_name and user_name not in ["প্রিয় সুহৃদ", "কবি", "Facebook User"]):
                    lead_manager.save_or_update_lead(
                        psid=user_psid or f"comment_{c_id}",
                        name=user_name,
                        message=f"[FB Comment on Post {post_id}] {c_text}",
                        notes=f"Converted from Facebook comment on post {post_id}"
                    )

                save_processed_comment(c_id)
                time.sleep(2)

        except Exception as e:
            logger.error(f"Error checking comments on post {post_id}: {e}")



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
            msg_id = s_res.json().get("message_id")
            if msg_id:
                ai_sent_msg_ids.add(msg_id)
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
                    # Check if this message was sent manually by human admin (not by AI agent)
                    if m_id not in ai_sent_msg_ids:
                        try:
                            m_time = datetime.strptime(m["created_time"], "%Y-%m-%dT%H:%M:%S%z")
                            mins_since_human = (datetime.now(timezone.utc) - m_time).total_seconds() / 60.0
                            if mins_since_human < 30.0:
                                human_takeover_until[user_psid] = time.time() + ((30.0 - mins_since_human) * 60)
                        except Exception:
                            pass
                    # A real human or bot reply exists, so earlier messages were already answered
                    break

                if m_id not in processed_ids:
                    user_msg_ids.append(m_id)
                    if m_text:
                        user_texts.insert(0, m_text)
                    if m.get("attachments", {}).get("data", []):
                        has_attachments = True

            # If Human Admin is actively chatting with this user, AI stands aside!
            if time.time() < human_takeover_until.get(user_psid, 0):
                if user_msg_ids:
                    logger.info(f"👤 Human Admin is actively chatting with {user_name} ({user_psid}). AI standing aside.")
                    for mid in user_msg_ids:
                        processed_ids.add(mid)
                continue

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

                    # Look up existing lead for already captured phone
                    existing_lead = lead_manager.get_lead_by_psid(user_psid)
                    already_has_phone = existing_lead.get("phone", "") if existing_lead else ""
                    if already_has_phone == "পেন্ডিং":
                        already_has_phone = ""

                    # Build chronological conversation history (last 6 messages)
                    history_lines = []
                    for m in reversed(msgs[:6]):
                        s_id = m.get("from", {}).get("id")
                        s_name = "পদ্যপাতা" if s_id == PAGE_ID else user_name
                        m_txt = m.get("message", "").strip().replace("\n", " ")
                        if m_txt and "Please let us know how we can help" not in m_txt:
                            history_lines.append(f"[{s_name}]: {m_txt}")
                    conv_history = "\n".join(history_lines)

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
                        reply = webhook_server.generate_ai_response(
                            user_message=combined_text,
                            user_name=user_name,
                            conversation_history=conv_history,
                            already_has_phone=already_has_phone
                        )

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

            # Skip if Human Admin is in active conversation window
            if time.time() < human_takeover_until.get(user_psid, 0):
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

            # If past 23.5 hours and still no response from user after attempts, gracefully archive
            if hours_since_user > 23.5:
                if followup_stage > 0 and followup_stage < 99:
                    lead_manager.update_lead_status(lead.get("id"), "Cold / Inactive", "Completed follow-up window (24h passed)")
                    lead_manager.record_followup(user_psid, 99, "Completed follow-up sequence, archived")
                continue

            followup_stage = lead.get("followup_stage", 0)

            # Determine appropriate stage
            target_stage = 0
            nudge_msg = ""

            # Stage 1: ~1 to 2.5 hours after silence (Warm, personal poke & ice-breaker)
            if followup_stage < 1 and (mins_since_page >= 55.0 or hours_since_user >= 1.0) and hours_since_user < 3.0:
                target_stage = 1
                nudge_msg = (
                    f"প্রিয় কবি {user_name}, আপনি কি একটু ব্যস্ত আছেন? ☕\n\n"
                    "একটা কথা জানতে খুব ইচ্ছে হলো—আচ্ছা, আপনি কতদিন ধরে কবিতা লিখছেন? আর নিজের লেখা সবচেয়ে প্রিয় কবিতা কোনটি? ✨"
                )

            # Stage 2: ~3 to 7 hours after silence (Strategic hook: Book vs. Visual Recitation)
            elif followup_stage < 2 and (mins_since_page >= 170.0 or hours_since_user >= 3.0) and hours_since_user < 7.5:
                target_stage = 2
                nudge_msg = (
                    f"প্রিয় কবি {user_name}, একটা কথা ভাবছিলাম—\n"
                    "আজকাল তো কাগুজে বই মানুষ খুব একটা পড়ে না। পাঠক এখন কবিতা দেখতে চায়, আবৃত্তিশিল্পীর ভরাট কণ্ঠে শুনতে চায়। আপনার সৃষ্টিশীল কবিতাকে যদি সুর আর সিনেমার মতো চমৎকার ভিজ্যুয়ালে রূপ দেওয়া যায়, তবে তা মুহূর্তেই হাজারো মানুষের হৃদয়ে পৌঁছে দেওয়া সম্ভব—যা কোনো বই দিয়ে হয়তো হতো না!\n\n"
                    "আপনার কি এমন কোনো পছন্দের কবিতা আছে যা সুন্দর আবৃত্তির মাধ্যমে সবার কাছে পৌঁছে দিতে চান? 🎬✨"
                )

            # Stage 3: ~8 to 20 hours after silence (Caring check-in & YouTube showcase)
            elif followup_stage < 3 and (mins_since_page >= 420.0 or hours_since_user >= 7.5) and hours_since_user < 21.0:
                target_stage = 3
                nudge_msg = (
                    f"কবি {user_name}, ভাবলাম আপনার একটু খোঁজ নিই। শেষ কবিতাটি কবে লিখেছিলেন?\n\n"
                    "অবসর পেলে আমাদের পদ্যপাতা ইউটিউব চ্যানেলের (https://www.youtube.com/@Poddopaataa) আবৃত্তিগুলো একটু দেখে নেবেন কিন্তু। আপনার মতো সৃষ্টিশীল মানুষের মতামত আমাদের খুব অনুপ্রাণিত করে! 🌸"
                )

            # Stage 4: ~21 to 23.5 hours after silence (Polite soft break-up — "বিরক্ত করব না")
            elif followup_stage < 4 and 21.0 <= hours_since_user <= 23.5:
                target_stage = 4
                nudge_msg = (
                    f"প্রিয় কবি {user_name}, আশা করি ভালো আছেন।\n"
                    "হয়তো অনেক ব্যস্ততার মধ্যে আছেন। আপনি যদি এখন আগ্রহী না হন, তবে পদ্যপাতা থেকে আপনাকে মেসেজ দিয়ে আর বিরক্ত করব না।\n\n"
                    "কখনো আপনার কবিতার আবৃত্তি বা ভিডিও নির্মাণের ইচ্ছে হলে আমাদের দরজা সবসময় খোলা রইল (হোয়াটসঅ্যাপ: 01409350858)। আপনার প্রতিটি দিন সৃষ্টিশীলতায় শান্তিময় ও উজ্জ্বল হোক! 🌿"
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
    logger.info("Initializing cache with past messages and comments...")
    load_processed_comments()

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

    # If processed_comments.json didn't exist yet, seed it with historical comments to avoid spamming past posts
    if not PROCESSED_COMMENTS_FILE.exists() or len(processed_comment_ids) == 0:
        try:
            feed_url = f"{GRAPH_URL}/{PAGE_ID}/feed"
            f_params = {
                "fields": "comments.limit(25){id}",
                "limit": 10,
                "access_token": PAGE_TOKEN,
                "appsecret_proof": APP_PROOF
            }
            f_res = requests.get(feed_url, params=f_params, timeout=10)
            if f_res.status_code == 200:
                for p in f_res.json().get("data", []):
                    for comm in p.get("comments", {}).get("data", []):
                        if comm.get("id"):
                            processed_comment_ids.add(comm["id"])
                save_processed_comment("")
                logger.info(f"Seeded {len(processed_comment_ids)} historical comment IDs to cache.")
        except Exception as e:
            logger.warning(f"Error seeding historical comments: {e}")

    logger.info("🟢 Poddopaataa Lead Conversion & Comment Responder Agent is ACTIVE!")
    logger.info("⚡ Real-time inbox: every 3s | Post comments: every 30s | Proactive follow-ups: every 60s")

    loop_count = 0
    while True:
        poll_and_reply_cycle()

        loop_count += 1
        # Run comment auto-responder cycle every 10 iterations (~30 seconds)
        if loop_count % 10 == 0:
            poll_and_reply_comments()

        # Run proactive follow-up cycle every 20 iterations (~60 seconds)
        if loop_count % 20 == 0:
            run_followup_cycle()

        time.sleep(3)


if __name__ == "__main__":
    main()
