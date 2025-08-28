# A2A Learning Lab - Agent Development Guide

## Project Overview
This is an A2A (Agent-to-Agent) learning project focused on multi-agent systems. The current implementation includes both static monitoring agents and AI-powered agents that can reason, communicate, and perform complex tasks.

## Critical Development Instructions

- You MUST stick to A2A protocols.
- You MUST use the A2A SDK and OpenAI SDK. Defer to A2A in the case of conflict.

### Python Environment
- **ALWAYS use `uv`** for running Python scripts: `uv run python <script>`
- **ALWAYS use `uv add`** for adding dependencies: `uv add <package>`
- Project uses Python 3.10+ with `uv` for dependency management

### Import Conventions
- **Use absolute imports from src/**: `from src.core.agent import AIAgent`
- **Never use relative imports from core**: `from core.agent import AIAgent` ❌
- **Set PYTHONPATH=src** when needed or run from project root
- **Module structure**: `src/core/`, `src/agents/`, `src/utils/`, `src/web/`

### Agent Architecture

#### Current Agents Structure
```
src/agents/
├── devops/infrastructure_monitor.py    # System monitoring, performance
├── secops/security_monitor.py          # Security analysis, threat detection  
├── finops/cost_monitor.py              # Cost optimization, budget analysis
└── host/coordinator.py                 # Multi-agent orchestration (TBD)
```

#### AI Agent Implementation Pattern
```python
from src.core.agent import AIAgent, AgentTool, A2AMessage
from src.core.config import settings

AGENT_SYSTEM_PROMPT = """
You are [Name], a [role] with expertise in [domain].
[Detailed personality and expertise description]
"""

agent_tools = [
    AgentTool(
        name="tool_name",
        description="What this tool does",
        parameters={"type": "object", "properties": {}}
    )
]

class MyAgent(AIAgent):
    def __init__(self):
        super().__init__(
            agent_id="my-agent-001",
            system_prompt=AGENT_SYSTEM_PROMPT,
            tools=agent_tools
        )
    
    async def _execute_tool(self, tool_call) -> Dict[str, Any]:
        # Implement tool execution logic
        pass
```

### Agent Personalities & Expertise

#### DevOps Agent (Alex)
- **Expertise**: Infrastructure, monitoring, performance optimization, capacity planning
- **Personality**: Methodical, detail-oriented, proactive about preventing issues
- **Tools**: System metrics, resource alerts, performance analysis

#### SecOps Agent (Jordan)  
- **Expertise**: Security monitoring, threat detection, vulnerability assessment, incident response
- **Personality**: Vigilant, thorough, always thinking about potential threats
- **Tools**: Security logs, failed login detection, vulnerability scans

#### FinOps Agent (Casey)
- **Expertise**: Cost optimization, budget planning, resource efficiency, ROI analysis
- **Personality**: Data-driven, business-focused, always looking for savings opportunities  
- **Tools**: Cost analysis, optimization recommendations, budget projections

#### Coordinator Agent (Sam) - Not yet implemented
- **Role**: Team lead who coordinates between specialists
- **Personality**: Strategic thinker, excellent communicator, sees big picture
- **Capability**: Delegates to appropriate agents, synthesizes responses

### Technology Stack
- **Backend**: FastAPI with HTMX for server-rendered components
- **AI**: OpenAI GPT-5 with function calling for tool use
- **Storage**: Redis for conversation history, PostgreSQL for persistent data
- **Deployment**: Docker Compose with health checks
- **Frontend**: Dark theme inspired by HashiCorp/Vercel/Linear

### Development Workflow
1. **Always test locally first**: `uv run python -m src.agents.{type}.{agent}`
2. **Use Docker for integration**: `docker compose up app`
3. **Check imports carefully**: Use `from src.` prefix for all internal imports
4. **Follow AI agent patterns**: System prompt → Tools → Execute pattern
5. **Test A2A communication**: Agents should communicate via A2AMessage/A2AResponse

### Key Files
- `src/core/agent.py` - AI agent base classes and A2A message types
- `src/core/config.py` - Configuration including OpenAI model settings
- `src/utils/redis_client.py` - Conversation history management
- `src/web/app.py` - HTMX endpoints for UI integration
- `docs/ai-agent-integration.md` - Detailed architecture documentation

### Environment Variables Needed
```bash
OPENAI_API_KEY=sk-...           # Required for AI agents
```

### Common Issues & Solutions
- **Import errors**: Use `from src.` prefix, not relative imports
- **Module not found**: Run with `uv run python` from project root
- **Redis connection**: Ensure Redis container is running
- **OpenAI API**: Set OPENAI_API_KEY environment variable

### Testing AI Agents
```bash
# Test individual agent
uv run python -m src.agents.finops.cost_monitor

# Test via A2A protocol  
uv run python -c "
from src.core.agent import A2AMessage
from src.agents.finops.cost_monitor import FinOpsAgent
import asyncio

async def test():
    agent = FinOpsAgent()
    msg = A2AMessage('test', agent.agent_id, 'analyze_costs', {}, 'test-conv')
    response = await agent.process_message(msg)
    print(response.response)

asyncio.run(test())
"
```

### A2A Streaming Multiturn Pattern Implementation ✅

#### Current Working Implementation
- **Multi-Turn Chat**: Each agent contributes individual messages to conversation thread
- **Streaming Pattern**: Follows A2A protocol for agent-to-agent communication
- **Working Agents**: DevOps (Alex) and FinOps (Casey) providing real agent responses
- **Individual Messages**: Each agent sends separate `div.message` - no aggregation

#### Key Features Implemented
```python
# Each agent contributes individually (A2A streaming pattern)
async def trigger_agent_contributions(conversation_id, user_message, html_parts):
    agents = [
        {"name": "🏗️ Infrastructure Monitor (Alex)", "port": 8082, "method": "get_system_metrics"},
        {"name": "💰 Cost Monitor (Casey)", "port": 8084, "method": "get_resource_costs"}
    ]
    
    # Each agent adds its own separate message
    for agent in agents:
        # Call agent -> Get response -> Add individual div.message
```

#### Message Flow Example
1. **User**: "Check system status" → Single user message div
2. **Alex**: Individual infrastructure analysis → Separate agent message div  
3. **Casey**: Individual cost analysis → Separate agent message div

#### Requirements for Simplicity
- **Keep HTML in component templates** (not Python strings)
- **Focus on learning over complexity**
- **Maintain A2A protocol patterns**
- **Individual agent contributions, no aggregation**

### Next Steps for AI Agent Development  
1. **✅ Implement A2A streaming multiturn pattern** - COMPLETED
2. **✅ Create individual agent message contributions** - COMPLETED  
3. **Refactor HTML to component templates** for simplicity
4. **Add SecOps agent (Jordan)** - currently intermittent
5. **Enhance agent reasoning** with context awareness

## Learning Objectives
This project demonstrates:
- **Multi-agent communication** via A2A protocol
- **AI agent reasoning** with tool use and function calling
- **Specialized agent domains** (DevOps, SecOps, FinOps)
- **Emergent behavior** through agent collaboration
- **Human-AI-agent interaction** patterns
- **Scalable agent architectures** for real-world applications

# Resources

- https://a2a-protocol.org/latest/topics/agent-discovery/   
- https://a2a-protocol.org/latest/topics/extensions/                                              
- https://a2a-protocol.org/latest/topics/life-of-a-task/#agent-message-or-a-task                  
- https://a2a-protocol.org/latest/topics/a2a-and-mcp/
- https://a2a-protocol.org/latest/tutorials/python/7-streaming-and-multiturn/
- https://openai.github.io/openai-agents-python/sessions/
- https://openai.github.io/openai-agents-python/running_agents/
- https://openai.github.io/openai-agents-python/multi_agent/
- https://openai.github.io/openai-agents-python/ref/memory/
- https://openai.github.io/openai-agents-python/ref/items/#agents.items.ReasoningItem
- 
