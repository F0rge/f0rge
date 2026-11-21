import assert from 'node:assert/strict';
import test from 'node:test';
import { plan, tested } from './plan.mjs';

const node = (...tags) => ({ data: { tags } });
const graph = {
  nodes: {
    'shop-api': node('platform:py', 'scope:shop'),
    'shop-web': node('platform:ts', 'scope:shop'),
    'shop-rewrite': node('platform:rust', 'scope:shop'),
    'sensor-api': node('platform:py', 'scope:sensor'),
    'shared-ui': node('platform:ts', 'scope:shared'),
    'ios': node('scope:shop'),
  },
};
const apps = [
  { app: 'sensor', host: 'pi', projects: [{ name: 'sensor-api' }] },
  { app: 'shop', host: 'railway', projects: [{ name: 'shop-api' }, { name: 'shop-web' }] },
];

test('nothing affected starts no language job and no App', () => {
  assert.deepEqual(plan([], graph, apps), { py: false, ts: false, rust: false, apps: [] });
});

test('a project without a platform tag starts no language job', () => {
  assert.deepEqual(plan(['ios'], graph, apps), { py: false, ts: false, rust: false, apps: [] });
});

test('one affected deployable Project selects its whole App, with its Host', () => {
  assert.deepEqual(plan(['shop-web'], graph, apps), {
    py: false, ts: true, rust: false,
    apps: [{ app: 'shop', host: 'railway', projects: 'shop-api,shop-web' }],
  });
});

test('a Project of the App that is not deployable does not release the App', () => {
  assert.deepEqual(plan(['shop-rewrite', 'shared-ui'], graph, apps), { py: false, ts: true, rust: true, apps: [] });
});

test('several Apps are each listed once', () => {
  const result = plan(['shop-api', 'shop-web', 'sensor-api'], graph, apps);
  assert.equal(result.py, true);
  assert.deepEqual(result.apps.map(({ app, host }) => `${app}@${host}`), ['sensor@pi', 'shop@railway']);
});

test('main skips the tests only when every tree in the range is marked', () => {
  const marked = (tree) => ['a', 'b'].includes(tree);
  assert.equal(tested(['a', 'b'], marked), true);
  assert.equal(tested(['a', 'c'], marked), false);
  assert.equal(tested([], marked), false);
  assert.equal(tested(['a'], () => { throw new Error('API down'); }), false);
});
