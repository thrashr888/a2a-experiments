#!/usr/bin/env python3

import asyncio
import logging
import signal
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import settings
from core.agent import AI_AgentExecutor
from core.host_agent import CoordinatorAgent
# from agents.coordinator.chat_coordinator import start_coordinator_server
from a2a_agents.devops.infrastructure_monitor import DevOpsAgent
from a2a_agents.secops.security_monitor import SecOpsAgent
from a2a_agents.finops.cost_monitor import FinOpsAgent

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers.default_request_handler import DefaultRequestHandler
from a2a.server.tasks import DatabaseTaskStore
from a2a.server.tasks import DatabasePushNotificationConfigStore
from a2a.server.events import InMemoryQueueManager
from a2a.types import AgentCard, AgentCapabilities, AgentSkill
from sqlalchemy.ext.asyncio import create_async_engine
import uvicorn
import os


def create_sqlite_engine(agent_id: str):
    """Create SQLite async engine for agent persistence"""
    # Ensure data directory exists
    os.makedirs(settings.data_dir, exist_ok=True)
    db_path = os.path.join(settings.data_dir, f"{agent_id}_tasks.db")
    return create_async_engine(f"sqlite+aiosqlite:///{db_path}")


def create_agent_card(agent_id: str, name: str, description: str, port: int, tags: list[str]) -> AgentCard:
    """Create an AgentCard for an agent"""
    # Create a basic skill for the agent
    skill = AgentSkill(
        id=f"{agent_id}-skill",
        name=f"{name} Core Skill",
        description=description,
        tags=tags,
        examples=[f"Help me with {tags[0] if tags else 'general tasks'}"]
    )
    
    return AgentCard(
        name=name,
        description=description,
        url=f"http://localhost:{port}",
        capabilities=AgentCapabilities(),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        protocol_version="0.3.0",
        preferred_transport="JSONRPC",
        skills=[skill],
        version="1.0.0"
    )


class A2ALabLauncher:
    def __init__(self):
        self.agents = []
        self.tasks = []
        self.shutdown_event = asyncio.Event()
        
        # Setup logging
        logging.basicConfig(
            level=getattr(logging, settings.log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler(settings.log_file) if settings.log_file else logging.NullHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
    
    async def start_agents(self):
        """Start all A2A agents"""
        self.logger.info("Starting A2A Learning Lab...")
        
        # Initialize agents with metadata
        agents_config = [
            (CoordinatorAgent(), settings.a2a_port, "coordinator-agent", "Chat Coordinator", "Manages conversations between specialized agents", ["coordination", "chat", "communication"]),
            (DevOpsAgent(), 8082, "devops-agent-alex-001", "Infrastructure Monitor (Alex)", "DevOps engineer specializing in system monitoring and infrastructure management", ["devops", "infrastructure", "monitoring"]),
            (SecOpsAgent(), 8083, "secops-agent-jordan-001", "Security Monitor (Jordan)", "Security engineer focused on threat detection and security monitoring", ["security", "monitoring", "threat-detection"]),
            (FinOpsAgent(), 8084, "finops-agent-casey-001", "Cost Monitor (Casey)", "Financial operations specialist managing cloud costs and budgets", ["finops", "cost-management", "budgets"])
        ]
        
        self.agents = [(agent, port) for agent, port, *_ in agents_config]
        
        # Start each agent in a separate task
        for agent, port, agent_id, name, description, tags in agents_config:
            task = asyncio.create_task(self._start_agent_safely(agent, port, agent_id, name, description, tags))
            self.tasks.append(task)
            # Small delay to avoid port conflicts
            await asyncio.sleep(1)
        
        self.logger.info(f"Started {len(self.agents)} agents")
    
    async def _start_agent_safely(self, agent, port, agent_id, name, description, tags):
        """Start an agent with error handling"""
        try:
            self.logger.info(f"Starting {name} on port {port}...")
            
            # Create AgentCard for this agent
            agent_card = create_agent_card(agent_id, name, description, port, tags)
            
            # Create executor and RequestHandler with SQLite persistence
            executor = AI_AgentExecutor(agent)
            
            # Create SQLite engine and stores
            engine = create_sqlite_engine(agent_id)
            task_store = DatabaseTaskStore(engine=engine)
            push_config_store = DatabasePushNotificationConfigStore(engine=engine)
            queue_manager = InMemoryQueueManager()
            
            # Initialize database tables
            await task_store.initialize()
            await push_config_store.initialize()
            
            request_handler = DefaultRequestHandler(
                agent_executor=executor,
                task_store=task_store,
                queue_manager=queue_manager,
                push_config_store=push_config_store
            )
            
            # Create A2A Starlette Application with correct parameters
            a2a_app = A2AStarletteApplication(
                agent_card=agent_card,
                http_handler=request_handler
            )
            
            # Build the Starlette app
            app = a2a_app.build()
            
            config = uvicorn.Config(
                app=app,
                host="0.0.0.0",
                port=port,
                log_level=settings.log_level.lower()
            )
            server = uvicorn.Server(config)
            await server.serve()

        except Exception as e:
            self.logger.error(f"Failed to start {name}: {e}")
            import traceback
            self.logger.error(f"Traceback: {traceback.format_exc()}")
    
    async def start_web_server(self):
        """Start the web server"""
        try:
            import uvicorn
            from web.app import app
            
            self.logger.info(f"Starting web server on {settings.host}:{settings.port}")
            
            config = uvicorn.Config(
                app=app,
                host=settings.host,
                port=settings.port,
                log_level=settings.log_level.lower()
            )
            
            server = uvicorn.Server(config)
            
            # Run server in a thread to avoid blocking
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                await loop.run_in_executor(executor, server.run)
                
        except Exception as e:
            self.logger.error(f"Failed to start web server: {e}")
    
    async def run(self):
        """Main run loop"""
        try:
            # Setup signal handlers
            for sig in [signal.SIGTERM, signal.SIGINT]:
                signal.signal(sig, self._signal_handler)
            
            # Start agents
            await self.start_agents()
            
            # Start coordinator server (disabled for now)
            # coordinator_task = asyncio.create_task(start_coordinator_server())
            # self.tasks.append(coordinator_task)
            
            # Start web server
            web_task = asyncio.create_task(self.start_web_server())
            self.tasks.append(web_task)
            
            self.logger.info("A2A Learning Lab is running...")
            self.logger.info(f"Web interface available at: http://{settings.host}:{settings.port}")
            self.logger.info("Press Ctrl+C to shutdown")
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
        except KeyboardInterrupt:
            self.logger.info("Received shutdown signal")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
        finally:
            await self.shutdown()
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}")
        self.shutdown_event.set()
    
    async def shutdown(self):
        """Graceful shutdown"""
        self.logger.info("Shutting down A2A Learning Lab...")
        
        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        self.logger.info("Shutdown complete")


async def main():
    """Main entry point"""
    launcher = A2ALabLauncher()
    await launcher.run()


if __name__ == "__main__":
    # Create logs directory if it doesn't exist
    if settings.log_file:
        Path(settings.log_file).parent.mkdir(parents=True, exist_ok=True)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)