//==================================================================================
// Copyright (c) 2020, Advanced Micro Devices, Inc. All rights reserved.
//
/// \author AMD Developer Tools Team
/// \file collatz-sequence-omp-dyn.c
///
//==================================================================================

#include <stdio.h>
#include <stdint.h>
#include <omp.h>

#define MAX_NUM 100000000

uint32_t collatz_sequence_count(uint64_t n)
{
    uint32_t count = 0;

    while (n != 1)
    {
        n = (n & 1) ? (3 * n + 1) : (n / 2);
        ++count;
    }

    return count;
}

int main()
{
    uint32_t maxCount = 0;
    uint64_t num = 0;

    #pragma omp parallel for shared(maxCount, num) schedule(dynamic)
    for (uint64_t n = 2; n < MAX_NUM; ++n)
    {
        uint32_t count = collatz_sequence_count(n);

        if (count > maxCount)
        {
            maxCount = count;
            num = n;
        }
    }

    printf("Max Collatz sequence count %d found for the number %ld.\n", maxCount, num);
    return 0;
}
