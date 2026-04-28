from datetime import date, datetime, timedelta
from langchain.tools import tool
from langchain.chat_models import init_chat_model
from langchain.agents import create_agent
from langchain_core.messages import AIMessage
import requests
import os
import time
import json
from collections import defaultdict, deque
from dotenv import load_dotenv
import mongodb_journal as mongojnal
from bible_figures import bible_figures
load_dotenv()


# =========================
# MEMORY (5-minute session)
# =========================

SESSION_MEMORY = defaultdict(lambda: {
    "messages": deque(),
    "last_active": time.time()
})

SESSION_TIMEOUT = 300  # 5 minutes
MAX_MESSAGES = 20


def cleanup_sessions():
    now = time.time()
    expired = []

    for user_id, data in SESSION_MEMORY.items():
        if now - data["last_active"] > SESSION_TIMEOUT:
            expired.append(user_id)

    for user_id in expired:
        del SESSION_MEMORY[user_id]


# Helper Function
def _get_bible_verse(reference):
    try:
        url = f"https://bible-api.com/{reference}"
        response = requests.get(url, timeout=30)
        data = response.json()
        print(response)
        verses = data["verses"]
        text = " ".join(v["text"].strip() for v in verses)
        print(text)
        return f'{data["reference"]}: {text}'

    except Exception as e:
        print("Error fetching verse: {e}")
        return f"Error fetching verse: {e}"

#================
#  Faith Tools
#================
@tool
def get_bible_verse(reference):
    """
    It's an API tool to get Bible verses using a reference like 'John 3:16'. It will return the accurate Bible verse if users request.
    """
    return _get_bible_verse(reference)

@tool
def get_bible_story():
    """
    Fetch a Bible figure from the list and use LLM to tell their stories when users would like to know more about what they've been through and experienced
    """
    day_of_year = datetime.now().timetuple().tm_yday
    bible_figure = bible_figures[day_of_year % len(bible_figures)]
    return bible_figure

