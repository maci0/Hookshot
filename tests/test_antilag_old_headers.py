"""Headers without VK_AMD_anti_lag still provide every public Anti-Lag entry point."""
import argparse
from pathlib import Path
import subprocess
import tempfile

RUN_ALL_ARGS = ["--cxx", "{cxx}"]
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="c++")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        for name in ("vk_antilag.cpp", "vk_antilag.h"):
            (folder / name).write_text((ROOT / "gpu/vk" / name).read_text())
        # No extension macro or AMD types, as with older Vulkan headers.
        (folder / "vk_internal.h").write_text("struct VkExtensionProperties {};\n")
        (folder / "vk_menu.h").write_text("")
        (folder / "test.cpp").write_text(r'''
#include "vk_antilag.h"
#include <cassert>
int main() {
    using namespace mkwvk;
    std::vector<const char*> wanted{"existing"};
    std::vector<VkExtensionProperties> available;
    void* next = nullptr;
    void** tail = &next;
    antilag_device_extensions(wanted, available);
    antilag_device_features(tail);
    antilag_device_created();
    assert(wanted.size() == 1 && tail == &next && next == nullptr);
    assert(!antilag_available() && antilag_frame() == 0);
    assert(antilag_present_frame == kAntiLagThisFrame);
    antilag_present_frame = 42;
    antilag_present();
    antilag_input();
    assert(antilag_frame() == 0);
}
''')
        exe = folder / "test"
        subprocess.run([args.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror",
                        str(folder / "vk_antilag.cpp"), str(folder / "test.cpp"),
                        "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
    print("PASS: old-header Anti-Lag API links and stays disabled")


if __name__ == "__main__":
    main()
