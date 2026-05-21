import { ApiBinaryBody, RawBinaryBody, binaryBodyToUint8Array, isApiBinaryBody } from "./api/runtime/binary";
import { ApiErrors, isApiError, resolveApiToast } from "./api/runtime/client";
import type { ApiError } from "./api/runtime/client";
import { createClients as createApiClients } from "./api/transports/http/api/factory";
import { createClients as createAltClients } from "./alt/transports/http/alt/factory";
import { createClients as createStaticClients } from "./static/transports/http/static/factory";
import {
  AuditPacket,
  AuditPacketFlagsValues,
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
import { HelloChannelMsgTypeEnum } from "./api/runtime/types";

declare const process: {
  argv: string[];
  exit(code?: number): never;
};

const SAMPLE_JPEG = new Uint8Array([
  0xff, 0xd8, 0xff, 0xe0, 0x00, 0x10, 0x4a, 0x46, 0x49, 0x46, 0x00, 0x01,
  0x01, 0x01, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xff, 0xd9,
]);

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

function buildAuditPacket(): AuditPacket {
  return {
    header: {
      flags: AuditPacketFlagsValues.HasItems,
      item_count: 2,
    },
    body: {
      items: [
        { id: 11, code: 101 },
        { id: 22, code: 202 },
      ],
      checksum: 2,
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

async function checkRaw(baseUrl: string): Promise<void> {
  const response = await fetch(`${baseUrl}/api/demo/raw`, { method: "POST" });
  const body = await response.text();
  if (!response.ok) {
    throw new Error(`raw status=${response.status} body=${body}`);
  }
}

async function checkXML(baseUrl: string): Promise<void> {
  const response = await fetch(`${baseUrl}/api/demo/delete$?arg1=ts-xml&arg2=7`, { method: "DELETE" });
  const body = await response.text();
  if (!response.ok || !body.includes("ts-xml")) {
    throw new Error(`xml status=${response.status} body=${body}`);
  }
}

async function checkStatic(baseUrl: string): Promise<void> {
  const { staticClient } = createStaticClients({ baseUrl });
  await staticClient.docJson();
  const rsp = await staticClient.dochaha();
  if (rsp.a !== "hello world") {
    throw new Error(`static.dochaha=${JSON.stringify(rsp)}`);
  }
}

async function checkHeader(baseUrl: string): Promise<void> {
  const { demoClient } = createApiClients({ baseUrl });
  const rsp = await demoClient.abc({ headers: { "x-token": "conformance-token" } });
  if (rsp.bc !== "header-ok") {
    throw new Error(`header=${JSON.stringify(rsp)}`);
  }
}

async function checkScalar(baseUrl: string): Promise<void> {
  const { helloClient } = createApiClients({ baseUrl });
  const text = await helloClient.string();
  const value = await helloClient.uint64();
  if (text !== "hello-string" || value !== 9007199254740991) {
    throw new Error(`scalar text=${text} value=${value}`);
  }
}

async function checkEnum(baseUrl: string): Promise<void> {
  const { helloClient } = createApiClients({ baseUrl });
  const item = await helloClient.stringEmun();
  const items = await helloClient.listEnum();
  if (item !== "a" || JSON.stringify(items) !== JSON.stringify(["a", "b"])) {
    throw new Error(`enum item=${item} items=${JSON.stringify(items)}`);
  }
}

async function checkMap(baseUrl: string): Promise<void> {
  const { demoClient, helloClient } = createApiClients({ baseUrl });
  const model = await demoClient.mapModel();
  if (model[1]?.haha !== 101) {
    throw new Error(`map model=${JSON.stringify(model)}`);
  }
  const hello = await helloClient.abc({ query: { type: HelloChannelMsgTypeEnum.PING } });
  if (hello.ping?.haha !== 1) {
    throw new Error(`hello abc=${JSON.stringify(hello)}`);
  }
  const enumMap = await helloClient.mapEnum();
  if (enumMap.a?.haha !== 11) {
    throw new Error(`map enum=${JSON.stringify(enumMap)}`);
  }
}

async function checkDeprecated(baseUrl: string): Promise<void> {
  const { demoClient } = createApiClients({ baseUrl });
  const rsp = await demoClient.postDeprecated({ json: { req1: "ts-deprecated", req2: 3 } });
  assertArrayEquals(rsp.list, ["ts-deprecated"], "deprecated.list");
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

async function checkAuditBinary(baseUrl: string): Promise<void> {
  const { binaryClient } = createApiClients({ baseUrl });
  const response = await binaryClient.auditPacket({
    query: { trace: "ts-audit" },
    binary: buildAuditPacket(),
  });
  if (response.trace !== "ts-audit" || response.item_count !== 2 || response.checksum !== 2) {
    throw new Error(`audit binary=${JSON.stringify(response)}`);
  }
}

async function checkBinaryResponse(baseUrl: string): Promise<void> {
  const { binaryClient } = createApiClients({ baseUrl });
  const response = await binaryClient.auditPacketResponse();
  if (
    response.header.flags !== AuditPacketFlagsValues.HasItems ||
    response.header.item_count !== 2 ||
    response.body.items[0]?.id !== 11 ||
    response.body.items[1]?.code !== 202 ||
    response.body.checksum !== 2
  ) {
    throw new Error(`binary response=${JSON.stringify(response)}`);
  }
}

async function checkMedia(baseUrl: string): Promise<void> {
  const { mediaClient } = createApiClients({ baseUrl });
  const preview = await mediaClient.mediaPreview({
    multipart: {
      title: "ts-media",
      image: { blob: SAMPLE_JPEG, filename: "preview.jpg", contentType: "image/jpeg" },
    },
  });
  if (preview.status !== 200 || preview.contentType !== "image/jpeg") {
    throw new Error(`media preview status=${preview.status} contentType=${preview.contentType}`);
  }
  await assertBlobStartsWith(preview.body, [0xff, 0xd8], "media preview");

  const frame = await mediaClient.mediaFrame();
  if (frame.contentType !== "image/jpeg") {
    throw new Error(`media frame contentType=${frame.contentType}`);
  }
  await assertBlobStartsWith(frame.body, [0xff, 0xd8], "media frame");

  const download = await mediaClient.mediaDownload();
  if (download.filename !== "media-report.xlsx") {
    throw new Error(`media download filename=${download.filename}`);
  }
  await assertBlobStartsWith(download.body, [0x50, 0x4b], "media download");

  const dynamic = await mediaClient.mediaDownloadDynamic();
  if (dynamic.filename !== "media-report-dynamic.xlsx") {
    throw new Error(`media dynamic download filename=${dynamic.filename}`);
  }
  await assertBlobStartsWith(dynamic.body, [0x50, 0x4b], "media dynamic download");

  const stream = await mediaClient.mediaMjpeg();
  const reader = stream.body?.getReader();
  if (!reader) {
    throw new Error("media stream body is empty");
  }
  const first = await reader.read();
  await reader.cancel();
  const chunk = new TextDecoder().decode(first.value ?? new Uint8Array());
  if (!chunk.includes("--frame")) {
    throw new Error(`media stream chunk=${chunk}`);
  }
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

async function checkSingleChannel(baseUrl: string): Promise<void> {
  const { apiClient } = createApiClients({ baseUrl });
  const channel = apiClient.openHelloChannel();
  const message = waitForMessage(channel, "single channel message");
  const close = waitForClose(channel, "single channel close");
  await channel.ready;
  await channel.send({ type: HelloChannelMsgTypeEnum.PING, data: { source: "ts" } });
  const received = await message;
  if (received.type !== HelloChannelMsgTypeEnum.PONG) {
    throw new Error(`single channel message=${JSON.stringify(received)}`);
  }
  const closed = await close;
  if (closed.code !== 1000) {
    throw new Error(`single channel close=${JSON.stringify(closed)}`);
  }
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

async function assertBlobStartsWith(blob: Blob, expected: readonly number[], label: string): Promise<void> {
  const actual = Array.from(new Uint8Array(await blob.arrayBuffer()).slice(0, expected.length));
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(`${label} prefix=${JSON.stringify(actual)} expected ${JSON.stringify(expected)}`);
  }
}

async function main(): Promise<void> {
  const baseUrl = process.argv[2];
  if (!baseUrl) {
    throw new Error("base URL argument is required");
  }
  const selected = scenarioSet(process.argv[3] || "rpc,binary,form,error,sse,websocket,naming,raw,xml,static,header,scalar,enum,map,deprecated,audit-binary,binary-response,media,single-channel");
  if (selected.has("rpc")) {
    await checkRPC(baseUrl);
  }
  if (selected.has("raw")) {
    await checkRaw(baseUrl);
  }
  if (selected.has("xml")) {
    await checkXML(baseUrl);
  }
  if (selected.has("static")) {
    await checkStatic(baseUrl);
  }
  if (selected.has("header")) {
    await checkHeader(baseUrl);
  }
  if (selected.has("scalar")) {
    await checkScalar(baseUrl);
  }
  if (selected.has("enum")) {
    await checkEnum(baseUrl);
  }
  if (selected.has("map")) {
    await checkMap(baseUrl);
  }
  if (selected.has("deprecated")) {
    await checkDeprecated(baseUrl);
  }
  if (selected.has("form")) {
    await checkForm(baseUrl);
  }
  if (selected.has("binary")) {
    await checkBinary(baseUrl);
  }
  if (selected.has("audit-binary")) {
    await checkAuditBinary(baseUrl);
  }
  if (selected.has("binary-response")) {
    await checkBinaryResponse(baseUrl);
  }
  if (selected.has("media")) {
    await checkMedia(baseUrl);
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
  if (selected.has("single-channel")) {
    await checkSingleChannel(baseUrl);
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
