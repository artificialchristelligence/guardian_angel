# knock.txt — Scheduler Manual

`knock.txt` is a plain-text file that defines scheduled prompts for your mentor agent.
Each job block is parsed on startup and registered with APScheduler.

---

## File structure

A job is a block of `key: value` pairs separated from the next job by a `---` divider.

```
name:     <unique_id>
schedule: <type> <fields>
prompt:   <text to send to agent>
chat_id:  <telegram chat id>
---
name:     <next_job>
schedule: <type> <fields>
prompt:   <text to send to agent>
chat_id:  <telegram chat id>
---
```

**Keys**

| Key        | Required | Description                                       |
| ---------- | -------- | ------------------------------------------------- |
| `name`     | No       | Unique job identifier. Defaults to `knock_job_N`. |
| `schedule` | Yes      | When to run. See schedule formats below.          |
| `prompt`   | Yes      | The text sent to `get_response_from_agent()`.     |
| `chat_id`  | No       | Telegram chat ID to deliver the response to.      |

> Lines beginning with `#` are treated as comments and ignored.
> Blank lines within a block are also ignored.

---

## Schedule formats

### `cron` — run at a fixed time

```
schedule: cron <MIN> <HOUR> <DOM> <MON> <DOW>
```

| Field | Meaning      | Allowed values                    |
| ----- | ------------ | --------------------------------- |
| MIN   | Minute       | 0–59                              |
| HOUR  | Hour (24h)   | 0–23                              |
| DOM   | Day of month | 1–31 or `*`                       |
| MON   | Month        | 1–12 or `*`                       |
| DOW   | Day of week  | 0–6 (Mon=0) or `mon`–`sun` or `*` |

Use `*` to mean "every". Ranges like `1-5` and lists like `1,3,5` are valid.

**Examples**

```
schedule: cron 0  9  *  *  *      # every day at 09:00
schedule: cron 30 17 *  *  1-5    # Mon–Fri at 17:30
schedule: cron 0  8  1  *  *      # 1st of every month at 08:00
schedule: cron 0  0  *  *  0      # every Sunday at midnight
schedule: cron 0  12 *  *  1,3,5  # Mon, Wed, Fri at 12:00
```

---

### `interval` — run repeatedly every N units

```
schedule: interval <N>m | <N>h | <N>d
```

| Suffix | Unit    |
| ------ | ------- |
| `m`    | minutes |
| `h`    | hours   |
| `d`    | days    |

**Examples**

```
schedule: interval 30m    # every 30 minutes
schedule: interval 6h     # every 6 hours
schedule: interval 1d     # every 24 hours
```

---

## Complete examples

### Daily morning briefing

```
name:     daily_briefing
schedule: cron 0 9 * * *
prompt:   Give me a concise summary of what I should focus on today
chat_id:  123456789
---
```

### Weekday end-of-day review

```
name:     eod_review
schedule: cron 0 17 * * 1-5
prompt:   Review the day and suggest three priorities for tomorrow
chat_id:  123456789
---
```

### Hourly quick check

```
name:     hourly_check
schedule: interval 1h
prompt:   Any urgent topics or blockers I should be aware of right now?
chat_id:  123456789
---
```

### Weekly report (no Telegram, prints to console)

```
name:     weekly_report
schedule: cron 0 18 * * 5
prompt:   Generate a structured weekly progress report with wins and blockers
---
```

### Monthly goal check

```
name:     monthly_goals
schedule: cron 0 9 1 * *
prompt:   Review my goals for this month and suggest adjustments based on progress
chat_id:  123456789
---
```

---

## Full knock.txt example

```
# ─── Daily jobs ────────────────────────────────────────────────

name:     morning_briefing
schedule: cron 0 9 * * *
prompt:   What should I focus on today? Be concise.
chat_id:  123456789
---

name:     eod_review
schedule: cron 0 17 * * 1-5
prompt:   End of day review: what went well and what to improve tomorrow?
chat_id:  123456789
---

# ─── Weekly jobs ───────────────────────────────────────────────

name:     weekly_report
schedule: cron 0 18 * * 5
prompt:   Generate a weekly summary with wins, blockers, and next week priorities
chat_id:  123456789
---

# ─── Interval jobs ─────────────────────────────────────────────

name:     health_check
schedule: interval 2h
prompt:   Quick check: am I on track with today's priorities?
chat_id:  123456789
---
```

---

## Finding your Telegram chat ID

The `chat_id` field tells the bot where to deliver scheduled responses.
There are four ways to find it.

### Option 1 — @userinfobot (easiest, personal chat)

1. Open Telegram and search for `@userinfobot`
2. Start it and send any message
3. It replies immediately with your personal chat ID

### Option 2 — @userinfobot in a group

1. Add `@userinfobot` to the group
2. Send any message in the group
3. It replies with the group's chat ID — this will be a negative number (e.g. `-1001234567890`)

### Option 3 — print it from your own bot

Temporarily add one line to `handle_message` in `app.py`, send your bot any message, then check the terminal:

```python
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    print(f"Chat ID: {update.message.chat_id}")   # add this, run, then remove
    ...
```

### Option 4 — Telegram API directly

Send your bot a message first, then open this URL in a browser:

```
https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
```

Look for `"chat": {"id": ...}` in the JSON response.

---

### Pasting the ID into knock.txt

```
chat_id: 123456789        # personal chat (positive number)
chat_id: -1001234567890   # group chat (negative number, keep the minus sign)
```

If `chat_id` is omitted entirely, the agent response is printed to the server console only.

---

## Behavior notes

- Jobs are loaded **once at startup**. To apply changes to `knock.txt`, restart the bot.
- If `chat_id` is omitted, the agent response is printed to the server console only.
- If a job fires while the previous run is still in progress, APScheduler will skip it with a warning (misfire grace: 60 seconds).
- Duplicate `name` values will cause the second job to overwrite the first. Keep names unique.
- A block missing either `schedule` or `prompt` is skipped with a warning in the logs.
