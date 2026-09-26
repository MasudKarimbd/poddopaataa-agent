"""
Poddopaataa 24/7 AI Messenger Agent
Autonomous Webhook Server for Facebook Messenger
Works 24/7 in cloud environments (Google Cloud Run / Render / Koyeb) at $0 cost.
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, Response, render_template, send_file
import requests
from dotenv import load_dotenv
import lead_manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("poddopaataa_agent")

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# App & Page Configuration
PAGE_ID = os.getenv("PODDOPAATAA_PAGE_ID", "377657402757335")
VERIFY_TOKEN = os.getenv("WEBHOOK_VERIFY_TOKEN", "poddopaataa_secret_token_2026")
GRAPH_API_VERSION = "v20.0"
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

# Load Page Access Token
def get_page_access_token() -> str:
    # First check environment variable
    token = os.getenv("PAGE_ACCESS_TOKEN", "")
    if token:
        return token
    
    # Check facebook_pages.json
    pages_file = BASE_DIR / "facebook_pages.json"
    if pages_file.exists():
        try:
            with open(pages_file, "r", encoding="utf-8") as f:
                pages = json.load(f)
                if PAGE_ID in pages:
                    return pages[PAGE_ID].get("access_token", "")
        except Exception as e:
            logger.error(f"Failed to read facebook_pages.json: {e}")
    return ""

PAGE_ACCESS_TOKEN = get_page_access_token()

# Initialize Flask app
app = Flask(__name__)

# Knowledge base context for Gemini / AI
KNOWLEDGE_BASE = """
আপনি 'পদ্যপাতা' (Poddopaataa) ফেসবুক পেজের একজন অত্যন্ত বিনীত, মার্জিত ও কাব্যিক সহকারী (AI Agent)।
আপনার দায়িত্ব হলো মেসেঞ্জারে আসা কবি ও সাহিত্যপ্রেমীদের প্রশ্নের নিখুঁত তথ্যসহ উত্তর দেওয়া।

পদ্যপাতা সম্পর্কে মূল তথ্য:
১. সেবা: লুকানো পাণ্ডুলিপি বা দুর্বল সোশ্যাল স্ট্যাটাস নয়—কবিতাকে পূর্ণাঙ্গ সিনেম্যাটিক 'কাব্যনাট্য'-এ রূপ দেওয়া হয় (প্রফেশনাল আবৃত্তি, আবেগঘন ভিজ্যুয়াল ডিজাইন, সাউন্ড স্কোর ও মিক্সিং, ফাইনাল ভিডিও এডিটিং)।
২. মূল্য তালিকা (স্বচ্ছ খরচ):
   - ১ম মিনিট: ১,৫০০ টাকা (আবৃত্তি ৫০০৳, ভিজ্যুয়াল ৭০০৳, সাউন্ড ১০০৳, এডিটিং ২০০৳)
   - পরবর্তী প্রতি অতিরিক্ত মিনিট: ১,০০০ টাকা
   - আনুমানিক হিসাব:
     * ১ মিনিট = ১,৫০০ টাকা
     * ২ মিনিট = ২,৫০০ টাকা
     * ৩ মিনিট = ৩,৫০০ টাকা
     (সাধারণত ১ মিনিট ≈ ১৫০–১৮০ শব্দ)
৩. ডেলিভারি ও সময়:
   - সাধারণত ৩ থেকে ৫ কার্যদিবসের মধ্যে তৈরি হয়।
   - কবিকে ফুল এইচডি ফাইল দেওয়া হয় এবং পদ্যপাতা চ্যানেলেও প্রচার করা হয়।
৪. কবিতা জমার নিয়ম:
   - কবিতার টেক্সট (লেখা)
   - কবির নাম + ছবি
   - সংক্ষিপ্ত পরিচিতি (বায়ো)
   - যোগাযোগ নম্বর
   (শর্ত: কোনো রাজনৈতিক বা ধর্মীয় বিদ্বেষমূলক কবিতা গ্রহণযোগ্য নয়)
