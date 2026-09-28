'use strict';

// Scans markdown todo checkboxes inside plan directories.
// Used by watzup-scan to compute per-plan progress without parsing full markdown ASTs.

const fs = require('node:fs');
const path = require('node:path');

const CHECKBOX_OPEN_RE = /^\s*[-*]\s+\[\s\]/gm;
const CHECKBOX_DONE_RE = /^\s*[-*]\s+\[[xX]\]/gm;

function countCheckboxesInText(text) {
  return {
    open: (text.match(CHECKBOX_OPEN_RE) || []).length,
    closed: (text.match(CHECKBOX_DONE_RE) || []).length,
  };
}

function toProgress(open, closed) {
  const total = open + closed;
  if (total === 0) return null;
  return { open, closed, total, complete: closed / total };
}

// List the .md files to scan for a plan: the plan-dir root (legacy flat layout,
// e.g. plan.md + phase-*.md at root) plus phases/*.md (current scaffold layout,
// where phase files live under phases/). `label` is the phase-file name used for
// display + sort; a phases/ file keeps its bare name so both layouts read alike.
function listPlanMarkdown(planDir, warnings) {
  const out = [];
  const pushDir = (dir, sub) => {
    let entries;
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch (error) {
      warnings.push(`could not read plan directory ${dir}: ${error.message}`);
      return;
    }
    for (const entry of entries) {
      if (!entry.isFile() || !entry.name.endsWith('.md')) continue;
      out.push({ path: path.join(dir, entry.name), name: entry.name, sub });
    }
  };
  pushDir(planDir, false);
  const phasesDir = path.join(planDir, 'phases');
  if (fs.existsSync(phasesDir)) pushDir(phasesDir, true);
  return out;
}

// Aggregate checkbox totals across a plan directory, splitting by phase file.
// Covers both the flat layout (phase-*.md at root) and the phases/ subdir.
// Returns null if the directory holds no markdown checkboxes at all.
function scanPlanDirectory(planDir, warnings) {
  if (!planDir || !fs.existsSync(planDir)) return null;

  const totals = { open: 0, closed: 0 };
  const phases = [];

  for (const file of listPlanMarkdown(planDir, warnings)) {
    let content;
    try {
      content = fs.readFileSync(file.path, 'utf8');
    } catch (error) {
      warnings.push(`could not read ${file.path}: ${error.message}`);
      continue;
    }
    const counts = countCheckboxesInText(content);
    totals.open += counts.open;
    totals.closed += counts.closed;
    // A file under phases/ is always a phase file; at root, match the phase- stem.
    const isPhase = file.sub || file.name.toLowerCase().startsWith('phase-');
    if (isPhase && counts.open + counts.closed > 0) {
      phases.push({
        file: file.name,
        open: counts.open,
        closed: counts.closed,
        complete: counts.closed / (counts.open + counts.closed),
      });
    }
  }

  const summary = toProgress(totals.open, totals.closed);
  if (!summary) return null;
  return { ...summary, phases: phases.sort((a, b) => a.file.localeCompare(b.file)) };
}

module.exports = { countCheckboxesInText, scanPlanDirectory, toProgress };
