import { test } from 'node:test';
import assert from 'node:assert/strict';
import { projected } from '../src/driver/projection.ts';

test('acknowledged correction never reverses a new geofence arrival; rejected predecessor blocks offline projection', () => {
  const cache = { trips: [], deliveries: { stop: { delivery: { status: 'ARRIVED' }, events: [] } } };
  const command = { action: { kind: 'CORRECT_ARRIVED', resource_id: 'stop' } };
  assert.equal(projected(cache, [{ command, state: 'SYNCED' }]).deliveries.stop.delivery.status, 'ARRIVED');
  assert.equal(projected(cache, [{ command, state: 'WAITING' }]).deliveries.stop.delivery.status, 'EN_ROUTE');
  assert.equal(cache.deliveries.stop.delivery.status, 'ARRIVED');
  assert.equal(projected(cache, [{ command, state: 'ERROR' }, { command, state: 'WAITING' }]).deliveries.stop.delivery.status, 'ARRIVED');
});