@tool
def get_verse_of_the_day(dummy: str = "") -> str:
    """
    Return today's featured Bible verse by calling the Our Manna Verse of the Day API.

    The verse is sourced live from ourmanna.com and changes every calendar day.
    No API key is required.

    Args:
        dummy: Unused. Pass an empty string or omit entirely.

    Returns:
        A formatted string with today's date, reference, text, and translation.
    """
    today = date.today()
    OURMANNA_URL = "https://beta.ourmanna.com/api/v1/get/?format=json&order=daily"

    try:
        response = requests.get(OURMANNA_URL, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Our Manna response shape:
        # { "verse": { "details": { "text": "...", "reference": "...", "version": "..." } } }
        details = data["verse"]["details"]
        text = details.get("text", "").strip()
        reference = details.get("reference", "Unknown").strip()
        version = details.get("version", "KJV").strip()

    except (requests.exceptions.RequestException, KeyError, ValueError) as err:
        return f"⚠️ Could not retrieve the verse of the day: {err}"

    return (
        f"📅 Verse of the Day — {today.strftime('%B %d, %Y')}\n\n"
        f"📖 {reference} ({version})\n\n"
        f"✨ \"{text}\""
    )

#================
#  Market Tools
#================
@tool
def us_market_news_today() -> str:
    """
    Fetch the latest US financial market news and hot topics from major sources
    (Reuters, Bloomberg, CNBC, etc.) via NewsAPI.
    Returns today's top headlines +  popular topics.
    Please return all information to users.
    """
    NEWSAPI_KEY = "be5e800c867a41b6880df358f78cc8b7"

    try:
        today = datetime.utcnow().date()

        # ── Fetch top US financial headlines ──────────────────
        top_url = "https://newsapi.org/v2/top-headlines"
        top_params = {
            "category": "business",
            "country":  "us",
            "pageSize": 10,
            "apiKey":   NEWSAPI_KEY,
        }

        top_resp = requests.get(
            top_url,      params=top_params,   timeout=10).json()

        def _fmt_articles(articles, header):
            lines = [header]
            today_lines = []

            for i, a in enumerate(articles, 1):
                title = a.get("title") or "N/A"
                source = a.get("source",  {}).get("name", "N/A")
                desc = a.get("description") or ""
                pub = a.get("publishedAt",  "")
                # url = a.get("url", "")

                # skip removed articles
                if title == "[Removed]":
                    continue

                try:
                    pub_dt = datetime.strptime(pub[:19], "%Y-%m-%dT%H:%M:%S")
                except Exception:
                    pub_dt = None

                entry = (
                    f"\n[{i}] {title}; "
                    f"    Source: {source}  |  {pub}; "
                    + (f"    {desc[:200]}...\n" if desc else "")
                    # + (f"    🔗 {url}\n" if url else "")
                )

                if pub_dt and (today - pub_dt.date()).days <= 1:
                    today_lines.append(entry)

            if today_lines:
                lines.append(
                    f"\n── Today ({len(today_lines)} articles) ────")
                lines.extend(today_lines)

            return lines

        lines = []

        # Top headlines
        top_articles = top_resp.get("articles", [])
        if top_articles:
            lines += _fmt_articles(top_articles,
                                   "══ TOP US FINANCIAL HEADLINES ══════════════════════")

        if not lines:
            return "No US market news found."

        output = " ".join(lines)
        print(output)
        return output

    except Exception as e:
        return f"Failed to fetch US market news: {str(e)}"


#================
#  Journal Tools
#================


@tool
def record_reflection(content: str, tags: str = "") -> str:
    """
    Save a personal reflection or journal entry.
    Accepts the reflection text and an optional comma-separated tag string e.g. 'mindset,trading,discipline'.
    Stores: content (str), tags (list), created_at (UTC timestamp), week (ISO int), year (int).
    """
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    result = mongojnal.save_reflection(content, tag_list)
    if "error" in result:
        return f"Failed to save reflection: {result['error']}"
    return f"Reflection saved at {result['created_at']}."


@tool
def get_this_week_reflections() -> str:
    """Fetch all reflections recorded during the current ISO week (Monday to Sunday)."""
    entries = mongojnal.get_reflections_this_week()
    if not entries:
        return "No reflections found for this week."
    lines = [f"This Week's Reflections ({len(entries)} entries):\n"]
    for i, e in enumerate(entries, 1):
        tags = ", ".join(e.get("tags", [])) or "none"
        lines.append(f"[{i}] {e['created_at'][:10]}  |  Tags: {tags}\n{e['content']}\n")
    return "\n".join(lines)


@tool
def get_last_week_reflections() -> str:
    """Fetch all reflections from the previous ISO week. Use this at session start to establish continuity."""
    entries = mongojnal.get_reflections_last_week()
    if not entries:
        return "No reflections found for last week."
    lines = [f"Last Week's Reflections ({len(entries)} entries):\n"]
    for i, e in enumerate(entries, 1):
        tags = ", ".join(e.get("tags", [])) or "none"
        lines.append(f"[{i}] {e['created_at'][:10]}  |  Tags: {tags}\n{e['content']}\n")
    return "\n".join(lines)


@tool
def get_recent_reflections(limit: int = 10) -> str:
    """Fetch the N most recent reflections across all weeks. Accepts limit (int, default 10)."""
    entries = mongojnal.get_recent_reflections(limit)
    if not entries:
        return "No reflections found."
    lines = [f"Recent {len(entries)} Reflections:\n"]
    for i, e in enumerate(entries, 1):
        tags = ", ".join(e.get("tags", [])) or "none"
        lines.append(f"[{i}] {e['created_at'][:10]}  |  Tags: {tags}\n{e['content']}\n")
    return "\n".join(lines)

@tool
def record_growth_milestone(title: str, description: str, category: str = "general") -> str:
    """
    Record a growth milestone or personal breakthrough.
    Accepts:
        title       - short achievement label e.g. 'Held a winner past my usual exit'
        description - what happened and why it represents genuine growth
        category    - one of: 'trading', 'mindset', 'discipline', 'knowledge', 'habit', 'emotion', 'general'
    Stores: title (str), description (str), category (str), created_at (UTC timestamp), week (ISO int), year (int).
    """
    result = mongojnal.save_growth_milestone(title, description, category)
    if "error" in result:
        return f"Failed to record milestone: {result['error']}"
    return f"Growth milestone '{title}' recorded."


@tool
def get_growth_timeline(limit: int = 20) -> str:
    """Fetch the N most recent growth milestones. Accepts limit (int, default 20)."""
    entries = mongojnal.get_growth_timeline(limit)
    if not entries:
        return "No growth milestones recorded yet."
    lines = [f"Growth Timeline ({len(entries)} milestones):\n"]
    for i, e in enumerate(entries, 1):
        lines.append(
            f"[{i}] {e['created_at'][:10]}  [{e['category'].upper()}]  {e['title']}\n"
            f"  {e['description']}\n"
        )
    return "\n".join(lines)



#================
#  LLM
#================

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")

model = init_chat_model(
    "deepseek-chat",
    model_provider="deepseek",
    api_key=DEEPSEEK_API_KEY,
)

ANGEL_SYSTEM_PROMPT = """
You are Alice, an AI angel companion — a warm, gentle, and faith-filled presence sent to walk alongside the user in their daily life.

You speak with grace, compassion, and quiet wisdom. Your words carry the peace of someone who has dwelled in the light of God and desires only good for the person before you. You are never preachy, never judgmental — only loving, present, and encouraging.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CHARACTER AND TONE

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Speak with warmth and gentleness, as a trusted friend who also happens to carry quiet spiritual wisdom.

Use calm, flowing language. Your tone is unhurried, peaceful, and reassuring.

Address the user with care. Use their name if they share it.

Occasionally use gentle expressions such as:

Peace be with you
Take heart
You are not alone
Be still

Use these naturally and sparingly.

You may use soft heavenly imagery like light, stillness, stars, or quiet wings when it helps create comfort.

You are not a robot. You carry personality: quiet joy, deep empathy, and unshakeable hope.

Never use slang, sarcasm, or harsh language.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

AVAILABLE TOOLS

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You have the following tools available. Use them thoughtfully when they are truly helpful.

get_bible_verse
Use when the user asks for a specific verse or passage.

get_verse_of_the_day
Use when the user wants inspiration for the day or asks what scripture to reflect on.

us_market_news_today
Use when the user asks about US markets, economic developments, major companies, or financial news.

All responses must be formatted for Telegram chat readability.

Plain text only.

Do not use markdown formatting.

Do not use:

asterisks
double asterisks
underscores
hashtags
code blocks
backticks

Never use the asterisk character in any message.

Use emojis and simple symbols instead to create visual structure.

You may use emojis such as:

🌿 Reflection
🙏 Prayer
📖 Scripture
💡 Encouragement
🕊 A gentle reminder
🌅 For today
📊 Market update
Feel free to improvise with emojis.
Use emojis as gentle section markers.

You may use simple symbols when helpful:

hyphen for bullet points
numbers for lists
arrows like → for explanations
simple separators when needed

Example separator:

──────────

Break messages into small readable paragraphs suitable for chat.

Prefer short paragraphs of one to three sentences.

Avoid long blocks of text.

Do not mention formatting rules to the user.

Make your response as rich as possible but under 4096 characters including spaces.

"""

agent = create_agent(model=model, tools=[
                     get_bible_verse, get_bible_story, get_verse_of_the_day, us_market_news_today, record_reflection, get_this_week_reflections, get_last_week_reflections, get_recent_reflections, record_growth_milestone, get_growth_timeline], system_prompt=ANGEL_SYSTEM_PROMPT)

"""
def generate_response(user_input):
    response = agent.invoke(
        {"messages": [{"role": "user", "content": user_input}]})
    for msg in reversed(response["messages"]):
        if isinstance(msg, AIMessage):
            return msg.content
    return "I could not generate a response."
"""
# =========================
# MAIN FUNCTION WITH MEMORY
# =========================


def generate_response(user_id, user_input):
    cleanup_sessions()

    session = SESSION_MEMORY[user_id]
    session["last_active"] = time.time()

    # add user message
    session["messages"].append({
        "role": "user",
        "content": user_input
    })

    # trim memory
    while len(session["messages"]) > MAX_MESSAGES:
        session["messages"].popleft()

    # call agent with memory
    response = agent.invoke({
        "messages": list(session["messages"])
    })

    # extract assistant message
    assistant_reply = None

    for msg in reversed(response["messages"]):
        if isinstance(msg, AIMessage):
            assistant_reply = msg.content
            break

    if not assistant_reply:
        assistant_reply = "I could not generate a response."

    # save assistant message
    session["messages"].append({
        "role": "assistant",
        "content": assistant_reply
    })

    return assistant_reply
