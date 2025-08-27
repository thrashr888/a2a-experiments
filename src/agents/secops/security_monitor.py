import asyncio
import re
import os
import subprocess
from typing import Dict, Any, List
from datetime import datetime, timedelta
from pathlib import Path
from utils.a2a_mock import A2AServer
from core.agent_registry import AgentCard, AgentType, registry


class SecurityMonitorAgent:
    def __init__(self):
        self.agent_id = "security-monitor-001"
        self.agent_card = AgentCard(
            id=self.agent_id,
            name="Security Monitor",
            description="Monitors security events, failed logins, and suspicious activities",
            agent_type=AgentType.SECOPS,
            capabilities=[
                "log_monitoring",
                "failed_login_detection",
                "network_scan_detection",
                "security_alerts"
            ],
            endpoint="http://localhost:8083",
            metadata={
                "version": "1.0.0",
                "author": "A2A Lab",
                "category": "security"
            }
        )
        
        # Common log paths to monitor
        self.log_paths = [
            "/var/log/auth.log",
            "/var/log/secure",
            "/var/log/messages",
            "/var/log/syslog"
        ]
        
    async def start(self):
        await registry.register_agent(self.agent_card)
        server = A2AServer()
        
        @server.method("scan_failed_logins")
        async def scan_failed_logins(hours: int = 24) -> Dict[str, Any]:
            return await self._scan_failed_logins(hours)
        
        @server.method("check_suspicious_processes")
        async def check_suspicious_processes() -> List[Dict[str, Any]]:
            return await self._check_suspicious_processes()
        
        @server.method("scan_network_connections")
        async def scan_network_connections() -> Dict[str, Any]:
            return await self._scan_network_connections()
        
        @server.method("get_security_alerts")
        async def get_security_alerts() -> List[Dict[str, Any]]:
            return await self._get_security_alerts()
        
        await server.start(host="0.0.0.0", port=8083)
    
    async def _scan_failed_logins(self, hours: int) -> Dict[str, Any]:
        failed_attempts = []
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        # Patterns for failed login attempts
        patterns = [
            r"Failed password for (\w+) from ([\d\.]+)",
            r"Invalid user (\w+) from ([\d\.]+)",
            r"authentication failure.*user=(\w+).*rhost=([\d\.]+)"
        ]
        
        for log_path in self.log_paths:
            if not os.path.exists(log_path):
                continue
                
            try:
                with open(log_path, 'r') as f:
                    for line in f:
                        for pattern in patterns:
                            match = re.search(pattern, line)
                            if match:
                                # Extract timestamp from log line (simplified)
                                timestamp_str = line.split()[0:3]
                                try:
                                    # This is a simplified timestamp extraction
                                    log_time = datetime.now()  # Placeholder for real timestamp parsing
                                    if log_time > cutoff_time:
                                        failed_attempts.append({
                                            "username": match.group(1),
                                            "source_ip": match.group(2),
                                            "timestamp": log_time.isoformat(),
                                            "log_line": line.strip()
                                        })
                                except:
                                    pass
            except Exception as e:
                continue
        
        # Aggregate by IP
        ip_counts = {}
        user_counts = {}
        
        for attempt in failed_attempts:
            ip = attempt["source_ip"]
            user = attempt["username"]
            
            ip_counts[ip] = ip_counts.get(ip, 0) + 1
            user_counts[user] = user_counts.get(user, 0) + 1
        
        return {
            "scan_period_hours": hours,
            "total_failed_attempts": len(failed_attempts),
            "unique_ips": len(ip_counts),
            "unique_users": len(user_counts),
            "top_attacking_ips": sorted(ip_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            "top_targeted_users": sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10],
            "recent_attempts": failed_attempts[-20:],  # Last 20 attempts
            "timestamp": datetime.now().isoformat()
        }
    
    async def _check_suspicious_processes(self) -> List[Dict[str, Any]]:
        suspicious_processes = []
        
        # List of potentially suspicious process names
        suspicious_names = [
            "nc", "netcat", "nmap", "masscan", "zmap",
            "sqlmap", "nikto", "dirb", "gobuster",
            "hydra", "john", "hashcat", "aircrack"
        ]
        
        try:
            result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
            for line in result.stdout.split('\n')[1:]:  # Skip header
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 11:
                        process_name = parts[10]
                        for suspicious in suspicious_names:
                            if suspicious in process_name.lower():
                                suspicious_processes.append({
                                    "user": parts[0],
                                    "pid": parts[1],
                                    "cpu": parts[2],
                                    "memory": parts[3],
                                    "command": " ".join(parts[10:]),
                                    "detected_pattern": suspicious,
                                    "timestamp": datetime.now().isoformat()
                                })
        except Exception as e:
            pass
        
        return suspicious_processes
    
    async def _scan_network_connections(self) -> Dict[str, Any]:
        try:
            # Get network connections
            result = subprocess.run(["netstat", "-an"], capture_output=True, text=True)
            connections = result.stdout.split('\n')[2:]  # Skip headers
            
            listening_ports = []
            established_connections = []
            
            for line in connections:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 4:
                        proto = parts[0]
                        local_addr = parts[3]
                        state = parts[-1] if len(parts) > 4 else ""
                        
                        if "LISTEN" in state:
                            listening_ports.append({
                                "protocol": proto,
                                "address": local_addr,
                                "port": local_addr.split(':')[-1]
                            })
                        elif "ESTABLISHED" in state:
                            established_connections.append({
                                "protocol": proto,
                                "local": local_addr,
                                "remote": parts[4] if len(parts) > 4 else "",
                                "state": state
                            })
            
            # Check for unusual ports
            common_ports = {"22", "80", "443", "53", "25", "110", "143", "993", "995"}
            unusual_ports = []
            
            for port_info in listening_ports:
                port = port_info["port"]
                if port not in common_ports and port.isdigit() and int(port) > 1024:
                    unusual_ports.append(port_info)
            
            return {
                "total_listening_ports": len(listening_ports),
                "total_established_connections": len(established_connections),
                "unusual_listening_ports": unusual_ports,
                "established_connections": established_connections[:20],  # Limit output
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _get_security_alerts(self) -> List[Dict[str, Any]]:
        alerts = []
        
        # Check for suspicious processes
        suspicious_procs = await self._check_suspicious_processes()
        if suspicious_procs:
            alerts.append({
                "type": "suspicious_processes",
                "severity": "high",
                "message": f"Found {len(suspicious_procs)} potentially suspicious processes",
                "details": suspicious_procs,
                "timestamp": datetime.now().isoformat()
            })
        
        # Check failed login attempts in last hour
        failed_logins = await self._scan_failed_logins(1)
        if failed_logins["total_failed_attempts"] > 10:
            alerts.append({
                "type": "failed_login_spike",
                "severity": "medium" if failed_logins["total_failed_attempts"] < 50 else "high",
                "message": f"{failed_logins['total_failed_attempts']} failed login attempts in last hour",
                "details": failed_logins,
                "timestamp": datetime.now().isoformat()
            })
        
        # Check network connections
        network_info = await self._scan_network_connections()
        if "unusual_listening_ports" in network_info and network_info["unusual_listening_ports"]:
            alerts.append({
                "type": "unusual_network_activity",
                "severity": "low",
                "message": f"Found {len(network_info['unusual_listening_ports'])} unusual listening ports",
                "details": network_info["unusual_listening_ports"],
                "timestamp": datetime.now().isoformat()
            })
        
        return alerts


if __name__ == "__main__":
    agent = SecurityMonitorAgent()
    asyncio.run(agent.start())