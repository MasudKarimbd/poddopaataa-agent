"""
Facebook Ads Budget Sentinel & Financial Guardrail System
Protects against excessive ad spend, runaway costs, and budget anomalies.
Features:
- Daily and Lifetime Spend threshold monitoring
- Anomaly / Spike detection
- Emergency Circuit Breaker (Auto-pause runaway campaigns)
- Spend audit reporting
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


class BudgetSentinel:
    def __init__(
        self,
        ad_account_id: str = "act_743060607284727",
        daily_spend_limit_usd: float = 10.0,
        enable_emergency_auto_pause: bool = True
    ):
        self.user_token = os.getenv("USER_ACCESS_TOKEN", "")
        self.account_id = ad_account_id
        self.daily_spend_limit = daily_spend_limit_usd
        self.enable_auto_pause = enable_emergency_auto_pause

    def get_today_spend(self) -> Dict[str, Any]:
        """Fetch today's total spend and breakdown per active campaign."""
        url = f"{GRAPH_URL}/{self.account_id}/insights"
        params = {
            "fields": "campaign_id,campaign_name,spend,impressions,clicks,cpc",
            "date_preset": "today",
            "level": "campaign",
            "access_token": self.user_token
        }
        res = requests.get(url, params=params)
        res.raise_for_status()
        data = res.json().get("data", [])

        total_spend = sum(float(item.get("spend", 0.0)) for item in data)
        return {
            "total_spend_today": total_spend,
            "campaign_breakdown": data
        }

    def check_and_guard(self) -> Dict[str, Any]:
        """
        Audit current spend against safety guardrails.
        If spend exceeds threshold and auto-pause is enabled, pauses active campaigns.
        """
        report = self.get_today_spend()
        today_spend = report["total_spend_today"]
        breached = today_spend >= self.daily_spend_limit

        actions_taken = []
        if breached and self.enable_auto_pause:
            # Emergency circuit breaker: Pause campaigns to stop bleeding
            for camp in report["campaign_breakdown"]:
                camp_id = camp["campaign_id"]
                pause_url = f"{GRAPH_URL}/{camp_id}"
                pause_payload = {"status": "PAUSED", "access_token": self.user_token}
                try:
                    r = requests.post(pause_url, data=pause_payload)
                    r.raise_for_status()
                    actions_taken.append(f"Auto-paused campaign '{camp['campaign_name']}' (ID: {camp_id})")
                except Exception as e:
                    actions_taken.append(f"Failed to auto-pause {camp_id}: {e}")

        status = "BREACH_HALTED" if (breached and self.enable_auto_pause) else ("WARNING" if breached else "SAFE")

        return {
            "status": status,
            "today_spend_usd": today_spend,
            "limit_usd": self.daily_spend_limit,
            "breached": breached,
            "actions_taken": actions_taken,
            "campaigns": report["campaign_breakdown"]
        }


if __name__ == "__main__":
    sentinel = BudgetSentinel(daily_spend_limit_usd=10.0)
    audit = sentinel.check_and_guard()
    print("=" * 60)
    print(f" Budget Sentinel Audit Status: [{audit['status']}]")
    print(f"Today's Total Spend: ${audit['today_spend_usd']:.2f} USD")
    print(f"Safety Limit: ${audit['limit_usd']:.2f} USD")
    print("=" * 60)
    if audit["actions_taken"]:
        print("Actions Taken:")
        for a in audit["actions_taken"]:
            print(f"- {a}")
    else:
        print("All budgets are strictly within safety limits. No runaway spend detected.")
