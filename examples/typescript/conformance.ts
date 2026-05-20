import { ApiBinaryBody, RawBinaryBody, binaryBodyToUint8Array, isApiBinaryBody } from "./api/runtime/binary";
import { ApiErrors, isApiError, resolveApiToast } from "./api/runtime/client";
import type { ApiError } from "./api/runtime/client";
import { createClients as createApiClients } from "./api/transports/http/api/factory";
import { createClients as createAltClients } from "./alt/transports/http/alt/factory";
import {
  DemoPacket,
  DemoPacketFlagsValues,
  DemoPacketWire,
} from "./api/routes/api/binary/types";
import {
  AssistantClientMessageVariants,
  AssistantServerMessage,
  dispatchAssistantServerMessage,
  SweepStreamMessage,
} from "./api/routes/api/demo/types";

declare const process: {
  argv: string[];
  exit(code?: number): never;
};

function scenarioSet(raw: string): Set<string> {
  return new Set(raw.split(",").map((item) => item.trim()).filter(Boolean));
}

function buildPacket(): DemoPacket {
  const payload = new TextEncoder().encode("payload-ok");
  return {
    header: {
      flags: DemoPacketFlagsValues.HasPayload | DemoPacketFlagsValues.HasScores,
      short_code: 0x010203,
      signed_delta: 7,
      item_count: 2,
      payload_len: payload.byteLength,
    },
    body: {
      items: [
        { id: 11, enabled: true, value: 1.25, label_len: 5, label: new TextEncoder().encode("alpha") },
        { id: 22, enabled: false, value: 2.5, label_len: 4, label: new TextEncoder().encode("beta") },
      ],
      payload,
      scores: [3.5, 4.5],
      checksum: 12,
    },
  };
}

async function checkRPC(baseUrl: string): Promise<void> {
  const { demoClient } = createApiClients({ baseUrl });
  const post = await demoClient.testPost({ json: { req1: "ts", req2: 7 } });
  assertArrayEquals(post.list, ["test_post", "ts"], "testPost.list");
  if (post.map.req2?.haha !== 7) {
    throw new Error(`testPost.map.req2=${JSON.stringify(post.map.req2)}`);
  }

  const put = await demoClient.putDemo({
    query: { arg1: "query", arg2: 3.5 },
    json: { req1: "body", req2: 9 },
  });
  assertArrayEquals(put.list, ["query", "body"], "putDemo.list");
  if (put.anon_kv.kv1 !== 9) {
    throw new Error(`putDemo.anon_kv=${JSON.stringify(put.anon_kv)}`);
  }
}

async function checkForm(baseUrl: string): Promise<void> {
  const { demoClient } = createApiClients({ baseUrl });
  const rsp = await demoClient.formSubmit({ form: { title: "ts-form", count: 4, enabled: true } });
  if (rsp.summary !== "ts-form" || rsp.count !== 4 || rsp.enabled !== true) {
    throw new Error(`formSubmit=${JSON.stringify(rsp)}`);
  }
}

async function checkBinary(baseUrl: string): Promise<void> {
  const packet = buildPacket();
  await callBinary(baseUrl, "ts-typed", packet);
  await callBinary(baseUrl, "ts-raw", new RawBinaryBody(binaryBodyToUint8Array(DemoPacketWire.toBinaryBody(packet))));
  await callBinary(baseUrl, "ts-stream", DemoPacketWire.body({ write: (writer) => DemoPacketWire.write(packet, writer) }));
}

async function callBinary(baseUrl: string, trace: string, binary: DemoPacket | ApiBinaryBody): Promise<void> {
  const { binaryClient } = createApiClients({ baseUrl });
  const response = isApiBinaryBody(binary)
    ? await binaryClient.packet({ query: { trace }, binary })
    : await binaryClient.packet({ query: { trace }, binary });
  const expected = {
    trace,
    version: 1,
    item_count: 2,
    payload: "payload-ok",
    score_sum: 8,
    first_label: "alpha",
    checksum: 12,
  };
  const record = response as unknown as Record<string, unknown>;
  for (const [key, value] of Object.entries(expected)) {
    if (record[key] !== value) {
      throw new Error(`binary ${trace} ${key}=${record[key]} expected ${value}`);
    }
  }
  assertArrayEquals(response.item_ids, [11, 22], `binary ${trace}.item_ids`);
}

async function checkTypedErrors(baseUrl: string): Promise<void> {
  const { demoClient } = createApiClients({ baseUrl });
  const ok = await demoClient.errorDemo({ query: { mode: "ok" } });
  if (ok.status !== "ok") {
    throw new Error(`errorDemo.ok=${JSON.stringify(ok)}`);
  }

  const rateLimited = await expectApiError(() => demoClient.errorDemo({ query: { mode: "rate_limit" } }));
  if (!rateLimited.is(ApiErrors.DemoErr.RateLimited)) {
    throw new Error(`rateLimit id=${rateLimited.id} code=${rateLimited.code}`);
  }
  const toast = resolveApiToast(rateLimited.toast, undefined, rateLimited.message);
  if (toast !== "请等待 30 秒后重试") {
    throw new Error(`rateLimit.toast=${toast}`);
  }

  const unknown = await expectApiError(() => demoClient.errorDemo({ query: { mode: "unknown" } }));
  if (unknown.id !== "" || unknown.code !== 70001 || unknown.message !== "example undefined business error") {
    throw new Error(`unknown id=${unknown.id} code=${unknown.code} message=${unknown.message}`);
  }
}

