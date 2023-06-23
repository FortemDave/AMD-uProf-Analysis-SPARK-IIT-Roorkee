#=====================================================================
# Copyright 2021 (c), Advanced Micro Devices, Inc. All rights reserved.
#
# AMDUmc.py -  UMC Counter collector.
#
# Developed by AMDuProf Profiler team.
#=====================================================================
from __future__ import division
from time import sleep
import sys
import os
import ctypes
import time
import math
import AMDUtils as utils
import AMDOSFeatures as osFeatures

g_fileBuffer = ''
g_sampleId = 0
g_umcCount = 8
isUmcStarted = False
if utils.IsLinux():
    g_libUtils = ctypes.CDLL(utils.GetApplicationPath() + '/libutils.so')

# UMC CLT and CTR Registers
UmcPerfCtl_Base = 0x50D00
UmcPerfCtl_Stride = 4
UmcPerfCtrLo_Base = 0x50D20
UmcPerfCtrHi_Base = 0x50D24
UmcPerfCtr_Stride = 8

# level: bus->clks->Event->data
outputStream = []
umcEventSets = []

class UmcEvent:
    def __init__(self, bus, clkIdx, groupIdx, eventIdx, ctrMsr, ctlMsr, event, eventName, counterType):
        self.bus = bus
        self.clkIdx = clkIdx
        self.groupIdx = groupIdx
        self.eventIdx = eventIdx
        self.ctrMsr = ctrMsr
        self.ctlMsr = ctlMsr
        self.event = event
        self.eventName = eventName
        self.counterType = counterType

class UmcRecord:
    def __init__(self, bus, clks, grp, evIdx, name, event, value):
        self.bus = bus
        self.clks = clks
        self.grp = grp
        self.evIdx = evIdx
        self.name = name
        self.event = event
        self.value = value

def InitPci():
    g_libUtils.InitPci()

def ReadPci(bus, dev, func, reg):
    return g_libUtils.ReadPci(bus, dev, func, reg)

def WritePci(bus, dev, func, reg, data):
    g_libUtils.WritePci(bus, dev, func, reg, data)

def ClosePci():
    g_libUtils.ClosePci()

def SmnRead(bus, address):
    WritePci(bus, 0, 0, 0xE0, address)
    return ReadPci(bus, 0, 0, 0xE4)

def SmnWrite(bus, address, data):
    WritePci(bus, 0, 0, 0xE0, address)
    WritePci(bus, 0, 0, 0xE4, data)

def GetBusNumber(node):
    dev = 0x18 + node
    func = 0x0
    offset = 0x84
    value = 0

    value = ReadPci(0, dev, func, offset)
    bus = value & 0xFF
    return bus

def IsUmcMonitored(bus, address):
    data = SmnRead(bus, address)
    return True if(0 != ((1 << 31) & data)) else False

def StartUmcMonitoring(evSet):
    for ev in evSet:
        if ('UMC' in ev.counterType and ev.ctrMsr and ev.event and not IsUmcMonitored(ev.bus, ev.ctlMsr)):
            # Write 0 to UMC::CH::PerfMonCtrLo and UMC::CH::PerfMonCtrHi

            SmnWrite(ev.bus, ev.ctrMsr, 0)
            SmnWrite(ev.bus, ev.ctrMsr + 4, 0)

            # Write event into regAddr (UMC::CH::PerfMonCtl) using SmnAccess with enable bit set
            SmnWrite(ev.bus, ev.ctlMsr, int(ev.event, 16))

def StopUmcMonitoring(evSet):

    for ev in evSet:
        if 'UMC' in ev.counterType and (IsUmcMonitored(ev.bus, ev.ctlMsr)):
            # Write 0 into ctl register
            SmnWrite(ev.bus, ev.ctlMsr, 0)

            # write 0 to counter registers
            SmnWrite(ev.bus, ev.ctrMsr, 0)
            SmnWrite(ev.bus, ev.ctrMsr + 4, 0)

