import json
import os
import shutil
import shlex
import subprocess
import asyncio
from typing import Dict, Any, List, Optional

from core.agent import AIAgent, AgentTool
from agents import Agent
from agents.mcp import MCPServer


GITOPS_SYSTEM_PROMPT = """
You are GitOps (Riley), an engineer focused on repository hygiene and CI/CD.

You have access to both direct git/gh commands and GitHub's MCP server for enhanced functionality.

Guidelines:
- Prefer read-only commands unless explicitly asked to modify state
- Use MCP tools for rich GitHub API access when available
- Fall back to gh CLI commands for basic operations
- Be concise; return only the essential information
- Sanitize inputs and avoid arbitrary command execution

Capabilities:
- Git repository operations (status, log, branches)
- GitHub API access via MCP (issues, PRs, commits, releases)
- Code analysis and security insights
- CI/CD workflow monitoring
"""


gitops_tools = [
    AgentTool(
        name="git_status",
        description="Get concise git status for a repo (porcelain v2).",
        parameters={
            "type": "object",
            "properties": {
                "repo_path": {"type": "string", "description": "Filesystem path to repo"}
            },
            "required": ["repo_path"],
        },
    ),
    AgentTool(
        name="git_log",
        description="Get last N commits (subject + short sha).",
        parameters={
            "type": "object",
            "properties": {
                "repo_path": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
            },
            "required": ["repo_path"],
        },
    ),
    AgentTool(
        name="git_branches",
        description="List local branches (current highlighted).",
        parameters={
            "type": "object",
            "properties": {"repo_path": {"type": "string"}},
            "required": ["repo_path"],
        },
    ),
    AgentTool(
        name="gh_pr_list",
        description="List GitHub PRs for a repo (requires gh CLI + auth).",
        parameters={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "owner/repo"},
                "state": {
                    "type": "string",
                    "enum": ["open", "closed", "merged", "all"],
                    "default": "open",
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
            },
            "required": ["repo"],
        },
    ),
    AgentTool(
        name="gh_issue_list",
        description="List GitHub issues for a repo (requires gh CLI + auth).",
        parameters={
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "owner/repo"},
                "state": {"type": "string", "enum": ["open", "closed", "all"], "default": "open"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
            },
            "required": ["repo"],
        },
    ),
    # MCP-based GitHub API tools
    AgentTool(
        name="github_search_repositories",
        description="Search GitHub repositories using MCP server",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "per_page": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10}
            },
            "required": ["query"],
        },
    ),
    AgentTool(
        name="github_get_file_contents",
        description="Get file contents from GitHub repository via MCP",
        parameters={
            "type": "object", 
            "properties": {
                "owner": {"type": "string", "description": "Repository owner"},
                "repo": {"type": "string", "description": "Repository name"},
                "path": {"type": "string", "description": "File path"},
                "ref": {"type": "string", "description": "Branch/commit ref", "default": "main"}
            },
            "required": ["owner", "repo", "path"],
        },
    ),
    AgentTool(
        name="github_create_issue",
        description="Create a GitHub issue via MCP server",
        parameters={
            "type": "object",
            "properties": {
                "owner": {"type": "string", "description": "Repository owner"},
                "repo": {"type": "string", "description": "Repository name"},  
                "title": {"type": "string", "description": "Issue title"},
                "body": {"type": "string", "description": "Issue body"}
            },
            "required": ["owner", "repo", "title"],
        },
    ),
]


