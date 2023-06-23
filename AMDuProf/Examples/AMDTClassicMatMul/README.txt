INTRODUCTION:
-------------
This is a "Textbook" implementation of matrix multiply.
The purpose of this program is to demonstrate measurement
and analysis of program performance using AMD uProf tool.
All engineers are familiar with simple matrix multiplication,
so this example should be easy to understand.

This implementation of matrix multiplication is a direct
translation of the "classic" textbook formula for matrix multiply.
Performance of the classic implementation is affected by an
inefficient data access pattern, which we should be able to
identify using AMD uProf tool.

Improved implementation of matrix multiplication interchanges the nesting
of innermost loops to improve the data access pattern. DC (Data Cache) and
Data Translation Lookaside Buffer (DTLB) misses should be reduced.


USAGE:
------
AMDTClassicMatMul       // Without any argument invokes inefficient implementation of matrix multiplication
AMDTClassicMatMul -c    // Invokes classic textbook implementation of matrix multiplication
AMDTClassicMatMul -i    // Invokes improved implementation of matrix multiplication
AMDTClassicMatMul -h    // Display help


PREBUILT BINARY:
----------------
This example comes with pre-built binary so that one can
quickly start profiling without first compiling the example
program. The pre-built binary can be found at:

For Windows: <uProf-Install-Dir>\Examples\AMDTClassicMatMul\bin\AMDTClassicMatMul.exe
For Linux  : <uProf-Install-Dir>/Examples/AMDTClassicMatMul/bin/AMDTClassicMatMul-bin

Note: Pre-built binaries might not work well for source view
during report generation, as the source path of the pre-built
binary might not match with the source file path on the profiling
system. For better results, it is recommeded to compile the
sample program before using it for profiling.


HOWTO BUILD ON WINDOWS:
-----------------------
Use the out of box AMDTClassicMatMulVS2015.sln for which you need
Visual Studio 2015. You can use any version of Visual Studio, but
in that case you may need to migrate the solution file to the target
Visual Studio version. To compile using any other compiler use the
source file: AMDTClassicMatMul.cpp


HOWTO BUILD ON LINUX:
---------------------
It comes with Makefile. You need to have 'make' and 'g++' to compile.
To compile using any other compiler use the source file: AMDTClassicMatMul.cpp

