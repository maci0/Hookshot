/* AArch64 LSE faults on a packed guest refcount; serialize its rare unaligned add. */
#include <stdint.h>
#include <string.h>

static unsigned char lock;

uint32_t a64_unaligned_fetch_add32(void *p, uint32_t value) {
    while (__atomic_exchange_n(&lock, 1, __ATOMIC_SEQ_CST)) {}
    uint32_t old;
    memcpy(&old, p, sizeof old);
    uint32_t next = old + value;
    memcpy(p, &next, sizeof next);
    __atomic_store_n(&lock, 0, __ATOMIC_SEQ_CST);
    return old;
}
