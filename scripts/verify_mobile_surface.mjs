// Inspect actual exported source maps, rather than inferring runtime from npm flags.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';

const root = 'apps/driver-mobile/dist';
const maps = [];
function visit(dir) {
  for (const item of fs.readdirSync(dir, {withFileTypes: true})) {
    const file = path.join(dir, item.name);
    if (item.isDirectory()) visit(file);
    else if (file.endsWith('.map')) maps.push(file);
  }
}
visit(root);
assert.ok(maps.length >= 2, 'Android and iOS source maps are required');
const forbidden = /(?:^|\/)node_modules\/(?:braces|node-forge|uuid|xcode|micromatch|@expo\/cli|@expo\/code-signing-certificates)\//;
const result = maps.map(file => {
  const map = JSON.parse(fs.readFileSync(file, 'utf8'));
  assert.ok(map.sources.length > 100, 'Source map must describe the real application bundle');
  const matches = map.sources.filter(source => forbidden.test(source.replaceAll('\\', '/')));
  assert.deepEqual(matches, [], `Tooling entered runtime bundle: ${file}`);
  return {file, sources: map.sources.length, advisoryPackageSources: matches};
});
console.log(JSON.stringify(result, null, 2));
