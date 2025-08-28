import json
import os
import psycopg2
import getpass
from typing import Dict, Any, List, Optional

from core.agent import AIAgent, AgentTool


DATAOPS_SYSTEM_PROMPT = """
You are Dana, a DataOps engineer focused on safe, efficient data access.

Your priorities:
- Run read-only queries and avoid any data modifications
- Be concise and return structured results
- Handle timeouts and large results gracefully
"""


dataops_tools = [
    AgentTool(
        name="run_query",
        description="Run a read-only SQL query against Postgres (SELECT only).",
        parameters={
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "SQL query (must start with SELECT or EXPLAIN)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max rows to return (default 100)",
                    "minimum": 1,
                    "maximum": 10000,
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Statement timeout in seconds (default 15)",
                    "minimum": 1,
                    "maximum": 120,
                },
            },
            "required": ["sql"],
        },
    ),
    AgentTool(
        name="check_connectivity",
        description="Verify connectivity to Postgres and return server details.",
        parameters={"type": "object", "properties": {}},
    ),
    AgentTool(
        name="list_tables",
        description="List tables available in the current database (optionally filtered by schema).",
        parameters={
            "type": "object",
            "properties": {
                "schema": {"type": "string", "description": "Schema name (optional)"}
            },
        },
    ),
    AgentTool(
        name="get_table_schema",
        description="Get column definitions for a table (name and type).",
        parameters={
            "type": "object",
            "properties": {
                "table": {
                    "type": "string",
                    "description": "Table name (optionally schema-qualified, e.g. public.users)",
                }
            },
            "required": ["table"],
        },
    ),
]


