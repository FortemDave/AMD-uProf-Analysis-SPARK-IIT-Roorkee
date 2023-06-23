#=====================================================================
# Copyright 2021 (c), Advanced Micro Devices, Inc. All rights reserved.
#
# AMDOSFeaturesWin.py - Utility functions to access OS specific features
#
# Developed by AMDuProf Profiler team.
#=====================================================================
import os
import sys
import struct
import glob
import ast
import ctypes
from os import path
from AMDClassDefinition import AMDuProfInterface

import AMDUtils as utils
import AMDClassDefinition as classDefs
import AMDCpuFeatures as cpuFeatures

TSCClock = 0x00000010

g_runinfo = classDefs.RunInfo()

def OsIsL3SliceThreadAvailable():
    return True

def ReadMSR(msr, cpu=0):

    return 0x0

def GetTsc(cpu):
    return 0x0

def CheckPerfEventParanoid():
    return True

def CheckNMIWatchdog(isUncoreDriver = True):
    if utils.IsLinux():
        nmi_watchdog = utils.ReadTextFromFile("/proc/sys/kernel/nmi_watchdog")
        if(nmi_watchdog == '1'):
            print("Warning: NMI watchdog is enabled and it uses one Core PMC counter. To make use of all the Core PMC counters, run the following command")
            print("sudo sh -c \'echo 0 > /proc/sys/kernel/nmi_watchdog\'")

def SetMultiplexingInterval(ms, typeStr):

    return False

def GetCpuMaxFreq():
    return 0

def GetL3CoreMask():
    l3Mask = ''

    for coresList in g_runinfo.ccxCores:
        l3Mask = ",".join((l3Mask, str(coresList[0])))

    return l3Mask[1:]

def GetDFCoreMask():
    dfMask = ''

    for coresList in g_runinfo.socketCores:
        dfMask = ",".join((dfMask, str(coresList[0])))
    return dfMask[1:]

def GetIODCoreMask(runInfo):
    # For Zen2/3, IOD is per socket
    return g_runinfo.sockets

def IsValidIRPERF():
    return True

def IsValidAPERF():
    return True

def IsValidMPERF():
    return True

def IsIRPERFEnabled():
    return g_runinfo.isIrperfAvailable

def IsAPERFEnabled():
    return g_runinfo.isAperfAvailable

def IsMPERFEnabled():
    return g_runinfo.isMperfAvailable

#TODO: we need to use this fucntion for Linux as well.
def PrepareRunInfo(isSystemInfo=False):
    global g_runinfo

    # Using AMDuProfPcm -n command to get the system topology
    amdTopologyCmd = ''
    amdSystemInfoCmd = ''
    isSMT = False

    uProfObj = AMDuProfInterface()
    amdTopologyCmd = uProfObj.getPcmPath() + " -n"
    amdSystemInfoCmd = uProfObj.getCLIPath() + " info --system"

    cpuTopology = utils.GetCmdOutput(amdTopologyCmd)
    systemInfo = utils.GetCmdOutput(amdSystemInfoCmd)

    if 'not recognized as an internal or external' in cpuTopology:
        print('Error: Not able to execute the command: ', amdTopologyCmd)
        sys.exit()

    if 'not recognized as an internal or external' in systemInfo:
        print('Error: Not able to execute the command: ', amdSystemInfoCmd)
        sys.exit()

    for line in systemInfo.split('\n'):
        if 'APERF & MPERF' in line:
            if 'Yes' == line.split(':')[1].strip():
                g_runinfo.isAperfAvailable = True
                g_runinfo.isMperfAvailable = True

        if 'IRPERF' in line:
            if 'Yes' == line.split(':')[1].strip():
                g_runinfo.isIrperfAvailable = True

        if 'SMT Enabled' in line:
            if 'Yes' == line.split(':')[1].strip():
                isSMT = True

        if 'Total number of Threads' in line:
            g_runinfo.totalCores = int(line.split(':')[1].strip())

        if 'Threads per Package' in line:
            g_runinfo.threadPerSocket = int(line.split(':')[1].strip())

        g_runinfo.coresPerSocket = g_runinfo.threadPerSocket if not isSMT else (g_runinfo.threadPerSocket//2)

        if 'IRPERF' in line:
            g_runinfo.isIRPERF = line.split(':')[1].strip()

    # Always available since it is read from driver
    g_runinfo.isL3SliceIdThreadMaskAvailable = True
    
    if isSystemInfo == False:
        g_runinfo.isIRPERF = True

    PcmRequiredAttr = ("package","ccd","thread")
    for line in cpuTopology.split('\n'):

        if "-" in line:
            continue

        #check for header
        if any(elem in line.lower() for elem in PcmRequiredAttr):
            # locate index of required attributes
            PcmHeader = list(map(str.lower, line.split()))
            AttrIdxList = [PcmHeader.index(attr) for attr in PcmRequiredAttr]
            continue

        curDataList = line.split()

        # change here if more attributes are required
        curSocket, curCcx, curThread = [int(curDataList[idx]) for idx in AttrIdxList]

        # FIXME: Fails when some cores are offline
        if len(g_runinfo.socketCores) == curSocket:
            g_runinfo.socketCores.append([curThread])
        else:
            g_runinfo.socketCores[curSocket].append(curThread)
        if len(g_runinfo.ccxCores) == curCcx:
            g_runinfo.ccxCores.append([curThread])
        else:
            g_runinfo.ccxCores[curCcx].append(curThread)

    g_runinfo.sockets = len(g_runinfo.socketCores)
    g_runinfo.ccxs = len(g_runinfo.ccxCores)
    g_runinfo.family, g_runinfo.model = cpuFeatures.GetFamilyModel()
    g_runinfo.family = int(g_runinfo.family, 16)
    g_runinfo.model = int(g_runinfo.model, 16)
    g_runinfo.umcCount = 2 * g_runinfo.sockets
    return g_runinfo

def GetRunInfo():
    return g_runinfo

