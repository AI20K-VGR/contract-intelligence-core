#!/usr/bin/env bash
# Open or close port 22 of an AWS security group for the GitHub runner that
# runs this script (.github/workflows/deploy.yml). Each rule carries the
# description "github-actions run <run id>", so `close` removes exactly what
# `open` added, and `open` first removes rules that a run left behind when it
# died before closing.
#
#   deploy/ssh_window.sh open  <security-group-id>
#   deploy/ssh_window.sh close <security-group-id>
#
# Needs the AWS CLI (preinstalled on GitHub-hosted runners) with credentials
# and region in the environment.
set -euo pipefail

action=${1:?usage: ssh_window.sh open|close <security-group-id>}
sg=${2:?usage: ssh_window.sh open|close <security-group-id>}
tag="github-actions run ${GITHUB_RUN_ID:?GITHUB_RUN_ID is not set}"

# Rule ids of inbound port-22 rules whose description is $1, or that any run
# opened when $1 is empty.
rules() {
  aws ec2 describe-security-group-rules --filters "Name=group-id,Values=$sg" \
    --query 'SecurityGroupRules[?IsEgress==`false` && FromPort==`22`].[SecurityGroupRuleId,Description]' \
    --output text |
    awk -F'\t' -v want="$1" '($2 == want) || (want == "" && $2 ~ /^github-actions run /) { print $1 }'
}

revoke() {
  [ $# -eq 0 ] && return 0
  aws ec2 revoke-security-group-ingress --group-id "$sg" --security-group-rule-ids "$@" >/dev/null
}

case "$action" in
  open)
    stale=$(rules "")
    if [ -n "$stale" ]; then
      echo "removing SSH rules left by earlier runs: $(echo $stale)"
      # shellcheck disable=SC2086
      revoke $stale
    fi
    ip=$(curl -fsS --max-time 10 https://checkip.amazonaws.com | tr -d '[:space:]')
    if [[ ! $ip =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]]; then
      echo "::error::cannot read this runner's public IPv4 (got '$ip')" >&2
      exit 1
    fi
    aws ec2 authorize-security-group-ingress --group-id "$sg" --ip-permissions \
      "[{\"IpProtocol\":\"tcp\",\"FromPort\":22,\"ToPort\":22,\"IpRanges\":[{\"CidrIp\":\"$ip/32\",\"Description\":\"$tag\"}]}]" \
      >/dev/null
    echo "port 22 on $sg open to $ip/32 ($tag)"
    ;;
  close)
    ids=$(rules "$tag")
    # shellcheck disable=SC2086
    revoke $ids
    echo "port 22 on $sg closed again ($(echo ${ids:-no rule left by this run}))"
    ;;
  *)
    echo "usage: ssh_window.sh open|close <security-group-id>" >&2
    exit 2
    ;;
esac