class GitOpsAgent(AIAgent):
    def __init__(self):
        super().__init__(
            agent_id="gitops-agent-riley-001",
            system_prompt=GITOPS_SYSTEM_PROMPT,
            tools=gitops_tools,
        )
        self._mcp_client = None
        
    async def _get_mcp_client(self, user_auth_token: str = None):
        """Initialize MCP client for GitHub server with end-user authentication"""
        if self._mcp_client is None or user_auth_token:
            try:
                if not user_auth_token:
                    # No end-user token available - this should trigger auth flow
                    self._mcp_client = {"available": False, "error": "End-user GitHub authentication required", "auth_required": True}
                    return self._mcp_client

                # Create GitHub MCP server instance using HTTP endpoint with user authentication
                github_mcp_server = MCPServer(
                    "github",
                    url="https://api.githubcopilot.com/mcp/",
                    headers={
                        "Authorization": f"Bearer {user_auth_token}"
                    }
                )
                
                # Create agent with MCP server
                self._openai_agent = Agent(
                    name="GitOps-MCP",
                    instructions="Use GitHub MCP tools to access GitHub API",
                    mcp_servers=[github_mcp_server]
                )
                
                self._mcp_client = {
                    "available": True, 
                    "token": user_auth_token, 
                    "source": "end_user",
                    "agent": self._openai_agent,
                    "server": github_mcp_server
                }
                
            except Exception as e:
                print(f"Failed to initialize MCP client: {e}")
                self._mcp_client = {"available": False, "error": str(e)}
        return self._mcp_client
        
    async def _call_mcp_tool(self, tool_name: str, params: Dict[str, Any], user_auth_token: str = None) -> Dict[str, Any]:
        """Call MCP tool with proper end-user authentication"""
        mcp_client = await self._get_mcp_client(user_auth_token)
        
        if not mcp_client.get("available"):
            # Check if authentication is required
            if mcp_client.get("auth_required"):
                return {
                    "ok": False, 
                    "error": "GitHub authentication required",
                    "auth_required": True,
                    "auth_message": "Please provide your GitHub personal access token to access GitHub via MCP. This token should have appropriate repository permissions for the requested operation.",
                    "auth_url": "https://github.com/settings/tokens"
                }
            return {"ok": False, "error": f"MCP not available: {mcp_client.get('error')}"}
            
        try:
            if tool_name == "github_search_repositories":
                return await self._github_search_repositories_mcp(params, mcp_client)
            elif tool_name == "github_get_file_contents": 
                return await self._github_get_file_contents_mcp(params, mcp_client)
            elif tool_name == "github_create_issue":
                return await self._github_create_issue_mcp(params, mcp_client)
            else:
                return {"ok": False, "error": f"Unknown MCP tool: {tool_name}"}
        except Exception as e:
            return {"ok": False, "error": f"MCP call failed: {str(e)}"}
    
    async def _github_search_repositories(self, params: Dict[str, Any], user_auth_token: str = None) -> Dict[str, Any]:
        """GitHub repository search via MCP with end-user authentication"""
        query = params["query"]
        per_page = params.get("per_page", 10)
        
        if not user_auth_token:
            return {"ok": False, "error": "End-user GitHub token required for repository search", "auth_required": True}
        
        if not shutil.which("gh"):
            return {"ok": False, "error": "GitHub search requires gh CLI or MCP server"}
        
        # Use user's token instead of host environment
        env = os.environ.copy()
        env["GH_TOKEN"] = user_auth_token
            
        result = self._run([
            "gh", "search", "repos", query, "--limit", str(per_page), 
            "--json", "name,owner,description,stars,language"
        ], env=env)
        
        if result["ok"]:
            try:
                repos = json.loads(result["stdout"]) if result["stdout"] else []
                return {"ok": True, "repositories": repos, "mcp_source": "github_mcp_server", "auth_source": "end_user"}
            except json.JSONDecodeError:
                return {"ok": False, "error": "Failed to parse search results"}
        return result
    
    async def _github_get_file_contents(self, params: Dict[str, Any], user_auth_token: str = None) -> Dict[str, Any]:
        """Get file contents via GitHub API through MCP with end-user authentication"""
        owner = params["owner"]
        repo = params["repo"] 
        path = params["path"]
        ref = params.get("ref", "main")
        
        if not user_auth_token:
            return {"ok": False, "error": "End-user GitHub token required for file access", "auth_required": True}
        
        if not shutil.which("gh"):
            return {"ok": False, "error": "File access requires gh CLI or MCP server"}
        
        # Use user's token instead of host environment
        env = os.environ.copy()
        env["GH_TOKEN"] = user_auth_token
            
        result = self._run([
            "gh", "api", f"repos/{owner}/{repo}/contents/{path}",
            "--jq", ".content", "-H", f"ref={ref}"
        ], env=env)
        
        if result["ok"] and result["stdout"]:
            import base64
            try:
                content = base64.b64decode(result["stdout"]).decode('utf-8')
                return {"ok": True, "content": content, "path": path, "mcp_source": "github_mcp_server", "auth_source": "end_user"}
            except Exception as e:
                return {"ok": False, "error": f"Failed to decode content: {str(e)}"}
        return result
    
    async def _github_create_issue(self, params: Dict[str, Any], user_auth_token: str = None) -> Dict[str, Any]:
        """Create GitHub issue via MCP with end-user authentication"""
        owner = params["owner"]
        repo = params["repo"]
        title = params["title"] 
        body = params.get("body", "")
        
        if not user_auth_token:
            return {"ok": False, "error": "End-user GitHub token required for issue creation", "auth_required": True}
        
        if not shutil.which("gh"):
            return {"ok": False, "error": "Issue creation requires gh CLI or MCP server"}
        
        # Use user's token instead of host environment
        env = os.environ.copy()
        env["GH_TOKEN"] = user_auth_token
            
        cmd = ["gh", "issue", "create", "--repo", f"{owner}/{repo}", "--title", title]
        if body:
            cmd.extend(["--body", body])
        
        result = self._run(cmd, env=env)
        if result["ok"]:
            result["mcp_source"] = "github_mcp_server"
            result["auth_source"] = "end_user"
        return result

    def _safe_path(self, repo_path: str) -> str:
        # Normalize path; optionally restrict to certain base directories if desired
        return os.path.abspath(repo_path)

    def _run(self, cmd: List[str], cwd: Optional[str] = None, timeout: int = 15, env: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        try:
            out = subprocess.run(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
                env=env or os.environ,
            )
            return {
                "ok": out.returncode == 0,
                "code": out.returncode,
                "stdout": out.stdout.strip(),
                "stderr": out.stderr.strip(),
                "cmd": " ".join(shlex.quote(c) for c in cmd),
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Command timed out"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    async def _execute_tool(self, tool_call, conversation_id: str, user_auth_token: str = None) -> Dict[str, Any]:
        name = tool_call.function.name
        args = json.loads(tool_call.function.arguments or "{}")

        if name == "git_status":
            repo = self._safe_path(args["repo_path"]) 
            return self._run(["git", "status", "--porcelain=v2", "-b"], cwd=repo)

        if name == "git_log":
            repo = self._safe_path(args["repo_path"]) 
            limit = int(args.get("limit", 10))
            fmt = "%h %s"
            return self._run(["git", "log", f"-n{limit}", f"--pretty=format:{fmt}"], cwd=repo)

        if name == "git_branches":
            repo = self._safe_path(args["repo_path"]) 
            return self._run(["git", "branch", "--list"], cwd=repo)

        if name == "gh_pr_list":
            repo = args["repo"]
            state = args.get("state", "open")
            limit = int(args.get("limit", 10))
            if not shutil.which("gh"):
                return {"ok": False, "error": "gh CLI not installed in container"}
            return self._run([
                "gh", "pr", "list", "--repo", repo, "--state", state, "--limit", str(limit),
                "--json", "number,title,author,createdAt,state,headRefName"
            ])

        if name == "gh_issue_list":
            repo = args["repo"]
            state = args.get("state", "open")
            limit = int(args.get("limit", 10))
            if not shutil.which("gh"):
                return {"ok": False, "error": "gh CLI not installed in container"}
            return self._run([
                "gh", "issue", "list", "--repo", repo, "--state", state, "--limit", str(limit),
                "--json", "number,title,author,createdAt,state"
            ])

        # MCP-based GitHub API tools with end-user authentication
        if name in ["github_search_repositories", "github_get_file_contents", "github_create_issue"]:
            return await self._call_mcp_tool(name, args, user_auth_token)

        return {"error": f"Unknown tool '{name}'"}

    # New MCP-based methods using OpenAI Agents
    async def _github_search_repositories_mcp(self, params: Dict[str, Any], mcp_client: Dict[str, Any]) -> Dict[str, Any]:
        """GitHub repository search using OpenAI Agents MCP integration"""
        try:
            query = params["query"]
            per_page = params.get("per_page", 10)
            
            # Use the OpenAI Agent with MCP server to search repositories
            agent = mcp_client["agent"]
            
            # Create a search query for the agent
            search_prompt = f"Search for GitHub repositories with query: '{query}'. Return the top {per_page} results with name, owner, description, stars, and language."
            
            # Execute the search using the OpenAI Agent with GitHub MCP
            response = await agent.run(search_prompt)
            
            return {
                "ok": True, 
                "response": response,
                "mcp_source": "github_mcp_server",
                "auth_source": "end_user"
            }
        except Exception as e:
            print(f"MCP repository search failed: {e}")
            # Fallback to existing gh CLI implementation
            return await self._github_search_repositories(params, mcp_client.get("token"))

    async def _github_get_file_contents_mcp(self, params: Dict[str, Any], mcp_client: Dict[str, Any]) -> Dict[str, Any]:
        """Get file contents using OpenAI Agents MCP integration"""
        try:
            owner = params["owner"]
            repo = params["repo"]
            path = params["path"]
            ref = params.get("ref", "main")
            
            # Use the OpenAI Agent with MCP server to get file contents
            agent = mcp_client["agent"]
            
            # Create a file retrieval query for the agent
            file_prompt = f"Get the contents of file '{path}' from repository '{owner}/{repo}' at reference '{ref}'."
            
            # Execute the file retrieval using the OpenAI Agent with GitHub MCP
            response = await agent.run(file_prompt)
            
            return {
                "ok": True,
                "content": response,
                "path": path,
                "mcp_source": "github_mcp_server", 
                "auth_source": "end_user"
            }
        except Exception as e:
            print(f"MCP file retrieval failed: {e}")
            # Fallback to existing gh CLI implementation  
            return await self._github_get_file_contents(params, mcp_client.get("token"))

    async def _github_create_issue_mcp(self, params: Dict[str, Any], mcp_client: Dict[str, Any]) -> Dict[str, Any]:
        """Create GitHub issue using OpenAI Agents MCP integration"""
        try:
            owner = params["owner"]
            repo = params["repo"]
            title = params["title"]
            body = params.get("body", "")
            
            # Use the OpenAI Agent with MCP server to create issue
            agent = mcp_client["agent"]
            
            # Create an issue creation query for the agent
            issue_prompt = f"Create a new GitHub issue in repository '{owner}/{repo}' with title '{title}'"
            if body:
                issue_prompt += f" and body: '{body}'"
            
            # Execute the issue creation using the OpenAI Agent with GitHub MCP
            response = await agent.run(issue_prompt)
            
            return {
                "ok": True,
                "response": response,
                "mcp_source": "github_mcp_server",
                "auth_source": "end_user"
            }
        except Exception as e:
            print(f"MCP issue creation failed: {e}")
            # Fallback to existing gh CLI implementation
            return await self._github_create_issue(params, mcp_client.get("token"))