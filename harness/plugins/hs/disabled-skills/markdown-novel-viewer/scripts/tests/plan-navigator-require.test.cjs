#!/usr/bin/env node

/**
 * Regression guard: plan-navigator must load without MODULE_NOT_FOUND.
 * It require()s the shared plan-table-parser; a missing parser crashes the
 * whole skill on load. This test stays red until the shared lib is present.
 * Run: node scripts/tests/plan-navigator-require.test.cjs
 */

const path = require('path');

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    passed++;
    console.log(`  ✓ ${name}`);
  } catch (err) {
    failed++;
    console.log(`  ✗ ${name}`);
    console.log(`    Error: ${err.message}`);
  }
}

function assertTrue(value, message) {
  if (!value) throw new Error(message);
}

function assertEqual(actual, expected, message) {
  if (actual !== expected) {
    throw new Error(`${message}: expected "${expected}", got "${actual}"`);
  }
}

// 1. Load the consumer — transitively require()s the shared parser. Red if missing.
test('plan-navigator.cjs loads without throwing', () => {
  require('../lib/plan-navigator.cjs');
});

// 2. The shared parser exports the three symbols plan-navigator destructures.
const parser = require('../../../_shared/lib/plan-table-parser.cjs');
test('parser exports parsePlanPhases as a function', () => {
  assertTrue(typeof parser.parsePlanPhases === 'function', 'parsePlanPhases not a function');
});
test('parser exports normalizeStatus + filenameToTitle as functions', () => {
  assertTrue(typeof parser.normalizeStatus === 'function', 'normalizeStatus not a function');
  assertTrue(typeof parser.filenameToTitle === 'function', 'filenameToTitle not a function');
});

// 3. Behavioral: a minimal header-aware phase table parses into the expected rows.
test('parsePlanPhases parses a minimal phase table', () => {
  const md = [
    '| Phase | Name | Status |',
    '|---|---|---|',
    '| 1 | Setup | Done |',
    '| 2 | Build | WIP |',
  ].join('\n');
  const phases = parser.parsePlanPhases(md, path.resolve('.'));
  assertEqual(phases.length, 2, 'phase count');
  assertEqual(phases[0].phaseId, '1', 'phase 1 id');
  assertEqual(phases[0].status, 'completed', 'phase 1 status');
  assertEqual(phases[1].status, 'in-progress', 'phase 2 status');
});

console.log('\n--- Test Results ---');
console.log(`Passed: ${passed}`);
console.log(`Failed: ${failed}`);
console.log(`Total: ${passed + failed}`);

if (failed > 0) {
  process.exit(1);
}
console.log('\nAll tests passed!');