def ReadUmcCount(evSet, tsc, params):
    data = 0
    global g_sampleId
    global g_fileBuffer

    for ev in evSet:
        if 'UMC' in ev.counterType and (IsUmcMonitored(ev.bus, ev.ctlMsr)):
            #print('Umc counting' +hex(ev.bus) + hex(ev.ctrMsr))
            valueLo = SmnRead(ev.bus, ev.ctrMsr)
            valueHi = SmnRead(ev.bus, ev.ctrMsr + 4)
            #print(valueHi)

            data = valueHi & 0xFFFF # 16 bits
            data = (data << 32) | valueLo
            recStr =  str(g_sampleId) + ',' \
                      + hex(ev.bus) + ',' \
                      + str(ev.clkIdx) + ',' \
                      + str(ev.groupIdx) + ',' \
                      + str(ev.eventIdx) + ',' \
                      + ev.eventName +  ',' \
                      + ev.event + ',' \
                      + str(data) +'\n'

            #print ('READ'+ recStr)
            g_fileBuffer += recStr

        elif 'TSC' in ev.counterType:
            busIdx = GetArrIndex(params.umcMask.split(','), hex(ev.bus))
            data = tsc[busIdx]
            recStr =  str(g_sampleId) + ',' \
                      + hex(ev.bus) + ',' \
                      + str(ev.clkIdx) + ',' \
                      + str(ev.groupIdx) + ',' \
                      + str(ev.eventIdx) + ',' \
                      + ev.eventName +  ',' \
                      + ev.event + ',' \
                      + str(data) +'\n'

            g_fileBuffer += recStr
            continue

    return data

def GetArrIndex(arr, key):
    pos = 0

    for item in arr:
        if key in item:
            return pos
        else:
            pos += 1
    return -1

def ReadMultiplexCounters(params, eventList):
    global g_sampleId
    tsc = []
    multiplexInterval = (params.umcMultiplexInterval / 1000) if (params.umcMultiplexInterval > 0) else(1 / len(eventList))

    for evSet in umcEventSets:
        # Tsc is core specific counter
        for busIdx,_ in enumerate(params.umcMask.split(',')):
            tsc.append(osFeatures.GetTsc(params.iodCoreMask[busIdx]))

        StartUmcMonitoring(evSet)
        time.sleep(multiplexInterval)

        # Read Tsc
        for busIdx,_ in enumerate(params.umcMask.split(',')):
            tsc[busIdx] = osFeatures.GetTsc(params.iodCoreMask[busIdx])- tsc[busIdx]

        ReadUmcCount(evSet, tsc, params)

        # Stop event monitoring
        StopUmcMonitoring(evSet)
    g_sampleId += 1
    return None

def PrepareEventSets(params, eventList):
    grpIdx = 0

    for grp in eventList:
        umcEventSets.append([])

        # start monitoring
        for busStr in params.umcMask.split(','):
            bus = int(busStr, 16)
            clkIdx = 0
            for umc in range(g_umcCount):
                ctlMsr = UmcPerfCtl_Base | (umc << 20)
                ctrMsr = UmcPerfCtrLo_Base | (umc << 20)

                evIdx = 0
                for ev in grp:
                    #print(str(grpIdx),str(evIdx),hex(bus), hex(ctrMsr), hex(ctlMsr), ev.cmd)
                    if 'UMC' in ev.counterType:
                        umcEventSets[grpIdx].append(UmcEvent(bus, clkIdx, grpIdx, evIdx, ctrMsr, ctlMsr, ev.cmd, ev.name, ev.counterType))
                        ctrMsr += 8
                        ctlMsr += 4
                    elif 'TSC' in ev.counterType:
                        #Since it TSC type counter PreparePerfCTL doesn't prepare the perfCtl hence 0x800fffff is hard coded for tsc
                        umcEventSets[grpIdx].append(UmcEvent(bus, clkIdx, grpIdx, evIdx, 0, 0, '0x800fffff', ev.name, ev.counterType))
                    evIdx += 1

                clkIdx += 1
        grpIdx += 1

def InitUmc(params, eventList, cmds):
    PrepareEventSets(params, eventList)
    InitPci()

def FinalizeUmc(params, eventList):
    global g_fileBuffer
    evGroupCnt = len(eventList)
    evCnt = 0

    for gp in eventList:
        evCnt += len(gp)

    ClosePci()

    params.rawFileHld.write('Samples:,'+ str(g_sampleId) + '\n')
    params.rawFileHld.write('evGroupCnt:,'+ str(evGroupCnt)+ '\n')
    params.rawFileHld.write('Events:,'+ str(evCnt) +'\n')
    params.rawFileHld.write('sampleId, bus,clks,grp,idx,name,event,value\n')
    params.rawFileHld.write(g_fileBuffer)
    params.rawFileHld.close()

