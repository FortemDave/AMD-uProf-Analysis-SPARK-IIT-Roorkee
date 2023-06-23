#=====================================================================
# Copyright 2020 (c), Advanced Micro Devices, Inc. All rights reserved.
#
# AMDOSFeatures.py - Utility functions to access OS specific features
#
# Developed by AMDuProf Profiler team.
#=====================================================================

import os
import sys
import struct
import glob
from pathlib import Path
import subprocess

import AMDUtils as utils
import AMDClassDefinition as classDefs
import AMDCpuFeatures as cpuFeatures

TSCClock = 0x00000010

g_runinfo = classDefs.RunInfo()

class OSPerfFeatures:
    def __init__(self):
        # if perf binary corresponding to the linux kernel version is not available
        # user can export env AMDPERF to perf binary at /usr/lib/linux-tools*/perf
        self.perf = os.getenv("AMDUPROFSYS_PERF")
        if not self.perf:
            self.perf = "perf"

        self.perfSupported = os.system(self.perf + " stat --log-fd 3 3>/dev/null true") == 0

        if not self.perfSupported:
            sys.exit("Either perf binary is missing or diabled - check /proc/sys/kernel/perf_event_paranoid")

def GetPerf():
    perf = os.getenv("AMDUPROFSYS_PERF")

    if not perf:
        perf = "perf"

    return perf

def OsIsL3SliceThreadAvailable():
    sliceIdFile = '/sys/devices/amd_l3/format/sliceid'
    sliceMaskFile = '/sys/devices/amd_l3/format/slicemask'
    threadMaskFile = '/sys/devices/amd_l3/format/threadmask'

    if Path(threadMaskFile).exists() and (Path(sliceIdFile).exists() or Path(sliceMaskFile).exists()):
        return True
    else:
        return False

def ReadMSR(msr, cpu=0):
    try:
        f = os.open('/dev/cpu/%d/msr' % (cpu,), os.O_RDONLY)
        os.lseek(f, msr, os.SEEK_SET)
    except OSError as err:
        # FIXME - This can fail is 'msr' module is not loaded - error message should be proper
        print('Error: Check if msr module os loaded. Use sudo modprobe msr to load msr module',err)
        sys.exit()

    val = struct.unpack('Q', os.read(f, 8))[0]
    os.close(f)

    return val

def GetTsc(cpu):
    return ReadMSR(TSCClock, cpu)

def WriteMSR(msr, val, cpu=0):
    f = os.open('/dev/cpu/%d/msr' % (cpu,), os.O_WRONLY)

    if f is not None:
        os.lseek(f, msr, os.SEEK_SET)
        os.write(f, struct.pack('Q', val))
        os.close(f)
    else:
        raise OSError("Error: The kernel module msr is not loaded (run modprobe msr).")

def WriteMSRAll(msr, val):
    n = glob.glob('/dev/cpu/[0-9]*/msr')

    for c in n:
        f = os.open(c, os.O_WRONLY)
        os.lseek(f, msr, os.SEEK_SET)
        os.write(f, struct.pack('Q', val))
        os.close(f)
    if not n:
        raise OSError("Error: The kernel module msr is not loaded (run modprobe msr).")

def CheckPerfEventParanoid():
    """
    Checks perf_event_paranoid bit.
    For unprivileged users profiling is only possible when perf_event_paranoid <= 0
    """
    perf_paranoid = utils.ReadTextFromFile("/proc/sys/kernel/perf_event_paranoid")
    if int(perf_paranoid) >= 1:
        print('The /proc/sys/kernel/perf_event_paranoid value is set', str(perf_paranoid) + '. Consider setting it to 0 or -1 by using the following command')
        print('sudo sh -c \'echo 0 >/proc/sys/kernel/perf_event_paranoid\'')
        sys.exit()


def CheckNMIWatchdog(isUncoreDriver = False):

    nmi_watchdog = utils.ReadTextFromFile("/proc/sys/kernel/nmi_watchdog")
    if(nmi_watchdog == '1'):
        print("Warning: NMI watchdog is enabled and it uses one Core PMC counter. To make use of all the Core PMC counters, run the following command")
        print("sudo sh -c \'echo 0 > /proc/sys/kernel/nmi_watchdog\'")
        if isUncoreDriver:
            # Exit if Uncore driver is being used.
            # remove this when nmi_watchdog is handled in uncore driver
            sys.exit()

