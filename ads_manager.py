"""
Meta Facebook Ads Management Engine
Automates Facebook Ad campaigns, ad sets, ads, budgets, and reporting via Marketing API.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests
from dotenv import load_dotenv

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

GRAPH_API_VERSION = "v20.0"
GRAPH_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


class FacebookAdsManager:
    def __init__(self, ad_account_id: Optional[str] = None):
        self.user_token = os.getenv("USER_ACCESS_TOKEN", "")
        self.default_account_id = ad_account_id or "act_743060607284727"

    def list_ad_accounts(self) -> List[Dict[str, Any]]:
        """List all Ad Accounts accessible by this user."""
        url = f"{GRAPH_URL}/me/adaccounts"
        params = {
            "fields": "id,name,account_id,account_status,currency,amount_spent,balance",
            "access_token": self.user_token
        }
        res = requests.get(url, params=params)
        res.raise_for_status()
        return res.json().get("data", [])

    def list_campaigns(self, account_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """List campaigns in the specified Ad Account."""
        act_id = account_id or self.default_account_id
        url = f"{GRAPH_URL}/{act_id}/campaigns"
        params = {
            "fields": "id,name,status,objective,daily_budget,lifetime_budget,start_time,stop_time",
            "limit": limit,
            "access_token": self.user_token
        }
        res = requests.get(url, params=params)
        res.raise_for_status()
        return res.json().get("data", [])

    def get_campaign_insights(
        self,
        account_id: Optional[str] = None,
        date_preset: str = "last_30d",
        level: str = "campaign"
    ) -> List[Dict[str, Any]]:
        """Retrieve performance insights: spend, impressions, clicks, CPC, CPM."""
        act_id = account_id or self.default_account_id
        url = f"{GRAPH_URL}/{act_id}/insights"
        params = {
            "fields": "campaign_name,impressions,clicks,spend,cpc,cpm,actions",
            "date_preset": date_preset,
            "level": level,
            "access_token": self.user_token
        }
        res = requests.get(url, params=params)
        res.raise_for_status()
        return res.json().get("data", [])

    def set_campaign_status(self, campaign_id: str, status: str = "PAUSED") -> Dict[str, Any]:
        """
        Update campaign status: 'ACTIVE' or 'PAUSED'.
        """
        url = f"{GRAPH_URL}/{campaign_id}"
        payload = {
            "status": status.upper(),
            "access_token": self.user_token
        }
        res = requests.post(url, data=payload)
        res.raise_for_status()
        return res.json()


if __name__ == "__main__":
    mgr = FacebookAdsManager()
    accounts = mgr.list_ad_accounts()
    print(f"Connected Ad Accounts ({len(accounts)}):")
    for a in accounts:
        print(f"- {a['name']} ({a['id']}) | Currency: {a.get('currency')} | Spent: {int(a.get('amount_spent', 0))/100:.2f}")

    print("\nRecent Campaigns on Default Account:")
    camps = mgr.list_campaigns(limit=5)
    for c in camps:
        print(f"- {c['name']} [{c['status']}] (ID: {c['id']})")
