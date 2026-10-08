// DEC-035: print the complete audit; permit only the two explicitly accepted M4 advisories.
import { spawnSync } from 'node:child_process';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../', import.meta.url));

const run = spawnSync(process.platform === 'win32' ? 'npm.cmd' : 'npm', ['audit', '--json'], {
  cwd: root, encoding: 'utf8', shell: process.platform === 'win32', maxBuffer: 8 * 1024 * 1024,
});
assert.ok(!run.error && (run.status === 0 || run.status === 1), 'npm audit failed to complete');
process.stdout.write(run.stdout);
process.stderr.write(run.stderr ?? '');
const report = JSON.parse(run.stdout);
fs.mkdirSync(path.join(root, 'artifacts'), { recursive: true });
fs.writeFileSync(path.join(root, 'artifacts/m4-npm-audit.json'), run.stdout);
assert.ok(report.vulnerabilities && report.metadata, 'Missing audit result');
const accepted = new Set([
  'https://github.com/advisories/GHSA-vfj7-8cjw-p6xm',
  'https://github.com/advisories/GHSA-86w9-cpqp-85rv',
]);
for (const vulnerability of Object.values(report.vulnerabilities)) {
  for (const advisory of vulnerability.via) {
    if (typeof advisory === 'string') {
      assert.ok(report.vulnerabilities[advisory], `Unknown propagated advisory: ${advisory}`);
    } else {
      assert.ok(accepted.has(advisory.url), `Unaccepted advisory: ${advisory.url}`);
    }
  }
}
console.log('DEC-035: only accepted M4 tooling advisories remain; runtime gates are required separately.');
