import asyncio
import json
import docker
from typing import Dict, Any, List
from datetime import datetime
import concurrent.futures

from core.agent import AIAgent, AgentTool, A2AMessage
from core.config import settings

DOCKER_SYSTEM_PROMPT = """
You are ContainerOps (Morgan), a specialized container operations engineer with expertise in Docker and container management.

Your expertise includes:
- Docker system monitoring and analysis
- Container lifecycle management (start/stop/restart containers)
- Container troubleshooting and operational control
- Image analysis and optimization
- Volume and network management
- Performance monitoring and resource analysis

Your personality: Technical, precise, focused on container best practices and optimization.

When providing information:
1. Always provide accurate, real-time Docker data
2. Suggest optimizations and best practices
3. Identify potential security or performance issues
4. Use precise technical terminology
5. Exercise caution with container management operations
"""

docker_tools = [
    AgentTool(
        name="get_docker_system_info",
        description="Get Docker daemon system information including version, storage driver, and resource usage.",
        parameters={"type": "object", "properties": {}},
    ),
    AgentTool(
        name="list_containers",
        description="List all containers with their status, resource usage, and basic information.",
        parameters={
            "type": "object",
            "properties": {
                "all": {
                    "type": "boolean",
                    "description": "Include stopped containers (default: false)",
                }
            },
        },
    ),
    AgentTool(
        name="get_container_details",
        description="Get detailed information about a specific container.",
        parameters={
            "type": "object",
            "properties": {
                "container_id": {
                    "type": "string",
                    "description": "Container ID or name",
                }
            },
            "required": ["container_id"],
        },
    ),
    AgentTool(
        name="list_images",
        description="List Docker images with size and usage information.",
        parameters={"type": "object", "properties": {}},
    ),
    AgentTool(
        name="get_docker_stats",
        description="Get real-time resource usage statistics for running containers.",
        parameters={"type": "object", "properties": {}},
    ),
    AgentTool(
        name="list_volumes",
        description="List Docker volumes with usage information.",
        parameters={"type": "object", "properties": {}},
    ),
    AgentTool(
        name="get_docker_disk_usage",
        description="Get Docker disk usage breakdown (images, containers, volumes, build cache).",
        parameters={"type": "object", "properties": {}},
    ),
    AgentTool(
        name="start_container",
        description="Start a Docker container by ID or name.",
        parameters={
            "type": "object",
            "properties": {
                "container_id": {
                    "type": "string",
                    "description": "Container ID or name to start",
                }
            },
            "required": ["container_id"],
        },
    ),
    AgentTool(
        name="stop_container",
        description="Stop a Docker container by ID or name.",
        parameters={
            "type": "object",
            "properties": {
                "container_id": {
                    "type": "string",
                    "description": "Container ID or name to stop",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds before forcing stop (default: 10)",
                    "default": 10,
                },
            },
            "required": ["container_id"],
        },
    ),
    AgentTool(
        name="restart_container",
        description="Restart a Docker container by ID or name.",
        parameters={
            "type": "object",
            "properties": {
                "container_id": {
                    "type": "string",
                    "description": "Container ID or name to restart",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds before forcing restart (default: 10)",
                    "default": 10,
                },
            },
            "required": ["container_id"],
        },
    ),
]


