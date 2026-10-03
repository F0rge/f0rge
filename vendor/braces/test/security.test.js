'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const braces = require('../index');

const patternAtDepth = depth => `${'{'.repeat(depth)}x${'}'.repeat(depth)}`;

test('bounds recursive parsing before deeply nested patterns exhaust the stack', () => {
  const hostilePattern = patternAtDepth(3500);

  assert.throws(
    () => braces(hostilePattern),
    error => error instanceof SyntaxError && error.code === 'ERR_BRACES_MAX_DEPTH',
  );
});

test('allows the documented safe boundary and rejects one level beyond it', () => {
  assert.doesNotThrow(() => braces(patternAtDepth(100)));
  assert.doesNotThrow(() => braces('('.repeat(100) + 'x' + ')'.repeat(100)));
  assert.throws(
    () => braces(patternAtDepth(101)),
    error => error instanceof SyntaxError && error.code === 'ERR_BRACES_MAX_DEPTH',
  );
  assert.throws(
    () => braces('('.repeat(101) + 'x' + ')'.repeat(101)),
    error => error instanceof SyntaxError && error.code === 'ERR_BRACES_MAX_DEPTH',
  );
});

test('allows callers to lower maxDepth but never raise the hard ceiling', () => {
  assert.doesNotThrow(() => braces(patternAtDepth(2), { maxDepth: 2 }));
  assert.throws(
    () => braces(patternAtDepth(3), { maxDepth: 2 }),
    error => error instanceof SyntaxError && error.code === 'ERR_BRACES_MAX_DEPTH',
  );

  for (const maxDepth of [Infinity, Number.NaN, Number.POSITIVE_INFINITY]) {
    assert.throws(
      () => braces(patternAtDepth(101), { maxDepth }),
      error => error instanceof SyntaxError && error.code === 'ERR_BRACES_MAX_DEPTH',
    );
  }
});

const nestedAst = depth => {
  const root = { type: 'root', nodes: [] };
  let parent = root;

  for (let index = 0; index < depth; index++) {
    const child = { type: 'paren', nodes: [], parent };
    parent.nodes.push(child);
    parent = child;
  }

  parent.nodes.push({ type: 'text', value: 'x', parent });
  return root;
};

test('bounds directly supplied ASTs in compile, expand, and stringify', () => {
  const hostileAst = nestedAst(101);

  for (const operation of [braces.compile, braces.expand, braces.stringify]) {
    assert.throws(
      () => operation(hostileAst),
      error => error instanceof SyntaxError && error.code === 'ERR_BRACES_MAX_DEPTH',
    );
    assert.throws(
      () => operation(hostileAst, { maxDepth: Infinity }),
      error => error instanceof SyntaxError && error.code === 'ERR_BRACES_MAX_DEPTH',
    );
  }

  for (const operation of [braces.compile, braces.expand, braces.stringify]) {
    assert.doesNotThrow(() => operation(nestedAst(100)));
  }
});

test('checks the longest path when direct AST nodes are shared across branches', () => {
  const chain = Array.from({ length: 101 }, () => ({ type: 'paren', nodes: [] }));
  for (let index = 0; index < chain.length - 1; index++) {
    chain[index].nodes.push(chain[index + 1]);
  }
  chain[chain.length - 1].nodes.push({ type: 'text', value: 'x' });

  const root = { type: 'root', nodes: [...chain].reverse() };

  assert.throws(
    () => braces.compile(root),
    error => error instanceof SyntaxError && error.code === 'ERR_BRACES_MAX_DEPTH',
  );
});

test('rejects cyclic direct ASTs before recursive walkers run', () => {
  const root = { type: 'root', nodes: [] };
  const child = { type: 'brace', nodes: [] };
  root.nodes.push(child);
  child.nodes.push(root);

  for (const operation of [braces.compile, braces.expand, braces.stringify]) {
    assert.throws(
      () => operation(root),
      error => error instanceof SyntaxError && error.code === 'ERR_BRACES_CYCLIC_AST',
    );
  }
});

test('rejects cyclic and excessive direct AST parent chains before expand traverses them', () => {
  const root = { type: 'root', nodes: [] };
  const child = { type: 'paren', nodes: [], parent: root };
  root.nodes.push(child);
  child.parent = child;

  assert.throws(
    () => braces.expand(root),
    error => error instanceof SyntaxError && error.code === 'ERR_BRACES_CYCLIC_AST',
  );

  const deepRoot = { type: 'root', nodes: [] };
  const leaf = { type: 'text', value: 'x' };
  deepRoot.nodes.push(leaf);
  let parent = deepRoot;

  for (let index = 0; index < 102; index++) {
    parent.parent = { type: 'unrecognized-parent' };
    parent = parent.parent;
  }

  assert.throws(
    () => braces.expand(deepRoot),
    error => error instanceof SyntaxError && error.code === 'ERR_BRACES_MAX_DEPTH',
  );
});

test('preserves normal expansion and stringify escapeInvalid output', () => {
  assert.deepEqual(braces('a/{x,y}/b'), ['a/(x|y)/b']);
  assert.deepEqual(braces.expand('a/{x,y}/b'), ['a/x/b', 'a/y/b']);
  assert.equal(braces.stringify(braces.parse('{{a}}'), { escapeInvalid: true }), '{{a}}');
  assert.deepEqual(braces('{1..8}', { escapeInvalid: true }), ['([1-8])']);
  assert.throws(
    () => braces.expand('{1..100}', { rangeLimit: 10 }),
    error => error instanceof RangeError && error.code !== 'ERR_BRACES_MAX_DEPTH',
  );
});
