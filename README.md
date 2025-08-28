# A2A Learning Lab - DevOps, SecOps, and FinOps Agent Ecosystem

A learning project exploring the Agent2Agent (A2A) Protocol with specialized agents for DevOps, SecOps, and FinOps operations in a homelab environment.

## Overview

This project implements a multi-agent system using the A2A Protocol where specialized agents collaborate to handle infrastructure operations, security monitoring, and financial optimization tasks. The system is designed to run in a Docker container on a homelab server.

## Agent Types

### DevOps Agents
- **Infrastructure Monitor Agent**: Monitors system resources, disk usage, network connectivity
- **Deployment Agent**: Handles container deployments, service restarts, configuration updates
- **Backup Agent**: Manages automated backups, restoration tasks, cleanup policies
- **Log Analysis Agent**: Parses logs, identifies issues, generates alerts

### SecOps Agents
- **Vulnerability Scanner Agent**: Scans for security vulnerabilities in containers and services
- **Security Monitor Agent**: Monitors failed login attempts, suspicious network activity
- **Compliance Agent**: Checks configuration compliance against security baselines
- **Incident Response Agent**: Coordinates security incident response workflows

### FinOps Agents
- **Cost Monitor Agent**: Tracks resource usage costs, cloud spending, energy consumption
- **Resource Optimizer Agent**: Identifies underutilized resources, suggests optimizations
- **Budget Alert Agent**: Monitors spending against budgets, sends cost alerts
- **Reporting Agent**: Generates financial reports, cost breakdowns, ROI analysis

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           A2A Task Router                              │
│                     AI-Powered Intelligent Routing                     │
│                                                                         │
│  User Question → Route to Single Best Agent → Agent Responds           │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            │                       │                       │
┌───────────▼──────────┐ ┌─────────▼──────────┐ ┌─────────▼──────────┐
│   DevOps Agent       │ │   SecOps Agent     │ │   FinOps Agent     │
│   (Alex)             │ │   (Jordan)         │ │   (Casey)          │
│   Infrastructure &   │ │   Security &       │ │   Cost Analysis &  │
│   System Monitoring  │ │   Threat Detection │ │   Optimization     │
└──────────────────────┘ └────────────────────┘ └────────────────────┘

┌─────────────────────┐      ┌─────────────────────┐
│  Docker Agent       │      │  DataOps Agent      │
│  (Morgan)           │      │  (Dana)             │
│  Container Mgmt &   │      │  PostgreSQL Queries│
│  Docker Operations  │      │  & Data Analysis    │
└─────────────────────┘      └─────────────────────┘
                        │
            ┌─────────────────────┐
            │      Web UI         │
            │  (HTMX + FastAPI)   │
            └─────────────────────┘
```

## Key Features

### ✅ **Proper A2A Protocol Implementation**
- **Intelligent Task Routing**: AI determines which single specialist agent should handle each request
- **Agent Identity**: Each agent speaks for themselves with their unique expertise and persona
- **Real Specialist Responses**: Only the most appropriate agent responds (no coordinator speaking for others)
- **Dynamic Agent Discovery**: Agents self-register and are discoverable via registry

### 🎯 **Smart Agent Routing**
- **DevOps Questions** → Alex (Infrastructure Monitor): system metrics, performance, disk usage
- **Security Questions** → Jordan (Security Monitor): threats, vulnerabilities, alerts  
- **Cost Questions** → Casey (Cost Monitor): spending analysis, optimization recommendations
- **Docker Questions** → Morgan (Docker Monitor): container management, Docker system info
- **Database Questions** → Dana (DataOps): PostgreSQL queries, schema inspection, data analysis

### 🔧 **Agent Capabilities**
- **Alex (DevOps)**: System monitoring, resource alerts, disk usage analysis
- **Jordan (SecOps)**: Security monitoring, threat detection, compliance checks
- **Casey (FinOps)**: Cost analysis, budget tracking, optimization suggestions  
- **Morgan (Docker)**: Container management (start/stop/restart), system monitoring, disk usage
- **Dana (DataOps)**: PostgreSQL database queries, schema inspection, data analysis and reporting

## Technology Stack

- **Language**: Python 3.10+ with `uv` for dependency management
- **A2A SDK**: `a2a-sdk[http-server]` for agent communication
- **Web UI**: Self-contained HTML/CSS/JavaScript
- **Database**: PostgreSQL (via docker-compose)
- **Cache**: Redis (via docker-compose)
- **Container**: Docker with multi-stage builds
- **Orchestration**: Docker Compose

## Project Structure

```
a2a-experiments/
├── README.md
├── pyproject.toml              # uv project configuration
├── docker-compose.yml          # PostgreSQL, Redis, app services
├── Dockerfile                  # Multi-stage container build
├── src/
│   ├── a2a_agents/
│   │   ├── devops/             # DevOps agent implementations
│   │   ├── secops/             # SecOps agent implementations
│   │   └── finops/             # FinOps agent implementations
│   ├── agents/
│   │   └── memory/             # Lightweight SQLite session storage
│   ├── core/
│   │   ├── agent.py            # Agent base + executor glue
│   │   ├── agent_registry.py   # Agent discovery and management
│   │   └── config.py           # Configuration management
│   ├── web/
│   │   ├── app.py              # Web server
│   │   └── static/             # HTML, CSS, JS files
│   └── utils/
│       └── a2a_mock.py         # Local A2A mock server/client utilities
├── tests/                      # Unit and integration tests
├── scripts/
│   ├── setup-dev.sh            # Development environment setup
│   └── health-check.sh         # Container health checks
└── docs/
    ├── agents.md               # Agent specifications
    └── deployment.md           # Deployment guide
