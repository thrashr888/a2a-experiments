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
+--------------------+    +--------------------+    +--------------------+
|   DevOps Agents    |    |   SecOps Agents    |    |   FinOps Agents    |
| - Infrastructure   |    | - Vulnerability    |    | - Cost Monitor     |
| - Deployment       |    | - Security Mon.    |    | - Resource Opt.    |
| - Backup           |    | - Compliance       |    | - Budget Alert     |
| - Log Analysis     |    | - Incident Resp.   |    | - Reporting        |
+--------------------+    +--------------------+    +--------------------+
            \                   |                           /
             \                  |                          /
              \                 |                         /
                       +---------------------+
                       |     Host Agent      |
                       |    (Orchestrator)   |
                       +---------------------+
                                  |
                       +---------------------+
                       |       Web UI        |
                       |   (HTML Frontend)   |
                       +---------------------+
```

## Use Cases

### Multi-Agent Scenarios

1. **Security Incident Response**
   - User reports suspicious activity
   - Security Monitor Agent detects the threat
   - Incident Response Agent coordinates response
   - Infrastructure Monitor Agent checks system impact
   - Cost Monitor Agent assesses incident costs

2. **Resource Optimization**
   - Cost Monitor Agent identifies high usage
   - Resource Optimizer Agent suggests improvements
   - Deployment Agent implements optimizations
   - Backup Agent ensures data safety during changes

3. **Compliance Audit**
   - Compliance Agent runs security checks
   - Vulnerability Scanner Agent identifies issues
   - Deployment Agent applies fixes
   - Reporting Agent generates audit reports

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
│   ├── agents/
│   │   ├── devops/             # DevOps agent implementations
│   │   ├── secops/             # SecOps agent implementations
│   │   └── finops/             # FinOps agent implementations
│   ├── core/
│   │   ├── host_agent.py       # Main orchestrator
│   │   ├── agent_registry.py   # Agent discovery and management
│   │   └── config.py           # Configuration management
│   ├── web/
│   │   ├── app.py              # Web server
│   │   └── static/             # HTML, CSS, JS files
│   └── utils/
│       ├── logging.py          # Structured logging
│       └── metrics.py          # Metrics collection
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
- [Sample Implementations](https://github.com/a2aproject/a2a-samples)
