import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import vm from "node:vm";

const source = readFileSync(new URL("../../app/static/js/http.js", import.meta.url), "utf8");

function loadClient(fetchImplementation) {
  const context = {
    AbortController,
    DOMException,
    clearTimeout,
    fetch: fetchImplementation,
    setTimeout,
  };
  context.window = context;
  vm.runInNewContext(source, context);
  return context.medbridgeHttp;
}

test("GET parses JSON and sends an accept header", async () => {
  let receivedHeaders;
  const client = loadClient(async (_url, options) => {
    receivedHeaders = options.headers;
    return new Response(JSON.stringify({ ok: true }), {
      headers: { "content-type": "application/json" },
    });
  });

  const { data } = await client.get("/api/example");
  assert.deepEqual(data, { ok: true });
  assert.match(receivedHeaders.Accept, /application\/json/);
});

test("non-success responses expose status and API detail", async () => {
  const client = loadClient(async () =>
    new Response(JSON.stringify({ detail: "Champ invalide" }), {
      status: 422,
      headers: { "content-type": "application/json" },
    }),
  );

  await assert.rejects(client.get("/api/example"), (error) => {
    assert.equal(error.name, "HttpError");
    assert.equal(error.status, 422);
    assert.equal(error.message, "Champ invalide");
    return true;
  });
});

test("non-success responses read the MedData Bridge error envelope", async () => {
  const client = loadClient(async () => new Response(JSON.stringify({
    error: { code: "VALIDATION_ERROR", message: "Champ obligatoire" },
  }), {
    status: 422,
    headers: { "content-type": "application/json" },
  }));

  await assert.rejects(
    client.get("/example"),
    (error) => error.name === "HttpError" && error.status === 422 && error.message === "Champ obligatoire",
  );
});

test("request can preserve a binary download payload", async () => {
  const client = loadClient(async () => new Response("archive", {
    headers: { "content-type": "application/octet-stream" },
  }));

  const { data } = await client.request("/export", { responseType: "blob" });
  assert.equal(await data.text(), "archive");
});
