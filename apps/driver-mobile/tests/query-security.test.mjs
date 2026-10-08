import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const query = require('query-string');
test('patched URI decoder preserves Expo Router query semantics and rejects exponential decoding work', () => {
  assert.deepEqual({...query.parse('name=Nguy%E1%BB%85n&id=a&id=b&empty&hash=%23')}, {name:'Nguyễn',id:['a','b'],empty:null,hash:'#'});
  assert.equal(query.stringify({id:'abc',name:'Nguyễn'},{sort:false}), 'id=abc&name=Nguy%E1%BB%85n');
  const started = performance.now();
  const result = query.parse('x=' + '%E0%A4'.repeat(2000));
  assert.equal(typeof result.x, 'string');
  assert.ok(performance.now()-started < 1000, 'Malformed URI decoding must stay bounded');
});
