"""R2P immediate masks leave unselected state alone without emitting updates."""
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
    source = (args.source / "gpu/vk/eden/shader_recompiler/frontend/maxwell/translate/impl/move_register_to_predicate.cpp").read_text()
    body = source[source.index("enum class Mode"):source.index("} // Anonymous namespace")]
    fixture = r'''
#include <array>
#include <bit>
#include <cassert>
#include <cstdint>
#include <stdexcept>
#include "common/bit_field.h"
using u32 = uint32_t;
using u64 = uint64_t;
using LogicError = std::logic_error;
namespace IR {
using Reg = u64;
struct Pred { u32 index; };
struct Value {
    u32 value; bool immediate;
    bool IsImmediate() const { return immediate; }
    u32 U32() const { return value; }
};
using U32 = Value;
struct U1 { bool value; };
struct IREmitter {
    std::array<bool,7> predicates{};
    std::array<bool,4> flags{};
    unsigned writes = 0, immediate_zero_ops = 0;
    U32 Imm32(u32 v) { return {v,true}; }
    U1 Imm1(bool v) { return {v}; }
    U32 BitFieldExtract(U32 v, U32 offset, U32 count, bool sign) {
        assert(count.value == 1 && offset.value < 32 && !sign);
        return {(v.value >> offset.value) & 1, v.immediate};
    }
    U1 GetZeroFromOp(U32 v) { immediate_zero_ops += v.immediate; return {v.value == 0}; }
    U1 LogicalNot(U1 v) { return {!v.value}; }
    U1 Select(U1 c, U1 a, U1 b) { return c.value ? a : b; }
    U1 GetPred(Pred p) { return {predicates[p.index]}; }
    void SetPred(Pred p, U1 v) { predicates[p.index] = v.value; ++writes; }
    U1 GetZFlag() { return {flags[0]}; }
    U1 GetSFlag() { return {flags[1]}; }
    U1 GetCFlag() { return {flags[2]}; }
    U1 GetOFlag() { return {flags[3]}; }
    void SetZFlag(U1 v) { flags[0] = v.value; ++writes; }
    void SetSFlag(U1 v) { flags[1] = v.value; ++writes; }
    void SetCFlag(U1 v) { flags[2] = v.value; ++writes; }
    void SetOFlag(U1 v) { flags[3] = v.value; ++writes; }
};
}
struct TranslatorVisitor {
    IR::IREmitter ir;
    u32 source;
    IR::U32 X(IR::Reg r) { assert(r == 17); return {source,false}; }
};
'''
    fixture += body + r'''
int main() {
    const u32 patterns[] = {0,1,0x55,0xaa,0xff,0x80};
    for (bool cc : {false,true})
    for (bool immediate : {false,true})
    for (u32 mask = 0; mask < 256; ++mask)
    for (u32 byte = 0; byte < 4; ++byte)
    for (u32 old : patterns)
    for (u32 bits : patterns) {
        TranslatorVisitor v{};
        // Neighbouring bytes differ so selector bugs cannot hide.
        v.source = (0xa55aa55au & ~(0xffu << (byte * 8))) | (bits << (byte * 8));
        for (u32 i = 0; i < 7; ++i) v.ir.predicates[i] = (old >> i) & 1;
        for (u32 i = 0; i < 4; ++i) v.ir.flags[i] = (old >> i) & 1;
        const u64 insn = (u64{17} << 8) | (u64{cc} << 40) | (u64{byte} << 41);
        R2P(v, insn, {mask,immediate});
        const u32 n = cc ? 4 : 7;
        const u32 selected = mask & ((1u << n) - 1);
        const u32 expected = (old & ~selected) | (bits & selected);
        for (u32 i = 0; i < 7; ++i)
            assert(v.ir.predicates[i] == bool(((cc ? old : expected) >> i) & 1));
        for (u32 i = 0; i < 4; ++i)
            assert(v.ir.flags[i] == bool(((cc ? expected : old) >> i) & 1));
        assert(v.ir.writes == (immediate ? std::popcount(selected) : n));
        if (immediate) assert(v.ir.immediate_zero_ops == 0);
    }
}
'''
    with tempfile.TemporaryDirectory() as tmp:
        cpp, exe = Path(tmp) / "r2p.cpp", Path(tmp) / "r2p"
        cpp.write_text(fixture)
        subprocess.run([args.cxx, "-std=c++20", "-O1", "-Wall", "-Wextra", "-Werror",
                        "-I" + str(args.source / "gpu/vk/compat"), str(cpp), "-o", str(exe)], check=True)
        subprocess.run([str(exe)], check=True)
    print("PASS: PR/CC, every mask and byte selector, immediate and dynamic state; no masked-out updates")


if __name__ == "__main__":
    main()
