from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio
import json
from datetime import datetime


class AgentType(Enum):
    DEVOPS = "devops"
    SECOPS = "secops"
    FINOPS = "finops"
    DATAOPS = "dataops"
    GITOPS = "gitops"
    HOST = "host"


class AgentStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ERROR = "error"
    BUSY = "busy"


@dataclass
class AgentCard:
    id: str
    name: str
    description: str
    agent_type: AgentType
    capabilities: List[str]
    endpoint: str
    status: AgentStatus = AgentStatus.OFFLINE
    last_seen: Optional[datetime] = None
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["agent_type"] = self.agent_type.value
        data["status"] = self.status.value
        data["last_seen"] = self.last_seen.isoformat() if self.last_seen else None
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentCard":
        data["agent_type"] = AgentType(data["agent_type"])
        data["status"] = AgentStatus(data["status"])
        if data.get("last_seen"):
            data["last_seen"] = datetime.fromisoformat(data["last_seen"])
        return cls(**data)


class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, AgentCard] = {}
        self._lock = asyncio.Lock()

    async def register_agent(self, agent_card: AgentCard) -> bool:
        async with self._lock:
            if agent_card.id in self._agents:
                return False

            agent_card.status = AgentStatus.ONLINE
            agent_card.last_seen = datetime.now()
            self._agents[agent_card.id] = agent_card
            return True

    async def update_agent_status(self, agent_id: str, status: AgentStatus) -> bool:
        async with self._lock:
            if agent_id not in self._agents:
                return False

            self._agents[agent_id].status = status
            self._agents[agent_id].last_seen = datetime.now()
            return True

    async def unregister_agent(self, agent_id: str) -> bool:
        async with self._lock:
            if agent_id in self._agents:
                del self._agents[agent_id]
                return True
            return False

    async def get_agent(self, agent_id: str) -> Optional[AgentCard]:
        async with self._lock:
            return self._agents.get(agent_id)

    async def list_agents(
        self,
        agent_type: Optional[AgentType] = None,
        status: Optional[AgentStatus] = None,
    ) -> List[AgentCard]:
        async with self._lock:
            agents = list(self._agents.values())

            if agent_type:
                agents = [agent for agent in agents if agent.agent_type == agent_type]

            if status:
                agents = [agent for agent in agents if agent.status == status]

            return agents

    async def find_agents_by_capability(self, capability: str) -> List[AgentCard]:
        async with self._lock:
            return [
                agent
                for agent in self._agents.values()
                if capability in agent.capabilities
                and agent.status == AgentStatus.ONLINE
            ]

    async def get_registry_state(self) -> Dict[str, Any]:
        async with self._lock:
            return {
                "total_agents": len(self._agents),
                "agents_by_type": {
                    agent_type.value: len(
                        [
                            agent
                            for agent in self._agents.values()
                            if agent.agent_type == agent_type
                        ]
                    )
                    for agent_type in AgentType
                },
                "agents_by_status": {
                    status.value: len(
                        [
                            agent
                            for agent in self._agents.values()
                            if agent.status == status
                        ]
                    )
                    for status in AgentStatus
                },
                "agents": [agent.to_dict() for agent in self._agents.values()],
            }


# Global registry instance
registry = AgentRegistry()
