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
