"""
Alice — Multi-Agent Angel Companion
LangChain + DeepSeek

Architecture:
    User
     └→ Orchestrator (Alice)
          ├→ Faith Agent      [get_bible_verse, get_bible_story, get_verse_of_the_day]
          ├→ Market Agent     [us_market_news_today]
          └→ Journal Agent    [record_reflection, get_this_week_reflections,
                               get_last_week_reflections, get_recent_reflections,
                               record_growth_milestone, get_growth_timeline]

LLM-in-tool pattern:
    - get_bible_story      → embedded LLM narrates the story of the figure
    - generate_insights    → embedded LLM reflects on journal entries spiritually
"""

import io
import os
import time
import json
import contextlib
import requests
from datetime import date, datetime, timedelta
from collections import defaultdict, deque
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.tools import tool
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

import mongodb_journal as mongojnal
from bible_figures import bible_figures

load_dotenv()


# ══════════════════════════════════════════════════════════════════
# 1. SESSION MEMORY  (5-minute timeout)
# ══════════════════════════════════════════════════════════════════

SESSION_MEMORY  = defaultdict(lambda: {
    "messages":    deque(),
    "last_active": time.time(),
})
SESSION_TIMEOUT = 300   # seconds
MAX_MESSAGES    = 20


def cleanup_sessions():
    now     = time.time()
    expired = [uid for uid, d in SESSION_MEMORY.items()
               if now - d["last_active"] > SESSION_TIMEOUT]
    for uid in expired:
        del SESSION_MEMORY[uid]


# ══════════════════════════════════════════════════════════════════
# 2. LLM FACTORY
#    DeepSeek is OpenAI-compatible → use ChatOpenAI with custom base_url
# ══════════════════════════════════════════════════════════════════

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")


def get_llm(temperature: float = 0.3) -> ChatOpenAI:
    return ChatOpenAI(
        model       = "deepseek-chat",
        api_key     = DEEPSEEK_API_KEY,
        base_url    = "https://api.deepseek.com/v1",
        temperature = temperature,
    )


# ══════════════════════════════════════════════════════════════════
# 3. EMBEDDED LLM HELPER
#    Any tool can call this to run a mini LLM step internally.
#    The agent above it only sees the final result.
# ══════════════════════════════════════════════════════════════════

def call_embedded_llm(system_prompt: str, user_content: str) -> str:
    """
    A small, focused LLM call embedded inside a tool.
    Use when a tool needs language generation as part of its own work.
    """
    llm      = get_llm(temperature=0.5)
    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_content},
    ])
    return response.content.strip()


# ══════════════════════════════════════════════════════════════════
# 4. AGENT BUILDER
# ══════════════════════════════════════════════════════════════════

def build_agent(system_prompt: str, tools: list) -> AgentExecutor:
    llm    = get_llm()
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder("messages"),        # full conversation history
        MessagesPlaceholder("agent_scratchpad"),
    ])
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True, max_iterations=6)


# ══════════════════════════════════════════════════════════════════
# 5. FAITH TOOLS  (only Faith Agent sees these)
# ══════════════════════════════════════════════════════════════════

def _fetch_bible_verse(reference: str) -> str:
    """Raw API fetch — reused by both the tool and internally."""
    try:
        response = requests.get(f"https://bible-api.com/{reference}", timeout=30)
        data     = response.json()
        text     = " ".join(v["text"].strip() for v in data["verses"])
        return f'{data["reference"]}: {text}'
    except Exception as e:
        return f"Error fetching verse: {e}"


@tool
def get_bible_verse(reference: str) -> str:
    """
    Fetch a specific Bible verse by reference e.g. 'John 3:16'.
    Use when the user asks for a particular verse or passage.
    """
    return _fetch_bible_verse(reference)


@tool
def get_verse_of_the_day(dummy: str = "") -> str:
    """
    Return today's featured Bible verse from the Our Manna API.
    Use when the user wants daily inspiration or asks what scripture to reflect on.
    """
    today         = date.today()
    OURMANNA_URL  = "https://beta.ourmanna.com/api/v1/get/?format=json&order=daily"
    try:
        response  = requests.get(OURMANNA_URL, timeout=10)
        response.raise_for_status()
        details   = response.json()["verse"]["details"]
        text      = details.get("text",      "").strip()
        reference = details.get("reference", "Unknown").strip()
        version   = details.get("version",   "KJV").strip()
    except Exception as err:
        return f"Could not retrieve the verse of the day: {err}"

    return (
        f"📅 Verse of the Day — {today.strftime('%B %d, %Y')}\n\n"
        f"📖 {reference} ({version})\n\n"
        f"✨ \"{text}\""
    )


