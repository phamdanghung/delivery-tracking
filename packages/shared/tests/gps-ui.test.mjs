import assert from 'node:assert/strict';
import {test} from 'node:test';
import {gpsFreshness, gpsLabels, engineLabels} from '../../../apps/admin-web/app/fleet/gps-state.ts';

test('web GPS status respects exact approved boundaries and ages cached data', () => {
  const now = Date.parse('2026-10-05T03:00:00Z');
  for (const [age, expected] of [[0,'NORMAL'],[30000,'NORMAL'],[30001,'STALE'],[31000,'STALE'],[120000,'STALE'],[120001,'LOST']]) {
    const at = new Date(now - age).toISOString();
    assert.equal(gpsFreshness({valid:true,gps_at:at,server_received_at:at}, now), expected);
    assert.ok(gpsLabels[expected].length > 0);
  }
  assert.equal(gpsFreshness(null, now), 'LOST');
  assert.equal(gpsFreshness({valid:false}, now), 'LOST');
  assert.equal(gpsFreshness({valid:true,gps_at:'bad',server_received_at:'bad'}, now), 'LOST');
  assert.equal(gpsFreshness({valid:true,gps_at:new Date(now-121000).toISOString(),server_received_at:new Date(now).toISOString()}, now), 'LOST');
  assert.equal(engineLabels.UNKNOWN, 'Không xác định');
});
