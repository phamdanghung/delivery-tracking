import assert from 'node:assert/strict';
import {test} from 'node:test';
import {datetimePayload, zaloSuggestions} from '../../../apps/admin-web/app/dispatch/helpers.ts';

test('Zalo suggestions require explicit labels, preserve unrecognized text, and do not parse guessed commitments', () => {
  assert.deepEqual(zaloSuggestions('Khách: Khách mô phỏng\nSĐT: 0900000000\nĐịa chỉ: Kho thử\nGhi chú: Cửa sau\nHẹn: 14h'), {
    recipient_name:'Khách mô phỏng', recipient_phone:'0900000000', address_text:'Kho thử', notes:'Cửa sau'
  });
  assert.deepEqual(zaloSuggestions('Nội dung không có nhãn\nSĐT:   '), {});
});

test('commitment datetime entered at company UTC+07 is independent of workstation timezone', () => {
  assert.equal(datetimePayload('2026-10-10T14:00'), '2026-10-10T14:00:00+07:00');
  assert.equal(datetimePayload(''), null);
  assert.equal(new Date(datetimePayload('2026-10-10T14:00')).toISOString(), '2026-10-10T07:00:00.000Z');
});
