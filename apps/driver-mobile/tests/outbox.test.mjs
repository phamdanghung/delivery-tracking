import { test } from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { randomUUID } from 'node:crypto';
import { unlinkSync } from 'node:fs';
import { Outbox } from '../src/offline/outbox.ts';

const command = (id, resource='trip') => ({client_action_id:id, occurred_at:'2026-10-07T07:00:00Z', action:{kind:'START_TRIP',resource_id:resource}});
function database(filename=':memory:') {
  const native = new DatabaseSync(filename);
  return { native, execAsync:async sql=>native.exec(sql), runAsync:async(sql,...args)=>native.prepare(sql).run(...args), getFirstAsync:async(sql,...args)=>native.prepare(sql).get(...args) ?? null };
}
test('SQLite durable queue survives store recreation, isolates owners, and retains exact id on lost response', async()=> {
  const filename=join(tmpdir(),`fleet-m4-${randomUUID()}.db`);
  const db=database(filename); const store=new Outbox(db,'a'); await store.init();
  await store.enqueue(command('one')); await store.save('today',{trip:'cached'});
  await store.sync(async()=>{throw new Error('response lost after server commit')},()=>{});
  db.native.close();
  const reopened=database(filename);
  const restored=new Outbox(reopened,'a'); await restored.init();
  assert.equal((await restored.list())[0].state,'WAITING');
  let sent; await restored.sync(async x=>{sent=x;return {ok:true,retryable:false}},()=>{});
  assert.deepEqual(sent,command('one')); assert.equal((await restored.list())[0].state,'SYNCED');
  assert.deepEqual(await restored.load('today'),{trip:'cached'});
  const other=new Outbox(reopened,'b');await other.init();assert.deepEqual(await other.list(),[]);assert.equal(await other.load('today'),null);
  reopened.native.close(); unlinkSync(filename);
});
test('parallel enqueue/sync preserves order, deduplicates commands and blocks a rejected predecessor',async()=>{
  const db=database(); const store=new Outbox(db,'a');await store.init();
  await Promise.all([store.enqueue(command('one')),store.enqueue(command('two'))]);
  await store.enqueue(command('one')); await assert.rejects(store.enqueue(command('one','different')));
  const sent=[];const send=async x=>{sent.push(x.client_action_id);return {ok:false,retryable:false,error:'409 stale'}};
  await Promise.all([store.sync(send,()=>{}),store.sync(send,()=>{})]);assert.deepEqual(sent,['one']);
  assert.equal((await store.list())[1].state,'WAITING');
  await store.retry();const accepted=[];
  await store.sync(async x=>{accepted.push(x.client_action_id);return {ok:true,retryable:false}},()=>{});
  assert.deepEqual(accepted,['one','two']);db.native.close();
});
test('restart recovers SYNCING and includes commands enqueued while network request is in flight',async()=>{
  const db=database();const store=new Outbox(db,'a');await store.init();await store.enqueue(command('one'));
  await store.save('outbox',[{command:command('one'),state:'SYNCING'}]);const restarted=new Outbox(db,'a');await restarted.init();
  let unlock;const gate=new Promise(resolve=>{unlock=resolve});const sent=[];
  const flight=restarted.sync(async x=>{sent.push(x.client_action_id);if(x.client_action_id==='one')await gate;return {ok:true,retryable:false}},()=>{});
  await restarted.enqueue(command('two'));unlock();await flight;assert.deepEqual(sent,['one','two']);db.native.close();
});
