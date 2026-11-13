"""Global table coalescing preserves ordered bindings and descriptor limits."""
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
    source = (args.source / "gpu/vk/eden/shader_recompiler/frontend/maxwell/translate_program.cpp").read_text()
    start = source.index("void AddGlobalTables(")
    body = source[start:source.index("\nvoid AddNVNStorageBuffers(", start)]
    fixture = r'''
#include <algorithm>
#include <array>
#include <cassert>
#include <cstdint>
#include <set>
#include <utility>
#include <vector>
using u32 = uint32_t;
using std::size_t;
enum class Stage { Compute, Task, Mesh, Fragment };
namespace Optimization { u32 g_nvn2_compute_layout_end = 0; }
struct Descriptor { u32 cbuf_index, cbuf_offset, count; bool is_written; };
struct Info {
    static constexpr size_t MAX_SSBOS = 128;
    static constexpr u32 kGlobalTableSize = 16;
    std::vector<Descriptor> storage_buffers_descriptors;
    std::array<std::pair<u32,u32>,4> global_tables{};
    u32 num_global_tables = 0;
    bool stores_global_memory = false, uses_global_memory = false;
    std::array<u32,32> constant_buffer_used_sizes{};
};
namespace IR { struct Program { Stage stage = Stage::Fragment; Info info; }; }
'''
    fixture += body + r'''
using Slot = std::pair<u32,u32>;
std::vector<Slot> unique_slots(const std::vector<Descriptor>& descriptors, size_t first = 0) {
    std::set<Slot> seen;
    std::vector<Slot> result;
    for (size_t i = first; i < descriptors.size(); ++i)
        for (u32 k = 0; k < descriptors[i].count; ++k) {
            Slot slot{descriptors[i].cbuf_index, descriptors[i].cbuf_offset + k * 16};
            if (seen.insert(slot).second) result.push_back(slot);
        }
    return result;
}
void check(std::initializer_list<Slot> tables, size_t expected, u32 entries) {
    IR::Program p;
    p.info.stores_global_memory = true;
    // Existing precise bindings must not merge with a global table.
    p.info.storage_buffers_descriptors.push_back({4,0x40,1,false});
    std::vector<Descriptor> original;
    for (auto slot : tables) {
        p.info.global_tables[p.info.num_global_tables++] = slot;
        original.push_back({slot.first,slot.second,16,true});
    }
    AddGlobalTables(p);
    const auto& ds = p.info.storage_buffers_descriptors;
    assert(ds.size() == expected + 1);
    assert(ds[0].count == 1 && !ds[0].is_written);
    assert(unique_slots(ds,1) == unique_slots(original));
    u32 total = 0;
    for (size_t i = 1; i < ds.size(); ++i) {
        assert(ds[i].is_written && ds[i].count > 1);
        total += ds[i].count;
    }
    assert(total == entries);
}
int main() {
    check({{4,0x40},{4,0x80},{4,0xe0},{4,0x120}}, 1, 30);
    check({{4,0x40},{4,0x40}}, 1, 16);
    check({{4,0x40},{4,0x140}}, 1, 32);
    check({{4,0x40},{4,0x150}}, 2, 32); // Gap.
    check({{4,0x40},{5,0x80}}, 2, 32);  // Different bank.
    check({{4,0x40},{4,0x48}}, 2, 32);  // Different slot alignment.
    check({{4,0x80},{4,0x40}}, 2, 32);  // Keep unsorted priority.
    check({}, 0, 0);
    IR::Program p;
    p.stage = Stage::Mesh;
    p.info.uses_global_memory = true;
    p.info.global_tables[0] = {0,0x880};
    p.info.num_global_tables = 1;
    AddGlobalTables(p);
    assert(p.info.storage_buffers_descriptors.size() == 2);
    assert(p.info.storage_buffers_descriptors[1].count == 3);
    assert(p.info.constant_buffer_used_sizes[0] == 0x8b0);
    p.info.storage_buffers_descriptors.resize(Info::MAX_SSBOS);
    AddGlobalTables(p);
    assert(p.info.storage_buffers_descriptors.size() == Info::MAX_SSBOS);
    // The last slot is available to a table; the fallback must not overflow.
    p.info.storage_buffers_descriptors.resize(Info::MAX_SSBOS - 1);
    AddGlobalTables(p);
    assert(p.info.storage_buffers_descriptors.size() == Info::MAX_SSBOS);
}
'''
    with tempfile.TemporaryDirectory() as tmp:
        cpp, exe = Path(tmp) / "tables.cpp", Path(tmp) / "tables"
        cpp.write_text(fixture)
        subprocess.run([args.cxx, "-std=c++20", "-Wall", "-Wextra", "-Werror", str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
    print("PASS: overlapping tables preserve ordered slots, write policy, fallback and capacity")


if __name__ == "__main__":
    main()
