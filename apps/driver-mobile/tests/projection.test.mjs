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

test('conflict projects neither old nor dependent commands, while other delivery remains usable',()=>{
  const cache={trips:[],deliveries:{a:{delivery:{status:'ARRIVED'}},b:{delivery:{status:'ARRIVED'}}}};
  const command=id=>({action:{kind:'CORRECT_ARRIVED',resource_id:id}});
  const result=projected(cache,[{command:command('a'),state:'CONFLICT'},{command:command('a'),state:'WAITING'},{command:command('b'),state:'WAITING'}]);
  assert.equal(result.deliveries.a.delivery.status,'ARRIVED');assert.equal(result.deliveries.b.delivery.status,'EN_ROUTE');
  assert.equal(projected(cache,[{command:command('a'),state:'DISCARDED'}]).deliveries.a.delivery.status,'ARRIVED');
});