class ContainerOpsAgent(AIAgent):
    def __init__(self):
        super().__init__(
            agent_id="containerops-agent-morgan-001",
            system_prompt=DOCKER_SYSTEM_PROMPT,
            tools=docker_tools,
        )
        self._docker_client = None

    def _get_docker_client(self):
        """Get Docker client with proper error handling"""
        if self._docker_client is None:
            try:
                self._docker_client = docker.from_env()
                # Test connection
                self._docker_client.ping()
            except Exception as e:
                print(f"Failed to connect to Docker daemon: {e}")
                return None
        return self._docker_client

    async def _execute_tool(self, tool_call, conversation_id: str, user_auth_token: str = None) -> Dict[str, Any]:
        function_name = tool_call.function.name
        kwargs = (
            json.loads(tool_call.function.arguments)
            if tool_call.function.arguments
            else {}
        )
        print(f"Executing Docker tool: {function_name} with args: {kwargs}")

        client = self._get_docker_client()
        if client is None:
            return {
                "error": "Cannot connect to Docker daemon. Ensure Docker is running and accessible."
            }

        try:
            if function_name == "get_docker_system_info":
                return await self._get_docker_system_info()
            elif function_name == "list_containers":
                return await self._list_containers(**kwargs)
            elif function_name == "get_container_details":
                return await self._get_container_details(**kwargs)
            elif function_name == "list_images":
                return await self._list_images()
            elif function_name == "get_docker_stats":
                return await self._get_docker_stats()
            elif function_name == "list_volumes":
                return await self._list_volumes()
            elif function_name == "get_docker_disk_usage":
                return await self._get_docker_disk_usage()
            elif function_name == "start_container":
                return await self._start_container(**kwargs)
            elif function_name == "stop_container":
                return await self._stop_container(**kwargs)
            elif function_name == "restart_container":
                return await self._restart_container(**kwargs)
            else:
                return {"error": f"Tool '{function_name}' not found."}
        except Exception as e:
            return {"error": f"Docker operation failed: {str(e)}"}

    async def _get_docker_system_info(self) -> Dict[str, Any]:
        """Get Docker system information"""
        client = self._get_docker_client()

        def get_system_info():
            try:
                info = client.info()
                version = client.version()

                return {
                    "docker_version": version.get("Version", "Unknown"),
                    "api_version": version.get("ApiVersion", "Unknown"),
                    "storage_driver": info.get("Driver", "Unknown"),
                    "containers_total": info.get("Containers", 0),
                    "containers_running": info.get("ContainersRunning", 0),
                    "containers_paused": info.get("ContainersPaused", 0),
                    "containers_stopped": info.get("ContainersStopped", 0),
                    "images_count": info.get("Images", 0),
                    "memory_total": info.get("MemTotal", 0),
                    "ncpu": info.get("NCPU", 0),
                    "docker_root_dir": info.get("DockerRootDir", "Unknown"),
                    "server_version": info.get("ServerVersion", "Unknown"),
                    "operating_system": info.get("OperatingSystem", "Unknown"),
                }
            except Exception as e:
                return {"error": f"Failed to get Docker system info: {str(e)}"}

        try:
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result = await asyncio.wait_for(
                    loop.run_in_executor(executor, get_system_info),
                    timeout=10.0,  # 10 second timeout
                )
            return result
        except asyncio.TimeoutError:
            return {"error": "Docker API call timed out after 10 seconds"}
        except Exception as e:
            return {"error": f"Failed to get Docker system info: {str(e)}"}

    async def _list_containers(self, all: bool = False) -> Dict[str, Any]:
        """List containers with their information"""
        client = self._get_docker_client()

        def list_containers():
            try:
                containers = client.containers.list(all=all)
                container_list = []

                for container in containers:
                    container_info = {
                        "id": container.id[:12],
                        "name": container.name,
                        "status": container.status,
                        "image": container.image.tags[0]
                        if container.image.tags
                        else container.image.id[:12],
                        "created": container.attrs["Created"],
                        "ports": container.ports,
                        "labels": container.labels,
                    }

                    # Add basic info only for now to avoid timeouts
                    container_list.append(container_info)

                return {
                    "containers": container_list,
                    "total_count": len(container_list),
                    "running_count": len(
                        [c for c in container_list if c["status"] == "running"]
                    ),
                }
            except Exception as e:
                return {"error": f"Failed to list containers: {str(e)}"}

        try:
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result = await asyncio.wait_for(
                    loop.run_in_executor(executor, list_containers),
                    timeout=15.0,  # 15 second timeout
                )
            return result
        except asyncio.TimeoutError:
            return {"error": "Docker container listing timed out after 15 seconds"}
        except Exception as e:
            return {"error": f"Failed to list containers: {str(e)}"}

    async def _get_container_details(self, container_id: str) -> Dict[str, Any]:
        """Get detailed container information"""
        client = self._get_docker_client()
        try:
            container = client.containers.get(container_id)

            details = {
                "id": container.id,
                "name": container.name,
                "status": container.status,
                "image": container.image.tags[0]
                if container.image.tags
                else container.image.id[:12],
                "command": container.attrs.get("Config", {}).get("Cmd"),
                "created": container.attrs["Created"],
                "started": container.attrs["State"].get("StartedAt"),
                "finished": container.attrs["State"].get("FinishedAt"),
                "exit_code": container.attrs["State"].get("ExitCode"),
                "ports": container.ports,
                "environment": container.attrs.get("Config", {}).get("Env", []),
                "mounts": [
                    {
                        "source": mount.get("Source"),
                        "destination": mount.get("Destination"),
                        "type": mount.get("Type"),
                        "read_write": mount.get("RW", True),
                    }
                    for mount in container.attrs.get("Mounts", [])
                ],
                "network_settings": container.attrs.get("NetworkSettings", {}),
                "restart_policy": container.attrs.get("HostConfig", {}).get(
                    "RestartPolicy"
                ),
                "log_config": container.attrs.get("HostConfig", {}).get("LogConfig"),
            }

            # Add logs (last 50 lines)
            try:
                logs = container.logs(tail=50).decode("utf-8")
                details["recent_logs"] = logs.split("\n")[-50:]
            except:
                details["recent_logs"] = ["Unable to fetch logs"]

            return details
        except Exception as e:
            return {"error": f"Failed to get container details: {str(e)}"}

    async def _list_images(self) -> Dict[str, Any]:
        """List Docker images"""
        client = self._get_docker_client()
        try:
            images = client.images.list()
            image_list = []

            for image in images:
                image_info = {
                    "id": image.id[:12],
                    "tags": image.tags,
                    "size_mb": round(image.attrs["Size"] / 1024 / 1024, 2),
                    "created": image.attrs["Created"],
                    "parent": image.attrs.get("Parent", ""),
                    "architecture": image.attrs.get("Architecture", ""),
                    "os": image.attrs.get("Os", ""),
                }
                image_list.append(image_info)

            # Sort by size descending
            image_list.sort(key=lambda x: x["size_mb"], reverse=True)

            total_size_mb = sum(img["size_mb"] for img in image_list)

            return {
                "images": image_list,
                "total_count": len(image_list),
                "total_size_mb": round(total_size_mb, 2),
            }
        except Exception as e:
            return {"error": f"Failed to list images: {str(e)}"}

    async def _get_docker_stats(self) -> Dict[str, Any]:
        """Get real-time container stats"""
        client = self._get_docker_client()
        try:
            running_containers = client.containers.list()
            stats_list = []

            for container in running_containers:
                try:
                    stats = container.stats(stream=False)
                    if stats:
                        # Calculate CPU usage
                        cpu_stats = stats.get("cpu_stats", {})
                        precpu_stats = stats.get("precpu_stats", {})

                        cpu_usage = 0.0
                        if cpu_stats and precpu_stats:
                            cpu_delta = cpu_stats.get("cpu_usage", {}).get(
                                "total_usage", 0
                            ) - precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
                            system_delta = cpu_stats.get(
                                "system_cpu_usage", 0
                            ) - precpu_stats.get("system_cpu_usage", 0)
                            if system_delta > 0:
                                cpu_usage = (cpu_delta / system_delta) * 100.0

                        # Memory usage
                        memory_stats = stats.get("memory_stats", {})
                        memory_usage = memory_stats.get("usage", 0)
                        memory_limit = memory_stats.get("limit", 0)
                        memory_percent = (
                            (memory_usage / memory_limit * 100)
                            if memory_limit > 0
                            else 0
                        )

                        # Network I/O
                        network_stats = stats.get("networks", {})
                        rx_bytes = sum(
                            net.get("rx_bytes", 0) for net in network_stats.values()
                        )
                        tx_bytes = sum(
                            net.get("tx_bytes", 0) for net in network_stats.values()
                        )

                        # Block I/O
                        blkio_stats = stats.get("blkio_stats", {}).get(
                            "io_service_bytes_recursive", []
                        )
                        read_bytes = sum(
                            item.get("value", 0)
                            for item in blkio_stats
                            if item.get("op") == "read"
                        )
                        write_bytes = sum(
                            item.get("value", 0)
                            for item in blkio_stats
                            if item.get("op") == "write"
                        )

                        container_stats = {
                            "container_id": container.id[:12],
                            "name": container.name,
                            "cpu_percent": round(cpu_usage, 2),
                            "memory_usage_mb": round(memory_usage / 1024 / 1024, 2),
                            "memory_limit_mb": round(memory_limit / 1024 / 1024, 2),
                            "memory_percent": round(memory_percent, 2),
                            "network_rx_mb": round(rx_bytes / 1024 / 1024, 2),
                            "network_tx_mb": round(tx_bytes / 1024 / 1024, 2),
                            "block_read_mb": round(read_bytes / 1024 / 1024, 2),
                            "block_write_mb": round(write_bytes / 1024 / 1024, 2),
                        }
                        stats_list.append(container_stats)
                except Exception as e:
                    print(f"Failed to get stats for {container.name}: {e}")

            return {
                "container_stats": stats_list,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"error": f"Failed to get container stats: {str(e)}"}

    async def _list_volumes(self) -> Dict[str, Any]:
        """List Docker volumes"""
        client = self._get_docker_client()
        try:
            volumes = client.volumes.list()
            volume_list = []

            for volume in volumes:
                volume_info = {
                    "name": volume.name,
                    "driver": volume.attrs.get("Driver", ""),
                    "mountpoint": volume.attrs.get("Mountpoint", ""),
                    "created": volume.attrs.get("CreatedAt", ""),
                    "labels": volume.attrs.get("Labels") or {},
                    "options": volume.attrs.get("Options") or {},
                }

                # Try to get size if possible
                try:
                    import os

                    mountpoint = volume.attrs.get("Mountpoint")
                    if mountpoint and os.path.exists(mountpoint):
                        size = sum(
                            os.path.getsize(os.path.join(dirpath, filename))
                            for dirpath, dirnames, filenames in os.walk(mountpoint)
                            for filename in filenames
                        )
                        volume_info["size_mb"] = round(size / 1024 / 1024, 2)
                    else:
                        volume_info["size_mb"] = "N/A"
                except:
                    volume_info["size_mb"] = "N/A"

                volume_list.append(volume_info)

            return {"volumes": volume_list, "total_count": len(volume_list)}
        except Exception as e:
            return {"error": f"Failed to list volumes: {str(e)}"}

    async def _get_docker_disk_usage(self) -> Dict[str, Any]:
        """Get Docker disk usage breakdown"""
        client = self._get_docker_client()
        try:
            df = client.df()

            def convert_bytes_to_mb(bytes_value):
                return round(bytes_value / 1024 / 1024, 2)

            # Process images
            images = df.get("Images", [])
            images_usage = {
                "count": len(images),
                "size_mb": convert_bytes_to_mb(
                    sum(img.get("Size", 0) for img in images)
                ),
                "reclaimable_mb": convert_bytes_to_mb(
                    sum(
                        img.get("Size", 0)
                        for img in images
                        if not img.get("Containers", 0)
                    )
                ),
            }

            # Process containers
            containers = df.get("Containers", [])
            containers_usage = {
                "count": len(containers),
                "size_mb": convert_bytes_to_mb(
                    sum(
                        cont.get("SizeRw", 0) + cont.get("SizeRootFs", 0)
                        for cont in containers
                    )
                ),
                "reclaimable_mb": convert_bytes_to_mb(
                    sum(
                        cont.get("SizeRw", 0) + cont.get("SizeRootFs", 0)
                        for cont in containers
                        if cont.get("State") != "running"
                    )
                ),
            }

            # Process volumes
            volumes = df.get("Volumes", [])
            volumes_usage = {
                "count": len(volumes),
                "size_mb": convert_bytes_to_mb(
                    sum(vol.get("Size", 0) for vol in volumes)
                ),
                "reclaimable_mb": convert_bytes_to_mb(
                    sum(
                        vol.get("Size", 0)
                        for vol in volumes
                        if vol.get("RefCount", 0) == 0
                    )
                ),
            }

            # Build cache
            build_cache = df.get("BuildCache", [])
            build_cache_usage = {
                "count": len(build_cache),
                "size_mb": convert_bytes_to_mb(
                    sum(cache.get("Size", 0) for cache in build_cache)
                ),
                "reclaimable_mb": convert_bytes_to_mb(
                    sum(
                        cache.get("Size", 0)
                        for cache in build_cache
                        if not cache.get("InUse", False)
                    )
                ),
            }

            total_size = (
                images_usage["size_mb"]
                + containers_usage["size_mb"]
                + volumes_usage["size_mb"]
                + build_cache_usage["size_mb"]
            )
            total_reclaimable = (
                images_usage["reclaimable_mb"]
                + containers_usage["reclaimable_mb"]
                + volumes_usage["reclaimable_mb"]
                + build_cache_usage["reclaimable_mb"]
            )

            return {
                "images": images_usage,
                "containers": containers_usage,
                "volumes": volumes_usage,
                "build_cache": build_cache_usage,
                "total_size_mb": round(total_size, 2),
                "total_reclaimable_mb": round(total_reclaimable, 2),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"error": f"Failed to get Docker disk usage: {str(e)}"}

    async def _start_container(self, container_id: str) -> Dict[str, Any]:
        """Start a Docker container"""
        client = self._get_docker_client()

        def start_container():
            try:
                container = client.containers.get(container_id)
                if container.status == "running":
                    return {
                        "success": True,
                        "message": f"Container {container.name} is already running",
                        "container_id": container.id[:12],
                        "status": container.status,
                    }

                container.start()
                container.reload()

                return {
                    "success": True,
                    "message": f"Successfully started container {container.name}",
                    "container_id": container.id[:12],
                    "status": container.status,
                }
            except Exception as e:
                return {"error": f"Failed to start container: {str(e)}"}

        try:
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result = await asyncio.wait_for(
                    loop.run_in_executor(executor, start_container),
                    timeout=30.0,
                )
            return result
        except asyncio.TimeoutError:
            return {"error": "Container start operation timed out after 30 seconds"}
        except Exception as e:
            return {"error": f"Failed to start container: {str(e)}"}

    async def _stop_container(
        self, container_id: str, timeout: int = 10
    ) -> Dict[str, Any]:
        """Stop a Docker container"""
        client = self._get_docker_client()

        def stop_container():
            try:
                container = client.containers.get(container_id)
                if container.status not in ["running", "paused"]:
                    return {
                        "success": True,
                        "message": f"Container {container.name} is already stopped (status: {container.status})",
                        "container_id": container.id[:12],
                        "status": container.status,
                    }

                container.stop(timeout=timeout)
                container.reload()

                return {
                    "success": True,
                    "message": f"Successfully stopped container {container.name}",
                    "container_id": container.id[:12],
                    "status": container.status,
                }
            except Exception as e:
                return {"error": f"Failed to stop container: {str(e)}"}

        try:
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result = await asyncio.wait_for(
                    loop.run_in_executor(executor, stop_container),
                    timeout=timeout + 10,
                )
            return result
        except asyncio.TimeoutError:
            return {
                "error": f"Container stop operation timed out after {timeout + 10} seconds"
            }
        except Exception as e:
            return {"error": f"Failed to stop container: {str(e)}"}

    async def _restart_container(
        self, container_id: str, timeout: int = 10
    ) -> Dict[str, Any]:
        """Restart a Docker container"""
        client = self._get_docker_client()

        def restart_container():
            try:
                container = client.containers.get(container_id)
                container.restart(timeout=timeout)
                container.reload()

                return {
                    "success": True,
                    "message": f"Successfully restarted container {container.name}",
                    "container_id": container.id[:12],
                    "status": container.status,
                }
            except Exception as e:
                return {"error": f"Failed to restart container: {str(e)}"}

        try:
            loop = asyncio.get_event_loop()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                result = await asyncio.wait_for(
                    loop.run_in_executor(executor, restart_container),
                    timeout=timeout + 15,
                )
            return result
        except asyncio.TimeoutError:
            return {
                "error": f"Container restart operation timed out after {timeout + 15} seconds"
            }
        except Exception as e:
            return {"error": f"Failed to restart container: {str(e)}"}

    async def start(self):
        await super().start(host="0.0.0.0", port=8085)
