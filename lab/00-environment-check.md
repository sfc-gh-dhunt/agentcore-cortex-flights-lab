# 00 - Environment Check

Confirm you can reach both Snowflake and AWS before building anything.

## Part A: Snowflake

1. Sign in to Snowsight with your assigned user (e.g. `user1`).
2. Find your **org-account identifier** (bottom-left account menu): it is in `<org>-<account>` format, e.g. `myorg-myaccount`. You will use this everywhere - **not** the short account locator.
3. Confirm the aviation data is present:

```sql
USE ROLE ACCOUNTADMIN;

SHOW DATABASES LIKE 'AIRPORT_%';

-- A quick look at the flight schedule data for London Heathrow
SELECT airline_name, COUNT(*) AS flights
FROM AIRPORT_LHR.PUBLIC.FLIGHT_SCHEDULE
GROUP BY airline_name
ORDER BY flights DESC
LIMIT 10;
```

You should see `AIRPORT_LHR` and `AIRPORT_LGW`, and a list of airlines with flight counts. See [sample-environment.md](../sample-environment.md) for the full object inventory.

## Part B: AWS

1. Open the AWS Console -> **EC2** -> **Instances**.
2. Select the instance whose name ends in `-ec2`, choose **Connect** -> **Session Manager** tab -> **Connect**.
3. In the terminal, confirm the tooling:

```bash
agentcore --help | head -5            # confirms the AgentCore CLI is installed
echo "AGENT_MODEL_ID=$AGENT_MODEL_ID"  # if empty, set it before deploy: export AGENT_MODEL_ID=us.anthropic.claude-sonnet-4-6
aws sts get-caller-identity            # confirms AWS credentials are present
```

4. Confirm Amazon Bedrock model access in your region: Bedrock console -> **Model catalog** -> any Anthropic Claude model should show **Available** (handled by the workshop stack).

## What's next

You will build the Snowflake side (semantic view -> Cortex Agent -> MCP server), then deploy a small agent to Bedrock AgentCore Runtime that calls it.

| If this works... | ...you're ready for |
|---|---|
| Airlines query returns rows | [01 - Create Semantic View](01-create-semantic-view.md) |
| `agentcore --help` prints commands | [04 - Deploy to AgentCore Runtime](04-deploy-agentcore-runtime.md) |

---

**Next:** [01 - Create Semantic View](01-create-semantic-view.md)
