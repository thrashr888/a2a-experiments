import json
import os
import shutil
import shlex
import subprocess
from typing import Dict, Any, List, Optional

from core.agent import AIAgent, AgentTool


GITOPS_SYSTEM_PROMPT = """
You are GitOps (Riley), an engineer focused on repository hygiene and CI/CD.

Guidelines:
- Prefer read-only commands unless explicitly asked to modify state
- Be concise; return only the essential information
- Sanitize inputs and avoid arbitrary command execution
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
]


class GitOpsAgent(AIAgent):
    def __init__(self):
        super().__init__(
            agent_id="gitops-agent-riley-001",
            system_prompt=GITOPS_SYSTEM_PROMPT,
            tools=gitops_tools,
        )

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

        return {"error": f"Unknown tool '{name}'"}
