import { ApiBinaryBody, RawBinaryBody, binaryBodyToUint8Array, isApiBinaryBody } from "./api/runtime/binary";
import { createClients } from "./api/transports/http/api/factory";
import {
  DemoFlagsValues,
  DemoPacket,
  DemoPacketWire,
} from "./api/routes/api/binary/binary";

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
  const envelope = isApiBinaryBody(binary)
    ? await binaryClient.packet({ query: { trace }, binary })
    : await binaryClient.packet({ query: { trace }, binary });
  if (envelope.code !== 0 || envelope.data == null) {
    throw new Error(`binary ${trace} failed: ${envelope.code} ${envelope.message}`);
  }
  const data = envelope.data;
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
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
