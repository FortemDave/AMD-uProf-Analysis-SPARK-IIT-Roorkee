//==================================================================================
// Copyright (c) 2016- 2018 , Advanced Micro Devices, Inc.  All rights reserved.
//
/// \author AMD Developer Tools Team
/// \file AMDProfileController.h
///
//==================================================================================

// This file is the only header that must be included by an application that
// wishes to use AMD Profile Controller APIs.

#pragma once

#ifdef __cplusplus
extern "C" {
#endif

#define AMD_PROFILE_SUCCESS                             0
#define AMD_PROFILE_ERROR_INTERNAL                     -1
#define AMD_PROFILE_WARN_PROFILE_ALREADY_RESUMED       -2
#define AMD_PROFILE_WARN_PROFILE_ALREADY_PAUSED        -3
#define AMD_PROFILE_ERROR_INVALID_ARG                  -4

#if defined(_WIN32) || defined(__CYGWIN__)
#define AMDPROFILE_API_CALL __stdcall
#else
#define AMDPROFILE_API_CALL
#endif

/// Enum to define the profiling modes that can be paused or resumed
typedef enum
{
    AMD_PROFILE_CPU = 0x1,
    //AMD_PROFILE_POWER = 0x2
} amdProfileMode;

/// Instruct the profiler to stop profiling. Profiling can be resumed using amdProfileResume.
/// \return True on success and False on failure
extern bool AMDPROFILE_API_CALL amdProfilePause(unsigned int reserved = AMD_PROFILE_CPU);

/// Instruct the profiler to resume profiling. Profiling can be paused using amdProfilePause.
/// \return True on success and False on failure
extern bool AMDPROFILE_API_CALL amdProfileResume(unsigned int reserved = AMD_PROFILE_CPU);

/// Returns the last error code
extern int AMDPROFILE_API_CALL amdGetLastProfileError(void);

#ifdef __cplusplus
}
#endif
