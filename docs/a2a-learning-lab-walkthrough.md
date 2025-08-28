# A2A Learning Lab — Codebase Walkthrough

This guide orients you to this repo through the lens of learning A2A (Agent‑to‑Agent) patterns. It highlights where the A2A pieces live, how messages flow, and how to extend the system.

## Goals
- Understand how agents are exposed as A2A services (JSON‑RPC over HTTP).
- See how AI reasoning + tool calling maps to A2A method invocations.
- Learn the streaming, multi‑turn pattern where each agent contributes individually.
- Quickly run locally with `uv` and iterate on agents.

## Project Structure (as implemented)
- `src/core/`
  - `agent.py`: A2A/LLM bridge. Defines `AIAgent`, `AgentTool`, `A2AMessage`, `A2AResponse`, and `AI_AgentExecutor` with enhanced A2A streaming, multiturn support, and well-known URI discovery.
  - `config.py`: Runtime configuration (`OPENAI_API_KEY`, ports, logging, data paths).
  - `agent_registry.py`: In‑memory discovery/metadata for agents used by the web UI and task routing flows.
- `src/a2a_agents/`
  - `devops/infrastructure_monitor.py`: DevOps agent (Alex) — system metrics, alerts, disk usage.
  - `secops/security_monitor.py`: SecOps agent (Jordan) — mock security checks, alerts.
  - `finops/cost_monitor.py`: FinOps agent (Casey) — cost estimates, optimizations, monthly projection.
  - `containerops/containerops_agent.py`: ContainerOps agent (Morgan) — container management, system info, disk usage.
  - `dataops/data_query.py`: DataOps agent (Dana) — PostgreSQL queries, schema inspection, data analysis.
- `src/web/`
  - `app.py`: FastAPI app with startup agent registration for the dashboard.
  - `routes/chat.py`: Chat endpoints with intelligent A2A routing (single specialist agent responds per message).
  - `routes/api.py`: HTMX components for stats and agents grid.
  - `templates/`: `dashboard.html` + `components/` partials for messages and status.
- `src/main.py`: Launches all agents as A2A JSON‑RPC services (A2A SDK + Uvicorn) and starts the web server.

Notes
- The docs in AGENTS.md use a canonical layout (`src/agents/...`). The implementation here uses `src/a2a_agents/...`. Import paths in code use the `src` package root (e.g., `from core...`, `from a2a_agents...`) assuming `PYTHONPATH=src` or launching from project root.

## How A2A Wiring Works

### 1) Exposing agents as A2A services
- `src/main.py` constructs an A2A server per agent using the A2A SDK:
  - Creates an `AgentCard` (from `a2a.types`) describing the agent.
  - Wraps each `AIAgent` in an `AI_AgentExecutor` (adapter in `src/core/agent.py`).
  - Builds a Starlette app via `A2AStarletteApplication` and serves it with Uvicorn.
  - **NEW**: Adds well-known URI endpoints (`/.well-known/agent-card.json`) for proper A2A agent discovery.
  - Ports:
    - DevOps (Alex): `8082`
    - SecOps (Jordan): `8083`
    - FinOps (Casey): `8084`
    - ContainerOps (Morgan): `8085`
    - DataOps (Dana): `8086`

### 2) Bridging LLM reasoning to A2A
- `AIAgent` encapsulates:
  - `system_prompt`: agent persona and domain.
  - `tools`: OpenAI function-call tool specs derived from `AgentTool`.
  - `process_message(A2AMessage)`: runs an LLM chat completion with tools and then executes tool calls via `_execute_tool`.
  - **NEW**: `request_clarification()`: supports A2A multiturn with `TaskState.input_required`.
  - **NEW**: `to_a2a_message()`: helper for converting A2A SDK types.
- `AI_AgentExecutor.execute(...)` adapts an incoming A2A `RequestContext` into an `A2AMessage`, calls `agent.process_message`, and emits updates via the A2A event queue.
  - **NEW**: Sends progressive `TaskStatusUpdateEvent` for streaming progress.
  - **NEW**: Uses `TaskArtifactUpdateEvent` with `lastChunk=True` for final responses.

