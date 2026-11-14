import assert from 'node:assert/strict';
import fs from 'node:fs';
import {spawnSync} from 'node:child_process';
import test from 'node:test';

const workflow = fs.readFileSync(new URL('../workflows/ci.yml', import.meta.url), 'utf8');

test('the Rust job always validates registration before direct Nx affected execution', () => {
  const section = workflow.split('\n  rust:\n')[1]?.split(/\n  [A-Za-z]/)[0];
  assert.ok(section, 'Rust CI job is required');
  assert.doesNotMatch(section, /^    if:/m, 'Zero affected crates still need the unconditional guard and fixture suite');
  assert.match(section, /npx nx run f0rge-rust-checks:test/);
  const guard = section.indexOf('node .github/rust/guard.mjs');
  const affected = section.indexOf('npx nx affected');
  assert.ok(guard > 0 && affected > guard, 'Cargo discovery must precede affected selection');
  assert.match(section, /-t=lint,format-check,test,build --exclude='\*,!tag:platform:rust'/);
  assert.match(workflow, /needs: \[python, frontend, rust\]/);
});

test('the actual aggregate shell requires successful Python, frontend and Rust results', () => {
  const section = workflow.split('      - name: Aggregate gate\n')[1];
  assert.ok(section);
  const source = section.match(/        run: \|\n((?:          .*\n?)+)/)?.[1];
  assert.ok(source, 'Aggregate shell block must be inspectable');
  const script = source.split('\n').map(line => line.slice(10)).join('\n');
  for (const job of ['PYTHON_RESULT', 'FRONTEND_RESULT', 'RUST_RESULT']) {
    for (const status of ['success', 'failure', 'skipped', 'cancelled', '']) {
      const result = spawnSync('bash', ['-c', script], {env: {...process.env, PYTHON_RESULT: 'success', FRONTEND_RESULT: 'success', RUST_RESULT: 'success', [job]: status}, encoding: 'utf8'});
      assert.equal(result.status === 0, status === 'success', `${job}=${status}: ${result.stdout}${result.stderr}`);
    }
  }
});
