// DEC-040: print the complete audit; permit only the two explicitly accepted M5 advisories.
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
fs.writeFileSync(path.join(root, 'artifacts/m5-npm-audit.json'), run.stdout);
assert.ok(report.vulnerabilities && report.metadata, 'Missing audit result');
assert.notEqual(process.env.APP_ENV, 'production', 'DEC-040 does not permit production risk acceptance');
assert.ok(Date.now() < Date.parse('2026-11-03T00:00:00+07:00'), 'DEC-040 review deadline exceeded; new review required');
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
console.log('DEC-040: only accepted M5 tooling advisories remain; runtime gates are required separately.');