def GetUmcMaskIdx(params, mask):
    idx = 0
    for umc in params.umcMask.split(','):
        #print umc, hex(mask)
        if hex(mask) in umc:
            return idx
        idx += 1

# Read raw binary event count values data file
def ReadUmcData(idx, ncpu, params, runInfo, eventCmdList):
    samples = 0
    prevSampleId = 0
    eventCount = 0
    evGroupCnt = 0
    record = []

    data = utils.OpenFile(params.rawDataList[idx], 'r')

    if (data == None):
        print ('Could not open raw data file: ',params.rawDataList[idx])
        sys.exit()

    for line in data:
        if 'Samples' in line:
            samples = int(line.split(',')[1].strip())

        elif 'evGroupCnt' in line:
            evGroupCnt = int(line.split(',')[1].strip())

        elif 'Events' in line:
            eventCount = int(line.split(',')[1].strip())

            for idx in range(samples):
                outputStream.append([])

                for bus in range(len(params.umcMask.split(','))):
                    outputStream[idx].append([])

                    for clk in range(params.umcCount):
                        outputStream[idx][bus].append([])

                        for grp in range(evGroupCnt):
                            outputStream[idx][bus][clk].append([])

        elif 'bus' in line:
            continue
        else:
            #print(line)
            sampleId = int(line.split(',')[0])
            clk = int(line.split(',')[2])
            grp = int(line.split(',')[3])
            evIdx = int(line.split(',')[4])
            name = line.split(',')[5]
            event = int(line.split(',')[6], 16)
            value = int(line.split(',')[7])

            bus = 0
            for u in params.umcMask.split(','):
                if u in line.split(',')[1]:
                    break
                bus += 1

            values = [0,0]
            values[0] = value * evGroupCnt
            values[1] = value

            #print ('DD'+ ',' + str(bus)+','+ str(clk)+','+ str(grp)+','+ str(evIdx)+ ','+str(name)+','+ str(event)+ ','+str(value))

            # For aggregated data
            if not params.isTimeSeries:
                if evIdx < len(outputStream[0][bus][clk][grp]):
                    outputStream[0][bus][clk][grp][evIdx].value[0] += values[0]
                    outputStream[0][bus][clk][grp][evIdx].value[1] += values[1]
                else:
                    outputStream[0][bus][clk][grp].append(UmcRecord(bus, clk, grp, evIdx, name, event, values))
            else:
                # Records for time series
                outputStream[sampleId][bus][clk][grp].append(UmcRecord(bus, clk, grp, evIdx, name, event, values))

    return outputStream, evGroupCnt, eventCount

def ConstructStrEvSet(evSetList):
    if not evSetList:
        return ""
    curEvSetStr = ",".join(evSetList)
    return  f"-e \"{curEvSetStr}\" "

def PrepareStatEvSet(params, eventCmdList):
    """Prepare event-set string for AMDuProfCLI stat
    Eg. -e "umc_ev_name1:umc/0x800000,umc_ev_name2:umc/0x8000001"
    """
    UMC_ID = params.TYPE_UMC
    hwCnt = utils.GetAvailablePmcs(UMC_ID)
    cmd = ""
    curEvSet = ""
    evCnt = 0
    # Find all occurrence of ip_clk
    # Each event-set must start with ip_clk
    ipClkIdxList = [idx for idx, ev in enumerate(eventCmdList[UMC_ID]) if "ip_clk" in ev.name]

    for idx, curIpClkIdx in enumerate(ipClkIdxList):
        nextIdx = len(eventCmdList[UMC_ID]) if idx == len(ipClkIdxList) -1 else ipClkIdxList[idx + 1]
        # Current event-set include all the events between current ip_clk and next susbequent ip_clk
        curEvSetList = [ ":".join((ev.name, ev.cmd)) for ev in eventCmdList[UMC_ID][curIpClkIdx : nextIdx]]
        #curEvSetList = [ ev.cmd for ev in eventCmdList[UMC_ID][curIpClkIdx : nextIdx]]
        cmd += (ConstructStrEvSet(curEvSetList[0:hwCnt]) + ConstructStrEvSet(curEvSetList[hwCnt:]))
    return cmd