৫. যোগাযোগের মাধ্যম ও লিংক:
   - WhatsApp নম্বর: 01409350858 (https://wa.me/8801409350858)
   - কবিদের হোয়াটসঅ্যাপ গ্রুপ: https://chat.whatsapp.com/BYga8IgbM31B1L2nlwDXa8
   - বিস্তারিত ওয়েবসাইট: https://poddopaataa.dreamakerbd.com/PPS03/
   - ইউটিউব চ্যানেল: https://www.youtube.com/@Poddopaataa

উত্তর দেওয়ার নির্দেশিকা:
- সবসময় বিনীত ও মার্জিত বাংলায় কথা বলবেন।
- যদি কেউ খরচ জিজ্ঞেস করে, মিনিটের হিসাব ও স্বচ্ছ রেট বুঝিয়ে বলবেন।
- যদি কেউ কবিতার ছবি পাঠায়, তাদের বলবেন লেখাটি টেক্সট আকারে ছবি ও নামসহ হোয়াটসঅ্যাপে (01409350858) পাঠিয়ে দিতে।
- উত্তর খুব বেশি লম্বা করবেন না, মূল পয়েন্ট স্পষ্ট রাখবেন এবং শেষে হোয়াটসঅ্যাপে যোগাযোগ বা ওয়েবসাইটে দেখার আমন্ত্রণ জানাবেন।
"""

def get_knowledge_base() -> str:
    """Read knowledge base from knowledge_base.txt if present, with fallback."""
    kb_file = BASE_DIR / "knowledge_base.txt"
    if kb_file.exists():
        try:
            with open(kb_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            logger.warning(f"Failed to read knowledge_base.txt: {e}")
    return KNOWLEDGE_BASE


def get_user_profile_name(psid: str) -> str:
    """Fetch user full name from Graph API or fallback gracefully."""
    token = get_page_access_token()
    if not token or not psid:
        return "কবি"
    try:
        url = f"{GRAPH_URL}/{psid}"
        res = requests.get(url, params={"fields": "name,first_name", "access_token": token}, timeout=5)
        if res.status_code == 200:
            data = res.json()
            return data.get("name") or data.get("first_name") or "কবি"
    except Exception:
        pass
    return "কবি"


def generate_ai_response(user_message: str, user_name: str = "কবি") -> str:
    """Generate witty, human-like, to-the-point responses using Gemini or fallback."""
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    kb_content = get_knowledge_base()
    
    # Check if user shared phone number
    detected_phone = lead_manager.extract_phone_number(user_message)
    
    if gemini_key:
        import time
        from google import genai
        client = genai.Client(api_key=gemini_key)
        phone_ctx = f"গ্রাহক ফোন নম্বর দিয়েছেন: {detected_phone}" if detected_phone else "গ্রাহক এখনো ফোন নম্বর দেননি।"
        prompt = (
            f"{kb_content}\n\n"
            f"গ্রাহকের নাম: {user_name}\n"
            f"গ্রাহকের বার্তা: \"{user_message}\"\n"
            f"ফোন নম্বর অবস্থা: {phone_ctx}\n\n"
            f"বিশেষ নির্দেশনা (কঠোরভাবে মানতে হবে):\n"
            f"১. আপনি কোনো রোবট বা কৃত্রিম সহকারী নন! আপনি পদ্যপাতার একজন রসিক, প্রাণবন্ত, আড্ডাবাজ ও সৃষ্টিশীল রক্ত-মাংসের বন্ধু।\n"
            f"২. উত্তর হবে একেবারে ছোট, চটপটে ও টু-দ্য-পয়েন্ট (২ থেকে ৪ বাক্যের মধ্যে শেষ করবেন)। অপ্রয়োজনীয় দীর্ঘ ভূমিকা বা ভারী লেকচার দেওয়া যাবে না।\n"
            f"৩. কথায় রস ও হালকা খুনসুটি থাকবে যাতে ক্লায়েন্ট কোনোভাবেই বুঝতে না পারে সে কোনো এআই-এর সাথে কথা বলছে।\n"
            f"৪. মিনিটের হিসাব বা খরচ জানতে চাইলে সরাসরি এক লাইনে হিসাব দিন (১ম মিনিট ১৫০০৳, অতিরিক্ত প্রতি মিনিট ১০০০৳। ৫ মিনিট হলে: ৫৫০০৳)।\n"
                    f"৫. যদি গ্রাহক এখনো নম্বর না দিয়ে থাকে: কথার রেশ ধরে সুন্দর ও মিষ্টি সুরে তার মোবাইল নম্বর চেয়ে নিন যাতে পদ্যপাতার নতুন আকর্ষণীয় অফার, বিশেষ ছাড় বা কবিতা/কাব্যনাট্য সংক্রান্ত যেকোনো তথ্য সরাসরি মেসেজ বা কল দিয়ে জানিয়ে দেওয়া যায় (যেমন: 'পদ্যপাতার যেকোনো নতুন অফার, বিশেষ ছাড় বা আপনার কবিতা নিয়ে দ্রুত যোগাযোগের জন্য আপনার সচল মোবাইল নম্বরটি শেয়ার করতে পারেন? আমরা মেসেজ বা কল দিয়ে সবকিছু আপনাকে সরাসরি জানিয়ে দেব! 😄')। কঠোর নিষেধাজ্ঞা: গ্রাহককে কখনোই 'ভয়েস মেসেজ পাঠাবো' বা কোনো প্রকার 'টেস্ট/যাচাই/পরখ' করার কথা বলা যাবে না।\n"
                    f"৬. যদি গ্রাহক মোবাইল নম্বর দিয়ে থাকে ({detected_phone or ''}): অত্যন্ত আন্তরিক ধন্যবাদ জানিয়ে বলুন যে নম্বরটি সংরক্ষিত হয়েছে—পদ্যপাতার যেকোনো নতুন আকর্ষণীয় অফার, কাব্যনাট্যের আপডেট কিংবা কবিতা সংক্রান্ত তথ্য তাকে মেসেজ বা কল দিয়ে জানিয়ে দেওয়া যাবে। এবার তাকে তার কবিতাটি এখানে বা হোয়াটসঅ্যাপে (01409350858) পাঠিয়ে দেওয়ার আমন্ত্রণ জানান। কঠোর নিষেধাজ্ঞা: গ্রাহককে 'ভয়েস মেসেজ পাঠাবো' বা কোনো টেস্ট/যাচাইয়ের কথা বলা সম্পূর্ণ নিষিদ্ধ।\n"
            f"৭. শুক্র-শনিবারে নক করলে হালকা রস করে বলুন এই দুই দিন ক্রিয়েটিভ টিম রিচার্জের ছুটি, তবে এখনই নম্বর ও কবিতা রেখে দিলে রবিবার সকালে সবার আগে তার কাজই ধরা হবে।\n"
            f"৮. হোয়াটসঅ্যাপ নম্বর: 01409350858 এবং সাইট: https://poddopaataa.dreamakerbd.com/PPS03/।"
        )
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=prompt
                )
                if response and response.text:
                    logger.info("[gemini-3.8-flash] Successfully generated witty AI response!")
                    return response.text.strip()
            except Exception as e:
                logger.warning(f"Gemini attempt {attempt+1} failed: {e}")
                time.sleep(0.5)

    # Intelligent Dynamic Witty Fallback Engine
    msg = user_message.strip()
    msg_lower = msg.lower()
    
    # Phone number receipt confirmation fallback
    if detected_phone:
        return (
            f"অসংখ্য ধন্যবাদ কবি {user_name}! আপনার নম্বর ({detected_phone}) সংরক্ষিত হয়েছে। 🎉\n\n"
            "পদ্যপাতার যেকোনো আকর্ষণীয় অফার, কাব্যনাট্যের আপডেট কিংবা আপনার কবিতা সংক্রান্ত তথ্য আমরা সরাসরি মেসেজ বা কল দিয়ে জানিয়ে দেব।\n"
            "এবার আপনার কবিতাটা ঝটপট এখানে বা আমাদের হোয়াটসঅ্যাপে (01409350858) পাঠিয়ে দিন! ☕✨"
        )
    
    # 1. Minute inquiry fallback
    import re
    bengali_digits = {'০':'0', '১':'1', '২':'2', '৩':'3', '৪':'4', '৫':'5', '৬':'6', '৭':'7', '৮':'8', '৯':'9'}
    normalized_msg = ''
    for char in msg:
        normalized_msg += bengali_digits.get(char, char)
    
    minute_match = re.search(r'(\d+)\s*(?:মিনিট|min)', normalized_msg, re.IGNORECASE)
    if minute_match:
        mins = int(minute_match.group(1))
        en_to_bn = str.maketrans('0123456789', '০১২৩৪৫৬৭৮৯')
        total_cost = 1500 if mins <= 1 else 1500 + ((mins - 1) * 1000)
        mins_bn = str(mins).translate(en_to_bn)
        total_cost_bn = f"{total_cost:,}".translate(en_to_bn)
        
        return (
            f"প্রিয় {user_name}, আপনার {mins_bn} মিনিটের সম্পূর্ণ কাব্যনাট্যের মোট খরচ মাত্র {total_cost_bn} টাকা! (আবৃত্তি, মিউজিক, ভিডিও এডিটিং সব একসাথেই) 🎬\n\n"
            "পদ্যপাতার বিশেষ অফার ও আপনার কবিতা নিয়ে দ্রুত যোগাযোগের জন্য আপনার সচল মোবাইল নম্বরটি শেয়ার করতে পারেন? আমরা মেসেজ বা কল দিয়ে সবকিছু সরাসরি জানিয়ে দেব। 😄"
        )

    # 2. General pricing fallback
    if any(w in msg_lower for w in ["টাকা", "খরচ", "কত টাকা", "কতো টাকা", "রেট", "মূল্য", "প্রাইজ", "ফি", "ব্যায়", "ব্যয়", "কত"]):
        return (
            f"সোজা হিসাব কবি {user_name}! ১ম মিনিট মাত্র ১,৫০০৳, এরপর প্রতি অতিরিক্ত মিনিটে ১,০০০৳ করে। এই খরচে প্রফেশনাল আবৃত্তি, আবেগঘন মিউজিক ও ফুল এইচডি ভিডিও সব পেয়ে যাচ্ছেন! ✨\n\n"
            "পদ্যপাতার বিশেষ কোনো ছাড় বা আপনার কবিতা নিয়ে কথা বলার জন্য মোবাইল নম্বরটি শেয়ার করতে পারেন? আমরা মেসেজ বা কল করে বিস্তারিত জানিয়ে দেব। 😄"
        )

    # 3. Delivery / Time fallback
    if any(w in msg_lower for w in ["সময়", "কতদিন", "কত দিন", "কবে", "কত সময়", "কতো দিন"]):
        return (
            f"সাধারণত ৩ থেকে ৫ কার্যদিবসের মধ্যেই আপনার কাব্যনাট্য ফুল এইচডি রেডি হয়ে যাবে! ☕\n\n"
            "আপনার মোবাইল নম্বরটা দিয়ে রাখলে আমাদের টিম মেসেজ বা কলে যোগাযোগ করে আপনার প্রোডাকশন স্লট নিশ্চিত করে নেবে!"
        )

    # 4. WhatsApp / Contact fallback
    if any(w in msg_lower for w in ["হোয়াটসঅ্যাপ", "হোয়াটসঅ্যাপ", "whatsapp", "নম্বর", "নাম্বার", "ফোন", "যোগাযোগ", "contact"]):
        return (
            "আমাদের অফিশিয়াল হোয়াটসঅ্যাপ নম্বর: 01409350858 (https://wa.me/8801409350858)\n\n"
            "আপনার মোবাইল নম্বরটা এখানে দিয়ে রাখলেও আমরা নতুন অফার ও আপডেট নিয়ে আপনার সাথে সরাসরি যোগাযোগ করে নেব! 😄"
        )

    # Default friendly witty welcome
    return (
        f"স্বাগতম প্রিয় {user_name}! পদ্যপাতায় আপনার প্রিয় কবিতাকে আমরা দারুণ এক নান্দনিক ও সিনেম্যাটিক কাব্যনাট্য বানিয়ে দিই! 🎬\n\n"
        "১ম মিনিট মাত্র ১৫০০৳, অতিরিক্ত প্রতি মিনিট ১০০০৳।\n"
        "নতুন অফার পেতে ও সরাসরি কথা বলতে আপনার মোবাইল নম্বরটি শেয়ার করতে পারেন! 😄"
    )
    



def send_messenger_reply(recipient_id: str, text: str) -> bool:
    """Send message reply to Facebook user via Graph API."""
    token = get_page_access_token()
    if not token:
        logger.error("No Page Access Token available!")
        return False

    url = f"{GRAPH_URL}/me/messages"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
        "messaging_type": "RESPONSE"
    }
    
    try:
        res = requests.post(url, params={"access_token": token}, json=payload, timeout=10)
        if res.status_code == 200:
            logger.info(f"Message sent successfully to PSID: {recipient_id}")
            return True
        else:
            logger.error(f"Failed to send message: {res.status_code} {res.text}")
            return False
    except Exception as e:
        logger.error(f"Exception sending message: {e}")
        return False


@app.route("/", methods=["GET"])
def health_check():
    """Health check endpoint for cloud monitoring."""
    return jsonify({
        "status": "online",
        "service": "Poddopaataa AI Messenger Agent",
        "page_id": PAGE_ID,
        "cost_model": "100% Free / Always Free Tier"
    }), 200


@app.route("/webhook", methods=["GET"])
def verify_webhook():
    """
    Facebook Webhook Verification endpoint.
    Meta sends GET request with hub.mode, hub.verify_token, hub.challenge.
    """
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("Webhook successfully verified by Meta!")
            return Response(challenge, status=200, mimetype="text/plain")
        else:
            logger.warning("Webhook verification token mismatch!")
            return Response("Verification token mismatch", status=403)

    return Response("Bad Request", status=400)


@app.route("/webhook", methods=["POST"])
def webhook_event():
    """
    Receive incoming Messenger events from Facebook in real time.
    """
    data = request.get_json(silent=True)
    if not data:
        return Response("No JSON payload", status=400)

    if data.get("object") == "page":
        for entry in data.get("entry", []):
            page_id = entry.get("id")
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event.get("sender", {}).get("id")
                recipient_id = messaging_event.get("recipient", {}).get("id")

                # Ignore messages sent by the page itself to prevent infinite loops
                if sender_id == PAGE_ID or sender_id == page_id:
                    continue

                # Check if it is a user message
                if "message" in messaging_event:
                    msg_obj = messaging_event["message"]
                    
                    # Ignore echoes
                    if msg_obj.get("is_echo"):
                        continue

                    msg_text = msg_obj.get("text", "")
                    attachments = msg_obj.get("attachments", [])
                    
                    # Fetch profile name
                    user_desc = get_user_profile_name(sender_id)
                    logger.info(f"Incoming message from {user_desc} ({sender_id}): '{msg_text}' (Attachments: {len(attachments)})")

                    # Capture lead immediately
                    lead_manager.save_or_update_lead(
                        psid=sender_id,
                        name=user_desc,
                        message=msg_text or "অ্যাটাচমেন্ট / ফাইল পাঠানো হয়েছে"
                    )

                    if attachments and not msg_text:
                        reply_text = (
                            f"প্রিয় {user_desc},\n"
                            "আপনার পাঠানো কবিতা/ছবির ফাইলটি পেয়েছি। আপনার এই কবিতা দিয়ে চমৎকার আবৃত্তি ও সিনেম্যাটিক ভিজ্যুয়াল সহ কাব্যনাট্য তৈরি করা সম্ভব।\n\n"
                            "• ব্যয়: ১ম মিনিট ১,৫০০ টাকা, অতিরিক্ত প্রতি মিনিট ১,০০০ টাকা\n"
                            "• সময়: ৩–৫ দিন\n\n"
                            "কবিতাটি টেক্সট আকারে আপনার ছবি ও পরিচিতি সহ সরাসরি হোয়াটসঅ্যাপে জমা দিন: 01409350858 (https://wa.me/8801409350858)\n"
                            "ওয়েবসাইট: https://poddopaataa.dreamakerbd.com/PPS03/"
                        )
                    else:
                        reply_text = generate_ai_response(msg_text, user_desc)

                    # Send immediate reply
                    send_messenger_reply(sender_id, reply_text)

        # Meta requires immediate 200 OK
        return Response("EVENT_RECEIVED", status=200)

    return Response("Not a page event", status=404)


@app.route("/leads", methods=["GET"])
def view_leads():
    """Web CRM dashboard showing all Messenger leads."""
    token = get_page_access_token()
    # Auto-sync from Facebook if empty or requested via ?sync=1
    if not lead_manager.get_all_leads() or request.args.get("sync") == "1":
        try:
            lead_manager.sync_leads_from_facebook(token)
        except Exception as e:
            logger.warning(f"Auto-sync on page load error: {e}")
            
    all_leads = lead_manager.get_all_leads()
    stats = lead_manager.get_lead_stats()
    return render_template("leads.html", leads=all_leads, stats=stats)


@app.route("/leads/download", methods=["GET"])
def download_leads_csv():
    """Download leads as Excel-compatible CSV."""
    csv_path = BASE_DIR / "leads.csv"
    if not csv_path.exists():
        lead_manager.sync_leads_to_csv(lead_manager.get_all_leads())
    return send_file(
        csv_path,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"poddopaataa_leads_{datetime.now().strftime('%Y%m%d')}.csv"
    )


@app.route("/api/leads", methods=["GET"])
def api_get_leads():
    """API endpoint to get JSON list of leads and stats."""
    return jsonify({
        "stats": lead_manager.get_lead_stats(),
        "leads": lead_manager.get_all_leads()
    }), 200


@app.route("/api/leads/sync", methods=["GET", "POST"])
def api_sync_leads():
    """Manually trigger full synchronization from Facebook Messenger conversations."""
    token = get_page_access_token()
    count = lead_manager.sync_leads_from_facebook(token)
    return jsonify({
        "success": True,
        "synced_count": count,
        "stats": lead_manager.get_lead_stats(),
        "leads": lead_manager.get_all_leads()
    }), 200


@app.route("/api/leads/update-status", methods=["POST"])
def api_update_lead_status():
    """API endpoint to update lead status from CRM UI."""
    data = request.get_json(silent=True) or {}
    lead_id = data.get("lead_id")
    status = data.get("status")
    notes = data.get("notes", "")
    if not lead_id or not status:
        return jsonify({"success": False, "error": "Missing parameters"}), 400
    ok = lead_manager.update_lead_status(lead_id, status, notes)
    return jsonify({"success": ok}), 200


# Background inbox listener for guaranteed zero-delay responses (works regardless of Meta Unpublished mode)
processed_message_ids = set()

def start_background_poller():
    """Continuously monitors conversations and replies within seconds."""
    import time
    logger.info("Starting background auto-reply engine for Poddopaataa...")
    
    token = get_page_access_token()
    
    # Auto-sync leads from Facebook on startup so no lead is ever missed!
    try:
        lead_manager.sync_leads_from_facebook(token)
    except Exception as e:
        logger.warning(f"Startup lead sync error: {e}")
    
    # Pre-populate already seen message IDs so we don't reply to past messages
    token = get_page_access_token()
    try:
        url = f"{GRAPH_URL}/{PAGE_ID}/conversations"
        params = {
            "fields": "messages.limit(1){id}",
            "limit": 10,
            "access_token": token
        }
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            for c in res.json().get("data", []):
                msgs = c.get("messages", {}).get("data", [])
                if msgs:
                    processed_message_ids.add(msgs[0]["id"])
            logger.info(f"Initialized poller cache with {len(processed_message_ids)} existing messages.")
    except Exception as e:
        logger.warning(f"Initial cache setup error: {e}")

    while True:
        try:
            url = f"{GRAPH_URL}/{PAGE_ID}/conversations"
            params = {
                "fields": "id,updated_time,participants,messages.limit(1){id,message,from,created_time,attachments}",
                "limit": 5,
                "access_token": token
            }
            res = requests.get(url, params=params, timeout=10)
            if res.status_code == 200:
                convs = res.json().get("data", [])
                for c in convs:
                    parts = c.get("participants", {}).get("data", [])
                    user_part = [p for p in parts if p["id"] != PAGE_ID]
                    if not user_part:
                        continue
                    user_name = user_part[0]["name"]
                    user_psid = user_part[0]["id"]
                    
                    msgs = c.get("messages", {}).get("data", [])
                    if msgs:
                        last_msg = msgs[0]
                        msg_id = last_msg.get("id")
                        sender_id = last_msg.get("from", {}).get("id")
                        
                        if sender_id != PAGE_ID and msg_id not in processed_message_ids:
                            processed_message_ids.add(msg_id)
                            msg_text = last_msg.get("message", "").strip()
                            attachments = last_msg.get("attachments", {}).get("data", [])
                            logger.info(f"[Auto-Poller] New message detected from {user_name} ({user_psid}): '{msg_text}'")
                            
                            # Capture lead immediately
                            lead_manager.save_or_update_lead(
                                psid=user_psid,
                                name=user_name,
                                message=msg_text or "অ্যাটাচমেন্ট / ফাইল পাঠানো হয়েছে"
                            )
                            
                            if attachments and not msg_text:
                                reply = (
                                    f"প্রিয় কবি {user_name},\n"
                                    "আপনার পাঠানো কবিতা/ছবির ফাইলটি পেয়েছি। আপনার এই কবিতা দিয়ে চমৎকার আবৃত্তি ও সিনেম্যাটিক ভিজ্যুয়াল সহ কাব্যনাট্য তৈরি করা সম্ভব।\n\n"
                                    "• ব্যয়: ১ম মিনিট ১,৫০০ টাকা, অতিরিক্ত প্রতি মিনিট ১,০০০ টাকা\n"
                                    "• সময়: ৩–৫ দিন\n\n"
                                    "কবিতাটি টেক্সট আকারে আপনার ছবি ও পরিচিতি সহ সরাসরি হোয়াটসঅ্যাপে জমা দিন: 01409350858 (https://wa.me/8801409350858)\n"
                                    "ওয়েবসাইট: https://poddopaataa.dreamakerbd.com/PPS03/"
                                )
                            else:
                                reply = generate_ai_response(msg_text, user_name)
                                
                            send_messenger_reply(user_psid, reply)
        except Exception as e:
            logger.error(f"[Auto-Poller loop error]: {e}")
        time.sleep(4)


# Start background thread automatically
import threading
poller_thread = threading.Thread(target=start_background_poller, daemon=True)
poller_thread.start()


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    logger.info(f"Starting Poddopaataa Agent on port {port}...")
    app.run(host="0.0.0.0", port=port)
