"""Exercise subgroup pinning without a GPU, including partially filled groups."""
from pathlib import Path
import subprocess
import tempfile

source = (Path(__file__).resolve().parents[1] / 'gpu/vk/vk_draw.cpp').read_text()
start = source.index('void pin_subgroup(')
end = source.index('\n}\n', start) + 2
program = r'''
#include <cstdint>
#include <cassert>
constexpr int VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_REQUIRED_SUBGROUP_SIZE_CREATE_INFO = 1;
constexpr unsigned VK_PIPELINE_SHADER_STAGE_CREATE_REQUIRE_FULL_SUBGROUPS_BIT = 1;
struct VkPipelineShaderStageRequiredSubgroupSizeCreateInfo { int type; unsigned requiredSubgroupSize = 0; };
struct VkPipelineShaderStageCreateInfo { unsigned stage, flags = 0; const void *pNext = nullptr; };
struct { unsigned sg32_stages = 1, sg64_stages = 2; struct { bool computeFullSubgroups = true; } vk13; } dev;
''' + source[start:end] + r'''
int main() {
    VkPipelineShaderStageCreateInfo a{1}, b{2}, c{2}, d{4};
    pin_subgroup(a, 32); pin_subgroup(b, 32); pin_subgroup(c, 64); pin_subgroup(d, 64);
    auto size = [](auto &s) { return static_cast<const VkPipelineShaderStageRequiredSubgroupSizeCreateInfo *>(s.pNext)->requiredSubgroupSize; };
    assert(size(a) == 32 && a.flags == 1);
    assert(size(b) == 64 && b.flags == 0);
    assert(size(c) == 64 && c.flags == 1);
    assert(!d.pNext && !d.flags);
    dev.vk13.computeFullSubgroups = false;
    VkPipelineShaderStageCreateInfo e{2}; pin_subgroup(e, 64);
    assert(size(e) == 64 && !e.flags);
}
'''
with tempfile.TemporaryDirectory() as directory:
    src = Path(directory) / 'pin.cpp'
    exe = Path(directory) / 'pin'
    src.write_text(program)
    subprocess.run(['c++', '-std=c++17', '-Wall', '-Werror', str(src), '-o', str(exe)], check=True)
    subprocess.run([str(exe)], check=True)
print('subgroup pin sizes, supported stages and full-group constraints pass')
