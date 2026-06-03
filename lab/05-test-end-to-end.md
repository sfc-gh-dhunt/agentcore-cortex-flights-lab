# 05 - Test End-to-End

Invoke the deployed agent and watch the full flow: your prompt -> Bedrock agent (router) -> Snowflake Cortex Agent (runs Analyst + executes SQL) -> answer. Address prompts call Amazon Location Service.

**Where:** the EC2 instance (Session Manager), from the `agentcore` directory you deployed from (where `.bedrock_agentcore.yaml` lives).

## Option A: `agentcore invoke` (simplest)

```sh
# Data question -> answered end-to-end by the Cortex Agent
agentcore invoke '{"prompt": "Which airline had the most delays at LHR in the last 7 days?"}'

# Geocoding -> Amazon Location Service
agentcore invoke '{"prompt": "What are the coordinates of London Heathrow Airport?"}'
```

The data question returns a written answer (often a table) sourced from Snowflake - no SQL is shown, because the Cortex Agent runs and executes it server-side. The geocode prompt returns latitude/longitude plus a label.

More example prompts:

```
What is the average departure delay by airline?
Which gates have the longest average dwell time?
Compare morning vs afternoon traffic volumes.
```

## Option B: interactive client

```sh
python3 invoke_agentcore.py
# or one-shot:
python3 invoke_agentcore.py --prompt "Which airlines have the most flights?"
```

It reads the runtime ARN from `.bedrock_agentcore.yaml` (or pass `--arn`).

## Debugging

**`AccessDenied` on `aws-marketplace:*` or `geo:*`**
- Run `sh fix_permissions.sh` and wait 30-60s for IAM propagation, then retry.

**SSL / hostname error talking to Snowflake**
- The account identifier has underscores. The agent converts them to hyphens automatically; if you changed the code, ensure the URL host uses hyphens.

**`Invalid length for parameter modelId`**
- `AGENT_MODEL_ID` was empty at deploy time. Re-run `agentcore launch --env AGENT_MODEL_ID=$AGENT_MODEL_ID`.

**Connectivity / empty data**
- Re-run the `tools/list` curl from section 04 step 3. If that fails, the PAT, account format, or grants are the issue - not the agent.

**`Permission denied` writing `.bedrock_agentcore.yaml`**
- You switched Linux users or changed `HOME`. Work as `ssm-user` from a directory you own (your home), and don't override `HOME`.

**Changes not taking effect**
- Edit `config.yaml`, then redeploy: `agentcore launch --env AGENT_MODEL_ID=$AGENT_MODEL_ID` (rebuilds the image).

**Tail runtime logs**
```sh
aws logs tail /aws/bedrock-agentcore/runtimes/<agent-id>-DEFAULT --since 15m
```

## What you built

A Bedrock AgentCore Runtime agent that routes natural-language questions to a Snowflake Cortex Agent for end-to-end, governed analytics, and to Amazon Location Service for geocoding - all driven by a single `config.yaml`.

---

**Next:** [06 - Extensions](06-extensions.md)
