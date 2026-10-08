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

const statusCommand = (id, entity) => ({...command(id,entity), action:{kind:'STATUS',resource_id:entity,data:{from_status:'ARRIVED',to_status:'DELIVERING'}}});
test('409 blocks only dependent entity, independent sync continues, and restart never retries conflict',async()=>{
  const filename=join(tmpdir(),`fleet-m4-conflict-${randomUUID()}.db`);let db=database(filename);let store=new Outbox(db,'driver');await store.init();
  const old=statusCommand('old','a');await store.enqueue(old);await store.enqueue(statusCommand('dependent','a'));await store.enqueue(statusCommand('independent','b'));
  const sent=[];await store.sync(async x=>{sent.push(x.client_action_id);return x.client_action_id==='old'?{ok:false,retryable:false,conflict:true,error:'409 changed'}:{ok:true,retryable:false}},()=>{});
  assert.deepEqual(sent,['old','independent']);assert.deepEqual((await store.list()).map(x=>x.state),['CONFLICT','WAITING','SYNCED']);
  await store.retry();await store.sync(async()=>{throw Error('must not retry conflict or dependent')},()=>{});
  db.native.close();db=database(filename);store=new Outbox(db,'driver');await store.init();
  assert.deepEqual((await store.list())[0].command,old);assert.equal((await store.list())[0].state,'CONFLICT');
  await assert.rejects(store.discard('old','seen',new Date().toISOString()));
  await store.reviewed('old',{review_token:'fresh',state:{status:'ARRIVED'},conflict:'changed'});
  await store.discard('old','Đã xem trạng thái mới',new Date().toISOString());
  const intent=(await store.list())[0].resolution;db.native.close();db=database(filename);store=new Outbox(db,'driver');await store.init();
  let lost=true;const decisions=[];const resolve=async(oldCommand,resolution)=>{decisions.push([oldCommand,resolution]);if(lost){lost=false;throw Error('lost response after server commit')}return {ok:true,retryable:false}};
  await store.sync(async()=>{throw Error('offline')},()=>{},resolve);assert.equal((await store.list())[0].state,'CONFLICT');
  const resumed=[];await store.sync(async x=>{resumed.push(x.client_action_id);return {ok:true,retryable:false}},()=>{},resolve);
  assert.deepEqual(decisions,[[old,intent],[old,intent]]);assert.deepEqual(resumed,['dependent']);assert.equal((await store.list())[0].state,'DISCARDED');
  await store.enqueue(statusCommand('unrelated-future','a'));assert.equal((await store.list()).at(-1).command.replaces_client_action_id,undefined);
  await assert.rejects(store.enqueue(statusCommand('wrong-entity','b'),['delivery:b'],'old'));
  await store.enqueue(statusCommand('replacement','a'),['delivery:a'],'old');const replacement=(await store.list()).at(-1).command;
  assert.equal(replacement.replaces_client_action_id,'old');assert.equal(replacement.client_action_id,'replacement');assert.deepEqual((await store.list())[0].command,old);
  await store.enqueue(statusCommand('later','a'));assert.equal((await store.list()).at(-1).command.replaces_client_action_id,undefined);
  db.native.close();unlinkSync(filename);
});
test('trip prerequisite conflict pauses its stops while another trip can sync; stale discard is not retried',async()=>{
  const db=database();const store=new Outbox(db,'driver');await store.init();
  await store.enqueue(command('start','trip'),['trip:trip','delivery:a','delivery:b']);await store.enqueue(statusCommand('a','a'));await store.enqueue(statusCommand('b','b'));await store.enqueue(command('other','other-trip'));
  const sent=[];await store.sync(async x=>{sent.push(x.client_action_id);return {ok:x.client_action_id!=='start',retryable:false,conflict:x.client_action_id==='start'}},()=>{});
  assert.deepEqual(sent,['start','other']);await store.reviewed('start',{review_token:'old',state:{status:'PLANNED'},conflict:'changed'});await store.discard('start','seen',new Date().toISOString());
  let tries=0;const resolve=async()=>{tries++;return {ok:false,retryable:false,error:'409 review stale'}};
  await store.sync(async()=>{throw Error('blocked')},()=>{},resolve);await store.sync(async()=>{throw Error('blocked')},()=>{},resolve);
  assert.equal(tries,1);const old=(await store.list())[0];assert.equal(old.state,'CONFLICT');assert.equal(old.review,undefined);assert.equal(old.resolution,undefined);assert.equal(old.resolution_attempts.length,1);
  await assert.rejects(store.discard('start','again',new Date().toISOString()));db.native.close();
});
