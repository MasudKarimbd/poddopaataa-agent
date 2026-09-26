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
from flask import Flask, request, jsonify, Response
import requests
from dotenv import load_dotenv

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

def generate_ai_response(user_message: str, user_name: str = "কবি") -> str:
    """Generate intelligent response using Gemini or resilient rule-based logic."""
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    
    if gemini_key:
        import time
        from google import genai
        for attempt in range(3):
            try:
                client = genai.Client(api_key=gemini_key)
                prompt = (
                    f"{KNOWLEDGE_BASE}\n\n"
                    f"গ্রাহকের নাম: {user_name}\n"
                    f"গ্রাহকের বার্তা: \"{user_message}\"\n\n"
                    f"নির্দেশনা:\n"
                    f"১. আপনি কোনো রোবট নন, একজন অত্যন্ত মার্জিত, রুচিশীল ও সহৃদয় সাহিত্য সহকারী।\n"
                    f"২. গ্রাহকের বার্তা গভীরভাবে বুঝে তার সুনির্দিষ্ট প্রশ্নের বুদ্ধিদীপ্ত উত্তর দিন।\n"
                    f"৩. যদি মিনিটের হিসাব থাকে (যেমন: ৫ মিনিট বা যে কোনো মিনিট): নিজে নির্ভুল গণিত হিসাব করে বলুন (১ম মিনিট ১৫০০ টাকা + পরবর্তী প্রতি অতিরিক্ত মিনিট ১০০০ টাকা। যেমন ৫ মিনিট হলে: ১৫০০ + ৪x১০০০ = ৫৫০০ টাকা)।\n"
                    f"৪. গ্রাহকের প্রশ্নের উত্তর সরাসরি প্রথম লাইনেই দেবেন, অতিরিক্ত বাহুল্য কথা বলবেন না।\n"
                    f"৫. কবিতা জমা ও আলোচনার জন্য হোয়াটসঅ্যাপ (01409350858) ও ওয়েবসাইটের লিঙ্ক (https://poddopaataa.dreamakerbd.com/PPS03/) সুন্দরভাবে উল্লেখ করুন।"
                )
                response = client.models.generate_content(
                    model="gemini-3.8-flash",
                    contents=prompt
                )
                if response and response.text:
                    logger.info(f"[Gemini 3.8 Flash] Successfully generated dynamic AI response!")
                    return response.text.strip()
            except Exception as e:
                logger.warning(f"Gemini API attempt {attempt+1} failed: {e}")
                time.sleep(1)

    # Intelligent Dynamic Engine
    msg = user_message.strip()
    msg_lower = msg.lower()
    
    # 1. Check for specific minute inquiries (e.g. "৫ মিনিট", "5 min", "২ মিনিটের জন্য কত")
    import re
    bengali_digits = {'০':'0', '১':'1', '২':'2', '৩':'3', '৪':'4', '৫':'5', '৬':'6', '৭':'7', '৮':'8', '৯':'9'}
    normalized_msg = ''
    for char in msg:
        normalized_msg += bengali_digits.get(char, char)
    
    minute_match = re.search(r'(\d+)\s*(?:মিনিট|min)', normalized_msg, re.IGNORECASE)
    if minute_match:
        mins = int(minute_match.group(1))
        en_to_bn = str.maketrans('0123456789', '০১২৩৪৫৬৭৮৯')
        if mins <= 1:
            total_cost = 1500
            breakdown_text = "১ম মিনিট ১,৫০০ টাকা"
        else:
            extra = mins - 1
            extra_cost = extra * 1000
            total_cost = 1500 + extra_cost
            extra_bn = str(extra).translate(en_to_bn)
            extra_cost_bn = f"{extra_cost:,}".translate(en_to_bn)
            breakdown_text = f"১ম মিনিট ১,৫০০ টাকা + পরবর্তী {extra_bn} মিনিটের জন্য {extra_cost_bn} টাকা"
        
        mins_bn = str(mins).translate(en_to_bn)
        total_cost_bn = f"{total_cost:,}".translate(en_to_bn)
        
        return (
            f"প্রিয় {user_name},\n"
            f"আপনার {mins_bn} মিনিটের কাব্যনাট্য তৈরির জন্য মোট ব্যয় হবে {total_cost_bn} টাকা ({breakdown_text})।\n\n"
            "এই খরচের মধ্যে যা যা অন্তর্ভুক্ত থাকবে:\n"
            "• অভিজ্ঞ কণ্ঠশিল্পী দিয়ে প্রফেশনাল আবৃত্তি রেকর্ড\n"
            "• কবিতার আবেগ অনুযায়ী সিনেম্যাটিক ভিজ্যুয়াল কম্পোজিশন\n"
            "• ব্যাকগ্রাউন্ড মিউজিক ও সাউন্ড ডিজাইন\n"
            "• ফুল এইচডি কালার ও ফাইনাল ভিডিও এডিটিং\n\n"
            "সময় লাগবে সাধারণত ৩ থেকে ৫ দিন। আপনার কবিতা, নাম ও ছবি সহ সরাসরি হোয়াটসঅ্যাপে জমা দিয়ে কনফার্ম করতে পারেন: 01409350858 (https://wa.me/8801409350858)\n"
            "বিস্তারিত দেখতে ভিজিট করুন: https://poddopaataa.dreamakerbd.com/PPS03/"
        )

    # 2. Check for word count inquiries
    word_match = re.search(r'(\d+)\s*(?:শব্দ|word)', normalized_msg, re.IGNORECASE)
    if word_match:
        words = int(word_match.group(1))
        estimated_mins = max(1, round(words / 160))
        estimated_cost = 1500 if estimated_mins == 1 else 1500 + ((estimated_mins - 1) * 1000)
        return (
            f"প্রিয় {user_name},\n"
            f"সাধারণত ১ মিনিটে ১৫০ থেকে ১৮০ শব্দ আবৃত্তি করা যায়। সেই হিসাবে আপনার {words} শব্দের কবিতার জন্য আনুমানিক {estimated_mins} মিনিটের কাব্যনাট্য হবে।\n\n"
            f"আনুমানিক ব্যয়: {estimated_cost:,} টাকা।\n"
            "আপনার কবিতাটি আমাদের হোয়াটসঅ্যাপে পাঠালে আমরা পড়ে সঠিক দৈর্ঘ্য ও খরচের হিসাব জানিয়ে দেব: 01409350858 (https://wa.me/8801409350858)\n"
            "ওয়েবসাইট: https://poddopaataa.dreamakerbd.com/PPS03/"
        )

    # 3. WhatsApp / Phone / Contact inquiries
    if any(w in msg_lower for w in ["হোয়াটসঅ্যাপ", "হোয়াটসঅ্যাপ", "whatsapp", "নম্বর", "নাম্বার", "ফোন", "যোগাযোগ", "contact"]):
        return (
            f"প্রিয় {user_name},\n"
            "পদ্যপাতার অফিসিয়াল হোয়াটসঅ্যাপ নম্বর: 01409350858\n"
            "সরাসরি চ্যাট করতে ক্লিক করুন: https://wa.me/8801409350858\n\n"
            "কবিদের হোয়াটসঅ্যাপ গ্রুপে যুক্ত হতে পারেন: https://chat.whatsapp.com/BYga8IgbM31B1L2nlwDXa8\n"
            "ওয়েবসাইট: https://poddopaataa.dreamakerbd.com/PPS03/"
        )

    # 4. Delivery time inquiries
    if any(w in msg_lower for w in ["সময়", "কতদিন", "কত দিন", "কবে", "কত সময়", "কতো দিন", "সময় লাগবে"]):
        return (
            f"প্রিয় {user_name},\n"
            "কবিতা জমা দেওয়ার পর সাধারণত ৩ থেকে ৫ কার্যদিবসের মধ্যে আপনার পূর্ণাঙ্গ কাব্যনাট্য তৈরি হয়ে যায়।\n\n"
            "রেডি ভিডিও ফাইল আপনাকে ফুল এইচডিতে দেওয়া হবে এবং আমাদের ইউটিউব চ্যানেলেও প্রচার করা হবে।\n"
            "কবিতা জমা দিতে আমাদের হোয়াটসঅ্যাপে যোগাযোগ করুন: 01409350858 (https://wa.me/8801409350858)\n"
            "ওয়েবসাইট: https://poddopaataa.dreamakerbd.com/PPS03/"
        )

    # 5. General pricing inquiries (without specific minutes)
    if any(w in msg_lower for w in ["টাকা", "খরচ", "কত টাকা", "কতো টাকা", "রেট", "মূল্য", "প্রাইজ", "ফি", "ব্যায়", "ব্যয়", "কত"]):
        return (
            f"প্রিয় {user_name},\n"
            "পদ্যপাতায় কবিতা থেকে কাব্যনাট্য তৈরির স্বচ্ছ ব্যয় তালিকা:\n"
            "• ১ম মিনিট: ১,৫০০ টাকা (আবৃত্তি ৫০০৳ + ভিজ্যুয়াল ৭০০৳ + সাউন্ড ১০০৳ + এডিটিং ২০০৳)\n"
            "• পরবর্তী প্রতি অতিরিক্ত মিনিট: ১,০০০ টাকা করে\n\n"
            "উদাহরণ হিসাব:\n"
            "  - ১ মিনিট = ১,৫০০ টাকা\n"
            "  - ২ মিনিট = ২,৫০০ টাকা\n"
            "  - ৩ মিনিট = ৩,৫০০ টাকা\n"
            "  - ৫ মিনিট = ৫,৫০০ টাকা\n\n"
            "আপনার কবিতার দৈর্ঘ্য (মিনিট বা শব্দের সংখ্যা) জানালে আমরা নির্দিষ্ট হিসাব করে দিতে পারি। কবিতা জমা দিতে যোগাযোগ করুন: WhatsApp 01409350858\n"
            "বিস্তারিত: https://poddopaataa.dreamakerbd.com/PPS03/"
        )

    # 6. Submission guidelines
    if any(w in msg_lower for w in ["কীভাবে", "কিভাবে", "নিয়ম", "জমা", "পাঠাবো", "পাঠাব", "প্রক্রিয়া", "পদ্ধতি"]):
        return (
            f"প্রিয় {user_name},\n"
            "কাব্যনাট্য তৈরির জন্য আপনার কবিতা জমা দেওয়ার নিয়ম:\n"
            "১. কবিতার টেক্সট (কোনো রাজনৈতিক বা ধর্মীয় বিদ্বেষমূলক কবিতা ব্যতীত)\n"
            "২. আপনার নাম ও একটি স্পষ্ট ছবি\n"
            "৩. সংক্ষিপ্ত কবি পরিচিতি ও যোগাযোগ নম্বর\n\n"
            "এগুলো সরাসরি আমাদের হোয়াটসঅ্যাপে পাঠিয়ে দিন: 01409350858 (https://wa.me/8801409350858)\n"
            "বিস্তারিত নিয়মাবলী দেখুন: https://poddopaataa.dreamakerbd.com/PPS03/"
        )

    # 7. YouTube channel
    if any(w in msg_lower for w in ["চ্যানেল", "ইউটিউব", "youtube", "ভিডিও", "নমুনা", "স্যাম্পল"]):
        return (
            f"প্রিয় {user_name},\n"
            "আমাদের নির্মিত পূর্ববর্তী কাব্যনাট্যগুলো দেখতে পদ্যপাতা ইউটিউব চ্যানেল ভিজিট করুন:\n"
            "👉 https://www.youtube.com/@Poddopaataa\n\n"
            "পদ্যপাতায় আপনার কবিতাটিও এমন দারুণ ভিজ্যুয়াল ও আবৃত্তিতে তৈরি করতে হোয়াটসঅ্যাপে যোগাযোগ করুন: 01409350858"
        )

    # Default welcoming response
    return (
        f"প্রিয় {user_name},\n"
        "পদ্যপাতায় আপনাকে স্বাগতম! আমরা আপনার প্রিয় কবিতাকে প্রফেশনাল আবৃত্তি, সিনেম্যাটিক ভিজ্যুয়াল ও সাউন্ড ডিজাইনের মাধ্যমে একটি পূর্ণাঙ্গ 'কাব্যনাট্য'-এ রূপ দিই।\n\n"
        "• ব্যয়: ১ম মিনিট ১,৫০০ টাকা, পরবর্তী প্রতি অতিরিক্ত মিনিট ১,০০০ টাকা\n"
        "• ডেলিভারি সময়: ৩–৫ দিন\n\n"
        "আপনার কবিতা নিয়ে সরাসরি কথা বলতে বা জমা দিতে আমাদের হোয়াটসঅ্যাপে নক দিন: 01409350858 (https://wa.me/8801409350858)\n"
        "বিস্তারিত তথ্য: https://poddopaataa.dreamakerbd.com/PPS03/"
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
                    
                    user_desc = "কবি"
                    logger.info(f"Incoming message from {sender_id}: '{msg_text}' (Attachments: {len(attachments)})")

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


# Background inbox listener for guaranteed zero-delay responses (works regardless of Meta Unpublished mode)
processed_message_ids = set()

def start_background_poller():
    """Continuously monitors conversations and replies within seconds."""
    import time
    logger.info("Starting background auto-reply engine for Poddopaataa...")
    
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