class DataOpsAgent(AIAgent):
    def __init__(self):
        super().__init__(
            agent_id="dataops-agent-dana-001",
            system_prompt=DATAOPS_SYSTEM_PROMPT,
            tools=dataops_tools,
        )

        # Read connection details from environment (outside-the-container DB)
        self.pg_host = os.getenv("PGHOST") or os.getenv("POSTGRES_HOST") or "localhost"
        self.pg_port = int(os.getenv("PGPORT", "5432"))
        self.pg_user = (
            os.getenv("PGUSER") or os.getenv("POSTGRES_USER") or getpass.getuser()
        )
        self.pg_password = (
            os.getenv("PGPASSWORD") or os.getenv("POSTGRES_PASSWORD") or None
        )
        # Default DB to the username if not provided (libpq default)
        self.pg_database = (
            os.getenv("PGDATABASE") or os.getenv("POSTGRES_DB") or self.pg_user
        )

    def _effective_host(self) -> str:
        """Determine the most appropriate host/socket to connect to.

        Preference order:
        1) If PGHOST looks like a socket directory, use it.
        2) If standard socket dir exists inside container, use it.
        3) Fallback to configured host (env/default).
        """
        host = self.pg_host
        try:
            if host and os.path.isabs(host) and os.path.isdir(host):
                return host
            # Prefer mounted socket if present
            if os.path.isdir("/var/run/postgresql"):
                return "/var/run/postgresql"
        except Exception:
            pass
        return host

    def _connect(self, connect_timeout: int = 5):
        if not all([self.pg_host, self.pg_user, self.pg_database]):
            raise RuntimeError(
                "Postgres connection not configured. Set at least PGHOST, PGUSER, PGDATABASE."
            )
        return psycopg2.connect(
            host=self._effective_host(),
            port=self.pg_port,
            user=self.pg_user,
            password=self.pg_password,
            dbname=self.pg_database,
            connect_timeout=connect_timeout,
        )

    def _is_readonly_sql(self, sql: str) -> bool:
        head = sql.strip().split(None, 1)
        if not head:
            return False
        first = head[0].upper()
        return first in {"SELECT", "EXPLAIN", "SHOW", "WITH"}

    async def _execute_tool(self, tool_call, conversation_id: str) -> Dict[str, Any]:
        fname = tool_call.function.name
        args = json.loads(tool_call.function.arguments or "{}")

        try:
            if fname == "run_query":
                return await self._run_query(
                    args.get("sql", ""),
                    limit=int(args.get("limit", 100)),
                    timeout_seconds=int(args.get("timeout_seconds", 15)),
                )
            elif fname == "check_connectivity":
                return await self._check_connectivity()
            elif fname == "list_tables":
                return await self._list_tables(args.get("schema"))
            elif fname == "get_table_schema":
                return await self._get_table_schema(args.get("table", ""))
            else:
                return {"error": f"Unknown tool '{fname}'"}
        except Exception as e:
            return {"error": str(e)}

    async def _check_connectivity(self) -> Dict[str, Any]:
        """Test DB connection and return basic server info."""
        import time

        def _blocking_ping():
            start = time.perf_counter()
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version()")
                    version_row = cur.fetchone()
                    cur.execute("SELECT current_database()")
                    db_row = cur.fetchone()
                    try:
                        cur.execute("SHOW server_version")
                        server_version = cur.fetchone()[0]
                    except Exception:
                        server_version = None
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            return {
                "connected": True,
                "server_version": server_version
                or (version_row[0] if version_row else None),
                "database": db_row[0] if db_row else None,
                "user": self.pg_user,
                "host": self._effective_host(),
                "port": self.pg_port,
                "via_unix_socket": os.path.isabs(self._effective_host()),
                "latency_ms": elapsed_ms,
            }

        import asyncio

        try:
            return await asyncio.to_thread(_blocking_ping)
        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
                "host": self._effective_host(),
                "port": self.pg_port,
                "user": self.pg_user,
                "database": self.pg_database,
            }

    async def _run_query(
        self, sql: str, limit: int, timeout_seconds: int
    ) -> Dict[str, Any]:
        if not sql:
            return {"error": "SQL is required"}
        if not self._is_readonly_sql(sql):
            return {
                "error": "Only read-only queries are allowed (SELECT/EXPLAIN/SHOW/WITH)"
            }

        def _blocking_query():
            with self._connect() as conn:
                with conn.cursor() as cur:
                    # Enforce read-only and statement timeout
                    cur.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY;")
                    cur.execute(
                        "SET statement_timeout = %s;", (timeout_seconds * 1000,)
                    )
                    # Apply limit if not present (best-effort, non-intrusive)
                    q = sql.strip().rstrip(";")
                    cur.execute(q)
                    columns = (
                        [desc[0] for desc in cur.description] if cur.description else []
                    )
                    rows = cur.fetchmany(size=limit)
                    return {"columns": columns, "rows": rows, "row_count": len(rows)}

        import asyncio

        result = await asyncio.to_thread(_blocking_query)
        return result

    async def _list_tables(self, schema: Optional[str]) -> Dict[str, Any]:
        def _blocking_list():
            with self._connect() as conn:
                with conn.cursor() as cur:
                    if schema:
                        cur.execute(
                            """
                            SELECT table_schema, table_name
                            FROM information_schema.tables
                            WHERE table_type = 'BASE TABLE' AND table_schema = %s
                            ORDER BY table_schema, table_name
                            """,
                            (schema,),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT table_schema, table_name
                            FROM information_schema.tables
                            WHERE table_type = 'BASE TABLE'
                            ORDER BY table_schema, table_name
                            """
                        )
                    return {
                        "tables": [
                            {"schema": r[0], "name": r[1]} for r in cur.fetchall()
                        ]
                    }

        import asyncio

        return await asyncio.to_thread(_blocking_list)

    async def _get_table_schema(self, table: str) -> Dict[str, Any]:
        if not table:
            return {"error": "table is required"}

        schema_name = None
        table_name = table
        if "." in table:
            schema_name, table_name = table.split(".", 1)

        def _blocking_schema():
            with self._connect() as conn:
                with conn.cursor() as cur:
                    if schema_name:
                        cur.execute(
                            """
                            SELECT column_name, data_type, is_nullable
                            FROM information_schema.columns
                            WHERE table_schema = %s AND table_name = %s
                            ORDER BY ordinal_position
                            """,
                            (schema_name, table_name),
                        )
                    else:
                        cur.execute(
                            """
                            SELECT column_name, data_type, is_nullable
                            FROM information_schema.columns
                            WHERE table_name = %s
                            ORDER BY ordinal_position
                            """,
                            (table_name,),
                        )
                    cols = cur.fetchall()
                    return {
                        "table": table,
                        "columns": [
                            {
                                "name": c[0],
                                "type": c[1],
                                "nullable": c[2] == "YES",
                            }
                            for c in cols
                        ],
                    }

        import asyncio

        return await asyncio.to_thread(_blocking_schema)
