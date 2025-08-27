"""Mock A2A server for testing agent communication"""

import asyncio
from typing import Dict, Any, Callable
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn

class A2AServer:
    """Mock A2A server implementation using FastAPI"""
    
    def __init__(self, agent=None):
        self.app = FastAPI()
        self.agent = agent
        self.methods: Dict[str, Callable] = {}
        
    def method(self, name: str):
        """Decorator to register method handlers"""
        def decorator(func):
            self.methods[name] = func
            return func
        return decorator
    
    async def start(self, host: str = "0.0.0.0", port: int = 8000):
        """Start the server"""
        
        @self.app.post("/process")
        async def process_request(request: Request):
            try:
                data = await request.json()
                
                # If we have a "process" method registered, use it
                if "process" in self.methods:
                    result = await self.methods["process"](data)
                    return JSONResponse(content=result)
                else:
                    return JSONResponse(
                        content={"error": "No process method registered"}, 
                        status_code=500
                    )
                    
            except Exception as e:
                print(f"A2A Mock Server Error: {e}")
                print(f"Error type: {type(e)}")
                import traceback
                traceback.print_exc()
                return JSONResponse(
                    content={"error": str(e)}, 
                    status_code=500
                )
        
        print(f"🚀 Starting A2A Mock Server on {host}:{port}")
        config = uvicorn.Config(app=self.app, host=host, port=port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()