# Experimental Radxa native CPU integration

This fork carries the Linux ARM64 host bridge for NxNative and the Hookshot Vulkan path on the Radxa Dragon Q6A (Adreno 643). The integration release and pinned source revisions are maintained in `maci0/snapdragon-nx`.

The CPU runs rewritten AArch64 code natively. Vulkan translates the guest GPU work, including task/mesh fallback to compute. This is not full-speed support: correct house-scene gameplay is roughly 6–7 fps at 1920×1080 presentation, with 854×480 internal rendering and a larger game resolve target. Sustained 1080p/60fps remains unmet.

Included work covers dma-buf-only imports, native host loading and guest pointer width, ARM64 signal/setjmp handling, atomic compatibility, GPU profiling attribution, overlapping global-table coalescing, immediate predicate-mask folding and mesh output word stores. The latter two remain experimental: predicate folding reduces SPIR-V size without a demonstrated gameplay gain; the mesh-store trial reduced its main dispatch from about 27.6 to 24.4 ms in one comparison.

The refreshed integration on upstream `1ea715d` passes 554 source checks, zero failures, 32 skipped. The hardware measurements were made on the previous integration base; the refreshed renderer and native host both built successfully after an initial reboot. The final copied-save smoke reached the HUD but showed a black scene and unbound storage-buffer warnings; the earlier renderer was restored. This is not a verified deployment. The smoke used the existing older Hookshot executable with the refreshed libraries, so it does not isolate which component or version mismatch caused the failure. Windows, macOS and other GPU families have not been validated for the native port. Audio/H.264 Linux backends are incomplete and diagnostic runs disable audio.

An unfinished global table lookup prototype is retained only as a patch in `docs/experiments/`; it is not enabled or compiled into this release. No game dumps, generated game code, private shader captures or keys are included.
