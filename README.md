```
          ✦  ·  ✦  ·  ✦  ·  ✦  ·  ✦  ·  ✦  ·  ✦
                         ___
                        (   )
                         | |
                     (         )
                       |     |
               ~~~~~~~ |     | ~~~~~~~
              ~~~~~~~~~|     |~~~~~~~~~
             ~~~~~~~~~~|     |~~~~~~~~~~
                        |   |
                        |   |
                       /     \
                      /  /_\  \
                     /  /   \  \
                    /__/     \__\
          ✦  ·  ✦  ·  ✦  ·  ✦  ·  ✦  ·  ✦  ·  ✦
```

# 😇 Angel Agent

> _"Your word is a lamp to my feet and a light to my path."_ — Psalm 119:105

A **scripture-powered AI companion** built with Python, LangChain, DeepSeek, and Telegram.
The Angel Agent brings you daily Bible verses, scheduled reminders, and faith-filled
AI responses — no database required.

---

## 🛠️ Tech Stack

![Python](https://img.shields.io/badge/Python_3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)
![DeepSeek](https://img.shields.io/badge/DeepSeek_LLM-4A90E2?style=for-the-badge&logo=openai&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram_Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)
![Bible API](https://img.shields.io/badge/Bible_API-8B5CF6?style=for-the-badge&logo=bookstack&logoColor=white)
![APScheduler](https://img.shields.io/badge/APScheduler-FF6B35?style=for-the-badge&logo=clockify&logoColor=white)

---

## ✨ Features

| Feature                    | Description                                                      |
| -------------------------- | ---------------------------------------------------------------- |
| 🤖 **AI Responses**        | Faith-centred conversations powered by DeepSeek via LangChain    |
| 📖 **Bible Verse Lookup**  | Fetch any verse by reference (e.g. `John 3:16`)                  |
| 🌅 **Verse of the Day**    | Automatically pushed to Telegram each morning                    |
| 📉 **Market Latest News**  | Fetch latest US stock market news                                |
| ⏰ **Scheduled Reminders** | Set personal reminders that the angel delivers at the right time |
| 🙏 **Prayer Prompt**       | Ask for a prayer on any topic and receive one                    |
| 💬 **Telegram Interface**  | Fully conversational — no app needed beyond Telegram             |

---

## 📁 Project Structure

```
angel_agent/
├── app.py              # Telegram bot + LangChain agent entry point
├── angel_agent.py      # LangChain tools (Bible API, US market news, prayer)
├── scheduler.py        # APScheduler jobs (verse of the day, market news)
├── mongodb_journal.py  # mongodb connection to document reflection and milestones
├── requirements.txt
└── .env                # Secrets — never commit this!
```

---

## ⚙️ Requirements

- Python 3.9+
- Telegram Bot Token
- DeepSeek API Key
- MongoDB Database Password
- Internet connection (Bible API is free, no key needed)

---

## 📦 Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/angel_agent.git
cd angel_agent
```

### 2. Create and activate a virtual environment

**macOS / Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows:**

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

Or manually:

```bash
pip install langchain langchain-deepseek python-telegram-bot requests python-dotenv apscheduler
```

---

## 🔑 Environment Variables

Create a `.env` file in your project root:

```env
DEEPSEEK_API_KEY=your_deepseek_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
CHAT_ID=your_telegram_chat_id
```

### Getting Your Keys

#### DeepSeek API Key (`DEEPSEEK_API_KEY`)

1. Visit [https://platform.deepseek.com/](https://platform.deepseek.com/)
2. Sign up or log in
3. Navigate to **API Keys** → click **Create API Key**
4. Copy and paste it into `.env`

#### Telegram Bot Token (`TELEGRAM_BOT_TOKEN`)

1. Open Telegram and search for **@BotFather**
2. Send `/start`, then `/newbot`
3. Follow the prompts — give your bot a name and username (must end in `bot`)
4. BotFather will return a token like:
   ```
   123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ
   ```
5. Copy it into `.env`

#### Telegram Chat ID to get notification

Send a message to your bot, then open:

```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
```

Look for

```
"chat": {
  "id": 123456789
}
```

## That number is your chat_id.

## 🚀 Running the Agent

```bash
python app.py
```

You should see:

```
[Angel Agent] Bot is running... 😇
```

Your Telegram bot is now live and listening.

---

## 🔧 Agent Tools

The Angel Agent comes with the following LangChain tools:

| Tool                   | Description                                                       |
| ---------------------- | ----------------------------------------------------------------- | --- |
| `get_bible_verse`      | Fetch a verse by reference via the Bible API (e.g. `Romans 8:28`) |
| `get_verse_of_the_day` | Retrieve today's featured verse                                   |     |
| `us_market_news_today` | Fetch latest US market news.                                      |     |

---

## 💬 Example Usage

**Look up a verse:**

```
John 3:16
```

> The agent calls `get_bible_verse` and returns:
> _"For God so loved the world that he gave his one and only Son..."_

**Get a devotional:**

```
Give me something to reflect on today
```

> The agent fetches a verse and adds a short reflection.

---

## 🏃 Hosting Options

### Option 1 — Local Machine (Development)

Keep the terminal open and run:

```bash
python app.py
```

The bot uses **polling** — no webhook setup needed.

### Option 2 — Azure Web App (Production)

1. Create a **Resource Group** and **App Service** (Python 3.11, Linux)
2. Add environment variables under **Settings → Environment Variables**
3. Set the startup command:
   ```
   gunicorn --bind=0.0.0.0 --timeout 600 app:app
   ```
4. Deploy via **Deployment Center** (GitHub or local Git)

### Option 3 — Raspberry Pi (Self-Hosted)

```bash
sudo apt install python3 python3-venv git -y
git clone <your-repo-url> && cd angel_agent
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py
```

To keep it running permanently, create a `systemd` service pointing to `app.py`.

---

## 🗺️ Roadmap

- [ ] Multi-translation Bible support (KJV, NIV, ESV)
- [ ] Weekly scripture plan / reading tracker
- [ ] Worship song suggestions via YouTube API
- [ ] Voice message replies with TTS

---

## 🙌 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

---

## 📜 Licence

MIT

---

_Built with faith, Python, and a little angelic inspiration. ✨_