def SetMultiplexingInterval(ms, typeStr):
    ret = False

    if(ms <= 0):
        print ('Invalid multiplexing sampling interval')
        sys.exit()

    if utils.HasRootPrivilege():

        if typeStr == 'core':
            cmd = 'echo ' + str(ms) + ' > /sys/devices/cpu/perf_event_mux_interval_ms'

        if typeStr == 'l3':
            cmd = 'echo ' + str(ms) + ' > /sys/devices/amd_l3/perf_event_mux_interval_ms'

        if typeStr == 'df':
            cmd = 'echo ' + str(ms) + ' > /sys/devices/amd_df/perf_event_mux_interval_ms'

        if typeStr == 'umc':
            # TODO: Environment variable can not be set. We may need to create a file to set
            # and read during collection
            cmd = 'export UMC_MULTIPLEX_INTERVAL=\"' + str(ms) +'\"'

        os.system(cmd)
        ret = True
        print('Multiplexing interval set to ' + str(ms) + 'ms')
    else:
        print('This option requires root privilege.')

    return ret

def GetCpuMaxFreq():
    raise NotImplementedError

def GetL3CoreMask():
    result = ''
    result = utils.ReadTextFromFile("/sys/bus/event_source/devices/amd_l3/cpumask")

    if ('-' in result):
        lscpu = utils.GetCmdOutput('lscpu -p')

        ccx = -1
        result = ''
        for ln in lscpu.split('\n'):
            if ln[0] == '#':
                continue

            ids = ln.split(',')
            ccsRead = int(ids[len(ids) -1])

            if (ccx != ccsRead) and (ccsRead > ccx):
               ccx = ccsRead
               result += ids[0] +','
        result = result[:-1]
    return result

def GetDFCoreMask():
    return utils.ReadTextFromFile("/sys/bus/event_source/devices/amd_df/cpumask")

def GetIODCoreMask(runInfo):
    # For Zen2/3, IOD is per socket
    return g_runinfo.sockets

# TODO: This function can be written common for Windows and Linux using AMDuProfCLI.
def PrepareRunInfo(isSystemInfo=False):
    global g_runinfo

    g_runinfo.isL3SliceIdThreadMaskAvailable = OsIsL3SliceThreadAvailable()

    lscpu = utils.GetCmdOutput("lscpu")
    numaString = []
    # TODO: need to findout number of UMCs
    g_runinfo.umcCount = 8

    # Check if IRPERF is accessible and enabled to count the retired instructions
    g_runinfo.isIRPERF = IsValidIRPERF()
    threadsPerCore = 0

    for line in lscpu.split('\n'):
        if(line.startswith('On-line')):
            cpuStr = line.split(':')[1].strip()

            if '-' in cpuStr:
                g_runinfo.totalCores = int(cpuStr.split('-')[1]) + 1
        elif(line.startswith('Socket(s)')):
            g_runinfo.sockets = int(line.split(':')[1].strip())

            for s in range(g_runinfo.sockets):
                g_runinfo.socketCores.append([])

        elif(line.startswith('NUMA node(s)')):
            g_runinfo.numaNodes = int(line.split(':')[1].strip())

            for s in range(g_runinfo.numaNodes):
                numaString.append('NUMA node'+str(s)+' CPU(s)')

        elif (line.startswith('Thread(s) per core')):
            threadsPerCore = int(line.split(':')[1].strip())

        elif (line.startswith('Core(s)')):
            g_runinfo.coresPerSocket = int(line.split(':')[1].strip())

        elif (line.startswith('CPU family')):
            g_runinfo.family = int(line.split(':')[1].strip())

        elif (line.startswith('Model:')):
            g_runinfo.model = int(line.split(':')[1].strip())

        elif (line.startswith('Model name')):
            g_runinfo.modelName = line.split(':')[1].strip()

        elif (line.startswith('CPU max MHz')):
            g_runinfo.cpuFreq = line.split(':')[1].strip()
        else:
            for s in numaString:
                if (line.startswith(s)):
                    g_runinfo.numaCores.append(line.split(':')[1].strip())

    cpuDir = '/sys/devices/system/cpu'
    entries = os.listdir(cpuDir)
    g_runinfo.threadPerSocket = threadsPerCore * g_runinfo.coresPerSocket

    for cpu in entries:
        cpuId = cpu[3:]
        if (utils.IsStrNumeric(cpuId)):
            # Check if CPU is online
            cpuOnlineFile = f'/sys/devices/system/cpu/cpu{cpuId}/online'
            if Path(cpuOnlineFile).exists():
                cpuState = utils.ReadTextFromFile(cpuOnlineFile)
                if cpuState == "0":
                    print(f"CPU {cpuId} is not online. Skipping...")
                    continue

            # Read ccx and socket id of current core
            L3SharedCpuList = utils.ReadTextFromFile(f"/sys/devices/system/cpu/cpu{cpuId}/cache/index3/shared_cpu_list")
            socketId = int(utils.ReadTextFromFile(f"/sys/devices/system/cpu/cpu{cpuId}/topology/physical_package_id"))
            g_runinfo.socketCores[socketId].append(int(cpuId))

            if (L3SharedCpuList not in g_runinfo.ccxCores):
                g_runinfo.ccxCores.append(L3SharedCpuList)

    g_runinfo.ccxCores.sort(key=lambda x:int(x.split('-')[-1]))

    for s in range(g_runinfo.sockets):
        g_runinfo.socketCores[s].sort()

    g_runinfo.ccxs = len(g_runinfo.ccxCores)
    return g_runinfo

