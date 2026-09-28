# ralph-sandbox-harness — the Ralph sandbox image with the harness guardrail's
# runtime dependency baked in.
#
# Derived (not forked) from the upstream Ralph sandbox. The harness rides into
# the container on the workspace bind-mount (harness/ + .claude/settings.json),
# so nothing harness-specific is baked here except three things the mount
# cannot carry: the Python interpreter, ruamel.yaml (+ its C accelerator) —
# the YAML reader the compliance hooks actually read through now (yaml_io.py,
# not PyYAML) — and PyYAML itself, kept only because harness/tests exercises
# the real thing for parity and the orchestrator/release tooling this image
# also runs still imports it directly (hooks do not). Also baked: the
# HARNESS_ROOT env the hooks resolve against.
#
# Floating base tag is deliberate (no pin): the sandbox follows upstream so
# security updates land automatically. Compatibility is assured at runtime by
# the gate-live probe each run, not by a frozen version string — if an upstream
# update ever broke the in-loop gate, the probe surfaces it and the launch
# falls back rather than running a bare bypass. Break-glass: pin a digest via
# RALPH_IMAGE=...@sha256:... at launch.
FROM docker.io/daonhan/ralph-sandbox:latest

USER root

# python3-yaml / python3-pytest via apt (not pip) — Debian's externally-managed
# environment (PEP 668) rejects a global pip install, and apt is the right home for a
# dependency the gate treats as load-bearing. python3-yaml stays even though harness
# source no longer imports PyYAML: harness/tests still exercises the real thing for
# parity, and the orchestrator/release tooling this image also runs imports it directly.
#
# ruamel.yaml is NOT in this line — it comes from pip in the next stanza, because the
# apt package is too old. The reason is measured and is spelled out there.
# ⚠ Either line REQUIRES A REBUILD to take effect; editing this file does not update an
# already-built image.
RUN apt-get update \
    && apt-get install -y python3 python3-yaml python3-pytest python3-pip \
    && rm -rf /var/lib/apt/lists/*

# ruamel.yaml comes from pip, NOT apt, and --break-system-packages is deliberate here.
# Measured, not assumed: Debian ships python3-ruamel.yaml 0.17.21, which is BELOW the
# >=0.18 floor harness/requirements.txt declares, and the difference is not cosmetic --
# 0.17.21 parses `2026-01-01T10:00:00Z` to a NAIVE datetime, silently dropping the
# timezone, where 0.19.1 and PyYAML both keep it. Comparing a naive datetime against an
# aware one raises TypeError, so the same config file would mean two different things
# inside and outside this image -- exactly the split the one-reader ruling exists to
# prevent. (No harness config carries a timestamp scalar today; this closes the hole
# before one does.) PEP 668's externally-managed guard protects a USER's system Python
# from being broken by a global install; this is a disposable, single-purpose image
# built from a pinned base, which is the case the escape hatch is for.
RUN pip3 install --no-cache-dir --break-system-packages \
        'ruamel.yaml>=0.18,<1' 'ruamel.yaml.clib>=0.2,<1'

# Hooks are registered as `python3 $HARNESS_ROOT/harness/hooks/*.py`. Ralph
# bind-mounts the workspace at /home/agent/workspace and runs claude there with
# a fixed argv (no --settings), so baking the env is how the hooks resolve
# without touching that argv.
ENV HARNESS_ROOT=/home/agent/workspace

USER agent