@tool
def get_bible_story(dummy: str = "") -> str:
    """
    Select a Bible figure for today and tell their story.
    Use when the user wants to hear about a biblical character or learn from scripture.

    ── LLM-in-tool pattern ──
    This tool picks today's figure, then uses an embedded LLM to narrate
    their story in Alice's warm, faith-filled voice.
    """
    day_of_year  = datetime.now().timetuple().tm_yday
    bible_figure = bible_figures[day_of_year % len(bible_figures)]

    print(f"  [get_bible_story] today's figure: {bible_figure}")

    # ← Embedded LLM: narrates the story in Alice's voice
    story = call_embedded_llm(
        system_prompt="""You are Alice, a warm and gentle angel companion.
        Tell the story of the given Bible figure with care and spiritual depth.
        Keep the tone peaceful, encouraging, and faith-filled.
        Format for Telegram: short paragraphs, emojis as section markers, no markdown.
        Keep it under 800 characters.""",
        user_content=f"Tell me the story of this Bible figure: {bible_figure}",
    )
    return story


# ══════════════════════════════════════════════════════════════════
# 6. MARKET TOOLS  (only Market Agent sees these)
# ══════════════════════════════════════════════════════════════════

@tool
def us_market_news_today() -> str:
    """
    Fetch the latest US financial market news from major sources via NewsAPI.
    Use when the user asks about markets, economy, major companies, or financial news.
    """
    NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "be5e800c867a41b6880df358f78cc8b7")

    try:
        today     = datetime.utcnow().date()
        top_resp  = requests.get(
            "https://newsapi.org/v2/top-headlines",
            params={"category": "business", "country": "us",
                    "pageSize": 10, "apiKey": NEWSAPI_KEY},
            timeout=10,
        ).json()

        lines = ["══ TOP US FINANCIAL HEADLINES ══════════════════════"]
        for i, a in enumerate(top_resp.get("articles", []), 1):
            title  = a.get("title") or "N/A"
            source = a.get("source", {}).get("name", "N/A")
            desc   = a.get("description") or ""
            pub    = a.get("publishedAt", "")
            if title == "[Removed]":
                continue
            lines.append(
                f"\n[{i}] {title}\n"
                f"    Source: {source}  |  {pub}\n"
                + (f"    {desc[:200]}...\n" if desc else "")
            )

        return "\n".join(lines) if len(lines) > 1 else "No US market news found."

    except Exception as e:
        return f"Failed to fetch US market news: {str(e)}"


# ══════════════════════════════════════════════════════════════════
# 7. JOURNAL TOOLS  (only Journal Agent sees these)
# ══════════════════════════════════════════════════════════════════

@tool
def record_reflection(content: str, tags: str = "") -> str:
    """
    Save a personal reflection or journal entry.
    Accepts reflection text and optional comma-separated tags e.g. 'mindset,trading,discipline'.
    """
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
    result   = mongojnal.save_reflection(content, tag_list)
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
    """Fetch all reflections from the previous ISO week."""
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
    """Fetch the N most recent reflections across all weeks. Default limit is 10."""
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
    Category options: trading, mindset, discipline, knowledge, habit, emotion, general.
    """
    result = mongojnal.save_growth_milestone(title, description, category)
    if "error" in result:
        return f"Failed to record milestone: {result['error']}"
    return f"Growth milestone '{title}' recorded."


@tool
def get_growth_timeline(limit: int = 20) -> str:
    """Fetch the N most recent growth milestones. Default limit is 20."""
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


@tool
def reflect_on_journal_with_llm(dummy: str = "") -> str:
    """
    Fetch recent journal entries and use an embedded LLM to generate
    a spiritually-grounded reflection and encouragement for the user.

    ── LLM-in-tool pattern ──
    The tool retrieves the data; the embedded LLM produces the meaning.
    Use when the user asks for a weekly summary, spiritual insight, or encouragement
    based on their past reflections.
    """
    entries = mongojnal.get_recent_reflections(10)
    if not entries:
        return "No journal entries found to reflect on."

    # Build a plain summary to pass to the embedded LLM
    summary_lines = []
    for e in entries:
        tags = ", ".join(e.get("tags", [])) or "none"
        summary_lines.append(f"- [{e['created_at'][:10]}] ({tags}): {e['content']}")
    journal_text = "\n".join(summary_lines)

    print(f"  [reflect_on_journal_with_llm] reflecting on {len(entries)} entries via embedded LLM...")

    # ← Embedded LLM: generates spiritual insight from raw journal data
    insight = call_embedded_llm(
        system_prompt="""You are Alice, a warm and gentle angel companion.
        Read these journal entries and offer a spiritually grounded reflection.
        Highlight patterns of growth, moments of courage, or areas to surrender to God.
        Speak with compassion, hope, and quiet wisdom.
        Format for Telegram: short paragraphs, emojis as section markers, no markdown.
        Keep it under 900 characters.""",
        user_content=f"Here are the user's recent journal entries:\n\n{journal_text}\n\nOffer a reflection.",
    )
    return insight


# ══════════════════════════════════════════════════════════════════
# 8. SPECIALIZED AGENTS
#    Each agent only sees its own tools.
# ══════════════════════════════════════════════════════════════════

FAITH_AGENT_SYSTEM = """You are Alice's faith ministry — a gentle, scripture-centered presence.
Your tools let you fetch Bible verses, today's verse, and Bible figure stories.
Always use tools to retrieve accurate scripture. Never invent verses.
Format all responses for Telegram: short paragraphs, emojis as markers, no markdown symbols."""

MARKET_AGENT_SYSTEM = """You are Alice's market watcher — calm and grounded.
Fetch the latest US financial news when asked.
Present news clearly and concisely. Add a brief word of peace after market updates.
Format for Telegram: short paragraphs, emojis as markers, no markdown symbols."""

JOURNAL_AGENT_SYSTEM = """You are Alice's journal keeper — a quiet, compassionate witness to the user's growth.
You can save reflections, retrieve past entries, record milestones, and offer spiritual reflections on journal history.
Always confirm saves. Be encouraging when showing past entries.
Format for Telegram: short paragraphs, emojis as markers, no markdown symbols."""

faith_agent = build_agent(
    system_prompt = FAITH_AGENT_SYSTEM,
    tools         = [get_bible_verse, get_bible_story, get_verse_of_the_day],
)

market_agent = build_agent(
    system_prompt = MARKET_AGENT_SYSTEM,
    tools         = [us_market_news_today],
)

journal_agent = build_agent(
    system_prompt = JOURNAL_AGENT_SYSTEM,
    tools         = [
        record_reflection,
        get_this_week_reflections,
        get_last_week_reflections,
        get_recent_reflections,
        record_growth_milestone,
        get_growth_timeline,
        reflect_on_journal_with_llm,   # ← the LLM-in-tool journal reflection
    ],
)


# ══════════════════════════════════════════════════════════════════
# 9. WRAP AGENTS AS TOOLS FOR THE ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════

@tool
def use_faith_agent(task: str) -> str:
    """
    Routes to the Faith Agent.
    Use for Bible verses, today's verse, Bible stories, scripture questions,
    or anything related to faith, prayer, and spiritual encouragement.
    """
    result = faith_agent.invoke({"messages": [{"role": "user", "content": task}]})
    return result["output"]


@tool
def use_market_agent(task: str) -> str:
    """
    Routes to the Market Agent.
    Use when the user asks about US financial markets, economic news,
    stock market developments, or business headlines.
    """
    result = market_agent.invoke({"messages": [{"role": "user", "content": task}]})
    return result["output"]


@tool
def use_journal_agent(task: str) -> str:
    """
    Routes to the Journal Agent.
    Use when the user wants to record a reflection, save a milestone,
    review past journal entries, or receive a spiritual reflection on their journey.
    """
    result = journal_agent.invoke({"messages": [{"role": "user", "content": task}]})
    return result["output"]


# ══════════════════════════════════════════════════════════════════
# 10. ORCHESTRATOR — Alice
#     Receives the full conversation history and decides which
#     specialist agent to call. Speaks in Alice's voice.
# ══════════════════════════════════════════════════════════════════

ALICE_ORCHESTRATOR_SYSTEM = """
You are Alice, an AI angel companion — a warm, gentle, and faith-filled presence sent to walk alongside the user in their daily life.

