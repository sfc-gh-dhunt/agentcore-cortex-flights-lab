# 04 - Deploy to AgentCore Runtime

Deploy the agent to **Amazon Bedrock AgentCore Runtime**. The agent connects to the Snowflake MCP server you created in section 03 and to Amazon Location Service for geocoding.

**Where:** the workshop EC2 instance, via AWS Console -> EC2 -> Instances -> select the `*-ec2` instance -> **Connect** -> **Session Manager**.

## Step 1: Get the code onto the instance

```bash
cd ~
git clone <repo-url> agentcore-cortex-flights-lab
cd agentcore-cortex-flights-lab/agentcore
```

## Step 2: Create your config.yaml

```bash
cp config.yaml.example config.yaml
nano config.yaml
```

Fill in your values from the previous sections:

```yaml
snowflake:
  account: <YOUR_SNOWFLAKE_ACCOUNT>   # org-account format, e.g. myorg-myaccount (NOT the account locator)
  user: <your-user>                  # e.g. user1
  pat_token: <your-PAT-token>        # the token from section 03 step 4 (eyJ...)
  database: AIRPORT_LHR
  schema: LAB_<YOUR_ID>
  warehouse: AVIA_LHR_WH

mcp:
  server_name: FLIGHT_OPS_MCP_<YOUR_ID>
  # Expose only the Cortex Agent tool so answers come back end-to-end (question-to-answer):
  tools:
    - flight-ops-agent

aws:
  place_index_name: agentcore-index
```

Save and exit (Ctrl+X, Y, Enter).

> **Common mistake:** using the account locator (e.g. `abc12345`) instead of the org-account format (`<org>-<account>`). PATs only work with the org-account format.

## Step 3: Verify connectivity to Snowflake

```bash
# Base host should return 302 (redirect) - this is normal
curl -s -o /dev/null -w "%{http_code}\n" --max-time 10 \
  "https://<YOUR_SNOWFLAKE_ACCOUNT>.snowflakecomputing.com"

# MCP server should list your tools
curl -s --max-time 15 -X POST \
  "https://<YOUR_SNOWFLAKE_ACCOUNT>.snowflakecomputing.com/api/v2/databases/AIRPORT_LHR/schemas/LAB_<YOUR_ID>/mcp-servers/FLIGHT_OPS_MCP_<YOUR_ID>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer <your-PAT-token>" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

You should see `flight-ops-agent` (and `flight-ops-analyst`) in the response.

- `Programmatic access token is invalid` -> using the locator instead of org-account format, or the PAT expired.
- `Network policy is required` -> a network policy must permit the caller IP (an account-level allow-all policy covers any EC2 IP).
- `does not exist or not authorized` -> re-check the grants from sections 01-03.

## Step 4: Install dependencies

```bash
pip install -r requirements.txt
```

## Step 5: Configure the AgentCore CLI

```bash
agentcore configure
```

Recommended answers:

| Prompt | Answer |
|---|---|
| Entrypoint | `snowflake_mcp_agentcore.py` |
| Agent name | press Enter to accept the default |
| Dependency file | `requirements.txt` (Enter) |
| Deployment type | `1` (Container) |
| Execution role | press Enter (auto-create) |
| ECR Repository | press Enter (auto-create) |
| OAuth authorizer | `no` (use default IAM authorization) |
| Request header allowlist | `no` |
| Memory setup | press Enter (create short-term memory) |
| Long-term memory | `no` |

Verify at any time with `agentcore configure list`.

## Step 6: Deploy

The model id is set during instance startup. Confirm it, then launch:

```bash
echo "AGENT_MODEL_ID=$AGENT_MODEL_ID"
# If empty, set one for your region, e.g.:
# export AGENT_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0

agentcore launch --env AGENT_MODEL_ID=$AGENT_MODEL_ID
```

This builds an ARM64 container with CodeBuild, pushes it to ECR, and creates the runtime endpoint + short-term memory. The first deploy takes ~5-8 minutes.

> **Important:** `AGENT_MODEL_ID` must have a value at deploy time, or the agent fails at invocation with `Invalid length for parameter modelId`.

### Verify in the console
- **Bedrock AgentCore -> Agent Runtime**: your agent shows **Status: READY**.
- **Bedrock AgentCore -> Memory**: a `*_mem` resource shows **Status: ACTIVE**.
- **ECR -> Repositories**: a `bedrock-agentcore-*` repo with a timestamped image.

## Step 7: Fix runtime permissions (run once)

The auto-created execution role lacks two permissions this agent needs:
- `geo:SearchPlaceIndexForText` - Amazon Location geocoding
- `aws-marketplace:ViewSubscriptions` / `Subscribe` - Bedrock checks the Anthropic Claude marketplace subscription on each model call

```bash
./fix_permissions.sh
```

The script auto-detects the runtime role from `.bedrock_agentcore.yaml` and attaches both inline policies. You only need to run it once; permissions persist across redeploys.

> **IAM propagation:** role changes take 10-60s to propagate. If a first invoke hits `AccessDenied` on `geo:` or the marketplace actions, wait 30s and retry.

---

**Next:** [05 - Test End-to-End](05-test-end-to-end.md)
