"""Host guest pointers must preserve all 39 address bits of the NVN window."""

import re
import subprocess
import tempfile
from pathlib import Path


root = Path(__file__).resolve().parents[1]
header = (root / "host/hos.h").read_text()
gp = re.search(r"^#define GP\(a\).*", header, re.M)
assert gp
start = header.index("static inline void *hos_guest_range(")
end = header.index("\n}", start) + 2
source = f"""
#include <assert.h>
#include <stdint.h>
#define A64_MEM ((uint8_t *)0x100000000000ULL)
#define HOS_SPACE_END (1ULL << 39)
{gp.group()}
{header[start:end]}
int main(void) {{
    const uint64_t addr = (1ULL << 32) + 0x1234;
    assert((uintptr_t)GP(addr) == 0x100000000000ULL + addr);
    assert((uintptr_t)hos_guest_range(addr, 16) == 0x100000000000ULL + addr);
    assert(!hos_guest_range(HOS_SPACE_END - 8, 16));
    return 0;
}}
"""
with tempfile.TemporaryDirectory() as tmp:
    exe = Path(tmp) / "pointer_width"
    subprocess.run(["cc", "-x", "c", "-", "-o", str(exe)], input=source, text=True, check=True)
    subprocess.run([str(exe)], check=True)
print("PASS: host guest pointers retain addresses above 4 GB")
