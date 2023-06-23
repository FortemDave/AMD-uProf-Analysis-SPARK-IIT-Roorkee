//==================================================================================
// Copyright (c) 2016 - 2018 , Advanced Micro Devices, Inc.  All rights reserved.
//
/// \author AMD Developer Tools Team
/// \file ClassicCpuProfileCtrl.cpp
///
//==================================================================================

// The purpose of this program is to demonstrate the use of 
// CPU Profile control APIs to provide the option to restrict
// the profiling to a specific part of the code.

// In this program, the CPU Profiler is restricted to the execution of classic_multiply_matrices() function.

// This program illustrates simple matrix multiplication.

// Disable MS compiler warnings:
#ifdef _MSC_VER
#define _CRT_SECURE_NO_WARNINGS
#endif

#include <cstdlib>
#include <cstdio>

// Include controller API header file.
#include <AMDProfileController.h>


static const int ROWS = 1000;     // Number of rows in each matrix
static const int COLUMNS = 1000;  // Number of columns in each matrix

float matrix_a[ROWS][COLUMNS];    // Left matrix operand
float matrix_b[ROWS][COLUMNS];    // Right matrix operand
float matrix_r[ROWS][COLUMNS];    // Matrix result

void initialize_matrices()
{
    // Define initial contents of the matrices
    for (int i = 0; i < ROWS; i++)
    {
        for (int j = 0; j < COLUMNS; j++)
        {
            matrix_a[i][j] = (float)rand() / RAND_MAX;
            matrix_b[i][j] = (float)rand() / RAND_MAX;
            matrix_r[i][j] = 0.0;
        }
    }
}

void classic_multiply_matrices()
{
    // Resume the CPU profiler
    amdProfileResume();

    // Multiply the two matrices
    for (int i = 0; i < ROWS; i++)
    {
        for (int j = 0; j < COLUMNS; j++)
        {
            float sum = 0.0;

            for (int k = 0; k < COLUMNS; k++)
            {
                sum = sum + matrix_a[i][k] * matrix_b[k][j];
            }

            matrix_r[i][j] = sum;
        }
    }

    //Pause the CPU profiler
    amdProfilePause();
}

void printHeader()
{
    printf("\nMatrix multiplication sample\n");
    printf("============================\n");
}

int main(int argc, char* argv[])
{
    printHeader();

    // Initialize the matrices
    printf("Initializing matrices\n");
    initialize_matrices();

    // Multiply the matrices
    printf("Multiplying matrices\n");
    classic_multiply_matrices();

    return 0;
}

