# AI Agent Integration Guide

## Overview

This document outlines how to transform the current A2A Learning Lab from static monitoring agents into intelligent AI agents that can reason, communicate, and perform complex tasks. The goal is to create a multi-agent system where specialized AI agents collaborate through the coordinator to solve problems.

## Current Architecture vs AI Architecture

### Current State
- **Static Agents**: Fixed responses, hardcoded logic
- **Simple Tools**: Basic system monitoring (CPU, memory, disk)  
- **No Reasoning**: Agents return predetermined responses
- **Limited Interaction**: Users trigger predefined workflows

### Target AI Architecture
- **AI Agents**: LLM-powered with distinct personas and expertise
- **Intelligent Tools**: Agents can reason about when and how to use tools
- **Dynamic Responses**: Context-aware, conversational responses
- **Chat Interface**: Natural language interaction with coordinator

## AI Agent Design Patterns

### 1. Agent Personas & System Prompts

Each agent should have a distinct personality and expertise area:

#### DevOps Agent (Infrastructure Specialist)
```python
DEVOPS_SYSTEM_PROMPT = """
You are Alex, a senior DevOps engineer with 10 years of experience in infrastructure management. 

Your expertise includes:
- System monitoring and alerting
- Infrastructure automation  
- Performance optimization
- Capacity planning
- Incident response

Your personality: Methodical, detail-oriented, proactive about preventing issues.

When answering questions:
1. Always check current system metrics first
2. Provide specific, actionable recommendations
3. Consider both immediate fixes and long-term improvements
4. Use infrastructure terminology naturally

Available tools:
- get_system_metrics() - Get current CPU, memory, disk stats
- get_resource_alerts() - Check for resource warnings
- analyze_performance_trends() - Historical analysis
"""
```

#### SecOps Agent (Security Specialist)  
```python
SECOPS_SYSTEM_PROMPT = """
You are Jordan, a cybersecurity analyst with expertise in threat detection and incident response.

Your expertise includes:
- Security monitoring and analysis
- Threat hunting and detection
- Vulnerability assessment
- Security policy enforcement
- Incident investigation

Your personality: Vigilant, thorough, always thinking about potential threats.

When answering questions:
1. Always assess security implications
2. Look for indicators of compromise
3. Recommend defense-in-depth strategies
4. Prioritize by risk level

Available tools:
- scan_security_logs() - Analyze recent security events
- check_failed_logins() - Detect brute force attempts
- analyze_network_traffic() - Look for suspicious patterns
- vulnerability_scan() - Check for known vulnerabilities
"""
```

#### FinOps Agent (Cost Optimization Specialist)
```python
FINOPS_SYSTEM_PROMPT = """
You are Casey, a FinOps engineer focused on cloud cost optimization and financial accountability.

Your expertise includes:
- Cost monitoring and analysis
- Resource optimization
- Budget planning and forecasting
- Chargeback and showback
- Cost anomaly detection

Your personality: Data-driven, business-focused, always looking for savings opportunities.

When answering questions:
1. Always consider cost implications
2. Provide ROI calculations when relevant
3. Suggest both immediate and strategic optimizations
4. Balance performance with cost

Available tools:
- get_resource_costs() - Current spending breakdown
- analyze_cost_trends() - Historical cost analysis
- get_optimization_recommendations() - Cost-saving suggestions
- calculate_savings_potential() - ROI projections
"""
```

#### Coordinator Agent (Orchestrator)
```python
COORDINATOR_SYSTEM_PROMPT = """
You are Sam, the team lead who coordinates between DevOps, SecOps, and FinOps specialists.

Your role:
- Understand user requests and delegate to appropriate specialists
- Synthesize information from multiple agents
- Provide holistic recommendations
- Facilitate collaboration between specialists
- Present findings in a clear, executive-friendly format

Your personality: Strategic thinker, excellent communicator, good at seeing the big picture.

When handling requests:
1. Analyze what expertise is needed
2. Ask relevant agents for their input
3. Synthesize responses into coherent recommendations
4. Always consider cross-functional implications (security + cost + performance)
5. Present actionable next steps

Available agents:
- DevOps (Alex) - Infrastructure and performance
- SecOps (Jordan) - Security and compliance  
- FinOps (Casey) - Cost optimization and budgeting
"""
```

