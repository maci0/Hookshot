"""Per-program pointer tracking reaches graphics/mesh stages and unwinds on failure."""
import argparse
from pathlib import Path
import subprocess
import tempfile

RUN_ALL_ARGS = ["--cxx", "{cxx}"]
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cxx", default="c++")
    parser.add_argument("--source", type=Path, default=ROOT)
    args = parser.parse_args()
    source = (args.source / "gpu/vk/vk_shader.cpp").read_text()
    for entry in ("void translate_into(", "void translate_mesh_into("):
        body = source[source.index(entry):]
        prefix = body[:body.index("try {")]
        assert "ScopedGmPort gm_port{p.key};" in prefix, entry + " lacks a program-wide override"
    start = source.index("struct ScopedGmPort {")
    guard = source[start:source.index("\n};", start) + 3]
    # No stage-local assignment may override the scope or leak to the next program.
    assert source.count("g_gm_port_this =") == guard.count("g_gm_port_this =")
    fixture = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
namespace Shader::Optimization { thread_local bool g_gm_port_this = false; }
bool key_listed(const char* key, const char* env) {
    assert(!strcmp(env, "EDEN_NX2_GM_PORT_PROGS"));
    return !strcmp(key, "43ec86f35fd937b9");
}
void logf(const char*, ...) {}
'''
    fixture += guard + r'''
int main() {
    using Shader::Optimization::g_gm_port_this;
    { ScopedGmPort selected{0x43ec86f35fd937b9ULL};
      assert(g_gm_port_this);
      { ScopedGmPort other{0}; assert(!g_gm_port_this); }
      assert(g_gm_port_this);
    }
    assert(!g_gm_port_this);
    try { ScopedGmPort selected{0x43ec86f35fd937b9ULL}; throw 1; }
    catch (int) { assert(!g_gm_port_this); }
    { ScopedGmPort other{0}; assert(!g_gm_port_this); }
}
'''
    with tempfile.TemporaryDirectory() as tmp:
        cpp, exe = Path(tmp) / "scope.cpp", Path(tmp) / "scope"
        cpp.write_text(fixture)
        subprocess.run([args.cxx, "-std=c++17", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
    print("PASS: all program stages share the override; nesting and exceptions restore it")


if __name__ == "__main__":
    main()
