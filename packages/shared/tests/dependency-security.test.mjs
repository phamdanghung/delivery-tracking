import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import test from 'node:test';

const require = createRequire(import.meta.url);
const xcode = require('xcode');
const fromXcode = createRequire(require.resolve('xcode'));
const uuid = fromXcode('uuid');

test('xcode uses the patched CommonJS uuid and generates valid unique project IDs', () => {
  assert.equal(fromXcode('uuid/package.json').version, '11.1.1');
  const project = xcode.project('unused.pbxproj');
  project.hash = {project: {objects: {PBXGroup: {}}}};
  const ids = Array.from({length: 1000}, () => project.generateUuid());
  assert.equal(new Set(ids).size, ids.length);
  for (const id of ids) assert.match(id, /^[0-9A-F]{24}$/);
});

test('uuid rejects an undersized v5 output buffer without writing into it', () => {
  const buffer = new Uint8Array(8).fill(42);
  assert.throws(() => uuid.v5('M0', uuid.v5.DNS, buffer), RangeError);
  assert.deepEqual([...buffer], Array(8).fill(42));
});
