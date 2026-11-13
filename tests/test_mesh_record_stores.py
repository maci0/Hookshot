"""Word-striped fallback output keeps every corner record and writes each word once."""
from pathlib import Path
import random


def main():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'gpu/vk/eden/shader_recompiler/backend/spirv/emit_spirv_mesh.cpp').read_text()
    body = source[source.index('void MeshFallbackEpilogue('):source.index('void StorePosition(')]
    for contract in ('OpLoopMerge(done, next', 'ctx.OpIMul(ctx.U32[1], taken, ctx.Const(words))',
                     'ctx.OpIAdd(ctx.U32[1], first, at)', 'ctx.OpUDiv(ctx.U32[1], at, ctx.Const(words))',
                     'ctx.OpUMod(ctx.U32[1], at, ctx.Const(words))',
                     'ctx.OpIAdd(ctx.U32[1], record, ctx.Const(4U))',
                     'ctx.OpUDiv(ctx.U32[1], record, ctx.Const(corners))',
                     'ctx.Const(std::max(ctx.mesh_threads, 1U))'):
        assert contract in body, contract
    assert 'AddLocalVariable' not in body
    rng = random.Random(291)
    for corners in (1, 2, 3):
        for vertices, primitives in ((1, 1), (33, 35), (64, 126)):
            for vl, pl in ((0, 0), (1, 0), (21, 0), (0, 3), (7, 5)):
                words = 1 + vl + pl
                primitive_base = ((vertices + 31) // 32) * vl * 32
                attrs = [rng.getrandbits(32) for _ in range(
                    primitive_base + ((primitives + 31) // 32) * pl * 32)]
                # Reused and out-of-range indices exercise the same vertex clamp.
                indices = [rng.randrange(vertices + 3) for _ in range(primitives * corners)]
                for count in (0, 1, primitives):
                    expected = []
                    for primitive in range(count):
                        for corner in range(corners):
                            vertex = min(indices[primitive * corners + corner], vertices - 1)
                            expected.append(1)
                            expected.extend(attrs[(vertex // 32) * vl * 32 + vertex % 32 + line * 32]
                                            for line in range(vl))
                            expected.extend(attrs[primitive_base + (primitive // 32) * pl * 32
                                                  + primitive % 32 + line * 32] for line in range(pl))
                    for threads in (1, 32, 64, 128):
                        result = [None] * len(expected)
                        for lane in range(threads):
                            for at in range(lane, count * corners * words, threads):
                                record, line = divmod(at, words)
                                assert result[at] is None
                                if line == 0:
                                    value = 1
                                elif line <= vl:
                                    vertex = min(indices[record], vertices - 1)
                                    value = attrs[(vertex >> 5) * vl * 32 + (vertex & 31) + (line - 1) * 32]
                                else:
                                    primitive = record // corners
                                    value = attrs[primitive_base + (primitive >> 5) * pl * 32
                                                  + (primitive & 31) + (line - 1 - vl) * 32]
                                result[at] = value
                        assert result == expected
    print('PASS: point/line/triangle record words, empty/full outputs, attributes and lane coverage')


if __name__ == '__main__':
    main()
