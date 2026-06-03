"""
Optional Streamlit UI that talks directly to the Snowflake-managed MCP server
(the same Cortex Agent the deployed AgentCore agent uses).

It reads agentcore/config.yaml for the account, PAT, database, schema, and MCP
server name, then calls the Cortex Agent tool and renders the final answer.

Run:
    cd extensions
    pip install -r requirements.txt
    streamlit run streamlit_app.py
"""

import json
from pathlib import Path

import requests
import streamlit as st
import yaml

CONFIG_PATH = Path(__file__).parent.parent / "agentcore" / "config.yaml"


def load_config():
    if not CONFIG_PATH.exists():
        return None
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f) or {}


def mcp_url(cfg):
    sf, mcp = cfg.get("snowflake", {}), cfg.get("mcp", {})
    host = sf["account"].replace("_", "-")  # Snowflake hostnames use hyphens, not underscores
    return (
        f"https://{host}.snowflakecomputing.com"
        f"/api/v2/databases/{sf['database']}/schemas/{sf['schema']}"
        f"/mcp-servers/{mcp['server_name']}"
    )


def pick_tool(cfg):
    """Use the configured allowlisted tool if present, else a sensible default."""
    tools = (cfg.get("mcp", {}) or {}).get("tools")
    if tools:
        return tools[0]
    return "flight-ops-agent"


def extract_answer(rpc_response):
    result = rpc_response.get("result", {})
    if rpc_response.get("error"):
        return f"MCP error: {json.dumps(rpc_response['error'])}"
    blocks = result.get("content", [])
    texts = [b["text"] for b in blocks if isinstance(b, dict) and isinstance(b.get("text"), str)]
    raw = "\n".join(texts).strip() or json.dumps(result)
    try:
        inner = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw
    if isinstance(inner, dict) and isinstance(inner.get("content"), list):
        finals = [
            i["text"] for i in inner["content"]
            if isinstance(i, dict) and i.get("type") == "text" and i.get("text", "").strip()
        ]
        if finals:
            return finals[-1].strip()
    return raw


def call_agent(cfg, tool_name, question):
    sf = cfg["snowflake"]
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {sf['pat_token']}",
    }
    # CORTEX_AGENT_RUN tools take 'text'; analyst tools take 'message'. Try 'text' first.
    payload = {
        "jsonrpc": "2.0",
        "id": "streamlit",
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": {"text": question}},
    }
    resp = requests.post(mcp_url(cfg), headers=headers, json=payload, timeout=150)
    if resp.status_code == 200 and "result" in resp.json():
        return extract_answer(resp.json())
    # Fall back to the analyst-style 'message' argument
    payload["params"]["arguments"] = {"message": question}
    resp = requests.post(mcp_url(cfg), headers=headers, json=payload, timeout=150)
    if resp.status_code == 200:
        return extract_answer(resp.json())
    return f"Error: HTTP {resp.status_code}\n```\n{resp.text[:500]}\n```"


# --- Streamlit UI ---

st.set_page_config(page_title="Flight Ops - Cortex Agent", page_icon="*", layout="wide")
st.title("Flight Operations Assistant")
st.caption("Powered by a Snowflake Cortex Agent via the managed MCP server")

cfg = load_config()
if not cfg:
    st.error("agentcore/config.yaml not found. Copy agentcore/config.yaml.example and fill it in.")
    st.stop()

tool_name = pick_tool(cfg)
sf = cfg.get("snowflake", {})
st.sidebar.header("Configuration")
st.sidebar.text(f"Account: {sf.get('account', 'N/A')}")
st.sidebar.text(f"DB/Schema: {sf.get('database', '')}.{sf.get('schema', '')}")
st.sidebar.text(f"MCP tool: {tool_name}")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if not st.session_state.messages:
    st.markdown("**Try asking:**")
    cols = st.columns(3)
    examples = [
        "Which airlines have the most flights?",
        "What's the average departure delay by airline?",
        "Which gates have the longest turnaround?",
    ]
    for col, example in zip(cols, examples):
        if col.button(example, use_container_width=True):
            st.session_state.messages.append({"role": "user", "content": example})
            st.rerun()

if prompt := st.chat_input("Ask about flight operations..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Asking the Cortex Agent..."):
            try:
                answer = call_agent(cfg, tool_name, prompt)
            except Exception as e:
                answer = f"Error: {e}"
        st.markdown(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer})
