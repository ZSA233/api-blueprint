import { ApiBinaryBody, RawBinaryBody, binaryBodyToUint8Array, isApiBinaryBody } from "./api/runtime/binary";
import { ApiErrors, isApiError, resolveApiToast } from "./api/runtime/client";
import type { ApiError } from "./api/runtime/client";
import { createClients } from "./api/transports/http/api/factory";
import {
  DemoFlagsValues,
  DemoPacket,
  DemoPacketWire,
} from "./api/routes/api/binary/types";

declare const process: {
  argv: string[];
  exit(code?: number): never;
};

function buildPacket(): DemoPacket {
  return {
    header: {
      flags: DemoFlagsValues.HasPayload | DemoFlagsValues.HasScores,
      short_code: 0x010203,
      signed_delta: 7,
      item_count: 2,
      payload_len: new TextEncoder().encode("payload-ok").byteLength,
    },
    body: {
      items: [
        { id: 11, enabled: true, value: 1.25, label_len: 5, label: new TextEncoder().encode("alpha") },
        { id: 22, enabled: false, value: 2.5, label_len: 4, label: new TextEncoder().encode("beta") },
      ],
      payload: new TextEncoder().encode("payload-ok"),
      scores: [3.5, 4.5],
      checksum: 12,
    },
  };
}

async function callBinary(baseUrl: string, trace: string, binary: DemoPacket | ApiBinaryBody): Promise<void> {
  const { binaryClient } = createClients({ baseUrl });
  const data = isApiBinaryBody(binary)
    ? await binaryClient.packet({ query: { trace }, binary })
    : await binaryClient.packet({ query: { trace }, binary });
  const dataRecord = data as unknown as Record<string, unknown>;
  const expected = {
    trace,
    version: 1,
    item_count: 2,
    payload: "payload-ok",
    score_sum: 8,
    first_label: "alpha",
    checksum: 12,
  };
  for (const [key, value] of Object.entries(expected)) {
    if (dataRecord[key] !== value) {
      throw new Error(`binary ${trace} ${key}=${dataRecord[key]} expected ${value}`);
    }
  }
  if (JSON.stringify(data.item_ids) !== JSON.stringify([11, 22])) {
    throw new Error(`binary ${trace} item_ids=${JSON.stringify(data.item_ids)}`);
  }
}

async function callTypedErrors(baseUrl: string): Promise<void> {
  const { demoClient } = createClients({ baseUrl });
  const ok = await demoClient.errorDemo({ query: { mode: "ok" } });
  if (ok.status !== "ok") {
    throw new Error(`error-demo ok status=${ok.status}`);
  }

  const token = await expectApiError(() => demoClient.errorDemo({ query: { mode: "token" } }));
  if (!token.is(ApiErrors.CommonErr.TokenExpire)) {
    throw new Error(`token ApiError id=${token.id} code=${token.code}`);
  }
  const tokenToast = resolveApiToast(
    token.toast,
    (key) => (key === "auth.token_expire" ? "translated token expired" : undefined),
    token.message,
  );
  if (tokenToast !== "translated token expired") {
    throw new Error(`token toast=${tokenToast}`);
  }

  const rateLimited = await expectApiError(() => demoClient.errorDemo({ query: { mode: "rate_limit" } }));
  if (!rateLimited.is(ApiErrors.DemoErr.RateLimited)) {
    throw new Error(`rate limit ApiError id=${rateLimited.id} code=${rateLimited.code}`);
  }
  const rateToast = resolveApiToast(rateLimited.toast, undefined, rateLimited.message);
  if (rateToast !== "请等待 30 秒后重试") {
    throw new Error(`rate limit toast=${rateToast}`);
  }

  const unknown = await expectApiError(() => demoClient.errorDemo({ query: { mode: "unknown" } }));
  if (unknown.id !== "" || unknown.code !== 70001 || unknown.message !== "example undefined business error") {
    throw new Error(`unknown ApiError id=${unknown.id} code=${unknown.code} message=${unknown.message}`);
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
    if (!error.raw) {
      throw new Error("ApiError raw payload is empty");
    }
    return error;
  }
  throw new Error("expected ApiError but request succeeded");
}

async function main(): Promise<void> {
  const baseUrl = process.argv[2];
  if (!baseUrl) {
    throw new Error("base URL argument is required");
  }
  const packet = buildPacket();
  await callBinary(baseUrl, "ts-typed", packet);
  const raw = new RawBinaryBody(binaryBodyToUint8Array(DemoPacketWire.toBinaryBody(packet)));
  await callBinary(baseUrl, "ts-raw", raw);
  const streaming = DemoPacketWire.body({ write: (writer) => DemoPacketWire.write(packet, writer) });
  await callBinary(baseUrl, "ts-stream", streaming);
  await callTypedErrors(baseUrl);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