### 3) Web chat to A2A agents (intelligent routing)
- `src/web/routes/chat.py` implements proper A2A protocol patterns:
  - `A2ATaskRouter` uses AI-powered routing to determine which single specialist agent should handle each user request
  - `route_to_specialist_agent(...)` sends the message to only the most appropriate agent using JSON‑RPC `message/send` to the agent's root endpoint
  - Each agent response is rendered as its own `div.message` using `components/agent_message.html` with the agent's proper identity
  - Routing rules: Infrastructure/DevOps → Alex, Security → Jordan, Costs → Casey, Containers → Morgan, Database → Dana
  - This follows proper A2A delegation patterns where only the right expert responds, rather than broadcasting to all agents
- Agent self-registration: Each agent registers itself in the registry on startup, enabling dynamic discovery

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
- The launcher starts five A2A services (one per agent) and the web server.
- In chat, your message appears once, followed by a single response from the most appropriate specialist agent — proper A2A task delegation.

## A2A Message Flow (Chat Path)
- UI posts to `/api/chat`.
- Backend renders the user message, then calls `route_to_specialist_agent(...)`:
  - Uses AI-powered routing to determine which single specialist agent should handle the request.
  - Builds a JSON‑RPC 2.0 payload with `method: "message/send"` and a user `Message` (`kind: "text`).
  - Sends only to the selected agent's JSON‑RPC endpoint (`http://localhost:<port>/`).
  - **Enhanced**: Agent sends initial `TaskStatusUpdateEvent` ("processing...").
  - **Enhanced**: Agent sends `TaskArtifactUpdateEvent` with final response.
  - Renders the agent's response with proper agent identity.
- This follows proper A2A delegation patterns where only the right expert responds.

### A2A Agent Discovery
- Each agent serves its `AgentCard` at `/.well-known/agent-card.json` for automatic discovery.
- Agents self-register in the registry on startup.
- Supports both curated registry and well-known URI discovery patterns.

## Extending the Lab
- Add a new agent
  - Create a file under `src/a2a_agents/<domain>/<agent>.py`.
  - Define persona, tools, and `_execute_tool`.
  - Register it in `src/main.py` by adding an entry to `agents_config` with a unique port and `AgentCard` metadata.
  - The routing will automatically include it based on agent registry entries.
- Improve routing logic
  - Modify the routing rules in `A2ATaskRouter.determine_best_agent()` to handle new agent types or capabilities.
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
- Ports in use: agents start on 8082–8086; stop prior processes or adjust.

## A2A Protocol Compliance ✅

This Learning Lab demonstrates advanced A2A protocol patterns:

### Agent Discovery
- **Well-Known URIs**: Each agent serves its `AgentCard` at `/.well-known/agent-card.json`
- **Registry Integration**: Agents self-register for dynamic discovery
- **Capability Advertisement**: Skills and capabilities properly exposed

### Task Lifecycle  
- **Streaming Events**: Progressive `TaskStatusUpdateEvent` during processing
- **Artifact Responses**: `TaskArtifactUpdateEvent` with `lastChunk=True` for final results
- **State Management**: Proper task states (`running`, `completed`, `input_required`)

### Multiturn Conversations
- **Clarification Requests**: Agents can set `TaskState.input_required` 
- **Context Preservation**: Tasks maintain `contextId` across turns
- **Native A2A Types**: Helper methods for SDK integration

### Message Protocol
- **JSON-RPC 2.0**: Proper `message/send` method implementation  
- **Streaming Pattern**: Multiple events per task for progress updates
- **Agent Identity**: Each specialist speaks for themselves

## A2A Docs & SDK References
- A2A protocol topics: agent discovery, extensions, and "life of a task".
- OpenAI Agents Python SDK: sessions, running agents, multi‑agent patterns, memory, and reasoning items.
- Follow the Learning Lab's simplicity constraints: individual agent messages, server‑rendered components, and A2A patterns first.

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
- You should see a single response from the most appropriate agent (likely Alex/DevOps for system status).

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

6) Test Agent Card discovery
- `curl -sS http://localhost:8082/.well-known/agent-card.json` - Get DevOps agent card
- `curl -sS http://localhost:8083/.well-known/agent-card.json` - Get SecOps agent card
- `curl -sS http://localhost:8084/.well-known/agent-card.json` - Get FinOps agent card

Troubleshooting
- Port in use: stop existing processes on 8082–8086/8080 or change ports in `src/core/config.py`.
- OpenAI key: ensure the key is exported or present in `.env`.
