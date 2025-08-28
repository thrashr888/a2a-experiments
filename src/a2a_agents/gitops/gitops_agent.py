import json
import os
import shutil
import shlex
import subprocess
import asyncio
from typing import Dict, Any, List, Optional

from core.agent import AIAgent, AgentTool


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
        
    async def _get_mcp_client(self):
        """Initialize MCP client for GitHub server if available"""
        if self._mcp_client is None:
            try:
                # This would normally connect to a GitHub MCP server
                # For now, we'll simulate MCP functionality using GitHub CLI
                github_token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
                if github_token:
                    self._mcp_client = {"available": True, "token": github_token}
                else:
                    self._mcp_client = {"available": False, "error": "No GitHub token"}
            except Exception as e:
                self._mcp_client = {"available": False, "error": str(e)}
        return self._mcp_client
        
    async def _call_mcp_tool(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call MCP tool (simulated using GitHub CLI for demonstration)"""
        mcp_client = await self._get_mcp_client()
        if not mcp_client.get("available"):
            return {"ok": False, "error": f"MCP not available: {mcp_client.get('error')}"}
            
        try:
            if tool_name == "github_search_repositories":
                return await self._github_search_repositories(params)
            elif tool_name == "github_get_file_contents": 
                return await self._github_get_file_contents(params)
            elif tool_name == "github_create_issue":
                return await self._github_create_issue(params)
            else:
                return {"ok": False, "error": f"Unknown MCP tool: {tool_name}"}
        except Exception as e:
            return {"ok": False, "error": f"MCP call failed: {str(e)}"}
    
    async def _github_search_repositories(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """GitHub repository search via MCP (simulated with gh CLI)"""
        query = params["query"]
        per_page = params.get("per_page", 10)
        
        if not shutil.which("gh"):
            return {"ok": False, "error": "GitHub search requires gh CLI or MCP server"}
            
        result = self._run([
            "gh", "search", "repos", query, "--limit", str(per_page), 
            "--json", "name,owner,description,stars,language"
        ])
        
        if result["ok"]:
            try:
                repos = json.loads(result["stdout"]) if result["stdout"] else []
                return {"ok": True, "repositories": repos, "mcp_source": "github_mcp_server"}
            except json.JSONDecodeError:
                return {"ok": False, "error": "Failed to parse search results"}
        return result
    
    async def _github_get_file_contents(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get file contents via GitHub API through MCP (simulated)"""
        owner = params["owner"]
        repo = params["repo"] 
        path = params["path"]
        ref = params.get("ref", "main")
        
        if not shutil.which("gh"):
            return {"ok": False, "error": "File access requires gh CLI or MCP server"}
            
        result = self._run([
            "gh", "api", f"repos/{owner}/{repo}/contents/{path}",
            "--jq", ".content", "-H", f"ref={ref}"
        ])
        
        if result["ok"] and result["stdout"]:
            import base64
            try:
                content = base64.b64decode(result["stdout"]).decode('utf-8')
                return {"ok": True, "content": content, "path": path, "mcp_source": "github_mcp_server"}
            except Exception as e:
                return {"ok": False, "error": f"Failed to decode content: {str(e)}"}
        return result
    
    async def _github_create_issue(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Create GitHub issue via MCP (simulated with gh CLI)"""
        owner = params["owner"]
        repo = params["repo"]
        title = params["title"] 
        body = params.get("body", "")
        
        if not shutil.which("gh"):
            return {"ok": False, "error": "Issue creation requires gh CLI or MCP server"}
            
        cmd = ["gh", "issue", "create", "--repo", f"{owner}/{repo}", "--title", title]
        if body:
            cmd.extend(["--body", body])
        
        result = self._run(cmd)
        if result["ok"]:
            result["mcp_source"] = "github_mcp_server"
        return result

    def _safe_path(self, repo_path: str) -> str:
        # Normalize path; optionally restrict to certain base directories if desired
        return os.path.abspath(repo_path)

    def _run(self, cmd: List[str], cwd: Optional[str] = None, timeout: int = 15) -> Dict[str, Any]:
        try:
            out = subprocess.run(
                cmd,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
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

    async def _execute_tool(self, tool_call, conversation_id: str) -> Dict[str, Any]:
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

        # MCP-based GitHub API tools
        if name in ["github_search_repositories", "github_get_file_contents", "github_create_issue"]:
            return await self._call_mcp_tool(name, args)

        return {"error": f"Unknown tool '{name}'"}