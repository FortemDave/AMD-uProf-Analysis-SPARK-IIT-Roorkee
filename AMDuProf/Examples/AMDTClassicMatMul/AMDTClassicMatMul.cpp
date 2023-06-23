// AMDTClassicMatMul.cpp : "Textbook" implementation of matrix multiply
// Copyright (c) 2005-2018 Advanced Micro Devices, Inc.

// The purpose of this program is to demonstrate measurement
// and analysis of program performance using AMD uProf tool.
// All engineers are familiar with simple matrix multiplication,
// so this example should be easy to understand.
//
// This implementation of matrix multiplication is a direct
// translation of the "classic" textbook formula for matrix multiply.
// Performance of the classic implementation is affected by an
// inefficient data access pattern, which we should be able to
// identify using AMD uProf tool.
//
// Improved implementation of matrix multiplication interchanges the nesting
// of innermost loops to improve the data access pattern. DC (Data Cache) and
// Data Translation Lookaside Buffer (DTLB) misses should be reduced.

//  Usage:
//      AMDTClassicMatMul       // Without any argument invokes inefficient implementation of matrix multiplication
//      AMDTClassicMatMul -c    // Invokes classic textbook implementation of matrix multiplication
//      AMDTClassicMatMul -i    // Invokes improved implementation of matrix multiplication
//      AMDTClassicMatMul -h    // Display help
//


// Disable MS compiler warnings:
#ifdef _MSC_VER
    #define _CRT_SECURE_NO_WARNINGS
#endif

#ifdef WIN32
    #include <windows.h>
#else
    #include <unistd.h>
    #include <sys/types.h>
    #include <pwd.h>
#endif
#include <cstdlib>
#include <cstdio>
#include <ctime>
#include <string.h>
#include <time.h>

static const int ROWS = 500 ;     // Number of rows in each matrix
static const int COLUMNS = 500 ;  // Number of columns in each matrix

float matrix_a[ROWS][COLUMNS] ;    // Left matrix operand
float matrix_b[ROWS][COLUMNS] ;    // Right matrix operand
float matrix_r[ROWS][COLUMNS] ;    // Matrix result

FILE* result_file = nullptr;
const int AMDTMATMUL_MAX_PATH_LEN = 512;
bool get_temp_directory(char* tempPath);

void initialize_matrices()
{
    // Define initial contents of the matrices
    for (int i = 0 ; i < ROWS ; i++)
    {
        for (int j = 0 ; j < COLUMNS ; j++)
        {
            matrix_a[i][j] = (float) rand() / RAND_MAX ;
            matrix_b[i][j] = (float) rand() / RAND_MAX ;
            matrix_r[i][j] = 0.0 ;
        }
    }
}

void print_result()
{
    // Print the result matrix
    if (result_file)
    {
        for (int i = 0 ; i < ROWS ; i++)
        {
            for (int j = 0 ; j < COLUMNS ; j++)
            {
                fprintf(result_file, "%6.4f ", matrix_r[i][j]) ;
            }

            fprintf(result_file, "\n") ;
        }
    }
}

void classic_multiply_matrices()
{
    // Multiply the two matrices
    for (int i = 0 ; i < ROWS ; i++)
    {
        for (int j = 0 ; j < COLUMNS ; j++)
        {
            float sum = 0.0 ;

            for (int k = 0 ; k < COLUMNS ; k++)
            {
                sum = sum + matrix_a[i][k] * matrix_b[k][j] ;
            }

            matrix_r[i][j] = sum ;
        }
    }
}

void improved_multiply_matrices()
{
    // Multiply the two matrices
    for (int i = 0 ; i < ROWS ; i++)
    {
        for (int k = 0; k < COLUMNS; k++)
        {
            for (int j = 0 ; j < COLUMNS ; j++)
            {
                matrix_r[i][j] = matrix_r[i][j] + matrix_a[i][k] * matrix_b[k][j] ;
            }
        }
    }
}

