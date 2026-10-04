import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

test('M0 preserves the supplied business API and database baseline byte for byte', () => {
  for (const [source, target] of [
    ['docs/specifications/04_OPENAPI.yaml', 'openapi/openapi.yaml'],
    ['docs/specifications/03_DATABASE_SCHEMA.sql', 'db/migrations/0001_baseline.sql'],
  ]) assert.deepEqual(readFileSync(target), readFileSync(source));
});
