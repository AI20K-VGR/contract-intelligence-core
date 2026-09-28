'use strict';

// Composite scoring + ranked next-step generation for watzup-scan.
//
// Score components per plan (higher = more urgent):
//   status:           in-progress > in-review > pending > others
//   workspace align:  plan in current worktree (+), on current branch (+)
//   provenance:       filesystem source > local ref > remote ref
//   momentum:         plans 40-90% complete get a bump (close to done, keep going)
//                     plans < 10% complete get a small starter bump
//
// Next-step output replaces the old flat string list. Each step is an object
// with action + rationale + priority bucket so the renderer can show *why*.

const path = require('node:path');

const STATUS_WEIGHT = {
  'in-progress': 400,
  'in-review': 300,
  pending: 150,
  completed: 0,
  cancelled: -200,
};

function getStatusBonus(status) {
  if (Object.prototype.hasOwnProperty.call(STATUS_WEIGHT, status)) return STATUS_WEIGHT[status];
  return 100;
}

function samePath(a, b) {
  if (!a || !b) return false;
  try {
    return path.resolve(a) === path.resolve(b);
  } catch {
    return false;
  }
}

function scorePlan(plan, current) {
  let score = 0;
  const reasons = [];

  const statusBonus = getStatusBonus(plan.status);
  score += statusBonus;
  if (statusBonus > 0) reasons.push(`status:${plan.status}`);

  const sources = plan.sources || (plan.source ? [plan.source] : []);
  let alignedWorktree = false;
  let alignedBranch = false;
  let fromFilesystem = false;
  let fromLocalRef = false;
  for (const source of sources) {
    if (source.worktree && samePath(source.worktree, current.root)) alignedWorktree = true;
    if (current.branch && (source.branch === current.branch || source.ref === current.branch)) alignedBranch = true;
    if (source.type === 'filesystem') fromFilesystem = true;
    if (source.refType === 'local') fromLocalRef = true;
  }
  if (alignedWorktree) { score += 600; reasons.push('current-worktree'); }
  if (alignedBranch) { score += 400; reasons.push('current-branch'); }
  if (fromFilesystem) score += 80;
  if (fromLocalRef) score += 40;

  if (plan.progress && plan.progress.total > 0) {
    const ratio = plan.progress.complete;
    if (ratio >= 0.4 && ratio <= 0.9) {
      const bump = Math.round(220 * ratio);
      score += bump;
      reasons.push(`momentum:${Math.round(ratio * 100)}%`);
    } else if (ratio < 0.1 && plan.progress.open > 0) {
      score += 60;
      reasons.push('just-started');
    }
  }

  return { score, reasons };
}

function findNextOpenPhase(plan) {
  if (!plan.progress || !Array.isArray(plan.progress.phases)) return null;
  return plan.progress.phases.find((phase) => phase.open > 0) || null;
}

function planProgressLabel(plan) {
  if (!plan.progress) return 'no checkbox data';
  const { closed, total, complete } = plan.progress;
  return `${closed}/${total} todos · ${Math.round(complete * 100)}% done`;
}

function buildRankedNextSteps(payload, limit = 6) {
  const steps = [];

  if (payload.current.dirty) {
    steps.push({
      priority: 'hygiene',
      action: 'Commit or stash current worktree changes before context switch.',
      rationale: `${payload.current.statusLines.length} dirty path(s) on ${payload.current.branch || 'detached HEAD'}.`,
    });
  }
  if (payload.current.detached) {
    steps.push({
      priority: 'hygiene',
      action: 'Create or switch to a named branch — current HEAD is detached.',
      rationale: `HEAD at ${payload.current.head}.`,
    });
  }

  const scored = payload.plans.unfinished
    .map((plan) => ({ plan, ...scorePlan(plan, payload.current) }))
    .sort((a, b) => b.score - a.score || a.plan.title.localeCompare(b.plan.title));

  for (const entry of scored) {
    if (steps.length >= limit) break;
    const { plan, score, reasons } = entry;
    const nextPhase = findNextOpenPhase(plan);
    const phaseLabel = nextPhase
      ? ` → next: ${nextPhase.file} (${nextPhase.closed}/${nextPhase.open + nextPhase.closed})`
      : '';
    steps.push({
      priority: 'plan',
      planId: plan.id,
      action: `Resume "${plan.title}"${phaseLabel}.`,
      rationale: `score=${score} [${reasons.join(', ') || 'no-signal'}]; ${plan.status}, ${planProgressLabel(plan)}.`,
    });
  }

  for (const roadmap of payload.roadmaps || []) {
    if (steps.length >= limit) break;
    if (!roadmap.activeMilestones || roadmap.activeMilestones.length === 0) continue;
    const top = roadmap.activeMilestones[0];
    const pct = roadmap.progress ? `, ${Math.round(roadmap.progress.complete * 100)}% done overall` : '';
    steps.push({
      priority: 'roadmap',
      action: `Advance roadmap milestone: "${top.heading}".`,
      rationale: `From ${roadmap.path}${pct}.`,
    });
  }

  if (steps.length === 0) {
    steps.push({
      priority: 'fallback',
      action: 'No in-flight work found; start from the highest-priority user request.',
      rationale: 'No dirty changes, unfinished plans, or active roadmap milestones detected.',
    });
  }

  return steps.slice(0, limit);
}

module.exports = { scorePlan, buildRankedNextSteps, findNextOpenPhase, planProgressLabel };
