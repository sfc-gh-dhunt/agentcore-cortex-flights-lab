#!/usr/bin/env python3
"""
Interactive client for invoking the agent deployed on Bedrock AgentCore Runtime.

Resolves the agent runtime ARN from (in order):
  1. --arn CLI argument
  2. AGENT_RUNTIME_ARN environment variable
  3. .bedrock_agentcore.yaml in the current directory (written by `agentcore launch`)

Usage:
  python3 invoke_agentcore.py
  python3 invoke_agentcore.py --arn arn:aws:bedrock-agentcore:...:runtime/your-agent
  python3 invoke_agentcore.py --prompt "How many flights are scheduled today?"
"""

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

import boto3

REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))


def _resolve_arn(cli_arn: str | None) -> str:
    if cli_arn:
        return cli_arn
    if os.environ.get("AGENT_RUNTIME_ARN"):
        return os.environ["AGENT_RUNTIME_ARN"]
    cfg = Path(".bedrock_agentcore.yaml")
    if cfg.exists():
        try:
            import yaml

            data = yaml.safe_load(cfg.read_text()) or {}
            agents = data.get("agents", {})
            for agent in agents.values():
                arn = (agent.get("bedrock_agentcore") or {}).get("agent_arn")
                if arn:
                    return arn
        except Exception as e:  # pragma: no cover - best effort
            print(f"(could not parse .bedrock_agentcore.yaml: {e})", file=sys.stderr)
    print(
        "Could not determine the agent runtime ARN. Pass --arn, set AGENT_RUNTIME_ARN,\n"
        "or run from the directory containing .bedrock_agentcore.yaml.",
        file=sys.stderr,
    )
    sys.exit(1)


def _print_stream(response) -> None:
    content_type = response.get("contentType", "")
    body = response["response"]
    if "text/event-stream" in content_type:
        for line in body.iter_lines(chunk_size=1):
            if not line:
                continue
            text = line.decode("utf-8") if isinstance(line, bytes) else line
            if text.startswith("data: "):
                text = text[len("data: ") :]
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                print(text, end="", flush=True)
                continue
            if isinstance(data, dict) and "result" in data:
                print(_render(data["result"]), flush=True)
            else:
                print(_render(data), flush=True)
        print()
    else:
        raw = body.read()
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            print(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
            return
        print(_render(data.get("result", data)))


def _render(result) -> str:
    """Pull readable text out of a Strands message dict, else stringify."""
    if isinstance(result, dict) and isinstance(result.get("content"), list):
        parts = [b.get("text", "") for b in result["content"] if isinstance(b, dict)]
        joined = "".join(parts).strip()
        if joined:
            return joined
    return result if isinstance(result, str) else json.dumps(result, indent=2)


def invoke(client, arn: str, prompt: str) -> None:
    session_id = f"session-{uuid.uuid4().hex}"  # AgentCore requires >= 33 chars
    response = client.invoke_agent_runtime(
        agentRuntimeArn=arn,
        runtimeSessionId=session_id,
        payload=json.dumps({"prompt": prompt}).encode(),
    )
    _print_stream(response)


def main() -> None:
    parser = argparse.ArgumentParser(description="Invoke an agent on Bedrock AgentCore Runtime.")
    parser.add_argument("--arn", help="Agent runtime ARN")
    parser.add_argument("--prompt", help="Single prompt (non-interactive); omit for interactive mode")
    args = parser.parse_args()

    arn = _resolve_arn(args.arn)
    client = boto3.client("bedrock-agentcore", region_name=REGION)

    if args.prompt:
        invoke(client, arn, args.prompt)
        return

    print("Interactive Bedrock AgentCore session. Type 'quit', 'exit', or 'bye' to end.")
    print("=" * 60)
    while True:
        try:
            prompt = input("\nEnter your prompt: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break
        if prompt.lower() in {"quit", "exit", "bye"}:
            print("Goodbye.")
            break
        if not prompt:
            continue
        invoke(client, arn, prompt)


if __name__ == "__main__":
    main()
