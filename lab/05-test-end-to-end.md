# 05 - Test End-to-End

Invoke the deployed agent and watch the full flow: your prompt -> Bedrock agent (router) -> Snowflake Cortex Agent (runs Analyst + executes SQL) -> answer. Address prompts also call Amazon Location Service.

**Where:** the EC2 instance (Session Manager), from `agentcore-cortex-flights-lab/agentcore`.

## Step 1: Start the interactive client

```bash
cd ~/agentcore-cortex-flights-lab/agentcore
python3 invoke_agentcore.py
```

The client reads the runtime ARN from `.bedrock_agentcore.yaml`. You can also pass `--arn <runtime-arn>` or set `AGENT_RUNTIME_ARN`.

## Step 2: Ask data questions (answered by the Cortex Agent)

These go to `flight-ops-agent`, which runs Cortex Analyst, executes the SQL inside Snowflake, and returns a complete answer:

```
Which airline had the most delays at LHR in the last 7 days?
What is the average departure delay by airline?
Which gates have the longest average dwell time?
Compare morning vs afternoon traffic volumes.
```

You should get a written answer (often with a table). The agent does not show intermediate SQL - the Cortex Agent handles that server-side.

## Step 3: Test geocoding (Amazon Location Service)

```
What are the coordinates of London Heathrow Airport?
Geocode: Nelson Road, Hounslow, London TW6
```

The agent calls `geocode_address` and returns latitude/longitude plus a label.

## Step 4: One-shot (non-interactive) invoke

```bash
python3 invoke_agentcore.py --prompt "Which airlines have the most flights?"
```

## Debugging

**Agent returns a connectivity / empty-data error**
- Re-run the `tools/list` curl from section 04 step 3. If it fails, the PAT, account format, or grants are the issue - not the agent.

**`Invalid length for parameter modelId`**
- `AGENT_MODEL_ID` was empty at deploy time. Re-run `agentcore launch --env AGENT_MODEL_ID=$AGENT_MODEL_ID`.

**`AccessDenied` on `geo:SearchPlaceIndexForText` or `aws-marketplace:*`**
- Run `./fix_permissions.sh` and wait 30-60s for IAM propagation, then retry.

**500 error / agent exception**
- Check CloudWatch logs for the runtime (Bedrock AgentCore -> your runtime -> Logs), or run `agentcore launch` again after editing `config.yaml`.

**Changes to config.yaml or the agent not taking effect**
- Redeploy: `agentcore launch --env AGENT_MODEL_ID=$AGENT_MODEL_ID` (rebuilds and pushes a new image).

## What you built

A Bedrock AgentCore Runtime agent that routes natural-language questions to a Snowflake Cortex Agent for end-to-end, governed analytics, and to Amazon Location Service for geocoding - all driven by a single `config.yaml`.

---

**Next:** [06 - Extensions](06-extensions.md)
