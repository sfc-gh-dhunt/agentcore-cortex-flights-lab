# Snowflake Cortex Agents + AWS Bedrock AgentCore: Aviation Ops Lab

A hands-on lab that connects a **Snowflake Cortex Agent** to **AWS Bedrock AgentCore Runtime**, using flight operations data for London Heathrow and Gatwick. You deploy a small agent to AgentCore Runtime that delegates data questions to a Snowflake Cortex Agent (question-to-answer, with the SQL run inside Snowflake) and geocodes locations with Amazon Location Service.

## Architecture

```
You (EC2 / Session Manager)
        │  prompt
        ▼
┌─────────────────────────────────────────────┐
│  Amazon Bedrock AgentCore Runtime            │
│  ┌─────────────────────────────────────────┐ │
│  │  Strands agent (Claude on Bedrock)      │ │   router only
│  │   • data question → Cortex Agent tool   │ │
│  │   • address       → geocode_address     │ │
│  └───────────────┬─────────────────────────┘ │
└──────────────────┼───────────────┬───────────┘
       MCP (HTTPS, │ PAT)           │ Amazon Location
                   ▼                ▼
        ┌──────────────────┐  ┌──────────────────┐
        │ Snowflake MCP    │  │ Amazon Location  │
        │  server          │  │  (place index)   │
        │   └─ Cortex Agent│  └──────────────────┘
        │       └─ Analyst → executes SQL → answer
        └──────────────────┘
```

The Snowflake **Cortex Agent** is the brain: a single tool call runs Cortex Analyst, executes the generated SQL, and returns a complete answer. The Bedrock agent does not generate or run SQL itself.

## What You Will Build

1. A **Semantic View** over flight operations data (schedules, delays, gate utilisation, traffic).
2. A **Cortex Agent** that answers natural-language questions using that semantic view.
3. A **Snowflake-managed MCP Server** exposing the agent (and, optionally, the analyst) over the Model Context Protocol.
4. An agent deployed to **AWS Bedrock AgentCore Runtime** that calls your MCP server and Amazon Location Service.
5. A working end-to-end flow: ask a question on AWS, get an answer grounded in Snowflake flight data.

## Prerequisites

| Requirement | Details |
|---|---|
| Snowflake account | Org-account identifier in `<org>-<account>` format |
| Snowflake login | Your assigned user (e.g. `user1`) with access to the aviation databases |
| AWS environment | An EC2 instance with the AgentCore CLI pre-installed (provided by the workshop), reachable via Session Manager |
| Amazon Bedrock model access | Anthropic Claude enabled in your region (handled by the workshop stack) |
| Python 3.10+ | On the EC2 instance |

## Lab Structure

| Section | Description |
|---|---|
| [00 - Environment Check](lab/00-environment-check.md) | Validate credentials and explore the data |
| [01 - Create Semantic View](lab/01-create-semantic-view.md) | Build a semantic view over flight ops tables |
| [02 - Create Cortex Agent](lab/02-create-cortex-agent.md) | Deploy a Cortex Agent using the semantic view |
| [03 - Create MCP Server](lab/03-create-mcp-server.md) | Expose the agent via a Snowflake-managed MCP server |
| [04 - Deploy to AgentCore Runtime](lab/04-deploy-agentcore-runtime.md) | Configure, deploy, and permission the agent on AWS |
| [05 - Test End-to-End](lab/05-test-end-to-end.md) | Validate the full flow with example prompts |
| [06 - Extensions](lab/06-extensions.md) | Optional: iterate with Cortex Code, add tools, build a UI |

## Data Environment

The Snowflake account has two pre-populated airport databases:

- **AIRPORT_LHR** - London Heathrow (millions of ADS-B positions, thousands of flight schedules)
- **AIRPORT_LGW** - London Gatwick

Each contains Dynamic Tables for traffic analysis, gate utilisation, runway crossings, and airline delays. See [sample-environment.md](sample-environment.md) for the full object inventory.

## The AgentCore agent

The deployable agent lives in [agentcore/](agentcore/):

| File | Purpose |
|---|---|
| `snowflake_mcp_agentcore.py` | The Strands/AgentCore agent. Config-driven; exposes the MCP server's tools and a geocoding tool. No code changes needed. |
| `config.yaml.example` | Copy to `config.yaml` and fill in your account, PAT, database, schema, MCP server name. |
| `requirements.txt` | Container dependencies. |
| `invoke_agentcore.py` | Interactive client to invoke the deployed runtime. |
| `fix_permissions.sh` | Adds the geocoding + marketplace IAM permissions the runtime role needs. |

It reads everything from `config.yaml` - the same agent works against any Snowflake MCP server. Set `mcp.tools` to just your Cortex Agent tool for a clean question-to-answer experience.

## Quick Start (on the EC2 instance)

```bash
git clone <repo-url>
cd agentcore-cortex-flights-lab/agentcore
cp config.yaml.example config.yaml
# edit config.yaml with your account, PAT, database, schema, and MCP server name
pip install -r requirements.txt
# then follow lab/04 to configure and launch on AgentCore Runtime
```

## Troubleshooting

| Issue | Solution |
|---|---|
| `Database does not exist or not authorized` | Check your role has access; the lab objects are created under `ACCOUNTADMIN`. |
| MCP `tools/list` returns empty | Verify grants: `GRANT USAGE ON MCP SERVER ... TO ROLE ...` and on the underlying agent/semantic view. |
| `Programmatic access token is invalid` | Use the org-account format (`<org>-<account>`) in `config.yaml`, not the account locator. Regenerate the PAT if expired. |
| `Network policy is required` | Ensure a network policy permits the caller IP (an account-level allow-all policy covers any EC2 IP). |
| `Invalid length for parameter modelId` | Set `AGENT_MODEL_ID` at deploy time (e.g. `agentcore launch --env AGENT_MODEL_ID=$AGENT_MODEL_ID`). |
| `AccessDenied` on `geo:` or `aws-marketplace:` | Run `fix_permissions.sh`; allow 10-60s for IAM propagation, then retry. |

## References

- [Snowflake Managed MCP Server](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-agents-mcp)
- [Cortex Agents - Build Agents](https://docs.snowflake.com/en/user-guide/snowflake-cortex/snowflake-intelligence/build-agents)
- [Amazon Bedrock AgentCore](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [Strands Agents SDK](https://strandsagents.com/)
- [Semantic View YAML spec](https://docs.snowflake.com/en/user-guide/views-semantic/semantic-view-yaml-spec)
