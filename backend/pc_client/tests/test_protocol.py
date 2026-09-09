import struct
import unittest

from pc_client.protocol import (
    AuthenticationChallenge,
    HEADER,
    PROTOCOL_VERSION,
    RESPONSE_FLAG,
    DataStatus,
    Opcode,
    ProtocolError,
    Status,
    VisibleState,
    build_history_chunk_request,
    build_authentication_proof_request,
    build_set_display_request,
    decode_current,
    decode_history_chunk,
    compute_authentication_proof,
    parse_response,
)


def make_response(opcode: Opcode, request_id: int, payload: bytes = b"") -> bytes:
    return HEADER.pack(
        PROTOCOL_VERSION,
        opcode,
        request_id,
        len(payload),
        Status.SUCCESS,
        RESPONSE_FLAG,
    ) + payload


class ProtocolTests(unittest.TestCase):
    def test_set_display_request_has_expected_little_endian_layout(self) -> None:
        packet = build_set_display_request(0x1234, 2, True)
        self.assertEqual(
            packet,
            bytes((PROTOCOL_VERSION, 2, 0x34, 0x12, 2, 0, 0, 0, 2, 1)),
        )

    def test_history_request_uses_stable_sequence_addressing(self) -> None:
        packet = build_history_chunk_request(7, 1, 0x11223344, 16)
        self.assertEqual(packet[8:], bytes((1, 0x44, 0x33, 0x22, 0x11, 16)))

    def test_decodes_current_snapshot(self) -> None:
        payload = struct.pack(
            "<IIhBBhBBhBB",
            0xAABBCCDD,
            42,
            2150,
            VisibleState.ON,
            1,
            0,
            VisibleState.DISCONNECTED,
            0,
            0,
            0,
            0,
        )
        response = parse_response(
            make_response(Opcode.GET_CURRENT, 9, payload),
            expected_opcode=Opcode.GET_CURRENT,
            expected_request_id=9,
        )
        current = decode_current(response)
        self.assertEqual(current.boot_id, 0xAABBCCDD)
        self.assertEqual(current.sensors[0].temperature_c, 21.5)
        self.assertEqual(current.sensors[0].visible_state, VisibleState.ON)
        self.assertIsNone(current.sensors[1].temperature_c)
        self.assertIsNone(current.average_c)

    def test_decodes_only_complete_history_records(self) -> None:
        records = struct.pack("<IhB", 10, -250, DataStatus.VALID)
        payload = struct.pack("<BIBB", 2, 10, 1, 7) + records
        chunk = decode_history_chunk(
            parse_response(make_response(Opcode.GET_HISTORY_CHUNK, 4, payload))
        )
        self.assertEqual(chunk.start_sequence, 10)
        self.assertEqual(chunk.records[0].temperature_c, -2.5)

        with self.assertRaises(ProtocolError):
            decode_history_chunk(
                parse_response(
                    make_response(Opcode.GET_HISTORY_CHUNK, 4, payload[:-1])
                )
            )

    def test_rejects_response_with_wrong_request_id(self) -> None:
        with self.assertRaises(ProtocolError):
            parse_response(
                make_response(Opcode.GET_CURRENT, 11, bytes(20)),
                expected_request_id=12,
            )

    def test_surfaces_server_status(self) -> None:
        packet = HEADER.pack(
            PROTOCOL_VERSION,
            Opcode.SET_DISPLAY,
            5,
            0,
            Status.NOT_AVAILABLE,
            RESPONSE_FLAG,
        )
        with self.assertRaises(ProtocolError) as caught:
            parse_response(packet)
        self.assertEqual(caught.exception.status, Status.NOT_AVAILABLE)

    def test_authentication_proof_is_deterministic_and_never_contains_pin(self) -> None:
        challenge = AuthenticationChallenge(bytes.fromhex("AABBCCDDEEFF"), 7, bytes(16))
        proof = compute_authentication_proof("012345", challenge)
        self.assertEqual(len(proof), 32)
        self.assertNotIn(b"012345", proof)
        packet = build_authentication_proof_request(9, proof)
        self.assertEqual(packet[8:], proof)
        self.assertEqual(
            proof.hex(),
            "a95347370222b1e6eb0abcda972c5c0306086912fdadde1b3d93e7c80076e255",
        )


if __name__ == "__main__":
    unittest.main()
