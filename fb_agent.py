"""
Facebook Automation Agent
Automates Facebook Pages via Meta Graph API:
- Multi-page management
- Publishing status, photos, videos, links
- Post scheduling
- Reading feed, comments, reactions
- Replying to comments
- Page insights and analytics
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
import requests
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

GRAPH_API_VERSION = "v20.0"
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
VIDEO_GRAPH_URL = f"https://graph-video.facebook.com/{GRAPH_API_VERSION}"


class FacebookAgent:
    def __init__(self, pages_file: Optional[str] = None):
        self.pages_file = Path(pages_file) if pages_file else BASE_DIR / "facebook_pages.json"
        self.pages: Dict[str, Dict[str, Any]] = {}
        self.app_id = os.getenv("APP_ID", "")
        self.app_secret = os.getenv("APP_SECRET", "")
        self.user_token = os.getenv("USER_ACCESS_TOKEN", "")
        self.default_page_id = os.getenv("DEFAULT_PAGE_ID", "")
        self.load_pages()

    def load_pages(self) -> None:
        """Load cached pages or fetch fresh list from Graph API."""
        if self.pages_file.exists():
            try:
                with open(self.pages_file, "r", encoding="utf-8") as f:
                    self.pages = json.load(f)
            except Exception as e:
                print(f"[Warning] Failed to load {self.pages_file}: {e}")

        if not self.pages and self.user_token:
            self.refresh_pages()

    def refresh_pages(self) -> Dict[str, Dict[str, Any]]:
        """Fetch fresh pages and tokens from Meta Graph API using user token."""
        url = f"{GRAPH_URL}/me/accounts"
        params = {
            "fields": "name,id,access_token,category,tasks",
            "limit": 100,
            "access_token": self.user_token
        }
        res = requests.get(url, params=params)
        res.raise_for_status()
        data = res.json().get("data", [])
        
        pages_dict = {}
        for p in data:
            pages_dict[p["id"]] = {
                "id": p["id"],
                "name": p["name"],
                "category": p.get("category"),
                "access_token": p["access_token"]
            }
        
        self.pages = pages_dict
        with open(self.pages_file, "w", encoding="utf-8") as f:
            json.dump(self.pages, f, ensure_ascii=False, indent=2)
        return self.pages

    def resolve_page(self, identifier: Optional[str] = None) -> Dict[str, Any]:
        """
        Find a page by ID or partial name match. Defaults to DEFAULT_PAGE_ID.
        """
        target = identifier or self.default_page_id
        if not target and self.pages:
            # Pick first available page
            target = list(self.pages.keys())[0]

        if not target:
            raise ValueError("No Facebook page identifier provided and no default page configured.")

        # Check exact ID match
        if target in self.pages:
            return self.pages[target]

        # Check name search (case-insensitive partial match)
        target_lower = str(target).strip().lower()
        for page_id, info in self.pages.items():
            if target_lower == info["name"].lower():
                return info
            if target_lower in info["name"].lower():
                return info

        raise ValueError(f"Page '{identifier}' not found in connected pages list.")

    def list_pages(self) -> List[Dict[str, Any]]:
        """Return list of all configured pages."""
        return list(self.pages.values())

    def get_page_details(self, page_id_or_name: Optional[str] = None) -> Dict[str, Any]:
        """Fetch live details for a page from Facebook Graph API."""
        page = self.resolve_page(page_id_or_name)
        url = f"{GRAPH_URL}/{page['id']}"
        params = {
            "fields": "id,name,about,fan_count,followers_count,link,verification_status",
            "access_token": page["access_token"]
        }
        res = requests.get(url, params=params)
        res.raise_for_status()
        return res.json()

    def post_text(
        self,
        message: str,
        page_id_or_name: Optional[str] = None,
        link: Optional[str] = None,
        schedule_time: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Publish a text / link status update to the page.
        Supports post scheduling via epoch timestamp (schedule_time).
        """
        page = self.resolve_page(page_id_or_name)
        url = f"{GRAPH_URL}/{page['id']}/feed"
        payload = {
            "message": message,
            "access_token": page["access_token"]
        }
        if link:
            payload["link"] = link

        if schedule_time:
            payload["published"] = False
            payload["scheduled_publish_time"] = schedule_time
        else:
            payload["published"] = True

        res = requests.post(url, data=payload)
        res.raise_for_status()
        return {"success": True, "page": page["name"], "page_id": page["id"], "result": res.json()}

    def post_photo(
        self,
        image_path_or_url: str,
        caption: str = "",
        page_id_or_name: Optional[str] = None,
        schedule_time: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Upload and publish a photo to the page (supports local file path or public image URL).
        """
        page = self.resolve_page(page_id_or_name)
        url = f"{GRAPH_URL}/{page['id']}/photos"
        
        data = {
            "caption": caption,
            "access_token": page["access_token"]
        }
        if schedule_time:
            data["published"] = False
            data["scheduled_publish_time"] = schedule_time
        else:
            data["published"] = True

        # Check if local file exists
        local_file = Path(image_path_or_url)
        if local_file.exists() and local_file.is_file():
            with open(local_file, "rb") as img_f:
                files = {"source": img_f}
                res = requests.post(url, data=data, files=files)
        else:
            # Treat as public image URL
            data["url"] = image_path_or_url
            res = requests.post(url, data=data)

        res.raise_for_status()
        return {"success": True, "page": page["name"], "page_id": page["id"], "result": res.json()}

    def post_video(
        self,
        video_path: str,
        title: str = "",
        description: str = "",
        page_id_or_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a video to the page.
        """
        page = self.resolve_page(page_id_or_name)
        video_file = Path(video_path)
        if not video_file.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        url = f"{VIDEO_GRAPH_URL}/{page['id']}/videos"
        data = {
            "title": title,
            "description": description,
            "access_token": page["access_token"]
        }
        with open(video_file, "rb") as vf:
            files = {"source": vf}
            res = requests.post(url, data=data, files=files)

        res.raise_for_status()
        return {"success": True, "page": page["name"], "page_id": page["id"], "result": res.json()}

    def get_feed(self, page_id_or_name: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve recent posts with engagement stats (reactions, comments, shares).
        """
        page = self.resolve_page(page_id_or_name)
        url = f"{GRAPH_URL}/{page['id']}/feed"
        params = {
            "fields": "id,message,created_time,shares,reactions.summary(true),comments.summary(true)",
            "limit": limit,
            "access_token": page["access_token"]
        }
        res = requests.get(url, params=params)
        res.raise_for_status()
        return res.json().get("data", [])

    def get_comments(self, post_id: str, page_id_or_name: Optional[str] = None, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Retrieve comments for a given post.
        """
        page = self.resolve_page(page_id_or_name)
        url = f"{GRAPH_URL}/{post_id}/comments"
        params = {
            "fields": "id,from,message,created_time,like_count",
            "limit": limit,
            "access_token": page["access_token"]
        }
        res = requests.get(url, params=params)
        res.raise_for_status()
        return res.json().get("data", [])

    def reply_comment(self, comment_id: str, message: str, page_id_or_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Reply to a comment on a page post.
        """
        page = self.resolve_page(page_id_or_name)
        url = f"{GRAPH_URL}/{comment_id}/comments"
        payload = {
            "message": message,
            "access_token": page["access_token"]
        }
        res = requests.post(url, data=payload)
        res.raise_for_status()
        return {"success": True, "result": res.json()}

    def delete_object(self, object_id: str, page_id_or_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Delete a post or comment by its ID.
        """
        page = self.resolve_page(page_id_or_name)
        url = f"{GRAPH_URL}/{object_id}"
        params = {"access_token": page["access_token"]}
        res = requests.delete(url, params=params)
        res.raise_for_status()
        return {"success": True, "result": res.json()}

    def get_page_insights(
        self,
        page_id_or_name: Optional[str] = None,
        period: str = "day"
    ) -> Dict[str, Any]:
        """
        Get high-level page insights & performance metrics.
        """
        page = self.resolve_page(page_id_or_name)
        url = f"{GRAPH_URL}/{page['id']}/insights"
        metrics = "page_impressions,page_engaged_users,page_post_engagements"
        params = {
            "metric": metrics,
            "period": period,
            "access_token": page["access_token"]
        }
        try:
            res = requests.get(url, params=params)
            res.raise_for_status()
            return res.json()
        except requests.HTTPError as e:
            return {"error": str(e), "note": "Insights data may require active page activity over 24-48 hours."}

    def get_conversations(
        self,
        page_id_or_name: Optional[str] = None,
        limit: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent Messenger conversations with participants and latest messages.
        """
        page = self.resolve_page(page_id_or_name)
        url = f"{GRAPH_URL}/{page['id']}/conversations"
        params = {
            "fields": "id,link,updated_time,participants,messages.limit(2){id,message,from,created_time,attachments}",
            "limit": limit,
            "access_token": page["access_token"]
        }
        res = requests.get(url, params=params)
        res.raise_for_status()
        return res.json().get("data", [])

    def get_conversation_messages(
        self,
        conversation_id: str,
        page_id_or_name: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve messages history inside a specific Messenger conversation.
        """
        page = self.resolve_page(page_id_or_name)
        url = f"{GRAPH_URL}/{conversation_id}"
        params = {
            "fields": f"participants,messages.limit({limit}){{id,message,from,created_time,attachments}}",
            "access_token": page["access_token"]
        }
        res = requests.get(url, params=params)
        res.raise_for_status()
        return res.json()

    def send_messenger_message(
        self,
        recipient_id: str,
        message: str,
        page_id_or_name: Optional[str] = None,
        tag: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Send a direct Messenger message to a user (recipient_id is user PSID).
        Note: Meta enforces a 24-hour messaging window. If outside 24h, a valid tag or human agent permission is required.
        """
        page = self.resolve_page(page_id_or_name)
        url = f"{GRAPH_URL}/{page['id']}/messages"
        payload: Dict[str, Any] = {
            "recipient": {"id": recipient_id},
            "message": {"text": message}
        }
        if tag:
            payload["messaging_type"] = "MESSAGE_TAG"
            payload["tag"] = tag
        else:
            payload["messaging_type"] = "RESPONSE"

        res = requests.post(
            url,
            params={"access_token": page["access_token"]},
            json=payload
        )
        res.raise_for_status()
        return {"success": True, "result": res.json()}


if __name__ == "__main__":
    agent = FacebookAgent()
    pages = agent.list_pages()
    print(f"Loaded {len(pages)} Facebook Pages successfully:")
    for p in pages:
        print(f"- {p['name']} (ID: {p['id']})")
