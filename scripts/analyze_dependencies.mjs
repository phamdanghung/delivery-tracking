// Report all lockfile paths and audit propagation; this does not filter the audit.
import fs from 'node:fs';
import path from 'node:path';

const [lockFile, auditFile, outputFile] = process.argv.slice(2);
if (!outputFile) throw new Error('Usage: node scripts/analyze_dependencies.mjs LOCK AUDIT OUTPUT');
const lock = JSON.parse(fs.readFileSync(lockFile, 'utf8'));
const audit = JSON.parse(fs.readFileSync(auditFile, 'utf8'));
const packages = lock.packages;
const targets = new Set(['braces', 'node-forge', 'uuid']);
const runtime = new Set(['expo', 'react-native', '@react-native/virtualized-lists']);
const tooling = new Set([
  '@expo/cli', '@expo/code-signing-certificates', '@expo/config', '@expo/config-plugins',
  '@expo/inline-modules', '@expo/local-build-cache-provider', '@expo/metro',
  '@expo/metro-config', '@expo/metro-file-map', '@expo/prebuild-config',
  '@next/eslint-plugin-next', '@react-native/community-cli-plugin', 'braces',
  'eslint-config-next', 'fast-glob', 'metro', 'metro-config', 'metro-file-map',
  'metro-transform-worker', 'micromatch', 'node-forge', 'uuid', 'xcode',
]);
function nameOf(key) {
  return packages[key]?.name ?? key.slice(key.lastIndexOf('node_modules/') + 13);
}
function resolve(from, name) {
  for (let dir = from; ; dir = path.posix.dirname(dir)) {
    const key = path.posix.join(dir === '.' ? '' : dir, 'node_modules', name);
    if (packages[key]) return packages[key].link ? packages[key].resolved : key;
    if (dir === '.' || !dir) break;
  }
  return null;
}
const graph = new Map();
for (const [key, value] of Object.entries(packages)) {
  if (value.link) continue;
  const deps = {...value.dependencies, ...value.optionalDependencies};
  if (!key.includes('node_modules/')) Object.assign(deps, value.devDependencies);
  graph.set(key, Object.keys(deps).map(name => resolve(key, name)).filter(Boolean));
}
const relevant = new Set([...graph.keys()].filter(key => targets.has(nameOf(key))));
let changed = true;
while (changed) {
  changed = false;
  for (const [key, deps] of graph) if (!relevant.has(key) && deps.some(dep => relevant.has(dep))) {
    relevant.add(key); changed = true;
  }
}
const paths = Object.fromEntries([...targets].map(name => [name, []]));
function walk(key, trail) {
  if (trail.includes(key) || !relevant.has(key)) return;
  const next = [...trail, key];
  if (targets.has(nameOf(key))) {
    paths[nameOf(key)].push(next.map(item => ({
      name: packages[item].name ?? nameOf(item), version: packages[item].version, location: item,
    })));
  }
  for (const dep of graph.get(key) ?? []) walk(dep, next);
}
for (const key of Object.keys(packages)) if (key.startsWith('apps/') && !key.includes('node_modules/')) walk(key, []);
function origins(name, seen = new Set()) {
  if (seen.has(name)) return [];
  const next = new Set([...seen, name]);
  return [...new Set((audit.vulnerabilities[name]?.via ?? []).flatMap(via =>
    typeof via === 'string' ? origins(via, next) : [via.name]))];
}
const findings = Object.entries(audit.vulnerabilities).map(([name, value]) => ({
  name, severity: value.severity, direct: value.isDirect, nodes: value.nodes,
  packageRole: runtime.has(name) ? 'A: product runtime package, advisory propagated from tooling'
    : tooling.has(name) ? 'B: build/dev/tooling' : 'UNREVIEWED',
  transitive: !value.isDirect, advisoryRoots: origins(name),
}));
const report = {summary: audit.metadata.vulnerabilities, findings, paths};
fs.writeFileSync(outputFile, JSON.stringify(report, null, 2) + '\n');
console.log(JSON.stringify({summary: report.summary, findings: findings.length,
  paths: Object.fromEntries(Object.entries(paths).map(([name, value]) => [name, value.length]))}, null, 2));
