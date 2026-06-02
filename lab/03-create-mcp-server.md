# 03 - Create MCP Server

Create a Snowflake-managed MCP server that exposes your Cortex Agent (and optionally the semantic view directly) as tools accessible via the Model Context Protocol.

## Background

The Snowflake-managed MCP server provides:
- A standard MCP endpoint that external clients can discover tools on and invoke them
- OAuth or PAT-based authentication
- RBAC for tool access (USAGE on MCP server + USAGE on agent / SELECT on semantic view)

## Step 1: Create the MCP Server

Replace `<YOUR_ID>` with your participant identifier:

```sql
USE ROLE ACCOUNTADMIN;
USE SCHEMA AIRPORT_LHR.LAB_<YOUR_ID>;

CREATE OR REPLACE MCP SERVER FLIGHT_OPS_MCP_<YOUR_ID>
  FROM SPECIFICATION $$
tools:
  - name: "flight-ops-agent"
    type: "CORTEX_AGENT_RUN"
    identifier: "AIRPORT_LHR.LAB_<YOUR_ID>.FLIGHT_OPS_AGENT_<YOUR_ID>"
    description: "Aviation operations intelligence agent for London Heathrow. Answers questions about flights, airlines, delays, gate utilisation, and traffic patterns."
    title: "LHR Flight Ops Agent"

  - name: "flight-ops-analyst"
    type: "CORTEX_ANALYST_MESSAGE"
    identifier: "AIRPORT_LHR.LAB_<YOUR_ID>.FLIGHT_OPS_SV"
    description: "Direct text-to-SQL over LHR flight operations data. Use for precise data queries about schedules, delays, gates, and traffic."
    title: "LHR Flight Ops Analyst"
$$;
```

## Step 2: Verify

```sql
-- Show MCP servers in your schema
SHOW MCP SERVERS IN SCHEMA AIRPORT_LHR.LAB_<YOUR_ID>;

-- Describe to see the tool specification
DESCRIBE MCP SERVER FLIGHT_OPS_MCP_<YOUR_ID>;
```

## Step 3: Determine Your MCP Endpoint URL

Your MCP server URL follows this pattern:

```
https://<account_url>/api/v2/databases/AIRPORT_LHR/schemas/LAB_<YOUR_ID>/mcp-servers/FLIGHT_OPS_MCP_<YOUR_ID>
```

where `<account_url>` is your org-account identifier followed by `.snowflakecomputing.com`, for example:
```
https://<YOUR_SNOWFLAKE_ACCOUNT>.snowflakecomputing.com/api/v2/databases/AIRPORT_LHR/schemas/LAB_<YOUR_ID>/mcp-servers/FLIGHT_OPS_MCP_<YOUR_ID>
```

Note this URL -- the AgentCore agent builds the same path from your `config.yaml` values (`account`, `database`, `schema`, `mcp.server_name`).

## Step 4: Create a PAT Token

You need a Programmatic Access Token to authenticate from AWS to Snowflake:

1. Go to Snowsight -> your user menu (bottom left) -> **Preferences** -> **Authentication**
2. Under **Programmatic access tokens**, click **Generate new token**
3. Name: `agentcore-lab`
4. Role restriction: `ACCOUNTADMIN` (the lab objects are owned by `ACCOUNTADMIN`)
5. Expiration: a few days is sufficient for the lab
6. Copy the token immediately -- it won't be shown again

Alternatively via SQL (the token is shown once in the results):
```sql
ALTER USER <YOUR_USERNAME> ADD PROGRAMMATIC ACCESS TOKEN agentcore_lab
  DAYS_TO_EXPIRY = 5
  ROLE_RESTRICTION = 'ACCOUNTADMIN';
```

Save this token securely -- you will need it for the next section.

## Step 5: Test the MCP Server Locally (Optional)

You can quickly test with `curl`:

```bash
# Set your values
export SNOWFLAKE_ACCOUNT_URL="<YOUR_SNOWFLAKE_ACCOUNT>.snowflakecomputing.com"
export SNOWFLAKE_PAT="<your-pat-token>"
export MCP_PATH="api/v2/databases/AIRPORT_LHR/schemas/LAB_<YOUR_ID>/mcp-servers/FLIGHT_OPS_MCP_<YOUR_ID>"

# List available tools
curl -s -X POST "https://${SNOWFLAKE_ACCOUNT_URL}/${MCP_PATH}" \
  -H "Authorization: Bearer ${SNOWFLAKE_PAT}" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python3 -m json.tool

# Invoke the analyst tool
curl -s -X POST "https://${SNOWFLAKE_ACCOUNT_URL}/${MCP_PATH}" \
  -H "Authorization: Bearer ${SNOWFLAKE_PAT}" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"flight-ops-analyst","arguments":{"message":"How many flights are in the schedule?"}}}' | python3 -m json.tool
```

You should see your two tools listed and get a data response.

---

**Next:** [04 - Deploy to AgentCore Runtime](04-deploy-agentcore-runtime.md)
