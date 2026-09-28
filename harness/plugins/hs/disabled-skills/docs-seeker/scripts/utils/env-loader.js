#!/usr/bin/env node

/**
 * Environment variable loader for docs-seeker skill
 * Respects order: process.env > skill/.env > <repo-root>/.env
 */

const fs = require('fs');
const path = require('path');

/**
 * Parse .env file content into key-value pairs
 * @param {string} content - .env file content
 * @returns {Object} Parsed environment variables
 */
function parseEnvFile(content) {
  const env = {};
  const lines = content.split('\n');

  for (const line of lines) {
    // Skip comments and empty lines
    if (!line || line.trim().startsWith('#')) continue;

    const match = line.match(/^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/);
    if (match) {
      const key = match[1];
      let value = match[2].trim();

      // Remove quotes if present
      if ((value.startsWith('"') && value.endsWith('"')) ||
          (value.startsWith("'") && value.endsWith("'"))) {
        value = value.slice(1, -1);
      }

      env[key] = value;
    }
  }

  return env;
}

/**
 * Walk upward from `start` until a directory containing .git is found.
 * Mirrors repomix_batch.py's _find_repo_root — robust to install depth, where a
 * hardcoded `../` count silently resolves to the wrong dir once the skill ships as
 * a plugin. Returns null if no repo root is found.
 * @param {string} start - directory to start from
 * @returns {string|null} repo root path, or null
 */
function findRepoRoot(start) {
  let current = path.resolve(start);
  for (let i = 0; i < 20; i++) {  // guard against weird mounts / no .git
    if (fs.existsSync(path.join(current, '.git'))) return current;
    const parent = path.dirname(current);
    if (parent === current) break;
    current = parent;
  }
  return null;
}

/**
 * Load environment variables from .env files in priority order
 * Priority: process.env > skill/.env > <repo-root>/.env
 * @returns {Object} Merged environment variables
 */
function loadEnv() {
  const skillDir = path.resolve(__dirname, '../..');
  const repoRoot = findRepoRoot(__dirname);

  const envPaths = [];
  if (repoRoot) envPaths.push(path.join(repoRoot, '.env'));  // Lowest priority
  envPaths.push(path.join(skillDir, '.env'));                // Highest priority (file)

  let mergedEnv = {};

  // Load .env files in order (lowest to highest priority)
  for (const envPath of envPaths) {
    if (fs.existsSync(envPath)) {
      try {
        const content = fs.readFileSync(envPath, 'utf8');
        const parsed = parseEnvFile(content);
        mergedEnv = { ...mergedEnv, ...parsed };
      } catch (error) {
        // Silently skip unreadable files
      }
    }
  }

  // process.env has highest priority
  mergedEnv = { ...mergedEnv, ...process.env };

  return mergedEnv;
}

/**
 * Get environment variable with fallback
 * @param {string} key - Environment variable key
 * @param {string} defaultValue - Default value if not found
 * @returns {string} Environment variable value
 */
function getEnv(key, defaultValue = '') {
  const env = loadEnv();
  return env[key] || defaultValue;
}

module.exports = {
  loadEnv,
  getEnv,
  parseEnvFile,
};
