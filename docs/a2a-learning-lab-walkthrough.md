# A2A Learning Lab — Codebase Walkthrough

This guide orients you to this repo through the lens of learning A2A (Agent‑to‑Agent) patterns. It highlights where the A2A pieces live, how messages flow, and how to extend the system.

## Goals
- Understand how agents are exposed as A2A services (JSON‑RPC over HTTP).
- See how AI reasoning + tool calling maps to A2A method invocations.
- Learn the streaming, multi‑turn pattern where each agent contributes individually.
- Quickly run locally with `uv` and iterate on agents.

## Project Structure (as implemented)
- `src/core/`
  - `agent.py`: A2A/LLM bridge. Defines `AIAgent`, `AgentTool`, `A2AMessage`, `A2AResponse`, and `AI_AgentExecutor` that adapts an `AIAgent` to the A2A server runtime.
  - `config.py`: Runtime configuration (`OPENAI_API_KEY`, ports, logging, data paths).
  - `agent_registry.py`: In‑memory discovery/metadata for agents used by the web UI and coordinator flows.
  - `host_agent.py`: Experimental coordinator agent (Sam) with a “delegate_to_agent” tool (not primary path).
- `src/a2a_agents/`
  - `devops/infrastructure_monitor.py`: DevOps agent (Alex) — system metrics, alerts, disk usage.
  - `secops/security_monitor.py`: SecOps agent (Jordan) — mock security checks, alerts.
  - `finops/cost_monitor.py`: FinOps agent (Casey) — cost estimates, optimizations, monthly projection.
  - `coordinator/chat_coordinator.py`: Alternative coordinator prototype (not used by the web path); shows direct agent calls.
- `src/web/`
  - `app.py`: FastAPI app with startup agent registration for the dashboard.
  - `routes/chat.py`: Chat endpoints and the A2A streaming multi‑turn pattern (each agent posts an individual message).
  - `routes/api.py`: HTMX components for stats and agents grid.
  - `templates/`: `dashboard.html` + `components/` partials for messages and status.
- `src/utils/a2a_mock.py`: Minimal FastAPI “A2A server” helper used by early prototypes. The live A2A runtime is created in `src/main.py` via the A2A SDK.
- `src/main.py`: Launches all agents as A2A JSON‑RPC services (A2A SDK + Uvicorn) and starts the web server.

Notes
- The docs in AGENTS.md use a canonical layout (`src/agents/...`). The implementation here uses `src/a2a_agents/...`. Import paths in code use the `src` package root (e.g., `from core...`, `from a2a_agents...`) assuming `PYTHONPATH=src` or launching from project root.

## How A2A Wiring Works

### 1) Exposing agents as A2A services
- `src/main.py` constructs an A2A server per agent using the A2A SDK:
  - Creates an `AgentCard` (from `a2a.types`) describing the agent.
  - Wraps each `AIAgent` in an `AI_AgentExecutor` (adapter in `src/core/agent.py`).
  - Builds a Starlette app via `A2AStarletteApplication` and serves it with Uvicorn.
  - Ports:
    - Coordinator (Sam): `8081`
    - DevOps (Alex): `8082`
    - SecOps (Jordan): `8083`
    - FinOps (Casey): `8084`

### 2) Bridging LLM reasoning to A2A
- `AIAgent` encapsulates:
  - `system_prompt`: agent persona and domain.
  - `tools`: OpenAI function-call tool specs derived from `AgentTool`.
  - `process_message(A2AMessage)`: runs an LLM chat completion with tools and then executes tool calls via `_execute_tool`.
- `AI_AgentExecutor.execute(...)` adapts an incoming A2A `RequestContext` into an `A2AMessage`, calls `agent.process_message`, and emits updates via the A2A event queue.

### 3) Web chat to A2A agents (multi‑turn streaming)
- `src/web/routes/chat.py` implements the Learning Lab chat UX:
  - `trigger_agent_contributions(...)` loops over agents and sends each a separate message using JSON‑RPC `message/send` to each agent’s root endpoint (A2A style). Each response is rendered as its own `div.message` using `components/agent_message.html` — this is the “A2A streaming multi‑turn pattern”.
  - For simplicity and clear learning, no final aggregation is performed — each specialist speaks for themselves.
  - A second, simpler path (`process_message_multi_turn`) shows direct REST calls to `/process` on known ports for DevOps/FinOps.
- `src/web/app.py` registers demo agents into the UI registry on startup so the dashboard can show them.

## Agent Implementation Pattern
Each domain agent follows the same structure: persona + tools + tool executor.

