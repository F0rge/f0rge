import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {actions, inspectProjects} from './guard.mjs';

const [action, projectRoot, ...extra] = process.argv.slice(2);
try {
  if (!actions.includes(action) || !projectRoot || extra.length) throw new Error('Usage: run-target.mjs <format-check|lint|test|build> <crate-root>');
  const root = fs.realpathSync(process.cwd());
  const directory = path.resolve(root, projectRoot);
  const project = inspectProjects(root).get(directory);
  if (!project || project.root !== projectRoot) throw new Error('Not a registered Rust project');
  const manifest = path.join(directory, 'Cargo.toml');
  const targetDirectory = path.join(root, 'target', 'nx', project.config.name);
  const metadata = spawnSync('cargo', ['metadata', '--format-version=1', '--locked', '--no-deps', '--manifest-path', manifest], {cwd: root, encoding: 'utf8'});
  if (metadata.status !== 0) throw new Error(`Cargo metadata failed: ${metadata.stderr.trim()}`);
  const data = JSON.parse(metadata.stdout);
  if (!fs.existsSync(path.join(data.workspace_root, 'Cargo.lock'))) throw new Error('Cargo.lock is required');
  const item = data.packages.find(item => fs.realpathSync(item.manifest_path) === fs.realpathSync(manifest));
  if (!item) throw new Error('Cargo package not found');
  const commands = {
    'format-check': ['fmt', '--manifest-path', manifest, '--package', item.name, '--', '--check'],
    lint: ['clippy', '--manifest-path', manifest, '--locked', '--package', item.name, '--all-targets', '--target-dir', targetDirectory, '--', '-D', 'warnings'],
    test: ['test', '--manifest-path', manifest, '--locked', '--package', item.name, '--target-dir', targetDirectory],
    build: ['build', '--manifest-path', manifest, '--locked', '--package', item.name, '--all-targets', '--target-dir', targetDirectory],
  };
  const result = spawnSync('cargo', commands[action], {cwd: root, stdio: 'inherit'});
  if (result.error) throw result.error;
  process.exitCode = result.status ?? 1;
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