### 2. Tool Integration Architecture

#### Tool Function Definitions
```python
from typing import Dict, List, Any
import json

class AgentTool:
    def __init__(self, name: str, description: str, parameters: Dict):
        self.name = name
        self.description = description
        self.parameters = parameters
    
    def to_openai_function(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }

# DevOps Tools
devops_tools = [
    AgentTool(
        name="get_system_metrics",
        description="Get current system resource utilization",
        parameters={
            "type": "object",
            "properties": {
                "include_history": {
                    "type": "boolean",
                    "description": "Include historical data for trend analysis"
                }
            }
        }
    ),
    AgentTool(
        name="analyze_performance",
        description="Analyze system performance and identify bottlenecks",
        parameters={
            "type": "object", 
            "properties": {
                "time_window": {
                    "type": "string",
                    "description": "Time window for analysis (1h, 24h, 7d)"
                }
            }
        }
    )
]
```

### 3. A2A Communication with AI

#### Enhanced A2A Message Format
```python
@dataclass
class A2AMessage:
    sender_id: str
    receiver_id: str
    method: str
    params: Dict[str, Any]
    conversation_id: str  # Track conversations
    context: Dict[str, Any]  # Additional context
    requires_reasoning: bool = True  # Flag for AI processing
    
@dataclass 
class A2AResponse:
    sender_id: str
    receiver_id: str
    conversation_id: str
    response: str  # Natural language response
    data: Dict[str, Any]  # Structured data
    tool_calls: List[Dict]  # Tools used
    confidence: float  # Response confidence 0-1
```

#### AI Agent Base Class
```python
from openai import AsyncOpenAI
from typing import List, Dict, Any

class AIAgent:
    def __init__(self, agent_id: str, system_prompt: str, tools: List[AgentTool]):
        self.agent_id = agent_id
        self.system_prompt = system_prompt
        self.tools = tools
        self.client = AsyncOpenAI()
        self.conversation_history = {}
    
    async def process_message(self, message: A2AMessage) -> A2AResponse:
        """Process incoming A2A message with AI reasoning"""
        
        # Get conversation context
        conversation = self.conversation_history.get(message.conversation_id, [])
        
        # Build messages for LLM
        messages = [
            {"role": "system", "content": self.system_prompt},
            *conversation,
            {"role": "user", "content": self._format_user_message(message)}
        ]
        
        # Call OpenAI with function calling
        response = await self.client.chat.completions.create(
            model="gpt-5",
            messages=messages,
            tools=[tool.to_openai_function() for tool in self.tools],
            tool_choice="auto"
        )
        
        # Process tool calls
        tool_results = []
        if response.choices[0].message.tool_calls:
            for tool_call in response.choices[0].message.tool_calls:
                result = await self._execute_tool(tool_call)
                tool_results.append(result)
        
        # Generate final response
        final_response = await self._generate_response(
            messages, response, tool_results
        )
        
        # Update conversation history
        self._update_conversation(message.conversation_id, messages, response)
        
        return A2AResponse(
            sender_id=self.agent_id,
            receiver_id=message.sender_id,
            conversation_id=message.conversation_id,
            response=final_response,
            data={"tool_results": tool_results},
            tool_calls=[tc.function for tc in response.choices[0].message.tool_calls or []]
        )
```

### 4. Chat Interface Design

