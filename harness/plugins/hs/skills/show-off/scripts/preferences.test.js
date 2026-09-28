import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';

import {
  loadPreferences,
  parseSetArgs,
  resetPreferences,
  savePreferences,
} from './preferences.js';

async function withTempPrefs(fn) {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), 'show-off-prefs-'));
  const prefsPath = path.join(dir, 'preferences.json');
  try {
    await fn({ SHOW_OFF_PREFS_PATH: prefsPath }, prefsPath);
  } finally {
    await fs.rm(dir, { recursive: true, force: true });
  }
}

test('loadPreferences returns default enabled workflow preferences', async () => {
  await withTempPrefs(async (env) => {
    const loaded = await loadPreferences({ env });

    assert.equal(loaded.exists, false);
    assert.equal(loaded.preferences.screenshots, true);
    assert.equal(loaded.preferences.publishing, true);
    assert.deepEqual(loaded.preferences.languages, ['vi', 'en']);
  });
});

test('savePreferences persists opt-out choices', async () => {
  await withTempPrefs(async (env, prefsPath) => {
    await savePreferences(
      { screenshots: false, publishing: false, languages: ['en'] },
      { env },
    );

    const stored = JSON.parse(await fs.readFile(prefsPath, 'utf8'));
    const loaded = await loadPreferences({ env });

    assert.equal(stored.screenshots, false);
    assert.equal(stored.publishing, false);
    assert.deepEqual(loaded.preferences.languages, ['en']);
  });
});

test('parseSetArgs supports user-facing aliases', () => {
  const updates = parseSetArgs([
    '--no-screenshots',
    '--no-publish',
    '--languages',
    'en',
  ]);

  assert.deepEqual(updates, {
    screenshots: false,
    publishing: false,
    languages: ['en'],
  });
});

test('resetPreferences removes persisted preferences', async () => {
  await withTempPrefs(async (env, prefsPath) => {
    await savePreferences({ screenshots: false, publishing: true, languages: ['vi'] }, { env });
    await resetPreferences({ env });

    await assert.rejects(fs.stat(prefsPath), { code: 'ENOENT' });
    const loaded = await loadPreferences({ env });
    assert.equal(loaded.preferences.screenshots, true);
    assert.deepEqual(loaded.preferences.languages, ['vi', 'en']);
  });
});

test('parseSetArgs rejects unsupported languages', () => {
  assert.throws(
    () => parseSetArgs(['--languages', 'en,fr']),
    /Unsupported language/,
  );
});
