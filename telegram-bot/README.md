# Life OS — Telegram Bot (local starter)

Message your Telegram bot → it runs your Claude Code skills (`/today`, `/week`, `/add`, …)
→ replies in the chat. Runs **headless on your Claude subscription** (no API key) and uses
**long-polling**, so no public URL/webhook is needed for local testing.

```
Telegram  ──▶  bot.py  ──▶  Claude Agent SDK  ──▶  your CLAUDE.md + .claude/commands
          ◀──         ◀──  (final text reply)
```

---

## Prerequisites

1. **Python 3.10+**
2. **Node.js + Claude Code CLI**, logged in with your subscription:
   ```powershell
   npm install -g @anthropic-ai/claude-code
   claude          # then log in with your Pro/Max account
   ```
   The Agent SDK reuses these CLI credentials — **do not** set `ANTHROPIC_API_KEY`.
   > Subscription billing for the Agent SDK starts **June 15, 2026**. Before that date you'd
   > still need an API key. Usage draws on your plan's monthly Agent SDK credit.
3. A **Telegram bot token**: open [@BotFather](https://t.me/BotFather) → `/newbot` → copy the token.

---

## Setup

```powershell
cd C:\Users\Saturn\Desktop\lifeMg\telegram-bot

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env       # then edit .env
```

Fill in `.env`:
- `TELEGRAM_BOT_TOKEN` → from BotFather
- `ALLOWED_CHAT_ID` → leave as `0` for now
- `PROJECT_DIR` → already points at your lifeMg project

---

## Run & test locally

```powershell
python bot.py
```

1. Open Telegram, find your bot, send any message (e.g. `hi`).
2. The bot replies with **your chat ID** (because `ALLOWED_CHAT_ID=0`).
3. Put that number into `.env` as `ALLOWED_CHAT_ID`, then **restart** `python bot.py`.
4. Now send `/today` — you'll get your daily briefing back in the chat. 🎉

Stop the bot with **Ctrl+C**.

---

## Conversations & commands

The bot keeps a **live, multi-turn conversation** per chat, so it remembers
what you just said instead of treating every message in isolation:

- **Plain text** (e.g. `what should I do today?`) starts an **implicit session**.
  Follow-ups within **10 minutes** keep the context — ask `and what about
  tomorrow?` and it knows what "tomorrow" refers to.
- **`/chat`** starts a longer **chat session** (context kept for **30 minutes**
  of inactivity). `/chat` on its own replies `Chat mode started.`; `/chat <text>`
  also sends your first message.
- **`/stop`** ends the current conversation immediately — it interrupts any work
  in progress, closes the session, and replies `Conversation stopped.`
- **Standalone commands** — `/today`, `/week`, `/add` on their own — run
  **one-shot** (a fresh, self-contained briefing) and do **not** touch the live
  conversation.
- **Command + follow-up** — e.g. `/today help me prioritize` — runs `/today`
  once, then feeds its result plus your follow-up into the conversation so you
  can discuss it.

Idle sessions are swept automatically in the background once they pass their
timeout, so abandoned chats don't keep a Claude connection open.

---

## ⚠️ Important: Notion & Calendar won't work yet

The pipeline (Telegram ↔ Claude ↔ your skills) works immediately, but **live Notion /
Google Calendar data does not**, because your current integrations are the hosted
`claude_ai_*` connectors tied to the desktop app — a headless server can't use those.

So right now:
- ✅ `/today` will **run the skill and reply** — proving the round-trip
- ❌ it **can't fetch Notion/Calendar** until you add server-side MCP servers

To make data work (phase 2), add local MCP servers the SDK can authenticate:
- **Notion** → an internal integration token (share your workspace with it)
- **Google Calendar** → an OAuth refresh token / service account

These get declared in `mcp_servers` on `ClaudeAgentOptions` (or a project `.mcp.json`).
Ping me and I'll wire that up.

---

## How it works (module layout)

The bot is split into focused modules:

- **`agent_runner.py`** — everything about talking to Claude. `build_options()`
  points the agent at your project, loads `CLAUDE.md` + `.claude/commands`, uses
  the Claude Code system prompt, and restricts tools (`permission_mode="dontAsk"`
  + an explicit `allowed_tools` list). `run_agent()` runs one **one-shot** turn;
  `LiveAgentClient` wraps a persistent `ClaudeSDKClient` for **multi-turn** chat.
- **`routing.py`** — `classify_message()` decides what a message is (stop / chat /
  standalone command / command+follow-up / plain conversation).
- **`sessions.py`** — `SessionManager` owns the live conversations per chat ID,
  their 10-/30-minute timeouts, and idle expiry.
- **`bot.py`** — the Telegram glue: **locks the bot to your chat ID**, shows
  "typing…", dispatches each message via the route, records telemetry, and splits
  long replies under Telegram's 4096-char limit.

---

## Security notes

- The bot **only responds to `ALLOWED_CHAT_ID`** — others are ignored.
- Tools run under `permission_mode="dontAsk"` with an explicit `allowed_tools`
  list (read-only filesystem + the Notion/Calendar MCP servers), so the agent
  can't run arbitrary tools even though only you can trigger it.
- `.env` is git-ignored — never commit your token.

---

## Run in Docker (server-ready)

The image bundles Python + Node + the Claude Code CLI + your project context
(`CLAUDE.md`, `.claude/commands`, `context/`). Long-polling means **no public URL needed** —
it runs the same on a server as on your laptop. Build files live in the **project root**
(`../Dockerfile`, `../docker-compose.yml`, `../.dockerignore`).

### 1. One-time: get a headless Claude token
The container can't do an interactive login, so generate a long-lived subscription token
**on your laptop**:
```powershell
claude setup-token
```
Copy the token it prints.

### 2. Configure the container env
```powershell
cd C:\Users\Saturn\Desktop\lifeMg\telegram-bot
copy .env.docker.example .env.docker
```
Fill `.env.docker` with: `TELEGRAM_BOT_TOKEN`, `ALLOWED_CHAT_ID`, `NOTION_TOKEN`, and
`CLAUDE_CODE_OAUTH_TOKEN` (from step 1). **Do not** set `PROJECT_DIR` (the image sets it)
and **do not** set `ANTHROPIC_API_KEY` (that switches to metered billing).

### 3. Build & run
From the **project root** (`C:\Users\Saturn\Desktop\lifeMg`):
```powershell
docker compose up --build -d      # build + run detached
docker compose logs -f            # watch logs; look for "Bot is running"
```
Then message your bot. To stop: `docker compose down`. It auto-restarts on crash/reboot
(`restart: unless-stopped`).

### Deploying to a host
Push this repo to a small always-on host (Railway / Fly.io / a VPS), set the same env vars
as secrets, and run `docker compose up -d`. Same image, same behavior.

## Google Calendar setup (token-based, server-ready)

Replaces the laptop-only hosted connector with `@cocal/google-calendar-mcp` so Calendar
works on a server too. **One-time, ~15 min.**

### Part A — Google Cloud (browser)
1. https://console.cloud.google.com → create a project (e.g. "Life OS").
2. **APIs & Services → Library** → search **Google Calendar API** → **Enable**.
3. **APIs & Services → OAuth consent screen**:
   - User type **External** → fill app name + your email.
   - **Test users:** add `tariqaroosh@gmail.com`.
   - **Publishing status → "In production"** (a personal unverified app is fine; this avoids
     the 7-day refresh-token expiry that "Testing" mode imposes). You'll click past an
     "unverified app" warning during auth — that's expected for your own app.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type **Desktop app** → Create → **Download JSON**.
5. Save that file as `telegram-bot/secrets/gcp-oauth.keys.json`.

### Part B — One-time local auth (gets the refresh token)
```powershell
cd C:\Users\Saturn\Desktop\lifeMg\telegram-bot
$env:GOOGLE_OAUTH_CREDENTIALS="$PWD\secrets\gcp-oauth.keys.json"
$env:GOOGLE_CALENDAR_MCP_TOKEN_PATH="$PWD\secrets\tokens"
npx -y @cocal/google-calendar-mcp auth
```
A browser opens → sign in as `tariqaroosh@gmail.com` → on the warning click
**Advanced → Go to … (unsafe)** → **Allow**. The token is saved under `secrets/tokens`.

### Part C — Enable it locally
Uncomment the two `GOOGLE_…` lines in `telegram-bot/.env` (Windows paths), restart the bot,
send `/today` — Calendar now comes from the new server.

### Part D — Docker
`secrets/` (creds + tokens) is mounted to `/app/secrets`; `.env.docker` already points there.
Just rebuild: `docker compose up --build -d`.

> Note: locally you may briefly have **two** calendar connectors (the old hosted one + this).
> On a server only this token-based one exists, which is the whole point.