void inefficient_multiply_matrices()
{
    // !!! Catch me if you can - doing some stupid things !!!
    for (int l = 0; l < 3; l++)
    {
        classic_multiply_matrices();
    }
}

void print_elapsed_time()
{
    double elapsed = 0.0;
    double resolution = 0.0;

    // Obtain and display elapsed execution time
    elapsed = (double)clock() / CLOCKS_PER_SEC;
    resolution = 1.0 / CLOCKS_PER_SEC;

    if (result_file)
    {
        fprintf(result_file, "Elapsed time: %8.4f sec (%6.4f sec resolution)\n", elapsed, resolution) ;
    }

    printf("Elapsed time: %8.4f sec (%6.4f sec resolution)\n", elapsed, resolution) ;
}

void printUsage()
{
    fprintf(stderr, "AMDTClassicMatMul [-c|-i|-h]\n");
    fprintf(stderr, "\t      Invoke inefficient implementation of matrix multiplication\n");
    fprintf(stderr, "\t-c    Invoke classic textbook implementation of matrix multiplication\n");
    fprintf(stderr, "\t-i    Invoke improved implementation of matrix multiplication\n");
    fprintf(stderr, "\t-h    Display help\n");
}


void printHeader()
{
    printf("\nMatrix multiplication sample\n");
    printf("============================\n");
}

int main(int argc, char* argv[])
{
    bool improved_classic = false;
    bool classic = false;

    // Parse command line arguments:
    if (argc == 2)
    {
        if (! strcmp("-i", argv[1]))
        {
            improved_classic = true;
        }
        else if (! strcmp("-c", argv[1]))
        {
            classic = true;
        }
        else if (!strcmp("-h", argv[1]))
        {
            printUsage();
            return (EXIT_FAILURE) ;
        }
    }

    // Print header to the console:
    printHeader();

    // Open the result file:
    char filePath[AMDTMATMUL_MAX_PATH_LEN] = {0};
    get_temp_directory(filePath);
    strcat(filePath, "AMDTClassicMatMul.txt");

    if ((result_file = fopen(filePath, "w")) == nullptr)
    {
        fprintf(stderr, "Couldn't open result file: %s\n", filePath) ;
        perror("AMDTClassicMatMul") ;
        //return (EXIT_FAILURE) ;
    }
    else
    {
        fprintf(result_file, "uProf classic matrix multiplication\n") ;
    }

    // Initialize the matrices:
    printf("Initializing matrices\n");
    initialize_matrices() ;

    // Multiply the matrices:
    printf("Multiplying matrices\n");

    // Doing some stupid things:
    if (false == classic && false == improved_classic)
    {
        printf("\nInvoke inefficient implementation of matrix multiplication\n");
        inefficient_multiply_matrices();
    }
    else if (true == classic)
    {
        printf("\nInvoke classic textbook implementation of matrix multiplication\n");
        classic_multiply_matrices() ;
    }
    else if (true == improved_classic)
    {
        printf("\nInvoke improved implementation of matrix multiplication\n");
        improved_multiply_matrices() ;
    }
    else
    {
        // Should never reach here
        return (EXIT_FAILURE) ;
    }

    print_elapsed_time() ;

    if (result_file)
    {
        fclose(result_file) ;
    }
}


bool get_temp_directory(char* tempPath)
{
    if (tempPath == nullptr)
    {
        return false;
    }

    tempPath[0] = 0;

#ifdef WIN32

    // Get Windows TEMP directory:
    GetEnvironmentVariableA("TEMP", tempPath, AMDTMATMUL_MAX_PATH_LEN);
    strcat(tempPath, "\\");

#else

    // Get the Linux user home directory:
    struct passwd* pw = getpwuid(getuid());

    if (pw != nullptr)
    {
        const char* homedir = pw->pw_dir;
        strcpy(tempPath, homedir);
        strcat(tempPath, "/");
    }
    else
    {
        strcpy(tempPath, "/tmp/");
    }

#endif

    return true;
}
