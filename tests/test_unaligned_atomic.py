"""The packed OoT refcount must add atomically at an odd guest address on ARM64."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "nx2"), str(ROOT / "third_party/a64-kit/lift")]
import insn

assert "a64_unaligned_fetch_add32" in insn.lse(0xb8ea0129)
cc = shutil.which("clang") or shutil.which("cc")
if not cc:
    print("SKIP: no C compiler")
    raise SystemExit(0)

source = r"""
#include <assert.h>
#include <pthread.h>
#include <stdint.h>
#include <string.h>
uint32_t a64_unaligned_fetch_add32(void *, uint32_t);
static unsigned char bytes[8];
static void *add_many(void *unused) {
    (void)unused;
    for (int i = 0; i < 10000; i++) a64_unaligned_fetch_add32(bytes + 1, 1);
    return 0;
}
int main(void) {
    uint32_t n = UINT32_MAX;
    memcpy(bytes + 1, &n, 4);
    assert(a64_unaligned_fetch_add32(bytes + 1, 1) == UINT32_MAX);
    memcpy(&n, bytes + 1, 4);
    assert(n == 0);
    pthread_t threads[4];
    for (int i = 0; i < 4; i++) assert(!pthread_create(&threads[i], 0, add_many, 0));
    for (int i = 0; i < 4; i++) assert(!pthread_join(threads[i], 0));
    memcpy(&n, bytes + 1, 4);
    assert(n == 40000);
}
"""
with tempfile.TemporaryDirectory() as tmp:
    src, exe = Path(tmp) / "test.c", Path(tmp) / "test"
    src.write_text(source)
    subprocess.run([cc, "-O2", "-pthread", str(src), str(ROOT / "nx2/rt/unaligned_atomic.c"), "-o", str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
print("PASS")
