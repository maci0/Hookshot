"""A full GPU timestamp pool must not charge untimed draws to the previous program."""
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
    source = (ROOT / "gpu/vk/vk_gprof.cpp").read_text()
    functions = source[source.index("void gprof_end("):source.index("void gprof_collect(")]
    fixture = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>
#include <utility>
using VkCommandBuffer = int;
constexpr uint32_t kQ = 8;
struct Span {
    std::string label;
    uint32_t qb = 0, qe = 0;
    int items = 1;
    uint64_t bytes = 0;
    bool nested = false;
};
struct Stream {
    uint32_t nq = 0;
    int outer = 0, run = -1;
    uint64_t run_key = 0;
    std::vector<Span> spans{Span{}};
} stream;
int64_t dropped = 0;
int level() { return 2; }
Stream* find(VkCommandBuffer cmd) { return cmd ? &stream : nullptr; }
uint32_t stamp(Stream& st, VkCommandBuffer) { assert(st.nq < kQ); return st.nq++; }
'''
    fixture += functions + r'''
int main() {
    gprof_run(0, 11);
    assert(stream.run == -1);
    gprof_run(1, 11);
    const int first = stream.run;
    gprof_run(1, 11);
    assert(stream.spans[first].items == 2 && stream.nq == 1);
    gprof_run(1, 22);
    const int second = stream.run;
    assert(stream.spans[first].qe == 1 && stream.spans[second].qb == 1);
    stream.nq = kQ - 2; // Other work used the remaining queries.
    gprof_run(1, 33);
    assert(stream.run == -1 && dropped == 1);
    assert(stream.spans[second].qe == kQ - 2 && stream.nq == kQ - 1);
    gprof_run(1, 44);
    assert(dropped == 2 && stream.nq == kQ - 1);
    gprof_end(1, "pass", 5, 0);
    assert(stream.nq == kQ && stream.spans[0].qe == kQ - 1);
    assert(stream.spans[second].qe == kQ - 2); // Pass end must not extend this program.
    assert(stream.spans.size() == 3);
    stream = Stream{};
    stream.nq = kQ - 2;
    gprof_run(1, 55); // Exhaustion before any program run was opened.
    assert(stream.run == -1 && stream.nq == kQ - 2 && dropped == 3);
    gprof_end(1, "pass", 1, 0);
    assert(stream.nq == kQ - 1);
}
'''
    with tempfile.TemporaryDirectory() as tmp:
        cpp = Path(tmp) / "test.cpp"
        exe = Path(tmp) / "test"
        cpp.write_text(fixture)
        subprocess.run([args.cxx, "-std=c++17", "-Wall", "-Wextra", "-Werror",
                        str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
    print("PASS: exhausted GPU queries close the previous program and preserve the pass end")


if __name__ == "__main__":
    main()
