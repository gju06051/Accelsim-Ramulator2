#ifndef SG_ACCELSIM_ATOMIC_H
#define SG_ACCELSIM_ATOMIC_H

#include <stdint.h>

__device__ __forceinline__ void sg_atomic_add_u32(uint32_t *addr, uint32_t value)
{
    uint32_t old = atomicAdd(addr, value);
    asm volatile("" :: "r"(old));
}

__device__ __forceinline__ void sg_atomic_sub_u32(uint32_t *addr, uint32_t value)
{
    uint32_t old = atomicSub(addr, value);
    asm volatile("" :: "r"(old));
}

__device__ __forceinline__ void sg_atomic_min_u32(uint32_t *addr, uint32_t value)
{
    uint32_t old = atomicMin(addr, value);
    asm volatile("" :: "r"(old));
}

#endif
