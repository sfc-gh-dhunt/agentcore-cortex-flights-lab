# 04 - Deploy to AgentCore Runtime

Deploy the agent to **Amazon Bedrock AgentCore Runtime**. It connects to the Snowflake MCP server from section 03 and to Amazon Location Service for geocoding.

**Where:** the workshop EC2 instance. In the AWS Console go to **EC2** -> **Instances** -> select the `*-ec2` instance -> **Connect** -> **Session Manager** tab -> **Connect**.

> Important environment notes (read first):
> - **Stay as the default `ssm-user`.** Do not `sudo su` to another user - the deploy writes local files, and switching users causes `Permission denied` on files owned by `ssm-user`.
> - **Do not override `HOME`.** The instance ships with pre-configured AWS credentials (a default profile that has deploy permissions). If you change `HOME`, the CLI falls back to the EC2 instance role, which cannot create ECR/runtime resources.
> - The instance has **no `git`** - we download a release tarball with `curl` instead.

## Step 1: Download the lab (no git required)

```sh
export HOME=/home/ssm-user
cd ~
REPO_TGZ="https://github.com/sfc-gh-dhunt/agentcore-cortex-flights-lab/archive/refs/heads/main.tar.gz"
curl -fsSL "$REPO_TGZ" -o lab.tgz
TOP=$(tar tzf lab.tgz | head -1)        # agentcore-cortex-flights-lab-main/
tar xzf lab.tgz
cd "${TOP}agentcore"
pwd && ls
```

## Step 2: Configure your Snowflake connection

```sh
cp config.yaml.example config.yaml
nano config.yaml
```

Fill in your values from sections 01-03:

```yaml
snowflake:
  account: <YOUR_SNOWFLAKE_ACCOUNT>     # org-account format, e.g. myorg-myaccount (NOT the locator). Underscores are auto-converted to hyphens.
  user: <your-user>                     # e.g. user1
  pat_token: <your-PAT-token>           # from section 03 (eyJ...)
  database: AIRPORT_LHR
  schema: LAB_<YOUR_ID>
  warehouse: AVIA_LHR_WH
mcp:
  server_name: FLIGHT_OPS_MCP_<YOUR_ID>
  tools:
    - flight-ops-agent                  # expose only the Cortex Agent -> question-to-answer
aws:
  place_index_name: agentcore-index
```

## Step 3: Verify connectivity to Snowflake

```sh
PAT=$(grep 'pat_token:' config.yaml | awk '{print $2}')
ACCT=$(grep 'account:' config.yaml | awk '{print $2}' | tr '_' '-')   # hyphens for the URL host
curl -s --max-time 15 -X POST \
  "https://${ACCT}.snowflakecomputing.com/api/v2/databases/AIRPORT_LHR/schemas/LAB_<YOUR_ID>/mcp-servers/FLIGHT_OPS_MCP_<YOUR_ID>" \
  -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
  -H "Authorization: Bearer ${PAT}" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | head -c 400; echo
```

You should see `flight-ops-agent` in the response. If you get a TLS/hostname error, your account has underscores - the agent code converts them to hyphens automatically, but this manual `curl` needs the hyphen form (the `tr` above handles it).

## Step 4: Set the model id

```sh
echo "AGENT_MODEL_ID=$AGENT_MODEL_ID"
# If empty, set it (US regions):
export AGENT_MODEL_ID=us.anthropic.claude-sonnet-4-6
```

## Step 5: Configure AgentCore (non-interactive)

```sh
agentcore configure -e snowflake_mcp_agentcore.py -rf requirements.txt -r us-east-1 -ni
```

This auto-creates the execution role + ECR repo, sets up short-term memory, and writes `.bedrock_agentcore.yaml`. (No local Docker needed - the build runs in CodeBuild.)

## Step 6: Launch

```sh
agentcore launch --env AGENT_MODEL_ID=$AGENT_MODEL_ID
```

First deploy builds an ARM64 image in CodeBuild and creates the runtime (a couple of minutes). Success ends with `Deployment completed successfully` and an **Agent ARN**.

> A `Transaction Search configuration failed ... logs:PutResourcePolicy` warning is **harmless** (optional observability) - the agent deploys and runs fine.

## Step 7: Fix runtime permissions (run once)

The auto-created runtime role needs two extra permissions: `geo:SearchPlaceIndexForText` (geocoding) and `aws-marketplace:ViewSubscriptions`/`Subscribe` (Bedrock checks the Claude marketplace subscription per call).

```sh
sh fix_permissions.sh
```

It auto-detects the **Runtime** execution role from `.bedrock_agentcore.yaml`. Allow 10-60s for IAM propagation before invoking.

### Verify in the console (optional)
- **Bedrock AgentCore -> Agent Runtime**: your agent shows **READY**.
- **ECR -> Repositories**: a `bedrock-agentcore-*` repo with an image.

---

**Next:** [05 - Test End-to-End](05-test-end-to-end.md)