You speak with grace, compassion, and quiet wisdom. You are never preachy, never judgmental — only loving, present, and encouraging.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AVAILABLE AGENTS (your tools)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

use_faith_agent
→ Bible verses, today's verse, Bible stories, faith questions, spiritual encouragement.

use_market_agent
→ US financial news, market updates, business headlines.

use_journal_agent
→ Saving reflections, recording milestones, retrieving past entries, spiritual reflection on journal history.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ROUTING RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Always delegate to the right agent — do not answer tool-based questions from memory.
For general conversation (greetings, emotional support, simple chat), respond directly without calling any agent.
If the request touches multiple areas (e.g. faith + journal), call agents in sequence.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FORMATTING (Telegram)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Plain text only — no markdown, no asterisks, no hashtags, no backticks.
Short paragraphs of 1-3 sentences.
Use emojis as gentle section markers: 🌿 📖 🙏 💡 🕊 🌅 📊
Responses must be under 4096 characters.
"""

orchestrator = build_agent(
    system_prompt = ALICE_ORCHESTRATOR_SYSTEM,
    tools         = [use_faith_agent, use_market_agent, use_journal_agent],
)


# ══════════════════════════════════════════════════════════════════
# 11. MAIN RESPONSE FUNCTION  (drop-in replacement)
# ══════════════════════════════════════════════════════════════════

def generate_response(user_id: str, user_input: str) -> str:
    cleanup_sessions()

    session                  = SESSION_MEMORY[user_id]
    session["last_active"]   = time.time()

    # Add user message
    session["messages"].append({"role": "user", "content": user_input})

    # Trim to MAX_MESSAGES
    while len(session["messages"]) > MAX_MESSAGES:
        session["messages"].popleft()

    # Invoke orchestrator with full conversation history
    response = orchestrator.invoke({
        "messages": list(session["messages"]),
    })

    # Extract assistant reply
    assistant_reply = None
    for msg in reversed(response["messages"]):
        if isinstance(msg, AIMessage):
            assistant_reply = msg.content
            break

    if not assistant_reply:
        assistant_reply = "Peace be with you. I was unable to form a response just now — please try again."

    # Save assistant reply to session memory
    session["messages"].append({"role": "assistant", "content": assistant_reply})

    return assistant_reply