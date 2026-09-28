---
name: hs:deep-swe
description: Benchmark a coding model on DeepSWE through Pier and OpenRouter. Use when users ask to run DeepSWE, score a model, or verify coding-agent benchmark results.
user-invocable: true
when_to_use: Invoke for a costed external coding-agent evaluation, not repository-local optimization.
category: dev-tools
keywords: [benchmark, deepswe, pier, openrouter, evaluation]
argument-hint: "<OpenRouter model slug>"
injectable: false
allowed-tools: [Bash, Read]
metadata:
  compliance-tier: workflow
---

# DeepSWE Benchmark

Runs an independent coding-agent evaluation on the DeepSWE benchmark via Pier: handles benchmark setup and reporting. Does not evaluate a repository metric or authorize model spend without the user's confirmation.

## Guardrails

- First confirm uv, git, Docker, and the Docker daemon are available.
- Confirm OPENROUTER_API_KEY is set without printing its value; if absent, stop and ask the user to configure it.
- Never echo, persist, commit, or place the key in a command, report, prompt,
  or benchmark artifact.
- Run one task before a subset. Get explicit user confirmation before a full 113-task corpus run — it consumes time and model tokens.

## Setup

    git clone https://github.com/datacurve-ai/deep-swe
    uv tool install datacurve-pier
    pier --help
    pier run --help

Run the commands below from the directory containing the cloned deep-swe folder. If you change into deep-swe instead, use tasks or tasks/<task-id> as the -p value.

DeepSWE currently documents 113 tasks, Pier as runner. Confirm current flags/task paths via help before running — this toolchain changes:
https://github.com/datacurve-ai/deep-swe
https://pypi.org/project/datacurve-pier/
https://deepswe.datacurve.ai/

## Run Safely

1. Verify the exact OpenRouter model slug at openrouter.ai/models.
2. Run a single task first. The current native model form is:

       pier run -p deep-swe/tasks/<task-id> --agent mini-swe-agent \
         --model openrouter/<vendor/model>

3. For a deterministic subset, use installed help to confirm task-count and sample-seed flags, then run a small fixed sample:

       pier run -p deep-swe/tasks --agent mini-swe-agent \
         --model openrouter/<vendor/model> --n-tasks 10 --sample-seed 0
4. Use a separate model-class route only when installed Pier help explicitly documents it; do not guess a version-specific flag.
5. Before a full corpus run, present the exact command, expected cost exposure,
   and stop condition. Continue only after explicit confirmation.

## Inspect and Report

Inspect the generated job directory with current Pier commands. When the installed version provides them, use pier view, pier analyze, and pier critique to inspect the result. Report the exact command, Pier version, task count, model slug, score/reward, cost when available, and blockers. Do not submit results
or contact a leaderboard without the user's request.

## Failure Handling

- For authentication failures, stop and have the user correct their environment.
- For provider or model mapping failures, verify the slug, consult current Pier help before changing the command.
- For unknown flags, do not retry a guessed syntax; inspect help first.
- Use hs:loop for iterative optimization of a metric in the user’s own
  repository rather than an external model benchmark.