```

## Quick Start

### Development Setup

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Initialize project
uv init --python 3.10
uv add "a2a-sdk[http-server]"
uv add fastapi uvicorn psycopg2-binary redis

# Start development services
docker-compose up -d postgres redis

# Run the application
uv run src/main.py
```

### Production Deployment

```bash
# Build and start all services
docker-compose up --build

# Access web interface
open http://localhost:8080
```

## Learning Goals

1. **A2A Protocol Understanding**: Learn how agents discover and communicate with each other
2. **Multi-Agent Orchestration**: Understand how to coordinate complex workflows across multiple agents
3. **Homelab Integration**: Practice deploying containerized applications in a home server environment
4. **Ops Domains**: Explore DevOps, SecOps, and FinOps practices through agent-based automation
5. **Python Development**: Use modern Python tooling (`uv`) and async programming patterns

## Next Steps

1. Implement basic Host Agent and agent registry
2. Create simple DevOps agents (infrastructure monitoring, log parsing)
3. Build minimal web UI for agent interaction
4. Add SecOps agents for security monitoring
5. Implement FinOps agents for cost tracking
6. Create complex multi-agent workflows
7. Add monitoring and alerting capabilities
8. Implement agent configuration and deployment automation

## Resources

- [A2A Protocol Documentation](https://github.com/a2aproject/A2A)
- [A2A Python SDK](https://github.com/a2aproject/a2a-python)

- [A2A Python SDK Tutorial - Agent Skills and Card](https://a2a-protocol.org/latest/tutorials/python/3-agent-skills-and-card/)
- [A2A Python SDK Tutorials - Agent Executor](https://a2a-protocol.org/latest/tutorials/python/4-agent-executor/)
- [A2A Python SDK Tutorials - Interact with Server](https://a2a-protocol.org/latest/tutorials/python/6-interact-with-server/)
  - [A2A Python SDK Tutorials - Streaming and Multiturn](https://a2a-protocol.org/latest/tutorials/python/7-streaming-and-multiturn/)

## Container Registry (GHCR)

- Publishing: GitHub Actions builds and pushes images to GHCR on pushes to `main` and version tags (`v*.*.*`).
- Image: `ghcr.io/<owner>/<repo>` (for this repo: `ghcr.io/<owner>/a2a-experiments`).
- Tags: branch name, git tag (e.g., `v1.2.3`), `latest` on default branch, and a `sha` tag.
  - Nightly builds: scheduled daily and tagged as `nightly`.

### Pull and Run

```bash
# Latest stable from default branch
docker pull ghcr.io/<owner>/<repo>:latest

# Nightly build
docker pull ghcr.io/<owner>/<repo>:nightly
docker run --rm -p 8080:8080 \
  -e OPENAI_API_KEY=sk-... \
  ghcr.io/<owner>/<repo>:latest
```

### GitHub Setup Notes

- Ensure repository Settings → Actions → General → Workflow permissions is set to “Read and write permissions”.
- No personal token needed: the workflow uses `${{ secrets.GITHUB_TOKEN }}` with `packages: write` permissions to push to GHCR.

## Connecting DataOps to Host Postgres

- Easiest (recommended): use `PGHOST=host.docker.internal` so the container reaches your macOS Postgres.
- Homebrew defaults (local runs):
  - Host `localhost`, Port `5432`, User `<your macOS username>`, DB `<your macOS username>`, empty password.
- Optional (advanced, sockets):
  - Set Postgres `unix_socket_directories` to a stable path (e.g., `/opt/homebrew/var/run/postgresql`).
  - Mount it into the container (see commented volume in `docker-compose.yml`).
  - Set `PGHOST` to the mounted path (e.g., `/var/run/postgresql`).
