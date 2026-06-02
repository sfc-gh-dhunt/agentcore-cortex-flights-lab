# 06 - Extensions

Optional exercises if you finish early or want to explore further.

## Extension 1: Iterate on the Semantic View with Cortex Code

Use Cortex Code (CoCo) to improve your semantic view based on real query failures:

1. Open Cortex Code and connect to your Snowflake account
2. Ask CoCo: "Help me improve my semantic view at `AIRPORT_LHR.LAB_<YOUR_ID>.FLIGHT_OPS_SV`"
3. Try queries that failed and use CoCo to add:
   - Missing synonyms
   - Better metric descriptions
   - Additional verified queries
   - New derived metrics (e.g. on-time percentage)

Example improvements to try:
```
"Add an on-time percentage metric to my semantic view"
"Add a verified query for finding the most common routes from LHR"
"Add Gatwick data as additional tables in the semantic view"
```

## Extension 2: Improve the Cortex Agent

Refine your agent's behavior:

```sql
-- Add more specific instructions
CREATE OR REPLACE AGENT AIRPORT_LHR.LAB_<YOUR_ID>.FLIGHT_OPS_AGENT_<YOUR_ID>
  FROM SPECIFICATION $$
models:
  orchestration: auto

instructions:
  response: >
    You are an aviation operations analyst for London Heathrow Airport.
    Always provide specific numbers. When showing rankings, include the top 5.
    Format delays in hours and minutes when over 60 minutes.
    If asked about trends, compare to the previous period where data allows.
  orchestration: >
    Use flight_ops_analyst for ALL aviation questions.
    For multi-part questions, break them down and call the tool multiple times.
    Always specify date ranges in your queries to the tool.

tools:
  - tool_spec:
      type: "cortex_analyst_text_to_sql"
      name: "flight_ops_analyst"
      description: >
        Queries LHR aviation operations data covering May 2026.
        Tables: flight schedules (3200+ flights), airline delays (daily aggregates),
        gate dwell times (15000+ records), hourly traffic (2000+ hours).
        Key metrics: departure delay, arrival delay, gate dwell time, aircraft count.
        Key dimensions: airline, date, gate, terminal, hour, vehicle category.

tool_resources:
  flight_ops_analyst:
    semantic_view: "AIRPORT_LHR.LAB_<YOUR_ID>.FLIGHT_OPS_SV"
$$;
```

## Extension 3: Add a Second Airport

Extend your semantic view to include Gatwick data for comparison:

```sql
-- Add LGW tables to your semantic view (CREATE OR REPLACE with additional tables)
-- Then test cross-airport queries through your deployed agent:
-- "Compare average delays at Heathrow vs Gatwick"
-- "Which airport has more traffic in the morning hours?"
```

## Extension 4: Build a Streamlit App

Create a simple Streamlit app that calls your deployed AgentCore agent:

```bash
cd extensions/
streamlit run streamlit_app.py
```

The app provides a chat interface where you type aviation questions and see answers from your full pipeline.

See `extensions/streamlit_app.py` for the starter code.

## Extension 5: Add MCP Server to Claude Desktop or VS Code

If you have Claude Desktop or VS Code with MCP support:

1. Get your OAuth client ID and secret (from the security integration)
2. Configure the MCP server URL in your client's MCP settings
3. Ask aviation questions directly in your IDE/desktop app

MCP server URL:
```
https://<YOUR_SNOWFLAKE_ACCOUNT>.snowflakecomputing.com/api/v2/databases/AIRPORT_LHR/schemas/LAB_<YOUR_ID>/mcp-servers/FLIGHT_OPS_MCP_<YOUR_ID>
```

## Extension 6: Add More Tools to the MCP Server

Extend your MCP server with a SQL execution tool:

```sql
CREATE OR REPLACE MCP SERVER AIRPORT_LHR.LAB_<YOUR_ID>.FLIGHT_OPS_MCP_<YOUR_ID>
  FROM SPECIFICATION $$
tools:
  - name: "flight-ops-agent"
    type: "CORTEX_AGENT_RUN"
    identifier: "AIRPORT_LHR.LAB_<YOUR_ID>.FLIGHT_OPS_AGENT_<YOUR_ID>"
    description: "Aviation operations intelligence agent for London Heathrow"
    title: "LHR Flight Ops Agent"

  - name: "flight-ops-analyst"
    type: "CORTEX_ANALYST_MESSAGE"
    identifier: "AIRPORT_LHR.LAB_<YOUR_ID>.FLIGHT_OPS_SV"
    description: "Direct text-to-SQL for precise flight operations queries"
    title: "LHR Flight Ops Analyst"

  - name: "sql-exec"
    type: "SYSTEM_EXECUTE_SQL"
    description: "Execute read-only SQL queries against the flight operations database"
    title: "SQL Query Tool"
    config:
      read_only: true
      query_timeout: 60
      warehouse: "AVIA_LHR_WH"
$$;
```

---

**Congratulations!** You have built an end-to-end pipeline from AWS Bedrock AgentCore Runtime through Snowflake's MCP server to a Cortex Agent backed by real aviation operations data.
