# Life OS Telegram bot — runtime image (Python + Node + Claude Code CLI)
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PROJECT_DIR=/app

# --- System deps + Node.js 20 (needed by the Claude CLI and the Notion MCP server) ---
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# --- Claude Code CLI (the runtime the Agent SDK drives) + Notion MCP server (pre-cached) ---
RUN npm install -g @anthropic-ai/claude-code @notionhq/notion-mcp-server @cocal/google-calendar-mcp

WORKDIR /app/telegram-bot

# --- Python deps (own layer so it caches across code changes) ---
COPY telegram-bot/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# --- Our own MCP server: the bot spawns `python -m lifeos_mcp.server` at runtime, so
#     the package must be importable image-wide. Installed non-editable (real image). ---
COPY lifeos-mcp /app/lifeos-mcp
RUN pip install --no-cache-dir /app/lifeos-mcp

# --- Project context the agent loads: CLAUDE.md, skills, reference docs, and the bot ---
COPY CLAUDE.md /app/CLAUDE.md
COPY .claude /app/.claude
COPY context /app/context
COPY telegram-bot/bot.py ./bot.py
COPY telegram-bot/agent_runner.py ./agent_runner.py
COPY telegram-bot/routing.py ./routing.py
COPY telegram-bot/sessions.py ./sessions.py
COPY telegram-bot/telemetry.py ./telemetry.py
# --- Run as a non-root user ---
# The Claude CLI refuses --dangerously-skip-permissions (what the SDK's
# permission_mode="bypassPermissions" maps to) when running as root, so a
# root container exits 1 during the agent's init handshake. Run as 'app'.
ENV HOME=/home/app
RUN useradd --create-home --uid 1001 app \
    && chown -R app:app /app
USER app

# Secrets (tokens, chat id) are provided at runtime via env / env_file — never baked in.
CMD ["python", "bot.py"]