#### WebSocket Chat Implementation
```python
from fastapi import WebSocket
import asyncio
import json

@app.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    await websocket.accept()
    conversation_id = str(uuid.uuid4())
    
    try:
        while True:
            # Receive user message
            data = await websocket.receive_text()
            user_message = json.loads(data)
            
            # Send to coordinator agent
            coordinator = get_coordinator_agent()
            response = await coordinator.process_user_request(
                user_message["text"], 
                conversation_id
            )
            
            # Stream response back to user
            await websocket.send_text(json.dumps({
                "type": "agent_response",
                "agent": "coordinator", 
                "text": response.response,
                "thinking": response.data.get("reasoning"),
                "agents_consulted": response.data.get("agents_consulted", [])
            }))
            
    except Exception as e:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": str(e)
        }))
```

#### Frontend Chat Component (HTMX + WebSocket)
```html
<!-- Chat Interface -->
<div id="chat-container" class="chat-container">
    <div id="chat-messages" class="chat-messages">
        <!-- Messages appear here -->
    </div>
    
    <div class="chat-input">
        <input type="text" 
               id="chat-input" 
               placeholder="Ask the coordinator a question..."
               hx-trigger="keyup[keyCode==13]"
               hx-post="/api/chat/send"
               hx-target="#chat-messages"
               hx-swap="beforeend">
        <button hx-post="/api/chat/send" hx-include="#chat-input">Send</button>
    </div>
</div>

<script>
// WebSocket for real-time chat
const ws = new WebSocket('ws://localhost:8080/ws/chat');
ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    const messagesDiv = document.getElementById('chat-messages');
    
    if (data.type === 'agent_response') {
        messagesDiv.innerHTML += `
            <div class="message agent-message">
                <div class="message-header">
                    <strong>${data.agent}</strong>
                    ${data.agents_consulted ? `<small>Consulted: ${data.agents_consulted.join(', ')}</small>` : ''}
                </div>
                <div class="message-content">${data.text}</div>
                ${data.thinking ? `<details><summary>Reasoning</summary>${data.thinking}</details>` : ''}
            </div>
        `;
    }
    
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
};
</script>
```

### 5. Example Interaction Flows

#### Scenario 1: Performance Investigation
```
User: "The system seems slow today. What's going on?"

Coordinator: "I'll investigate the performance issue. Let me check with our DevOps specialist."

[A2A] Coordinator -> DevOps: {
    "method": "investigate_performance",
    "params": {"complaint": "system seems slow"},
    "conversation_id": "conv_123"
}

DevOps Agent (thinking):
- User reports slowness
- Need to check current system metrics
- Should look at recent trends
- May need to identify specific bottlenecks

[Tool Call] get_system_metrics(include_history=true)
[Tool Call] analyze_performance(time_window="1h")

DevOps Response: "I found the issue! CPU utilization has been consistently above 85% for the past hour, with memory at 78%. There's a process consuming excessive resources. I recommend immediate investigation of high-CPU processes and possibly adding resources."

Coordinator: "Based on Alex's analysis, your system slowness is caused by high CPU utilization (85%+) and memory pressure (78%). Here's what I recommend:

**Immediate Actions:**
1. Identify and investigate high-CPU processes
2. Consider killing non-essential processes
3. Monitor for improvement

**Short-term:**
- Add CPU/memory resources if this is a recurring pattern
- Set up alerts for 80%+ resource utilization

Would you like me to have Jordan check if this could be related to any security issues, or Casey to analyze the cost implications of scaling up resources?"
```

#### Scenario 2: Security + Cost Analysis
```
User: "We're getting a lot of failed login attempts. Should we be worried and what will it cost to improve security?"

Coordinator: "This requires both security analysis and cost assessment. Let me consult with Jordan and Casey."

[Parallel A2A calls]
Coordinator -> SecOps: "Analyze failed login patterns and security risk"
Coordinator -> FinOps: "Estimate costs for improved security measures"

SecOps: "I detected 847 failed login attempts in the past hour from 15 different IPs. This appears to be a coordinated brute force attack. Risk level: HIGH. I recommend immediate implementation of rate limiting, IP blocking, and 2FA."

FinOps: "Security improvements will cost approximately $150-300/month depending on solution. However, a successful breach could cost $50K-500K. ROI strongly favors investment in security."

Coordinator: "**SECURITY ALERT**: You're experiencing a coordinated brute force attack (847 attempts from 15 IPs). 

**Immediate Actions Required:**
1. Implement rate limiting (block IPs after 5 failed attempts)
2. Enable 2FA for all accounts
3. Monitor attack patterns

**Cost Analysis:**
- Security improvements: $150-300/month
- Potential breach cost: $50K-500K
- **Recommendation**: Immediate investment justified

Shall I have Jordan implement the security measures while Casey sets up monitoring for ongoing security costs?"
```

