import {readdirSync, readFileSync, realpathSync} from 'node:fs';
import {join} from 'node:path';

// Run in the final image, in addition to (not instead of) build traces/raw audit.
const forbidden = new Set(['braces', 'node-forge', 'expo', 'react-native', '@expo/cli']);
const visited = new Set();
const packages = new Set();
const found = new Set();
function walk(directory) {
  const real = realpathSync(directory);
  if (visited.has(real)) return;
  visited.add(real);
  for (const entry of readdirSync(directory, {withFileTypes:true})) {
    const file = join(directory, entry.name);
    if (entry.isDirectory()) walk(file);
    else if (entry.isFile() && entry.name === 'package.json') {
      const pkg = JSON.parse(readFileSync(file, 'utf8'));
      if (pkg.name) packages.add(pkg.name);
      if (forbidden.has(pkg.name)) found.add(pkg.name);
    }
  }
}
walk('/workspace');
const nonRoot = process.getuid() !== 0;
const runtimePresent = packages.has('next') && packages.has('react');
console.log(JSON.stringify({nonRoot, runtimePresent, packages:packages.size,
  forbiddenPackages:[...found]}, null, 2));
if (!nonRoot || !runtimePresent || found.size) process.exit(1);
