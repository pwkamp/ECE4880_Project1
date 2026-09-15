import { describe, expect, it } from "vitest";
import vectors from "./protocol_vectors.json";

function buildRequest(opcode: number, requestId: number, payload: Uint8Array): Uint8Array {
  const bytes = new Uint8Array(8 + payload.length);
  const view = new DataView(bytes.buffer);
  view.setUint8(0, vectors.protocol_version);
  view.setUint8(1, opcode);
  view.setUint16(2, requestId, true);
  view.setUint16(4, payload.length, true);
  view.setUint8(6, 0);
  view.setUint8(7, 0);
  bytes.set(payload, 8);
  return bytes;
}

describe("shared thermometer protocol vectors", () => {
  it.each(vectors.request_vectors)("encodes $name independently", (vector) => {
    const opcodeValues: Record<string, number> = {
      GET_CURRENT: 1,
      SET_DISPLAY: 2,
      GET_HISTORY_CHUNK: 4,
      AUTH_BEGIN: 5,
    };
    const payload = Uint8Array.from(vector.payload_hex.match(/.{2}/g)?.map((value) => parseInt(value, 16)) ?? []);
    const actual = Array.from(buildRequest(opcodeValues[vector.opcode], vector.request_id, payload))
      .map((value) => value.toString(16).padStart(2, "0"))
      .join("");
    expect(actual).toBe(vector.packet_hex);
  });
});
