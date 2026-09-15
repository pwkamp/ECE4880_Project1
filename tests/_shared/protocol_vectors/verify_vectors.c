#include <stdint.h>
#include <stdio.h>
#include <string.h>

/* Independent C consumer for the language-neutral request vectors. */
static size_t build_request(uint8_t *out, uint8_t opcode, uint16_t request_id,
                            const uint8_t *payload, uint16_t payload_size) {
    out[0] = 2;
    out[1] = opcode;
    out[2] = (uint8_t)(request_id & 0xffu);
    out[3] = (uint8_t)(request_id >> 8u);
    out[4] = (uint8_t)(payload_size & 0xffu);
    out[5] = (uint8_t)(payload_size >> 8u);
    out[6] = 0;
    out[7] = 0;
    if (payload_size > 0) {
        memcpy(out + 8, payload, payload_size);
    }
    return (size_t)payload_size + 8u;
}

int main(void) {
    static const uint8_t expected[] = {0x02, 0x02, 0x02, 0x00, 0x02,
                                       0x00, 0x00, 0x00, 0x02, 0x01};
    static const uint8_t payload[] = {0x02, 0x01};
    uint8_t actual[sizeof(expected)] = {0};
    size_t length = build_request(actual, 2, 2, payload, sizeof(payload));
    if (length != sizeof(expected) || memcmp(actual, expected, sizeof(expected)) != 0) {
        fputs("C protocol vector mismatch\n", stderr);
        return 1;
    }
    return 0;
}
