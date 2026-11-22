import assert from 'node:assert/strict';
import test from 'node:test';
import { words } from './image.mjs';

test('a command splits into words without a shell', () => {
  assert.deepEqual(words('medusa db:migrate && medusa exec x.js'), ['medusa', 'db:migrate', '&&', 'medusa', 'exec', 'x.js']);
});

test('quotes group a word and are removed', () => {
  assert.deepEqual(words(`/bin/sh -c 'A="$B" uv run alembic upgrade head'`), ['/bin/sh', '-c', 'A="$B" uv run alembic upgrade head']);
});

test('an empty or missing command has no words', () => {
  assert.deepEqual(words(''), []);
  assert.deepEqual(words('  \n'), []);
  assert.deepEqual(words(undefined), []);
});
