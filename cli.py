"""
Command Line Interface for Facebook Automation Suite
Usage examples:
    python cli.py list
    python cli.py info --page "DreaMaker Entertainment"
    python cli.py post --page "DreaMaker Entertainment" --text "Welcome to our page!"
    python cli.py post-photo --page "DreaMaker Entertainment" --photo "banner.jpg" --caption "New visual"
    python cli.py feed --page "DreaMaker Entertainment" --limit 5
    python cli.py delete --page "DreaMaker Entertainment" --id "12345_67890"
"""

import sys
import argparse
import json
from fb_agent import FacebookAgent

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description="Facebook Page Automation CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available sub-commands")

    # Command: list
    subparsers.add_parser("list", help="List all managed Facebook pages")

    # Command: info
    info_p = subparsers.add_parser("info", help="Get live page details and follower count")
    info_p.add_argument("--page", type=str, required=False, help="Page name or ID")

    # Command: post
    post_p = subparsers.add_parser("post", help="Publish text status update to a page")
    post_p.add_argument("--page", type=str, required=False, help="Page name or ID")
    post_p.add_argument("--text", type=str, required=True, help="Post text content")
    post_p.add_argument("--link", type=str, required=False, help="Optional URL link attachment")

    # Command: post-photo
    photo_p = subparsers.add_parser("post-photo", help="Upload and publish a photo")
    photo_p.add_argument("--page", type=str, required=False, help="Page name or ID")
    photo_p.add_argument("--photo", type=str, required=True, help="Local image file path or web image URL")
    photo_p.add_argument("--caption", type=str, default="", help="Photo caption text")

    # Command: feed
    feed_p = subparsers.add_parser("feed", help="View recent posts on page")
    feed_p.add_argument("--page", type=str, required=False, help="Page name or ID")
    feed_p.add_argument("--limit", type=int, default=5, help="Number of posts to retrieve")

    # Command: comments
    comm_p = subparsers.add_parser("comments", help="View comments on a post")
    comm_p.add_argument("--page", type=str, required=False, help="Page name or ID")
    comm_p.add_argument("--post", type=str, required=True, help="Post ID")

    # Command: reply
    reply_p = subparsers.add_parser("reply", help="Reply to a comment")
    reply_p.add_argument("--page", type=str, required=False, help="Page name or ID")
    reply_p.add_argument("--comment", type=str, required=True, help="Comment ID")
    reply_p.add_argument("--text", type=str, required=True, help="Reply text")

    # Command: delete
    del_p = subparsers.add_parser("delete", help="Delete a post or comment")
    del_p.add_argument("--page", type=str, required=False, help="Page name or ID")
    del_p.add_argument("--id", type=str, required=True, help="Post or comment ID to delete")

    # Command: messages
    msg_p = subparsers.add_parser("messages", help="List recent Messenger conversations")
    msg_p.add_argument("--page", type=str, required=False, help="Page name or ID")
    msg_p.add_argument("--limit", type=int, default=10, help="Number of conversations to retrieve")

    # Command: send-message
    send_msg_p = subparsers.add_parser("send-message", help="Send a Messenger message to a user")
    send_msg_p.add_argument("--page", type=str, required=False, help="Page name or ID")
    send_msg_p.add_argument("--recipient", type=str, required=True, help="Recipient user PSID")
    send_msg_p.add_argument("--text", type=str, required=True, help="Message text to send")
    send_msg_p.add_argument("--tag", type=str, required=False, help="Optional Meta message tag (e.g. HUMAN_AGENT)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    agent = FacebookAgent()

    try:
        if args.command == "list":
            pages = agent.list_pages()
            print("\n Connected Facebook Pages:")
            print("=" * 60)
            for idx, p in enumerate(pages, 1):
                print(f"{idx}. {p['name']}")
                print(f"   ID: {p['id']}")
                print(f"   Category: {p.get('category', 'N/A')}")
                print("-" * 60)

        elif args.command == "info":
            info = agent.get_page_details(args.page)
            print("\n Page Details:")
            print("=" * 60)
            print(f"Name: {info.get('name')}")
            print(f"ID: {info.get('id')}")
            print(f"Followers: {info.get('followers_count', info.get('fan_count', 'N/A'))}")
            print(f"About: {info.get('about', 'N/A')}")
            print(f"Link: {info.get('link', 'N/A')}")
            print("=" * 60)

        elif args.command == "post":
            res = agent.post_text(message=args.text, page_id_or_name=args.page, link=args.link)
            print(f" Success! Post published to '{res['page']}'")
            print(f"Post ID: {res['result'].get('id')}")

        elif args.command == "post-photo":
            res = agent.post_photo(image_path_or_url=args.photo, caption=args.caption, page_id_or_name=args.page)
            print(f" Success! Photo published to '{res['page']}'")
            print(f"Photo Post ID: {res['result'].get('id')}")

        elif args.command == "feed":
            posts = agent.get_feed(page_id_or_name=args.page, limit=args.limit)
            print(f"\n Recent Posts ({len(posts)}):")
            print("=" * 60)
            for p in posts:
                print(f"Post ID: {p.get('id')}")
                print(f"Time: {p.get('created_time')}")
                print(f"Message: {p.get('message', '[Media / No text]')}")
                print("-" * 60)

        elif args.command == "comments":
            comments = agent.get_comments(post_id=args.post, page_id_or_name=args.page)
            print(f"\n Comments on Post {args.post}:")
            print("=" * 60)
            for c in comments:
                user = c.get("from", {}).get("name", "Unknown")
                print(f"From: {user} (ID: {c.get('id')})")
                print(f"Message: {c.get('message')}")
                print("-" * 60)

        elif args.command == "reply":
            res = agent.reply_comment(comment_id=args.comment, message=args.text, page_id_or_name=args.page)
            print(f" Replied successfully! Comment ID: {res['result'].get('id')}")

        elif args.command == "delete":
            res = agent.delete_object(object_id=args.id, page_id_or_name=args.page)
            print(f" Successfully deleted object {args.id}")

        elif args.command == "messages":
            convs = agent.get_conversations(page_id_or_name=args.page, limit=args.limit)
            target_page = agent.resolve_page(args.page)
            page_id = target_page["id"]
            print(f"\n Messenger Conversations for '{target_page['name']}' ({len(convs)}):")
            print("=" * 60)
            for idx, c in enumerate(convs, 1):
                parts = c.get("participants", {}).get("data", [])
                user_part = [p for p in parts if p["id"] != page_id]
                user_name = user_part[0]["name"] if user_part else "Unknown"
                user_psid = user_part[0]["id"] if user_part else "N/A"
                inbox_link = f"https://www.facebook.com{c.get('link', '')}" if c.get("link") else "N/A"
                
                msgs = c.get("messages", {}).get("data", [])
                last_msg_text = msgs[0].get("message", "[Media / Attachment]") if msgs else "[No message]"
                sender = msgs[0].get("from", {}).get("name", "Unknown") if msgs else ""
                created = msgs[0].get("created_time", "") if msgs else ""
                
                is_from_user = (msgs and msgs[0].get("from", {}).get("id") != page_id)
                status_icon = "🔴 Needs Reply" if is_from_user else "🟢 Replied"

                print(f"{idx}. [{status_icon}] User: {user_name}")
                print(f"   PSID: {user_psid} | Time: {created}")
                print(f"   Inbox Link: {inbox_link}")
                print(f"   Last from {sender}: {last_msg_text}")
                print("-" * 60)

        elif args.command == "send-message":
            res = agent.send_messenger_message(
                recipient_id=args.recipient,
                message=args.text,
                page_id_or_name=args.page,
                tag=args.tag
            )
            print(f" Message sent successfully! Result: {res.get('result')}")

        elif args.command == "guard":
            from budget_guard import BudgetSentinel
            sentinel = BudgetSentinel(daily_spend_limit_usd=args.limit)
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

    except Exception as e:
        print(f" Error: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
