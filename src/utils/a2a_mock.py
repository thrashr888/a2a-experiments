"""
Mock A2A SDK implementation for learning purposes.

This provides a simple implementation that mimics the A2A SDK structure
while the real SDK API is being explored.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Callable, Optional
from datetime import datetime
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


logger = logging.getLogger(__name__)


class A2ARequest(BaseModel):
    """A2A request model"""
    id: str
    method: str
    params: Dict[str, Any] = {}
    timestamp: str = None
    
    def __init__(self, **data):
        if not data.get('timestamp'):
            data['timestamp'] = datetime.now().isoformat()
        super().__init__(**data)


class A2AResponse(BaseModel):
    """A2A response model"""
    id: str
    result: Any = None
    error: Optional[str] = None
    timestamp: str = None
    
    def __init__(self, **data):
        if not data.get('timestamp'):
            data['timestamp'] = datetime.now().isoformat()
        super().__init__(**data)


class A2AServer:
    """Mock A2A Server implementation"""
    
    def __init__(self):
        self.app = FastAPI(title="A2A Agent Server")
        self.methods: Dict[str, Callable] = {}
        self.setup_routes()
        
    def setup_routes(self):
        """Setup FastAPI routes for A2A protocol"""
        
        @self.app.post("/a2a/call")
        async def handle_a2a_call(request: A2ARequest):
            logger.info(f"Received A2A call: {request.method}")
            
            if request.method not in self.methods:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Method '{request.method}' not found"
                )
            
            try:
                # Call the registered method
                method = self.methods[request.method]
                if asyncio.iscoroutinefunction(method):
                    result = await method(**request.params)
                else:
                    result = method(**request.params)
                
                return A2AResponse(
                    id=request.id,
                    result=result
                )
                
            except Exception as e:
                logger.error(f"Error executing method {request.method}: {e}")
                return A2AResponse(
                    id=request.id,
                    error=str(e)
                )
        
        @self.app.get("/health")
        async def health():
            return {"status": "healthy", "timestamp": datetime.now().isoformat()}
        
        @self.app.get("/a2a/methods")
        async def list_methods():
            return {"methods": list(self.methods.keys())}
    
    def method(self, name: str):
        """Decorator to register a method"""
        def decorator(func: Callable):
            self.methods[name] = func
            logger.info(f"Registered method: {name}")
            return func
        return decorator
    
    async def start(self, host: str = "127.0.0.1", port: int = 8000):
        """Start the A2A server"""
        logger.info(f"Starting A2A server on {host}:{port}")
        config = uvicorn.Config(
            app=self.app,
            host=host,
            port=port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()


class A2AClient:
    """Mock A2A Client implementation"""
    
    def __init__(self, endpoint: str):
        self.endpoint = endpoint.rstrip('/')
        self.base_url = f"{self.endpoint}/a2a"
        
    async def call(self, method: str, **params) -> Any:
        """Call a method on the A2A server"""
        import httpx
        import uuid
        
        request_data = A2ARequest(
            id=str(uuid.uuid4()),
            method=method,
            params=params
        )
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.base_url}/call",
                    json=request_data.dict(),
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = A2AResponse(**response.json())
                    if result.error:
                        raise Exception(result.error)
                    return result.result
                else:
                    raise Exception(f"HTTP {response.status_code}: {response.text}")
                    
        except httpx.ConnectError:
            logger.warning(f"Could not connect to {self.endpoint}")
            raise Exception(f"Cannot connect to agent at {self.endpoint}")
        except Exception as e:
            logger.error(f"A2A call failed: {e}")
            raise


# For backward compatibility, if the real SDK becomes available
try:
    from a2a import A2AServer as RealA2AServer, A2AClient as RealA2AClient
    logger.info("Using real A2A SDK")
    A2AServer = RealA2AServer
    A2AClient = RealA2AClient
except ImportError:
    logger.info("Using mock A2A SDK implementation")
    # Use the mock implementations defined above