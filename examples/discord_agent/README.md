# EPLAI — Agentic Discord Bot

A powerful, self-learning Discord AI bot written **100% in EPL** (English Programming Language) — no Python bridge, no external frameworks.

## How It Works

### Architecture

```
Discord Gateway (WebSocket)
         │
    gateway.epl          ← EPL native net_ws_connect
         │
    main.epl             ← Entry point and orchestrator
     /   |    \
agent  memory  tools
.epl   .epl   .epl
  │      │       │
Groq   SQLite  DuckDuckGo
API    DB      (free search)
(free)
```

### Files

| File | Purpose |
|------|---------|
| `main.epl` | Entry point. Loads env vars, sets up DB, starts gateway |
| `gateway.epl` | Full Discord WebSocket Gateway protocol in EPL |
| `agent.epl` | Agentic LLM reasoning loop with tool calling |
| `memory.epl` | SQLite persistent memory (history + facts + knowledge) |
| `tools.epl` | Tool registry (web search, math, time) |

### The Agentic Loop

The bot doesn't just reply — it **thinks in steps**:

1. User sends `!ask me something`
2. Bot loads last 12 messages from SQLite for context
3. Bot loads known facts about this user
4. Groq LLaMA 3 70B reasons about the request
5. If it needs the web → emits `SEARCH:<query>` → DuckDuckGo Instant API → result fed back
6. If it learns something → emits `REMEMBER:<fact>` → saved to SQLite permanently
7. Final answer sent back to Discord via REST API

### Self-Learning

- Every conversation is stored in `agent_memory.db`
- The bot builds a profile of each user (their interests, name, preferences) via `REMEMBER:` commands
- The bot accumulates world knowledge via `LEARN:<topic>|<info>` commands
- All of this is injected back into the context on every future conversation

## Setup & Run

### 1. Install only one dependency (websocket-client for EPL's net_ws_connect)

```powershell
pip install websocket-client
```

### 2. Get Your Free API Keys

- **Groq (Free LLaMA 3 70B):** Sign up at [console.groq.com](https://console.groq.com) → Create API Key
- **Discord Bot Token:** Go to [discord.com/developers/applications](https://discord.com/developers/applications) → New App → Bot → Enable **Message Content Intent** → Copy Token

### 3. Set Environment Variables

```powershell
$env:DISCORD_TOKEN="your_discord_bot_token"
$env:GROQ_API_KEY="your_groq_api_key"
```

### 4. Run the Bot

```powershell
cd examples\discord_agent
epl main.epl
```

You'll see:
```
╔══════════════════════════════════════════════╗
║      EPLAI Discord Agent v1.0                ║
║  Built 100% in EPL — English Prog. Language  ║
╚══════════════════════════════════════════════╝
✅ DISCORD_TOKEN loaded.
✅ GROQ_API_KEY loaded.
[Memory] ✅ Database ready.
[Bot] Connecting to Discord Gateway using EPL native WebSocket...
[Gateway] ✅ Bot logged in as: EPLAI#1234
```

## Commands in Discord

| Command | Description |
|---------|-------------|
| `!<anything>` | Chat with the AI |
| `!help` | Show all commands |
| `!stats` | Your conversation stats |
| `!forget` | Clear your memory |