### 6. Implementation Roadmap

#### Phase 1: AI Agent Foundation
1. **Setup LLM Integration**
   - Add OpenAI client to agents
   - Implement function calling
   - Create agent base classes

2. **Enhance A2A Protocol**
   - Add conversation tracking
   - Support for reasoning/context
   - Tool call integration

3. **Update Agent Implementations**
   - Replace static responses with AI reasoning
   - Add system prompts and personas
   - Implement tool functions

#### Phase 2: Chat Interface
1. **WebSocket Integration**
   - Real-time chat communication
   - Message streaming
   - Connection management

2. **Frontend Chat UI**
   - HTMX-based chat interface
   - Message history
   - Typing indicators

3. **Coordinator Intelligence**
   - Multi-agent orchestration
   - Context synthesis
   - Response formatting

#### Phase 3: Advanced Features
1. **Conversation Memory**
   - Persistent chat history
   - Context across sessions
   - Learning from interactions

2. **Advanced Tool Integration**
   - External API calls
   - Database operations
   - File system operations

3. **Agent Collaboration**
   - Multi-step workflows
   - Agent-to-agent consultation
   - Conflict resolution

### 7. Configuration & Environment

#### Environment Variables
```bash
# AI Configuration
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5
AI_TEMPERATURE=0.1
MAX_TOKENS=2000

# A2A Configuration  
A2A_CONVERSATION_TIMEOUT=3600
A2A_MAX_HISTORY_LENGTH=20
A2A_ENABLE_REASONING_LOGS=true

# Agent Configuration
DEVOPS_AGENT_ENABLED=true
SECOPS_AGENT_ENABLED=true
FINOPS_AGENT_ENABLED=true
COORDINATOR_AGENT_ENABLED=true
```

#### Dependencies
```toml
# Add to pyproject.toml
[project.dependencies]
openai = "^1.0.0"
tiktoken = "^0.5.0"  # Token counting
websockets = "^12.0"  # WebSocket support
redis = "^5.0.0"  # Conversation persistence
sentence-transformers = "^2.2.0"  # Semantic search
```

### 8. Learning Objectives

This AI agent integration demonstrates key A2A concepts:

1. **Agent Autonomy**: Each AI agent makes independent decisions using its tools and reasoning
2. **Specialized Expertise**: Agents have distinct domains and capabilities
3. **Protocol-Based Communication**: Structured message passing between agents
4. **Emergent Behavior**: Complex problem-solving emerges from agent collaboration
5. **Human-AI Interaction**: Natural language interface to multi-agent system
6. **Tool Integration**: Agents can use external tools and APIs
7. **Context Management**: Maintaining conversation state across interactions
8. **Scalable Architecture**: Easy to add new agents and capabilities

The result is a system where users can ask natural questions and get intelligent, multi-faceted responses that combine infrastructure monitoring, security analysis, and cost optimization insights.

## Next Steps

1. Review this architecture and adjust based on your learning goals
2. Choose which phase to start with (recommend Phase 1)
3. Set up OpenAI API access
4. Begin implementing AI agent base classes
5. Test with simple interactions before building chat interface

This approach transforms the A2A Learning Lab from a monitoring dashboard into an intelligent, conversational multi-agent system that demonstrates real-world A2A patterns while remaining focused on learning and experimentation.