async function checkSSE(baseUrl: string): Promise<void> {
  const { demoClient } = createApiClients({ baseUrl });
  const bridge = demoClient.subscribeSweepEvents({ open: { run_id: "ts-sse" } });
  const message = waitForMessage<SweepStreamMessage>(bridge, "sse message");
  const close = waitForClose<{ code?: number; reason?: string }>(bridge, "sse close");
  await bridge.ready;
  const received = await message;
  if (received.type !== "state" || !received.data.status.includes("ts-sse")) {
    throw new Error(`sse message=${JSON.stringify(received)}`);
  }
  const closed = await close;
  if (closed.code !== 1000 || closed.reason !== "example stream complete") {
    throw new Error(`sse close=${JSON.stringify(closed)}`);
  }
}

async function checkWebSocket(baseUrl: string): Promise<void> {
  const { demoClient } = createApiClients({ baseUrl });
  const channel = demoClient.openAssistantSession({ open: { session_id: "ts-ws" } });
  const message = waitForMessage<AssistantServerMessage>(channel, "websocket message");
  const close = waitForClose<{ code?: number; reason?: string }>(channel, "websocket close");
  await channel.ready;
  await channel.send(AssistantClientMessageVariants.input({ text: "hello" }));
  const received = await message;
  const text = dispatchAssistantServerMessage(received, {
    delta: (data) => data.text,
    done: (data) => data.message_id,
    log: (data) => `${data.level}:${data.message}`,
  });
  if (!text.includes("ts-ws") || !text.includes("hello")) {
    throw new Error(`websocket message=${JSON.stringify(received)}`);
  }
  await channel.send(AssistantClientMessageVariants.cancel({ reason: "ts complete" }));
  const closed = await close;
  if (closed.code !== 1000 || closed.reason !== "ts complete") {
    throw new Error(`websocket close=${JSON.stringify(closed)}`);
  }
}

async function checkNaming(baseUrl: string): Promise<void> {
  const { conflictClient } = createApiClients({ baseUrl });
  const api = await conflictClient.default({ query: { class_: "ts-api" } });
  if (api.default !== "api-default" || api.class_ !== "ts-api" || api.enum !== "default") {
    throw new Error(`api conflict=${JSON.stringify(api)}`);
  }

  const { conflictClient: altConflictClient } = createAltClients({ baseUrl });
  const alt = await altConflictClient.default({ query: { class_: "ts-alt" } });
  if (alt.default !== "alt-default" || alt.class_ !== "ts-alt" || alt.enum !== "class") {
    throw new Error(`alt conflict=${JSON.stringify(alt)}`);
  }
}

async function expectApiError(action: () => Promise<unknown>): Promise<ApiError> {
  try {
    await action();
  } catch (error) {
    if (!isApiError(error)) {
      throw new Error(`expected ApiError, got ${String(error)}`);
    }
    if (error.routeId !== "api.demo.get.errordemo") {
      throw new Error(`ApiError routeId=${error.routeId}`);
    }
    return error;
  }
  throw new Error("expected ApiError");
}

function waitForMessage<T>(
  bridge: { onMessage(listener: (message: T) => void): () => void },
  label: string,
): Promise<T> {
  return withTimeout(new Promise<T>((resolve) => {
    const unsubscribe = bridge.onMessage((message) => {
      unsubscribe();
      resolve(message);
    });
  }), label);
}

function waitForClose<T>(
  bridge: { onClose(listener: (info: T) => void): () => void },
  label: string,
): Promise<T> {
  return withTimeout(new Promise<T>((resolve) => {
    const unsubscribe = bridge.onClose((info) => {
      unsubscribe();
      resolve(info);
    });
  }), label);
}

function withTimeout<T>(promise: Promise<T>, label: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`${label} timed out`)), 5000);
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (error) => {
        clearTimeout(timer);
        reject(error);
      },
    );
  });
}

function assertArrayEquals(actual: readonly unknown[], expected: readonly unknown[], label: string): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`${label}=${JSON.stringify(actual)} expected ${JSON.stringify(expected)}`);
  }
}

async function main(): Promise<void> {
  const baseUrl = process.argv[2];
  if (!baseUrl) {
    throw new Error("base URL argument is required");
  }
  const selected = scenarioSet(process.argv[3] || "rpc,binary,form,error,sse,websocket,naming");
  if (selected.has("rpc")) {
    await checkRPC(baseUrl);
  }
  if (selected.has("form")) {
    await checkForm(baseUrl);
  }
  if (selected.has("binary")) {
    await checkBinary(baseUrl);
  }
  if (selected.has("error")) {
    await checkTypedErrors(baseUrl);
  }
  if (selected.has("sse")) {
    await checkSSE(baseUrl);
  }
  if (selected.has("websocket")) {
    await checkWebSocket(baseUrl);
  }
  if (selected.has("naming")) {
    await checkNaming(baseUrl);
  }
  console.log("typescript conformance passed");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
