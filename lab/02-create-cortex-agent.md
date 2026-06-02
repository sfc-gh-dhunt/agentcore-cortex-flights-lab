# 02 - Create Cortex Agent

Create a Cortex Agent that uses your semantic view to answer natural-language questions about flight operations.

## Step 1: Create the Agent

Replace `<YOUR_ID>` with your participant identifier:

```sql
USE ROLE ACCOUNTADMIN;
USE SCHEMA AIRPORT_LHR.LAB_<YOUR_ID>;

CREATE OR REPLACE AGENT FLIGHT_OPS_AGENT_<YOUR_ID>
  COMMENT = 'Aviation operations intelligence agent for LHR'
  FROM SPECIFICATION $$
models:
  orchestration: auto

instructions:
  response: >
    You are an aviation operations analyst for London Heathrow Airport.
    Provide concise, data-driven answers about flight schedules, delays,
    gate utilisation, and traffic patterns. Always include specific numbers
    and timeframes in your responses. If data is limited, say so.
  orchestration: >
    Use the flight_ops_analyst tool for all questions about flights, airlines,
    delays, gates, traffic, and airport operations. For questions outside
    aviation operations, politely decline and explain your scope.

tools:
  - tool_spec:
      type: "cortex_analyst_text_to_sql"
      name: "flight_ops_analyst"
      description: >
        Answers questions about London Heathrow airport operations including:
        flight schedules (departures, arrivals, airlines, routes, terminals, gates),
        delay metrics (departure delays, arrival delays, by airline, by day),
        gate utilisation (dwell times, turnaround times, per gate, per airline),
        and hourly traffic volumes (aircraft counts by category and time).
        Covers data from May 2026.
        
        When to use: Any question about flights, airlines, delays, gates, traffic,
        or operational performance at LHR.
        
        When NOT to use: Questions about other airports (unless comparing), 
        passenger numbers (not in dataset), financial data, or weather.

tool_resources:
  flight_ops_analyst:
    semantic_view: "AIRPORT_LHR.LAB_<YOUR_ID>.FLIGHT_OPS_SV"
    execution_environment:
      type: warehouse
      warehouse: "AVIA_LHR_WH"
$$;
```

## Step 2: Verify the Agent

```sql
-- Check it exists
SHOW AGENTS IN SCHEMA AIRPORT_LHR.LAB_<YOUR_ID>;

-- Describe it
DESCRIBE AGENT FLIGHT_OPS_AGENT_<YOUR_ID>;
```

## Step 3: Test the Agent

Test with a few questions using the SQL function. Note: `DATA_AGENT_RUN` requires a JSON request body as its second argument:

```sql
-- Simple test - extract the text answer
WITH resp AS (
  SELECT TRY_PARSE_JSON(SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
    'AIRPORT_LHR.LAB_<YOUR_ID>.FLIGHT_OPS_AGENT_<YOUR_ID>',
    $${"messages": [{"role": "user", "content": [{"type": "text", "text": "Which airlines have the most flights at Heathrow? Top 5."}]}], "stream": false}$$
  )) AS r
)
SELECT f.value:text::STRING AS answer
FROM resp, TABLE(FLATTEN(r:content)) f
WHERE f.value:type::STRING = 'text';
```

Try a few more:

```sql
-- Average delay by airline
WITH resp AS (
  SELECT TRY_PARSE_JSON(SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
    'AIRPORT_LHR.LAB_<YOUR_ID>.FLIGHT_OPS_AGENT_<YOUR_ID>',
    $${"messages": [{"role": "user", "content": [{"type": "text", "text": "What is the average departure delay by airline?"}]}], "stream": false}$$
  )) AS r
)
SELECT f.value:text::STRING AS answer
FROM resp, TABLE(FLATTEN(r:content)) f
WHERE f.value:type::STRING = 'text';

-- Gate dwell times
WITH resp AS (
  SELECT TRY_PARSE_JSON(SNOWFLAKE.CORTEX.DATA_AGENT_RUN(
    'AIRPORT_LHR.LAB_<YOUR_ID>.FLIGHT_OPS_AGENT_<YOUR_ID>',
    $${"messages": [{"role": "user", "content": [{"type": "text", "text": "Which gates have the longest average dwell time?"}]}], "stream": false}$$
  )) AS r
)
SELECT f.value:text::STRING AS answer
FROM resp, TABLE(FLATTEN(r:content)) f
WHERE f.value:type::STRING = 'text';
```

## Step 4: Grant Permissions

The MCP server will need to invoke your agent:

```sql
GRANT USAGE ON AGENT AIRPORT_LHR.LAB_<YOUR_ID>.FLIGHT_OPS_AGENT_<YOUR_ID>
  TO ROLE ACCOUNTADMIN;
```

## Tips

- If the agent returns "I don't have information about that", check your semantic view has the relevant dimensions/metrics
- If you get SQL errors in the response, the semantic view definition may need adjustment (column names, expressions)
- You can iterate on the agent instructions without recreating - just use `CREATE OR REPLACE`

---

**Next:** [03 - Create MCP Server](03-create-mcp-server.md)
