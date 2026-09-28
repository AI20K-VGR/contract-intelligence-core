'use strict';

// Discover and summarize roadmap documents under each worktree's docs/ folder.
// We do not parse the roadmap structure deeply; we surface active milestones and
// aggregate checkbox progress so the priority scorer can rank against in-flight plans.

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { countCheckboxesInText, toProgress } = require('./checkboxes.cjs');

const ROADMAP_NAME_RE = /(roadmap|milestones?)\.md$/i;
const ACTIVE_TERMS_RE = /\b(in[\s-]?progress|pending|todo|in[\s-]?review|active|planned|next)\b/i;
const DONE_TERMS_RE = /\b(complete|completed|done|shipped|released|launched|✅)\b/i;

function findRoadmapFiles(worktrees, warnings) {
  const found = [];
  for (const worktree of worktrees) {
    if (!worktree.path || !fs.existsSync(worktree.path)) continue;
    const docsDir = path.join(worktree.path, 'docs');
    if (!fs.existsSync(docsDir)) continue;
    let entries;
    try {
      entries = fs.readdirSync(docsDir, { withFileTypes: true });
    } catch (error) {
      warnings.push(`could not read docs directory ${docsDir}: ${error.message}`);
      continue;
    }
    for (const entry of entries) {
      if (!entry.isFile() || !ROADMAP_NAME_RE.test(entry.name)) continue;
      found.push({
        worktree: worktree.path,
        absolutePath: path.join(docsDir, entry.name),
        relativePath: path.join('docs', entry.name),
        branch: worktree.branch || null,
      });
    }
  }
  return found;
}

// Pull section headings (## - ####) that look like active milestones.
// Heuristic: the heading text or the following ~500 chars contains an "active"
// term but not a clear "done" term. Strikethrough or done emojis disqualify.
function extractActiveMilestones(content, limit = 8) {
  const milestones = [];
  const headingRe = /^(#{2,4})\s+(.+)$/gm;
  let match;
  while ((match = headingRe.exec(content)) !== null) {
    const heading = match[2].trim();
    if (/^~~.*~~$/.test(heading)) continue;
    const slice = content.slice(match.index, match.index + 600);
    const headingHasActive = ACTIVE_TERMS_RE.test(heading);
    const sliceHasActive = ACTIVE_TERMS_RE.test(slice);
    const headingDone = DONE_TERMS_RE.test(heading);
    if (headingDone) continue;
    if (!headingHasActive && !sliceHasActive) continue;
    milestones.push({ heading, depth: match[1].length });
    if (milestones.length >= limit) break;
  }
  return milestones;
}

function readRoadmap(file, warnings) {
  let content;
  try {
    content = fs.readFileSync(file.absolutePath, 'utf8');
  } catch (error) {
    warnings.push(`could not read roadmap ${file.absolutePath}: ${error.message}`);
    return null;
  }
  const checkboxes = countCheckboxesInText(content);
  return {
    worktree: file.worktree,
    branch: file.branch,
    path: file.relativePath,
    progress: toProgress(checkboxes.open, checkboxes.closed),
    activeMilestones: extractActiveMilestones(content),
    hash: crypto.createHash('sha1').update(content).digest('hex').slice(0, 12),
  };
}

// Collapse duplicate roadmap reads coming from sibling worktrees that happen to
// hold the same docs/roadmap content. Keys on relativePath + content hash so
// a divergent roadmap on a different branch still shows up as its own entry.
function dedupeRoadmaps(roadmaps) {
  const byKey = new Map();
  for (const roadmap of roadmaps) {
    const key = `${roadmap.path}:${roadmap.hash}`;
    if (!byKey.has(key)) byKey.set(key, roadmap);
  }
  return [...byKey.values()];
}

function scanRoadmaps(worktrees, warnings) {
  const all = findRoadmapFiles(worktrees, warnings)
    .map((file) => readRoadmap(file, warnings))
    .filter(Boolean);
  return dedupeRoadmaps(all);
}

module.exports = { scanRoadmaps, findRoadmapFiles, extractActiveMilestones, readRoadmap };
