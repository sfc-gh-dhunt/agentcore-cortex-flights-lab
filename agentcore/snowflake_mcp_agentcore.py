"""
Snowflake MCP -> Amazon Bedrock AgentCore agent.

A vendor-neutral Strands agent, deployed on Bedrock AgentCore Runtime, that acts
as a thin router:

  * Data / analytical questions are delegated to a Snowflake-managed MCP server.
    When that server exposes a Cortex Agent tool (type CORTEX_AGENT_RUN), a single
    tool call returns a complete, final answer - the Cortex Agent runs Cortex
    Analyst, executes the generated SQL, and composes the response server-side.
    This agent simply surfaces that answer; it does NOT generate or run SQL itself.
  * Addresses / place names are geocoded with Amazon Location Service.

All configuration comes from config.yaml (see config.yaml.example). No credentials
are embedded in this file.

Drop-in contract for Bedrock AgentCore Runtime:
  - entrypoint `invoke(payload)` reads payload["prompt"] and returns {"result": ...}
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import boto3
import requests
import yaml
from bedrock_agentcore import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models.bedrock import BedrockModel
from strands_tools import current_time

app = BedrockAgentCoreApp()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (config.yaml; no hardcoded secrets or defaults for credentials)
# ---------------------------------------------------------------------------

def _load_config() -> Dict[str, Any]:
    config_file = Path(__file__).parent / "config.yaml"
    if config_file.exists():
        try:
            with open(config_file) as f:
                cfg = yaml.safe_load(f) or {}
                logger.info("Configuration loaded from %s", config_file)
                return cfg
        except Exception as e:  # pragma: no cover - defensive
            logger.error("Failed to parse config.yaml: %s", e)
            raise
    logger.warning("config.yaml not found next to the agent; required values must be set.")
    return {}


CONFIG = _load_config()


def _cfg(key: str, section: str, default: Any = None) -> Any:
    section_data = CONFIG.get(section)
    if isinstance(section_data, dict) and key in section_data:
        return section_data[key]
    return default


SNOWFLAKE_ACCOUNT = _cfg("account", "snowflake")
SNOWFLAKE_USER = _cfg("user", "snowflake")
SNOWFLAKE_PAT_TOKEN = _cfg("pat_token", "snowflake")
SNOWFLAKE_DATABASE = _cfg("database", "snowflake")
SNOWFLAKE_SCHEMA = _cfg("schema", "snowflake")
MCP_SERVER_NAME = _cfg("server_name", "mcp")
# Optional allowlist of MCP tool names to expose. When omitted/empty, all tools
# advertised by the server are exposed. For a Cortex-Agent-centric setup, set this
# to just the Cortex Agent tool so the model answers question-to-answer.
MCP_TOOL_ALLOWLIST: Optional[List[str]] = _cfg("tools", "mcp")
AWS_PLACE_INDEX_NAME = _cfg("place_index_name", "aws", "agentcore-index")

_REQUIRED = {
    "snowflake.account": SNOWFLAKE_ACCOUNT,
    "snowflake.pat_token": SNOWFLAKE_PAT_TOKEN,
    "snowflake.database": SNOWFLAKE_DATABASE,
    "snowflake.schema": SNOWFLAKE_SCHEMA,
    "mcp.server_name": MCP_SERVER_NAME,
}
_missing = [name for name, value in _REQUIRED.items() if not value]
if _missing:
    raise RuntimeError(
        "Missing required configuration: "
        + ", ".join(_missing)
        + ". Copy config.yaml.example to config.yaml and fill it in."
    )

# Snowflake account hostnames use hyphens, not underscores. If the account
# identifier is entered with underscores (e.g. ORG-ACME_PROD), Python's TLS
# verification rejects the underscore hostname even though curl tolerates it.
# Convert underscores to hyphens for the URL host only.
_ACCOUNT_HOST = SNOWFLAKE_ACCOUNT.replace("_", "-")
MCP_URL = (
    f"https://{_ACCOUNT_HOST}.snowflakecomputing.com"
    f"/api/v2/databases/{SNOWFLAKE_DATABASE}/schemas/{SNOWFLAKE_SCHEMA}"
    f"/mcp-servers/{MCP_SERVER_NAME}"
)
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "Authorization": f"Bearer {SNOWFLAKE_PAT_TOKEN}",
}
# Cortex Agents run multiple steps server-side; allow generous time.
MCP_TIMEOUT_SECONDS = int(os.environ.get("MCP_TIMEOUT_SECONDS", "150"))

AGENT_MODEL_ID = os.environ.get(
    "AGENT_MODEL_ID", "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
)

logger.info("MCP server: %s.%s.%s", SNOWFLAKE_DATABASE, SNOWFLAKE_SCHEMA, MCP_SERVER_NAME)
logger.info("Model: %s", AGENT_MODEL_ID)

location_client = boto3.client("location")


# ---------------------------------------------------------------------------
# MCP transport (direct JSON-RPC over HTTPS with PAT bearer auth)
# ---------------------------------------------------------------------------

def _mcp_rpc(method: str, params: Dict[str, Any], request_id: int = 1) -> Dict[str, Any]:
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    response = requests.post(MCP_URL, headers=_HEADERS, json=payload, timeout=MCP_TIMEOUT_SECONDS)
    response.raise_for_status()
    return response.json()


def _list_mcp_tools() -> List[Dict[str, Any]]:
    data = _mcp_rpc("tools/list", {}, request_id=1)
    return data.get("result", {}).get("tools", [])


def _extract_answer(rpc_response: Dict[str, Any]) -> str:
    """Turn an MCP tools/call response into a human-readable answer.

    Handles both shapes seen on Snowflake MCP servers:
      * Cortex Agent (CORTEX_AGENT_RUN): result.content[0].text is a JSON string
        whose inner "content" list ends with the final {"type":"text"} answer.
      * Cortex Analyst / plain tools: result.content is a list of text/JSON blocks.
    """
    if rpc_response.get("error"):
        return f"MCP error: {json.dumps(rpc_response['error'])}"

    result = rpc_response.get("result", {})
    if result.get("isError"):
        return f"Tool reported an error: {json.dumps(result.get('content'))}"

    blocks = result.get("content", [])
    texts: List[str] = []
    for block in blocks:
        if isinstance(block, dict) and isinstance(block.get("text"), str):
            texts.append(block["text"])
        else:
            texts.append(json.dumps(block))
    raw = "\n".join(t for t in texts if t).strip()

    # If the payload is a Cortex Agent transcript, pull out the final text event.
    try:
        inner = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw

    if isinstance(inner, dict) and isinstance(inner.get("content"), list):
        final_texts = [
            item["text"]
            for item in inner["content"]
            if isinstance(item, dict)
            and item.get("type") == "text"
            and isinstance(item.get("text"), str)
            and item["text"].strip()
        ]
        if final_texts:
            return final_texts[-1].strip()
    return raw


def _call_mcp_tool(tool_name: str, arguments: Dict[str, Any]) -> str:
    try:
        logger.info("Calling MCP tool '%s' with %s", tool_name, arguments)
        data = _mcp_rpc("tools/call", {"name": tool_name, "arguments": arguments}, request_id=12346)
        return _extract_answer(data)
    except requests.exceptions.RequestException as e:
        logger.error("MCP call to '%s' failed: %s", tool_name, e)
        return f"Error calling Snowflake MCP tool '{tool_name}': {e}"


# ---------------------------------------------------------------------------
# Dynamic tool registration: one Strands tool per exposed MCP tool
# ---------------------------------------------------------------------------

def _sanitize(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", name)


def _primary_arg(input_schema: Dict[str, Any]) -> str:
    """Pick the single argument name an MCP tool expects (e.g. 'text'/'message')."""
    required = input_schema.get("required")
    if isinstance(required, list) and required:
        return required[0]
    properties = input_schema.get("properties")
    if isinstance(properties, dict) and properties:
        return next(iter(properties))
    return "message"


def _make_tool(mcp_name: str, arg_name: str, description: str):
    """Build a Strands @tool wrapper that forwards a single string to an MCP tool."""

    def _wrapper(request: str) -> str:
        return _call_mcp_tool(mcp_name, {arg_name: request})

    _wrapper.__name__ = _sanitize(mcp_name)
    _wrapper.__qualname__ = _wrapper.__name__
    _wrapper.__doc__ = (
        f"{description}\n\n"
        ":param request: The natural-language question or input to send.\n"
        ":returns: The tool's complete answer as text."
    )
    return tool(_wrapper)


def _build_mcp_tools() -> List[Any]:
    available = _list_mcp_tools()
    if MCP_TOOL_ALLOWLIST:
        allow = set(MCP_TOOL_ALLOWLIST)
        selected = [t for t in available if t.get("name") in allow]
        missing = allow - {t.get("name") for t in available}
        if missing:
            logger.warning("Configured mcp.tools not found on server: %s", ", ".join(sorted(missing)))
    else:
        selected = available

    tools: List[Any] = []
    for t in selected:
        name = t.get("name")
        if not name:
            continue
        arg_name = _primary_arg(t.get("inputSchema", {}) or {})
        description = t.get("description") or f"Snowflake MCP tool '{name}'."
        tools.append(_make_tool(name, arg_name, description))
        logger.info("Registered MCP tool '%s' (arg '%s')", name, arg_name)
    if not tools:
        logger.warning("No MCP tools registered from %s", MCP_URL)
    return tools


# ---------------------------------------------------------------------------
# AWS-native tool: geocoding via Amazon Location Service
# ---------------------------------------------------------------------------

@tool
def geocode_address(address: str) -> dict:
    """Geocode a street address or place name into coordinates using Amazon Location Service.

    :param address: The address or place name to geocode.
    :returns: A dict with the coordinates and a human-readable label, or an error.
    """
    response = location_client.search_place_index_for_text(
        IndexName=AWS_PLACE_INDEX_NAME, Text=address
    )
    results = response.get("Results") or []
    if results:
        place = results[0]["Place"]
        return {"coordinates": place["Geometry"]["Point"], "label": place.get("Label")}
    return {"error": "Address not found."}


# ---------------------------------------------------------------------------
# Agent (built lazily so transient startup network issues don't crash the runtime)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a helpful data assistant backed by Snowflake.

- For any data or analytical question, call the available Snowflake tool(s). These
  tools return a COMPLETE, final answer - they run the query and execute the SQL
  internally. Present that answer to the user directly. Do NOT invent, display, or
  claim to run SQL yourself, and do not describe intermediate steps unless asked.
- Preserve any tables, figures, or formatting the tool returns.
- Use geocode_address to convert an address or place name into coordinates when the
  user asks for a location or coordinates.
- Use current_time when the answer depends on the current date or time (for example
  phrases like "today", "this week", or "the last 7 days").
- If a tool returns an error, report it plainly rather than guessing an answer.
"""

_agent: Optional[Agent] = None


def _get_agent() -> Agent:
    global _agent
    if _agent is None:
        tools = _build_mcp_tools() + [geocode_address, current_time]
        _agent = Agent(
            model=BedrockModel(model_id=AGENT_MODEL_ID),
            tools=tools,
            system_prompt=SYSTEM_PROMPT,
        )
    return _agent


@app.entrypoint
def invoke(payload):
    prompt = payload.get("prompt", "Hello, how can I help you?")
    try:
        response = _get_agent()(prompt)
        return {"result": response.message}
    except Exception as e:  # surface errors to the caller instead of a bare 500
        logger.exception("Agent invocation failed")
        return {"result": f"Error: {e}"}


if __name__ == "__main__":
    app.run()
