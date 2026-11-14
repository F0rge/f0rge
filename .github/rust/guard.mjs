import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

export const actions = ['format-check', 'lint', 'test', 'build'];
const ignored = new Set(['node_modules', '.git', '.venv', 'target', 'dist', '.next', '.medusa']);
const fail = message => {throw new Error(message);};
const relative = (root, value) => path.relative(root, value).split(path.sep).join('/');
export const targetCommand = (action, projectRoot) => `node .github/rust/run-target.mjs ${action} ${projectRoot}`;

function filesBelow(directory, wanted, output = []) {
  if (!fs.existsSync(directory)) return output;
  for (const item of fs.readdirSync(directory, {withFileTypes: true})) {
    if (ignored.has(item.name)) continue;
    const entry = path.join(directory, item.name);
    if (item.isDirectory()) filesBelow(entry, wanted, output);
    else if (wanted.has(item.name)) {
      if (item.isSymbolicLink()) fail(`Symlinked Rust/project manifest is unsupported: ${entry}`);
      output.push(entry);
    }
  }
  return output;
}

export function inspectProjects(root = process.cwd()) {
  root = fs.realpathSync(root);
  const files = ['apps', 'libs'].flatMap(folder => filesBelow(path.join(root, folder), new Set(['Cargo.toml', 'project.json'])));
  const projects = new Map();
  for (const file of files.filter(file => path.basename(file) === 'project.json')) {
    const config = JSON.parse(fs.readFileSync(file, 'utf8'));
    if (config.tags?.includes('platform:rust')) projects.set(path.dirname(file), {root: relative(root, path.dirname(file)), config});
  }
  for (const manifest of files.filter(file => path.basename(file) === 'Cargo.toml')) {
    if (!projects.has(path.dirname(manifest))) fail(`${relative(root, manifest)} requires sibling project.json with platform:rust`);
  }
  if (projects.size) {
    const inputs = JSON.parse(fs.readFileSync(path.join(root, 'nx.json'), 'utf8')).namedInputs?.rust;
    const required = ['{projectRoot}/**/*', '!{projectRoot}/target/**/*', '{workspaceRoot}/**/Cargo.toml', '{workspaceRoot}/**/Cargo.lock', '{workspaceRoot}/rust-toolchain.toml', '{workspaceRoot}/rust-toolchain', '{workspaceRoot}/.cargo/**/*', '{workspaceRoot}/**/.cargo/config.toml', '{workspaceRoot}/rustfmt.toml', '{workspaceRoot}/clippy.toml', '{workspaceRoot}/.github/rust/**/*'];
    if (!Array.isArray(inputs) || required.some(input => !inputs.includes(input))) fail('nx.json namedInputs.rust is missing required Rust source/toolchain/lock/tooling inputs');
  }
  const names = new Set();
  for (const [directory, project] of projects) {
    const {config, root: projectRoot} = project;
    if (!/^(apps|libs)\/[A-Za-z0-9_./-]+$/.test(projectRoot)) fail(`Unsupported Rust project path: ${projectRoot}`);
    if (!fs.existsSync(path.join(directory, 'Cargo.toml'))) fail(`${projectRoot} is tagged Rust without Cargo.toml`);
    if (!/^[A-Za-z0-9][A-Za-z0-9_-]*$/.test(config.name ?? '') || names.has(config.name)) fail(`Missing/duplicate Rust Nx project name: ${projectRoot}`);
    names.add(config.name);
    if (config.root !== undefined && config.root !== projectRoot) fail(`${projectRoot} must not override the Nx project root`);
    if (Object.hasOwn(config.namedInputs ?? {}, 'rust')) fail(`${projectRoot} must not override namedInputs.rust`);
    const dependencies = config.implicitDependencies ?? [];
    if (!Array.isArray(dependencies) || dependencies.some(name => typeof name !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]*$/.test(name)) || new Set(dependencies).size !== dependencies.length) fail(`${projectRoot} implicitDependencies must be unique exact project names`);
    if (!config.tags.some(tag => /^scope:[a-z0-9-]+$/.test(tag)) || config.tags.some(tag => tag.startsWith('platform:') && tag !== 'platform:rust')) fail(`${projectRoot} needs one Rust platform tag and a scope tag`);
    for (const action of actions) {
      const target = config.targets?.[action];
      if (target?.executor !== 'nx:run-commands' || target.options?.command !== targetCommand(action, projectRoot) || Object.keys(target.options ?? {}).length !== 1) fail(`${projectRoot}:${action} must use the fixed Rust runner`);
      if (target.cache !== false || JSON.stringify(target.inputs) !== JSON.stringify(['rust', '^rust']) || JSON.stringify(target.outputs) !== '[]' || target.dependsOn?.length || target.configurations || target.defaultConfiguration) fail(`${projectRoot}:${action} requires uncached fixed inputs/outputs with no overrides`);
    }
  }
  return projects;
}

