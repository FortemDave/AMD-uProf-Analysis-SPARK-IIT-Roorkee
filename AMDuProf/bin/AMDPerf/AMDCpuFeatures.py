#=====================================================================
# Copyright 2020 (c), Advanced Micro Devices, Inc. All rights reserved.
#
# AMDCpuFeatures.py - Utility functions to get the information about
#   CPU details and the availability of the CPU features.
#
# Developed by AMDuProf Profiler team.
#=====================================================================

import os
import sys
import platform
import subprocess
from pathlib import Path
import re
import multiprocessing

import AMDUtils as utils
import AMDOSFeatures as osFeatures

# MSR Addresses
AMD_HWCR_MSR = 0xC0010015
AMD_TSC_MSR = 0x00000010
AMD_P0STATE_MSR = 0xC0010064

# P-State Mask bits
AMD_PSTATE_CPUDID_MASK_17H = 0x3F00
AMD_PSTATE_CPUFID_MASK_17H = 0xFF
AMD_PSTATE_CPUDID_BITSHIFT_17H = 8

def GetFamilyModel():
    foundInfo = False
    family = 0
    model = 0

    if utils.IsWindows():
        uinfo = platform.uname()
        f = uinfo[5].split(" ")
        family = hex(int(f[2]))
        model = hex(int(f[4]))
    else:
        cpuinfoPath = Path("/proc/cpuinfo")
        all_info = cpuinfoPath.read_text()

        for line in all_info.split("\n"):
            if "cpu family" in line:
                family = hex(int(re.sub(".*cpu family.*:", "", line, 1)))
            elif "model" in line:
                model = hex(int(re.sub(".*model.*:", "", line, 1 )))
                foundInfo = True

            if foundInfo:
                break

    return family, model

def GetProcessorFamily():
    family, _= GetFamilyModel()
    return family

def GetProcessorModel():
    _, model = GetFamilyModel()
    return model

def GetOnlineCpu():
    return multiprocessing.cpu_count()

def IsZP():
    return CheckAMDProcessorFamilyModel(int('0x17', 16), int('0x0', 16), int('0x0f', 16))

def IsSSP():
    return CheckAMDProcessorFamilyModel(int('0x17', 16), int('0x30', 16), int('0x3f', 16))

#def GetPhysicalProcessorsCount():
#    # return multiprocessing.cpu_count()
#    return psutil.cpu_count(logical=True)
#
#def GetLogicalProcessorsCount():
#    return psutil.cpu_count(logical=False)
#
#def GetCpuFrequency():
#    # This returns the P0 State frequency ?
#    current, min, max = psutil.cpu_freq()
#    return max

def CheckAMDProcessorFamilyModel(family, modelLow, modelHigh):
    currentFamily, currentModel = GetFamilyModel()
    currentFamily = int(currentFamily, 16)
    currentModel = int(currentModel, 16)

    if currentFamily == family and modelLow <= currentModel <= modelHigh:
        return True

    return False

def IsMSRModuleLoaded():
    output = subprocess.getoutput('lsmod | grep msr')

    if ('msr' in output):
        return True

    return False

def IsLinuxPerfAvailable():
    """Checks if Linux perf is available.
    """
    try:
        subprocess.Popen(["perf"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).communicate()
    except OSError as e:
        if e.errno== os.errno.ENOENT:
            return False
    return True

def EnableIRPERF():
    hwConfig = AMD_HWCR_MSR
    irperfMask = (1 << 30)

    if not utils.HasRootPrivilege():
        print ('Error: Need root permission to execute this command')
        sys.exit()

    if not IsMSRModuleLoaded():
        print ('Error: MSR module is not loaded. use \'sudo modprobe msr\' to load msr module')
        sys.exit()

    if not osFeatures.IsIRPERFEnabled():
        for c in range(GetOnlineCpu()):
            value = osFeatures.ReadMSR(hwConfig, c)
            enabled = (value >> 30) & 1

            if not enabled:
                value |= irperfMask
                osFeatures.WriteMSR(hwConfig, value, c)

    print("IRPERF enabled")

    return True

