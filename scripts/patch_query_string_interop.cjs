// Expo Router SDK 57 uses query-string 7 (CJS). The patched decoder 0.5 is ESM.
// Adapt only the import, not decoding behavior. Fail closed if upstream changes.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const filename = require.resolve('query-string');
const manifest = JSON.parse(fs.readFileSync(path.join(path.dirname(filename), 'package.json'), 'utf8'));
assert.equal(manifest.version, '7.1.3', 'Review compatibility patch after query-string upgrade');
const original = "const decodeComponent = require('decode-uri-component');";
const patched = "const decodeComponent = require('decode-uri-component').default;";
const content = fs.readFileSync(filename, 'utf8');
assert.ok(content.includes(original) || content.includes(patched), 'Upstream import changed');
if (content.includes(original)) fs.writeFileSync(filename, content.replace(original, patched));
const decoderFile = require.resolve('decode-uri-component', { paths: [path.dirname(filename)] });
const decoder = JSON.parse(fs.readFileSync(path.join(path.dirname(decoderFile), 'package.json'), 'utf8'));
assert.equal(decoder.version, '0.5.0', 'Patched upstream decoder is required');
const query = require('query-string');
assert.equal(query.parse('name=Nguy%E1%BB%85n').name, 'Nguyễn');
console.log('query-string CJS import compatibility verified with upstream decoder 0.5.0');
