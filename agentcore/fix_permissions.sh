#!/usr/bin/env sh
#
# Extend the AgentCore Runtime execution role with the two extra permissions
# this agent needs at invocation time:
#   * geo:SearchPlaceIndexForText          (Amazon Location geocoding tool)
#   * aws-marketplace:ViewSubscriptions    (Bedrock checks the Anthropic Claude
#   * aws-marketplace:Subscribe             marketplace subscription on each call)
#
# Run once after the first `agentcore launch`. Permissions persist across redeploys.
# IAM changes can take 10-60s to propagate.
#
# Role resolution order:
#   1. first argument        ./fix_permissions.sh <ROLE_NAME>
#   2. $AGENTCORE_ROLE env var
#   3. the *Runtime* role in .bedrock_agentcore.yaml (NOT the CodeBuild role)
set -eu

ROLE_NAME="${1:-${AGENTCORE_ROLE:-}}"

if [ -z "${ROLE_NAME}" ] && [ -f .bedrock_agentcore.yaml ]; then
  # Prefer the runtime execution role; fall back to the first IAM role found.
  ROLE_ARN="$(grep -Eo 'arn:aws:iam::[0-9]+:role/[A-Za-z0-9_+=,.@/-]+' .bedrock_agentcore.yaml | grep -i runtime | head -n1 || true)"
  if [ -z "${ROLE_ARN}" ]; then
    ROLE_ARN="$(grep -Eo 'arn:aws:iam::[0-9]+:role/[A-Za-z0-9_+=,.@/-]+' .bedrock_agentcore.yaml | head -n1 || true)"
  fi
  ROLE_NAME="${ROLE_ARN##*/}"
fi

if [ -z "${ROLE_NAME}" ]; then
  echo "ERROR: could not determine the runtime execution role." >&2
  echo "Pass it explicitly:  sh fix_permissions.sh <ROLE_NAME>" >&2
  echo "(Find it in the AgentCore console under your runtime, or in .bedrock_agentcore.yaml.)" >&2
  exit 1
fi

echo "Attaching inline policies to role: ${ROLE_NAME}"

aws iam put-role-policy \
  --role-name "${ROLE_NAME}" \
  --policy-name LocationServiceAccess \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {"Effect": "Allow", "Action": "geo:SearchPlaceIndexForText", "Resource": "*"}
    ]
  }'

aws iam put-role-policy \
  --role-name "${ROLE_NAME}" \
  --policy-name BedrockMarketplaceAccess \
  --policy-document '{
    "Version": "2012-10-17",
    "Statement": [
      {"Effect": "Allow", "Action": ["aws-marketplace:ViewSubscriptions", "aws-marketplace:Subscribe"], "Resource": "*"}
    ]
  }'

echo "Done. Inline policies LocationServiceAccess and BedrockMarketplaceAccess attached to ${ROLE_NAME}."
echo "Allow 10-60s for IAM propagation before invoking the agent."
