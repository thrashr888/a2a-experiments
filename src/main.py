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
import uvicorn


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
        
        # Initialize agents
        self.agents = [
            (CoordinatorAgent(), settings.a2a_port),
            (DevOpsAgent(), 8082),
            (SecOpsAgent(), 8083),
            (FinOpsAgent(), 8084)
        ]
        
        # Start each agent in a separate task
        for agent, port in self.agents:
            task = asyncio.create_task(self._start_agent_safely(agent, port))
            self.tasks.append(task)
            # Small delay to avoid port conflicts
            await asyncio.sleep(1)
        
        self.logger.info(f"Started {len(self.agents)} agents")
    
    async def _start_agent_safely(self, agent, port):
        """Start an agent with error handling"""
        try:
            agent_name = agent.__class__.__name__
            self.logger.info(f"Starting {agent_name} on port {port}...")
            
            executor = AI_AgentExecutor(agent)
            app = A2AStarletteApplication(agent_executor=executor)
            
            config = uvicorn.Config(
                app=app,
                host="0.0.0.0",
                port=port,
                log_level=settings.log_level.lower()
            )
            server = uvicorn.Server(config)
            await server.serve()

        except Exception as e:
            self.logger.error(f"Failed to start {agent.__class__.__name__}: {e}")
    
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