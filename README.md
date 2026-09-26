# Facebook Page Automation Suite

An automated Meta Graph API engine for managing Facebook Pages, publishing posts/photos/videos, moderating comments, and monitoring insights.

## Connected Pages (9 Total)
1. **DreaMaker** (ID: `2424138970931747`, URL: `facebook.com/dreamakerbd`)
2. **DreaMaker Entertainment** (ID: `887212307811163`)
3. **জয় বাংলাদেশ** (ID: `725678557299926`)
4. **TANIS Bangladesh** (ID: `665859680531047`)
5. **পদ্যপাতা** (ID: `377657402757335`)
6. **DreaMaker Shop** (ID: `356267878167652`)
7. **Masud Karim** (ID: `2028638667408363`)
8. **DreaMaker Infotainment** (ID: `165509230193146`)
9. **Shakh** (ID: `550506388439397`)

---

## Capabilities
- **Multi-Page Management**: Select and operate across any of the connected pages.
- **Publish Status Posts**: Publish text updates with or without links.
- **Publish Photos**: Upload local images or publish web image URLs.
- **Publish Videos**: Direct upload to Meta Video Graph API.
- **Post Scheduling**: Specify UNIX timestamp to schedule posts in the future.
- **Feed & Engagement**: View recent posts with reaction counts, comments, and shares.
- **Comment Moderation**: Read comments and reply directly as the page.
- **Post Deletion**: Delete posts or comments by ID.
- **Page Insights**: Track followers, impressions, and engagements.
- **Budget Sentinel & Safety Guardrail**: Real-time spend monitoring with Emergency Circuit Breaker (auto-pauses campaigns if daily budget threshold is exceeded to prevent overspending).

---

## File Structure
- [`.env`](file:///h:/Social%20Midia%20Marketing/.env): Stores API keys, User Access Token, and default Page ID.
- [`facebook_pages.json`](file:///h:/Social%20Midia%20Marketing/facebook_pages.json): Cached mapping of Page names, IDs, categories, and Page Access Tokens.
- [`fb_agent.py`](file:///h:/Social%20Midia%20Marketing/fb_agent.py): Core Python agent class (`FacebookAgent`) providing all API methods.
- [`cli.py`](file:///h:/Social%20Midia%20Marketing/cli.py): CLI interface to run commands directly from terminal or via agent instructions.

---

## CLI Usage Examples

### 1. List all connected pages
```bash
python cli.py list
```

### 2. View page info and follower count
```bash
python cli.py info --page "DreaMaker Entertainment"
```

### 3. Publish a text post
```bash
python cli.py post --page "DreaMaker Entertainment" --text "Welcome to our page! Stay tuned for upcoming creative projects."
```

### 4. Publish a photo post
```bash
python cli.py post-photo --page "DreaMaker Entertainment" --photo "C:\path\to\image.jpg" --caption "Our latest visual artwork."
```

### 5. View recent posts
```bash
python cli.py feed --page "DreaMaker Entertainment" --limit 5
```

### 6. View comments on a post
```bash
python cli.py comments --page "DreaMaker Entertainment" --post "<POST_ID>"
```

### 7. Reply to a comment
```bash
python cli.py reply --page "DreaMaker Entertainment" --comment "<COMMENT_ID>" --text "ধন্যবাদ আপনার সুন্দর মন্তব্যের জন্য!"
```

### 8. View Messenger conversations
```bash
python cli.py messages --page "পদ্যপাতা" --limit 10
```

### 9. Send a Messenger message / reply
```bash
python cli.py send-message --page "পদ্যপাতা" --recipient "<USER_PSID>" --text "আপনার মেসেজের জন্য ধন্যবাদ!"
```
*(নোট: মেটা-র ২৪ ঘণ্টার পলিসি প্রযোজ্য।)*
