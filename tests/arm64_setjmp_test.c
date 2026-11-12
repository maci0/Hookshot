#include "../host/hos_setjmp.c"
#include <stdio.h>

__attribute__((noinline)) static void jump_back(void **buf, int value) {
    volatile int scratch[256] = {value};
    recomp_sj_longjmp(buf, scratch[0]);
}

int main(void) {
    for (int trial = 0; trial < 2; trial++) {
        int value = trial ? 7 : 0;
        void *buf[32] = {0};
        volatile int local = 42;
        int result = recomp_sj_setjmp(buf);
        if (result == 0) jump_back(buf, value);
        if (result != (value ? value : 1) || local != 42) return 1;
    }
    puts("ARM64 nonlocal jump passed");
    return 0;
}
