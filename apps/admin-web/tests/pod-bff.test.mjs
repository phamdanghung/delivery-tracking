import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { createServer } from "node:http";
import { createRequire, stripTypeScriptTypes } from "node:module";
import { once } from "node:events";
import { test } from "node:test";
import { pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
const { NextRequest } = await import("next/server.js");
function moduleUrl(source) {
  return "data:text/javascript;base64," + Buffer.from(stripTypeScriptTypes(source, { mode: "transform" })).toString("base64");
}

test("POD gallery uses authenticated BFF GET routes; no public or write bridge", async () => {
  const seen = [];
  // Transport fixture for the real handler; backend RBAC/storage are integration-tested separately.
  const server = createServer((req, res) => {
    seen.push({ path: req.url, authorization: req.headers.authorization });
    res.setHeader("Content-Type", "application/json");
    res.statusCode = !req.headers.authorization ? 401
      : req.headers.authorization === "Bearer denied" ? 403 : 200;
    res.end(JSON.stringify({ result: "transport fixture" }));
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const previous = process.env.API_URL;
  process.env.API_URL = `http://127.0.0.1:${server.address().port}`;
  try {
    const origin = moduleUrl(await readFile(new URL("../app/api/internal/origin.ts", import.meta.url), "utf8"));
    const source = (await readFile(new URL("../app/api/internal/[...path]/route.ts", import.meta.url), "utf8"))
      .replace('"next/server"', JSON.stringify(pathToFileURL(require.resolve("next/server")).href))
      .replace('"../origin"', JSON.stringify(origin));
    const handler = await import(moduleUrl(source));
    const delivery = "11111111-1111-4111-8111-111111111111";
    const photo = "22222222-2222-4222-8222-222222222222";
    const paths = [`deliveries/${delivery}/pod/photos`, `deliveries/${delivery}/pod/photos/${photo}/url`];
    async function invoke(path, token, method = "GET") {
      return handler[method](new NextRequest(`http://localhost/api/internal/${path}`, {
        method, headers: token ? { cookie: `fleet_access=${token}` } : {},
      }), { params: Promise.resolve({ path: path.split("/") }) });
    }
    for (const path of paths) {
      const response = await invoke(path, "staff");
      assert.equal(response.status, 200);
      assert.equal(response.headers.get("cache-control"), "no-store");
      assert.deepEqual(seen.at(-1), { path: `/api/v1/${path}`, authorization: "Bearer staff" });
      assert.equal((await invoke(path)).status, 401);
      assert.equal((await invoke(path, "denied")).status, 403);
      const count = seen.length;
      assert.equal((await invoke(path, "staff", "POST")).status, 404);
      assert.equal(seen.length, count);
    }
    const count = seen.length;
    for (const path of ["public/tracking/token/pod/photos", `${paths[0]}/all`, `${paths[0]}/../photos`, `deliveries/${delivery}/pod/upload`]) {
      assert.equal((await invoke(path, "staff")).status, 404);
    }
    assert.equal(seen.length, count);
  } finally {
    if (previous === undefined) delete process.env.API_URL;
    else process.env.API_URL = previous;
    await new Promise((resolve) => server.close(resolve));
  }
});

test("M7 BFF preserves staff auth, scoped read/write, CSRF and bounded private receipt uploads",async()=> {
  const seen=[];
  const server=createServer(async(req,res)=> {
    const chunks=[];for await (const part of req) chunks.push(part);
    seen.push({path:req.url,authorization:req.headers.authorization,mime:req.headers['content-type'],metadata:req.headers['x-receipt-metadata'],bytes:Buffer.concat(chunks).length});
    res.setHeader('Content-Type','application/json');res.statusCode=!req.headers.authorization?401:req.headers.authorization==='Bearer denied'?403:200;
    res.end(JSON.stringify({id:'transport-only'}));
  });
  server.listen(0,'127.0.0.1');await once(server,'listening');
  const previous=process.env.API_URL;process.env.API_URL=`http://127.0.0.1:${server.address().port}`;
  try {
    const origin=moduleUrl(await readFile(new URL('../app/api/internal/origin.ts',import.meta.url),'utf8'));
    const source=(await readFile(new URL('../app/api/internal/[...path]/route.ts',import.meta.url),'utf8'))
      .replace('"next/server"',JSON.stringify(pathToFileURL(require.resolve('next/server')).href))
      .replace('"../origin"',JSON.stringify(origin));
    const handler=await import(moduleUrl(source+"\nexport const m7TransportInstance = 7;\n"));
    async function invoke(path,method='GET',body,headers={}) {
      return handler[method](new NextRequest(`http://localhost/api/internal/${path}`,{method,body,
        headers:{host:'localhost',origin:'http://localhost',cookie:'fleet_access=staff',...headers}}),
        {params:Promise.resolve({path:path.split('/')})});
    }
    const id='11111111-1111-4111-8111-111111111111';
    for (const path of ['fuel/profiles','fuel/entries',`fuel/entries/${id}/receipt-url`,'fuel/reconciliations','maintenance/status','maintenance/events',`maintenance/events/${id}/receipt-url`,'vehicle-documents','safety/alerts','expenses',`expenses/${id}/receipt-url`]) {
      assert.equal((await invoke(path)).status,200,JSON.stringify({path,seen}));assert.equal(seen.at(-1).authorization,'Bearer staff');
      assert.equal((await invoke(path,'GET',undefined,{cookie:''})).status,401);
      assert.equal((await invoke(path,'GET',undefined,{cookie:'fleet_access=denied'})).status,403);
    }
    assert.equal((await invoke(`safety/alerts/${id}/state`,'PATCH',JSON.stringify({from_state:'NEW',to_state:'SEEN'}))).status,200);
    const before=seen.length;
    assert.equal((await invoke('expenses','POST','{}',{origin:'http://attacker.invalid'})).status,403);
    assert.equal((await invoke('public/tracking/token/expenses')).status,404);
    assert.equal((await invoke('vehicles/'+id+'/commands','POST','{}')).status,404);
    assert.equal((await invoke('expense-receipts','GET')).status,404);assert.equal(seen.length,before);
    const metadata=JSON.stringify({client_action_id:id,trip_id:id,sha256:'a'.repeat(64),content_type:'image/png',source:'ALBUM_SELECTED',captured_at:'2026-10-15T07:00:00Z'});
    const bytes=new Uint8Array([137,80,78,71]).buffer;
    const uploaded=await invoke('expense-receipts','POST',bytes,{'content-type':'image/png','x-receipt-metadata':metadata});
    assert.equal(uploaded.status,200);assert.equal(uploaded.headers.get('cache-control'),'no-store');
    assert.equal(seen.at(-1).metadata,metadata);assert.equal(seen.at(-1).bytes,4);assert.equal(seen.at(-1).mime,'image/png');
    assert.equal((await invoke('vehicle-receipts','POST',bytes,{'content-type':'image/png','x-receipt-metadata':metadata})).status,200);
    const count=seen.length;
    assert.equal((await invoke('expense-receipts','POST',bytes,{'content-type':'image/png'})).status,422);
    assert.equal((await invoke('expense-receipts','POST',new Uint8Array(20*1024*1024+1).buffer,{'content-type':'image/png','x-receipt-metadata':metadata})).status,413);
    assert.equal(seen.length,count);
  } finally {
    if(previous===undefined)delete process.env.API_URL;else process.env.API_URL=previous;
    await new Promise(resolve=>server.close(resolve));
  }
});
