'use strict';

const MAX_DEPTH = 100;

const getMaxDepth = options => {
  const requested = options && options.maxDepth;

  if (typeof requested !== 'number' || !Number.isFinite(requested)) {
    return MAX_DEPTH;
  }

  return Math.min(MAX_DEPTH, Math.max(0, Math.floor(requested)));
};

const depthError = maximum => {
  const error = new SyntaxError(`braces: nesting exceeds maximum allowed depth (${maximum})`);
  error.code = 'ERR_BRACES_MAX_DEPTH';
  return error;
};

const assertDepth = (depth, maximum) => {
  if (depth > maximum) {
    throw depthError(maximum);
  }
};

const validateAst = (root, options = {}) => {
  if (!root || typeof root !== 'object') {
    throw new TypeError('Expected an AST object');
  }

  const maximum = getMaxDepth(options);
  const active = new WeakSet();
  const maxContainerDepth = new WeakMap();
  const nodes = new Set();
  const stack = [{ node: root, depth: 0, exiting: false }];

  while (stack.length > 0) {
    const frame = stack.pop();
    const { node, depth, exiting } = frame;

    if (exiting) {
      active.delete(node);
      let height = Array.isArray(node.nodes) ? 0 : Number.NEGATIVE_INFINITY;

      if (Array.isArray(node.nodes)) {
        for (const child of node.nodes) {
          const childHeight = maxContainerDepth.get(child);
          if (childHeight !== Number.NEGATIVE_INFINITY) {
            height = Math.max(height, childHeight + 1);
          }
        }
      }

      maxContainerDepth.set(node, height);
      continue;
    }

    if (!node || typeof node !== 'object') {
      throw new TypeError('Expected AST nodes to be objects');
    }

    const hasChildren = Array.isArray(node.nodes);
    if (hasChildren) {
      assertDepth(depth, maximum);
    }

    if (active.has(node)) {
      const error = new SyntaxError('braces: AST contains a cycle');
      error.code = 'ERR_BRACES_CYCLIC_AST';
      throw error;
    }

    if (maxContainerDepth.has(node)) {
      const cachedDepth = maxContainerDepth.get(node);
      if (cachedDepth !== Number.NEGATIVE_INFINITY) {
        assertDepth(depth + cachedDepth, maximum);
      }
      continue;
    }

    active.add(node);
    nodes.add(node);
    stack.push({ node, depth, exiting: true });

    if (node.nodes === undefined) {
      continue;
    }

    if (!Array.isArray(node.nodes)) {
      throw new TypeError('Expected AST node children to be an array');
    }

    for (let index = node.nodes.length - 1; index >= 0; index--) {
      stack.push({ node: node.nodes[index], depth: depth + 1, exiting: false });
    }
  }

  for (const node of nodes) {
    const parents = new WeakSet();
    let parent = node.parent;
    let parentDepth = 0;

    while (parent && typeof parent === 'object') {
      if (parents.has(parent)) {
        const error = new SyntaxError('braces: AST parent links contain a cycle');
        error.code = 'ERR_BRACES_CYCLIC_AST';
        throw error;
      }

      parents.add(parent);
      parentDepth++;
      if (parentDepth > maximum + 1) {
        throw depthError(maximum);
      }
      parent = parent.parent;
    }
  }
};

module.exports = { MAX_DEPTH, assertDepth, getMaxDepth, validateAst };