export function validate(root = process.cwd(), {staticOnly = false} = {}) {
  root = fs.realpathSync(root);
  const projects = inspectProjects(root);
  if (staticOnly) return [...projects.values()];
  const manifests = [...projects.keys()].map(directory => path.join(directory, 'Cargo.toml'));
  if (fs.existsSync(path.join(root, 'Cargo.toml'))) manifests.unshift(path.join(root, 'Cargo.toml'));
  const covered = new Set();
  const seenWorkspaces = new Set();
  for (const manifest of manifests) {
    const result = spawnSync('cargo', ['metadata', '--format-version=1', '--locked', '--no-deps', '--manifest-path', manifest], {cwd: root, encoding: 'utf8'});
    if (result.status !== 0) fail(`Cargo metadata failed for ${relative(root, manifest)}: ${result.stderr.trim()}`);
    const metadata = JSON.parse(result.stdout);
    if (manifest !== path.join(root, 'Cargo.toml') && !metadata.packages.some(item => fs.realpathSync(item.manifest_path) === fs.realpathSync(manifest))) fail('Nested virtual Cargo workspaces are not supported; use the repository-root workspace or standalone package roots');
    const workspace = fs.realpathSync(metadata.workspace_root);
    if (workspace !== root && !workspace.startsWith(root + path.sep)) fail('Cargo workspace is outside the repository');
    if (!fs.existsSync(path.join(workspace, 'Cargo.lock'))) fail(`${relative(root, workspace) || '.'} requires a committed Cargo.lock`);
    if (seenWorkspaces.has(workspace)) continue;
    seenWorkspaces.add(workspace);
    for (const item of metadata.packages.filter(item => metadata.workspace_members.includes(item.id))) {
      const directory = fs.realpathSync(path.dirname(item.manifest_path));
      const project = projects.get(directory);
      if (!project) fail(`Cargo member ${relative(root, directory)} is not a registered Rust Nx project`);
      covered.add(directory);
      for (const dependency of item.dependencies.filter(dependency => dependency.path)) {
        const dependencyRoot = fs.realpathSync(dependency.path);
        const registered = projects.get(dependencyRoot);
        if (!registered) fail(`${project.root} has an unregistered local Cargo dependency: ${relative(root, dependencyRoot)}`);
        if (project.root.startsWith('libs/') && registered.root.startsWith('apps/')) fail(`${project.root}: shared libraries must not depend on app crates`);
        if (!project.config.implicitDependencies?.includes(registered.config.name)) fail(`${project.root} must declare implicitDependencies: ${registered.config.name}`);
      }
    }
  }
  for (const [directory, project] of projects) if (!covered.has(directory)) fail(`${project.root} is not covered by a locked Cargo workspace`);
  return [...projects.values()];
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  try {
    if (process.argv.slice(2).some(argument => argument !== '--static')) fail('Only --static is supported');
    const projects = validate(process.cwd(), {staticOnly: process.argv.includes('--static')});
    console.log(`Rust registration check passed (${projects.length} projects; ${process.argv.includes('--static') ? 'static' : 'Cargo metadata'}).`);
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
