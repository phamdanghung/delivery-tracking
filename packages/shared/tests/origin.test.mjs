import assert from 'node:assert/strict';
import {test} from 'node:test';
import {sameOrigin} from '../../../apps/admin-web/app/api/internal/origin.ts';

test('web CSRF check accepts the real loopback Host and rejects foreign, missing or mismatched Origin', () => {
  assert.equal(sameOrigin('http://127.0.0.1:3000', 'http:', '127.0.0.1:3000'), true);
  assert.equal(sameOrigin('http://localhost:3000', 'http:', 'localhost:3000'), true);
  assert.equal(sameOrigin('https://fleet.example', 'https:', 'fleet.example'), true);
  for (const origin of [null, 'null', 'http://evil.example', 'http://localhost:3001', 'https://localhost:3000', 'http://localhost:3000.evil.example']) {
    assert.equal(sameOrigin(origin, 'http:', 'localhost:3000'), false);
  }
  assert.equal(sameOrigin('http://localhost:3000', 'http:', null), false);
});