Example: DevOps (Alex) — `src/a2a_agents/devops/infrastructure_monitor.py`
- Tools
  - `get_system_metrics`: CPU/memory/disk via `psutil`.
  - `get_resource_alerts`: simple threshold alerts.
  - `check_disk_usage(path)`: disk usage for a given path.
- `_execute_tool(...)` dispatches to async helpers that return structured JSON; the LLM composes the final response based on tool results.

FinOps (Casey) and SecOps (Jordan) follow the same shape, with tailored tools and mock data where needed.

## Running Locally
Prereqs
- Python 3.10+
- `uv` (package and run manager)
- Environment variable: `OPENAI_API_KEY` (required for LLM calls)

Steps
- From project root:
  - `export OPENAI_API_KEY=sk-...`
  - `uv run python src/main.py`
  - Open `http://localhost:8080` for the dashboard/chat.

Behavior
- The launcher starts four A2A services (one per agent) and the web server.
- In chat, your message appears once, followed by individual agent messages (Alex, Jordan, Casey) rendered separately — no aggregation.

## A2A Message Flow (Chat Path)
- UI posts to `/api/chat`.
- Backend renders the user message, then calls `trigger_agent_contributions(...)`:
  - Builds a JSON‑RPC 2.0 payload with `method: "message/send"` and a user `Message` (`kind: "text").
  - Sends to each agent’s JSON‑RPC endpoint (`http://localhost:<port>/`).
  - Handles each agent’s result and adds an individual message component.
- This mirrors how A2A agents converse in a shared thread while remaining decoupled.

## Extending the Lab
- Add a new agent
  - Create a file under `src/a2a_agents/<domain>/<agent>.py`.
  - Define persona, tools, and `_execute_tool`.
  - Register it in `src/main.py` by adding an entry to `agents_config` with a unique port and `AgentCard` metadata.
  - Optionally include it in the streaming list in `trigger_agent_contributions(...)` for UI participation.
- Improve coordinator routing
  - `src/web/routes/chat.py` contains `AICoordinator` that builds a dynamic tool `call_agent` from the registry. You can use this to let the LLM decide which agent to call.
- Persist conversations (optional)
  - You can add a lightweight in-memory or file-backed history later if desired, but it isn’t required to learn A2A patterns here.
- Refactor HTML
  - Keep HTML in `templates/components` (already done). Avoid constructing HTML in Python strings.

## Useful Files & Pointers
- A2A adapter: `src/core/agent.py` (`AI_AgentExecutor`, `AIAgent`)
- Agents: `src/a2a_agents/*/*_monitor.py`
- Web routing: `src/web/routes/chat.py`, `src/web/routes/api.py`
- UI templates: `src/web/templates/` and `src/web/templates/components/`
- Launcher: `src/main.py`

## Common Issues
- Import paths: ensure `PYTHONPATH=src` (running via `uv run python src/main.py` from project root achieves this).
- OpenAI key: set `OPENAI_API_KEY` in your environment.
- Ports in use: agents start on 8081–8084; stop prior processes or adjust.

## A2A Docs & SDK References
- A2A protocol topics: agent discovery, extensions, and “life of a task”.
- OpenAI Agents Python SDK: sessions, running agents, multi‑agent patterns, memory, and reasoning items.
- Follow the Learning Lab’s simplicity constraints: individual agent messages, server‑rendered components, and A2A patterns first.

## Try It

Quick, copy‑paste friendly steps to see the A2A pattern in action.

1) Prepare environment
- Copy env and set `OPENAI_API_KEY`:
  - `cp .env.example .env`
  - `export OPENAI_API_KEY=sk-...` (or put it in `.env`)

2) Run everything with `uv`
- `uv run python src/main.py`
- Open `http://localhost:8080` in a browser.

3) Chat from the UI
- Type: `Check system status`
- You should see three separate agent messages (Alex/DevOps, Jordan/SecOps, Casey/FinOps) appear as individual bubbles — no aggregation.

4) Curl the chat endpoint (returns HTML snippet)
- `curl -sS -X POST -H 'Content-Type: application/x-www-form-urlencoded' \
    -d 'message=Check system status' http://localhost:8080/api/chat`

5) Directly ping an agent via A2A JSON‑RPC
- DevOps (Alex) example:
  - `curl -sS http://localhost:8082/ -H 'Content-Type: application/json' -d '{
        "jsonrpc": "2.0",
        "method": "message/send",
        "params": {"message": {"messageId": "cli-test-1", "role": "user", "parts": [{"kind": "text", "text": "get_system_metrics"}]}},
        "id": "1"
      }'`

Troubleshooting
- Port in use: stop existing processes on 8081–8084/8080 or change ports in `src/core/config.py`.
- OpenAI key: ensure the key is exported or present in `.env`.