def GetRunInfo():
    return g_runinfo

def IsIRPERFEnabled():
    IrperfPath = '/sys/bus/event_source/devices/msr/events/irperf'
    return  Path(IrperfPath).exists()

def IsAPERFEnabled():
    AperfPath = '/sys/bus/event_source/devices/msr/events/aperf'
    return  Path(AperfPath).exists()

def IsMPERFEnabled():
    MperfPath = '/sys/bus/event_source/devices/msr/events/mperf'
    return  Path(MperfPath).exists()

def IsValidIRPERF():
    enabled = False
    if not IsIRPERFEnabled():
        return enabled

    # Check if Linux perf is available
    if not isLinuxPerfAvailable():
        sys.exit("Eorror: Linux perf is not available")

    perfPath = GetPerf() + ' stat -e msr/irperf/ echo'
    output = subprocess.getoutput(perfPath)

    for ln in output.split('\n'):
        try:
            if 'irperf' in ln:
                if int(ln.strip().split(' ')[0].replace(',', '')) > 0:
                    return True
            if 'syntax error' in ln:
                return False
        except:
            return False

    return enabled

def IsValidAPERF():
    enabled = False
    if not IsAPERFEnabled():
        return enabled

    # Check if Linux perf is available
    if not isLinuxPerfAvailable():
        sys.exit("Eorror: Linux perf is not available")

    perfPath = GetPerf() + ' stat -e msr/aperf/ echo'
    output = subprocess.getoutput(perfPath)

    for ln in output.split('\n'):
        try:
            if 'aperf' in ln:
                if int(ln.strip().split(' ')[0].replace(',', '')) > 0:
                    return True
            if 'syntax error' in ln:
                return False
        except:
            return False

    return enabled

def IsValidMPERF():
    enabled = False
    if not IsMPERFEnabled():
        return enabled

    # Check if Linux perf is available
    if not isLinuxPerfAvailable():
        sys.exit("Eorror: Linux perf is not available")

    perfPath = GetPerf() + ' stat -e msr/mperf/ echo'
    output = subprocess.getoutput(perfPath)

    for ln in output.split('\n'):
        try:
            if 'mperf' in ln:
                if int(ln.strip().split(' ')[0].replace(',', '')) > 0:
                    return True
            if 'syntax error' in ln:
                return False
        except:
            return False

    return enabled

def isLinuxPerfAvailable():
    output =  subprocess.getoutput('perf --version')

    if 'perf version' in output:
       return True
    elif 'perf not found' in output:
       return False