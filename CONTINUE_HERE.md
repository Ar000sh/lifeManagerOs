# 🚧 Continue Here — Life OS Telegram Bot

A resume doc so you can pick this up any day. Last updated mid-build: the bot **works locally**
(Telegram + Claude subscription + Notion + Calendar). Remaining work is **deploying to a server**,
where Google Calendar needs token-based auth.

---

## ✅ What's done

### Notion life-OS (all live)
- **Modules** for SS 2026: Security 2, Deep learning, Programming Paradigms (lecture/exercise times in Notes).
- **Businesses** under 🚀 Business: Laundromat, Van Company, **TBHShop** (in-dev webshop), **Evening Dresses Export** (research) — each with its own Tasks DB + seeded tasks.
- **📆 My Week** page: Google Calendar embed slot + linked "This Week" task views for all areas.
- **Skills** `/today`, `/week`, `/add` updated to cover all 4 businesses and prefer filtered Notion queries.

### Google Calendar blocks (recurring, Europe/Berlin)
- Uni lectures/exercises (until 2026-09-15), Work shifts, Business blocks — all color-coded.

### Telegram bot (`telegram-bot/`)
- `bot.py` — long-polling, runs skills via Claude Agent SDK on **subscription auth** (no API key).
- Locked to chat id **1672283963**. Cross-platform (Windows + Linux/Docker).
- Notion via token-based `@notionhq/notion-mcp-server` (real filtered queries). **Working.**
- Containerized: `Dockerfile`, `docker-compose.yml`, `.dockerignore` — **image builds OK**.

### Integration status
| Integration | Status | Auth |
|---|---|---|
| Telegram | ✅ working | bot token in `.env` |
| Claude (subscription) | ✅ working | `claude setup-token` done → `CLAUDE_CODE_OAUTH_TOKEN` |
| Notion | ✅ working | integration token `NOTION_TOKEN` |
| Google Calendar | ⏳ **code wired, needs OAuth setup** | `@cocal/google-calendar-mcp` |

---

## ⬜ What's left (in order)

### 1. Google Calendar OAuth — the last integration gap
Full walkthrough is in **`telegram-bot/README.md` → "Google Calendar setup"**. Summary:
- [ ] **A.** Google Cloud: create project → enable Calendar API → OAuth consent screen
      (add `tariqaroosh@gmail.com` as test user, set **Publishing status = In production** to avoid
      7-day token expiry) → create **Desktop app** OAuth client → download JSON →
      save as `telegram-bot/secrets/gcp-oauth.keys.json`
- [ ] **B.** Run once locally: `npx -y @cocal/google-calendar-mcp auth` (with the two `GOOGLE_…`
      env vars set) → approve in browser → token saved to `secrets/tokens`
- [ ] **C.** Uncomment the two `GOOGLE_…` lines in `telegram-bot/.env`, restart bot, test `/today`

### 2. Prep the container env
- [ ] Copy `telegram-bot/.env.docker.example` → **`telegram-bot/.env.docker`** (compose reads the
      `.env.docker` file, NOT the `.example`). It already has all tokens filled in.

### 3. Test in Docker
- [ ] `cd C:\Users\Saturn\Desktop\lifeMg` → `docker compose up --build -d` → `docker compose logs -f`
- [ ] Message the bot; confirm `/today` returns calendar + Notion data

### 4. Deploy to a server
- [ ] Pick a host: Railway / Fly.io / Render / cheap VPS (Hetzner). Long-polling needs no public URL.
- [ ] Push repo + set the same env vars as secrets + mount `secrets/` → `docker compose up -d`

### 5. Security housekeeping
- [ ] **Revoke the exposed Telegram token** in @BotFather (`/revoke`) — it was shared in chat.
      Paste the new token into `.env` and `.env.docker`.
- [ ] Optional: also rotate the Notion token if desired.

---

## 🔑 Quick reference

**Run locally:**
```powershell
cd C:\Users\Saturn\Desktop\lifeMg\telegram-bot
.\.venv\Scripts\python.exe bot.py
```

**Run in Docker:**
```powershell
cd C:\Users\Saturn\Desktop\lifeMg
docker compose up --build -d
docker compose logs -f
docker compose down            # stop
```

**Key files**
| File | What |
|---|---|
| `telegram-bot/bot.py` | the bot |
| `telegram-bot/.env` | local secrets (Telegram, Notion, chat id; Calendar paths commented) |
| `telegram-bot/.env.docker` | container secrets (create from `.example`) |
| `telegram-bot/secrets/` | Google OAuth creds + saved token (git-ignored) |
| `telegram-bot/README.md` | full setup + Google Calendar walkthrough |
| `Dockerfile`, `docker-compose.yml` | container |
| `.claude/commands/{today,week,add}.md` | the skills |
| `context/notion.md` | Notion workspace map |

## ⚠️ Gotchas
- **`.env.docker`** is what compose reads — not `.env.docker.example`.
- Don't set `PROJECT_DIR` in `.env.docker` (image sets it to `/app`); don't set `ANTHROPIC_API_KEY`
  (would switch off subscription billing).
- Google "Testing" mode = refresh token dies after 7 days → set **In production**.
- First `/today` after a rebuild is slow (npx fetches MCP servers once, then caches).
