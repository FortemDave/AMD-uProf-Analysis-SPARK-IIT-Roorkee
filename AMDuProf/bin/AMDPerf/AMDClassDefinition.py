#=====================================================================
# Copyright 2020 (c), Advanced Micro Devices, Inc. All rights reserved.
#
# AMDClassDefinition.py - Definitions used in AMDuProfSys.py.
#
# Developed by AMDuProf Profiler team.
#=====================================================================
import AMDUtils as utils
import os
from pathlib import Path
import glob

class Metric:
    __slots__ = ("Abbreviation", "Name", "Expression","Description","UseRaw","Unit","Child","cfg")
    def __init__(self, metric, cfg, runInfo):
        self.Abbreviation = metric['Abbreviation'] if 'Abbreviation' in metric else "UNKNOWN"
        self.Name = metric['Name'] if 'Name' in metric else "UNKNOWN"
        exp = metric['Expression'] if 'Expression' in metric else "UNKNOWN"

        if (runInfo.isIRPERF):
            exp = exp.replace('OsUserInst','irperf')
        else:
            exp = exp.replace('OsUserInst','retired_instructions')

        # Following evaluation is to avaid manual changes in the ini file for these counters
        if not 'NonPrintingDFclkCycleInNs' in exp:
            # Do this only for SSP and Milan
            exp = exp.replace('DFclkCycleInNs','(1000 / fDfFreq)')

        exp = exp.replace('fRefClkFreqMHz','(100)')
        exp = exp.replace('fDfFreq','(((df_clk_measure.umask0x1)/(tsc))*(fCpuMhz))')
        exp = exp.replace('(fCpuMhz)', str(runInfo.cpuFreq))
        exp = exp.replace('(CpuMhz)', str(runInfo.cpuFreq))
        exp = exp.replace('IpClk','ncm0_reqq_occpncy.threshold')
        self.Expression = exp
        self.Description = metric['Description'] if 'Description' in metric else "UNKNOWN"
        self.UseRaw = int(metric['UseRaw']) if 'UseRaw' in metric else 0
        self.Unit = metric['Unit'] if 'Unit' in metric else "UNKNOWN"
        self.Child = metric['Child'] if 'Child' in metric else ""
        self.cfg = cfg

class EventCmd:
    def __init__(self, name, cmd, eventType, mergeEvent, counterType):
        self.name = name
        self.cmd = cmd
        self.eventType = eventType
        self.mergeEvent = mergeEvent
        self.counterType = counterType

class OutStream:
    def __init__(self, core, thread, value, ena, run, tm, ev, name):
        self.core = core
        self.thread = thread
        self.value = value
        self.ena = ena
        self.run = run
        self.tm = tm
        self.ev = ev
        self.name = name

    def __repr__(self) -> str:
        return f"\ncore:{self.core}\nname:{self.name}\nevent:{self.ev}\nvalue:{self.value}\n"

class GrpEvents:
    def __init__(self, name, events, cfg):
        self.name = name
        self.events = events
        self.cfg = cfg

class XLSXLine:
    def __init__(self, line, style, cfg):
        self.line = line
        self.style = style
        self.cfg = cfg

class ExpName:
    __slots__ = ("nameStr","name","cfg")
    def __init__(self, nameStr, name, cfg):
        self.nameStr = nameStr
        self.name = name
        self.cfg = cfg

class XlsxSheets:
    def __init__(self, name):
        self.name = name
        self.cfgSheet = None
        self.cfgSheetName = name + '_cfg'
        self.dataSheet = None
        self.dataSheetName = name + '_data'
        self.dataRow = 0
        self.cfgRow = 0

class RunInfo:
    def __init__(self):
        self.sockets = 0
        self.totalCores = 1
        self.coresPerSocket = 0
        self.threadPerSocket = 0
        self.family = ''
        self.model = ''
        self.modelName = ''
        self.isUncoreDriver = False
        self.cpuFreq = ''
        self.socketCores = []
        self.numaNodes = 0
        self.numaCores = []
        self.ccxs = 0
        self.ccxCores = []
        self.ccds = 0
        self.ccdCores = []
        self.node0Cpu = ''
        self.node1Cpu = ''
        self.coreMask = ''
        self.dfMask = ''
        self.l3Mask = ''
        self.umcMask = ''
        self.commandLine = ''
        self.node = []
        self.numaFirstCore = []
        self.dfs = None
        self.rawDataFiles = []
        self.cfgList = []
        self.isL3SliceIdThreadMaskAvailable = False
        self.umcCount = 0
        self.umcCntArr = []
        # use irperf or C0, need to rename
        self.isIRPERF = False
        self.isMperfAvailable = False
        self.isIrperfAvailable = False
        self.isAperfAvailable = False

class Aggregate:
    def __init__(self):
        self.SYSTEM = 0
        self.PACKAGE = 1
        self.NUMA = 2
        #self.CCD = 3
        self.CCX = 3
        self.totalGroups = self.CCX + 1
        self.valueStr = ['system', 'package', 'numa', 'ccx']
        self.valueInstance = []
        self.value = []

class CommonParams:
    def __init__(self):
        self.cfgList = []
        self.hasCore = False
        self.hasDF = False
        self.hasL3 = False
        self.hasUMC = False
        self.collect = True
        self.argv = None
        self.coreMask = ''
        self.dfMask = ''
        self.l3Mask = ''
        self.umcMask = ''
        self.umcCount = 0
        self.umcFcores = ''
        self.mask = []
        self.swp = False
        self.passCmd = ''
        self.verbose = False
        self.pid = ''
        self.tid = ''
        self.inherit = ''
        self.interval = 0
        self.duration = 0
        self.outputFile = ''
        self.isOutputFile = False
        self.rawDataList = []
        self.collectRaw = False
        self.genRawEvent = False
        self.rawEventFile = ''
        self.inputFile = ''
        self.format = 'XLS'
        self.TYPE_CORE = 0
        self.TYPE_DF = 1
        self.TYPE_L3 = 2
        self.TYPE_UMC = 3
        self.cfgTypeList = [0, 1, 2, 3]
        self.groupby = ''
        self.isTimeSeries = False
        self.isL3SliceIdThreadMaskAvailable = False
        self.rawFileHld = ''
        self.samplingPeriod = 0
        self.iodCoreMask = []
        self.isIRPERF = False
        self.umcMultiplexInterval = 0
        self.uncoreDriverMuxInterval = 0
        self.commandLine = ''
        self.precision = 2
        self.isUncoreDriver = True if utils.IsWindows() else False
        self.collectGroup = []

class SessionInfo:
    def __init__(self):
        self.cores = 0
        self.ncpu = 0
        self.hasCore = False
        self.hasDf = False
        self.date = ''

class CfgDepth():
    def __init__(self, name, depth):
        self.name = name
        self.depth = depth

class ReportData():
    def __init__(self, name, cfg):
        self.name = name
        self.cfg = cfg

class PMCEvent:
    __slots__ = ('EventName', 'EventCode', 'BriefDescription', 'PublicDescription', 'UMask', 'CMask', 'Invert', 'Edge', 'CounterType', 'EventType', 'MergeEvent', 'ThreadMask', 'SliceMask', 'SliceId', 'EnAllCores', 'EnAllSlices', 'CoreId', 'RwMask', 'PrioMask', 'SizeMask', 'ChipSelMask')
    def __init__(self, event):
        self.EventName = event['EventName'] if 'EventName' in event else "UNKNOWN"
        self.EventCode = event['EventCode'] if 'EventCode' in event else 0
        self.BriefDescription = event['BriefDescription'] if 'BriefDescription' in event else "UNKNOWN"
        self.PublicDescription = event['PublicDescription'] if 'PublicDescription' in event else "UNKNOWN"
        self.UMask = event['Umask'] if 'Umask' in event else "0x0"
        self.CMask = event['Cmask'] if 'Cmask' in event else "0x0"
        self.Invert = event['Invert'] if 'Invert' in event else 0
        self.Edge = event['Edge'] if 'Edge' in event else 0
        self.CounterType = event['CounterType'] if 'CounterType' in event else "UNKNOWN"
        self.EventType = event['EventType'] if 'EventType' in event else "UNKNOWN"
        self.MergeEvent = event['MergeEvent'] if 'MergeEvent' in event else "No"

        # L3 specific masks
        self.ThreadMask =  event['ThreadMask'] if 'ThreadMask' in event else "UNKNOWN"
        # L3 specific masks Family 17
        self.SliceMask =  event['SliceMask'] if 'SliceMask' in event else "UNKNOWN"
        # L3 specific masksFamily 19
        self.SliceId =  event['SliceId'] if 'SliceId' in event else "UNKNOWN"
        self.EnAllCores =  event['EnAllCores'] if 'EnAllCores' in event else "UNKNOWN"
        self.EnAllSlices =  event['EnAllSlices'] if 'EnAllSlices' in event else "UNKNOWN"
        self.CoreId =  event['CoreId'] if 'CoreId' in event else "UNKNOWN"

        # UMC Soecific masks
        self.RwMask =  event['RwMask'] if 'RwMask' in event else "0x0"
        self.PrioMask =  event['PriorityMask'] if 'PriorityMask' in event else "0x0"
        self.SizeMask =  event['SizeMask'] if 'SizeMask' in event else "0x0"
        self.ChipSelMask =  event['ChipSelMask'] if 'ChipSelMask' in event else "0x0"

    def PreparePerfCTL(self, scope, runInfo, params):
        eventStr = ''
        if 'msr' in self.CounterType.lower():
            # FIXME: This is a work around for Redhat 7.7 aperf issue
            # Need to check eventId is same or need to read from the platform
            if self.EventName == 'aperf':
                if params.isUncoreDriver and params.collect:
                    eventStr = 'msr/' + self.EventName + '/'
                else:
                    eventStr = 'msr/event=0x01/'
            else:
                eventStr = 'msr/' + self.EventName + '/'
        elif 'core' == self.CounterType.lower():
            eventStr = self.__prepareCorePerfCTL(scope, params)

        elif 'l3' == self.CounterType.lower():
            eventStr = self.__prepareL3PerfCTL(runInfo, params)

        elif 'df' == self.CounterType.lower():
            eventStr = self.__prepareDFPerfCTL(runInfo, params)

        elif 'umc' == self.CounterType.lower():
            eventStr = self.__prepareUmcPerfCTL(params)

        return eventStr, self.CounterType

    def __prepareUmcPerfCTL(self, params):
        raw = 0x80000000
        event = int(self.EventCode, 16)
        PrioMask = int(self.PrioMask, 16)
        RwMask = int(self.RwMask, 16)
        SizeMask = int(self.SizeMask, 16)
        ChipSelMask = int(self.ChipSelMask, 16)

        raw |= ((ChipSelMask & 0xf) << 16) | ((SizeMask & 0x3 ) << 14)|((PrioMask & 0xf ) << 10)|((RwMask & 0x3) << 8)|(event & 0xFF)
        if params.isUncoreDriver:
            return "umc/" + hex(raw)
        else:
            return hex(raw)

    def __prepareCorePerfCTL(self, scope, params):
        event = int(self.EventCode, 16)
        unitMask = int(self.UMask, 16)
        cntMask = int(self.CMask, 16)

        cntMaskBit = 0
        invCntMaskBit = 0
        edgeEventBit = 0
        sampleEventBit = 0

        eventLowBits = (event & 0xFF)
        eventHighBits = ((event & 0xF00) << 24)
        maskBits = (unitMask << 8)
        userBit = 0
        osBit = 0

        if cntMask != 0:
            cntMaskBit = (cntMask & 0xFF) << 24

            if self.Invert != 0:
                invCntMaskBit = (1 << 23)

        if self.Edge != 0:
            edgeEventBit = (1 << 18)

        enableBit = (1 << 22)
        # guestOnly = (1 << 40)
        # hostOnly = (1 << 41)


        if params.isUncoreDriver and params.collect:
            if scope == 'u':
                userBit = (1 << 16)
            elif scope == 'k':
                osBit = (1 << 17)
            else:
                userBit = (1 << 16)
                osBit = (1 << 17)

            raw = hex(eventLowBits | eventHighBits | maskBits | userBit | osBit |
                  edgeEventBit | cntMaskBit | invCntMaskBit | sampleEventBit | enableBit )
            raw = 'core/0x' + raw[2:]

        else:
            userBit = (1 << 16) #for linux-perf set both user and os bit
            osBit = (1 << 17)
            raw = hex(eventLowBits | eventHighBits | maskBits | userBit | osBit |
                  edgeEventBit | cntMaskBit | invCntMaskBit | sampleEventBit | enableBit )
            raw = 'r' + raw[2:]
            if scope != '':
                raw += ':' + scope

        return raw

    def __prepareL3PerfCTL(self, runInfo, params):
        evStr =""
        if self.CounterType.lower() == 'l3':
            # Only for collecting profile data using windows driver
            if (params.isUncoreDriver and params.collect):
                if (runInfo.family == 0x17):
                    # 0-7: event code, 8-15: mask, 48-51: Slice id, 56-63: Thread mask
                    evStr = (int(self.ThreadMask, 16) << 56)\
                        | (int(self.SliceId, 16) << 48)\
                        | (1 <<22)\
                        | (int(self.UMask, 16) << 8)\
                        | int(self.EventCode, 16)

                    evStr = 'l3/' + hex(evStr)

                elif (runInfo.family == 0x19):
                    # 0-7: event code, 8-15: mask, 42-44: core id, 46:enallslice, 47:enallcore 48-50: Slice id, 56-63: Thread mask
                    evStr = ((int(self.ThreadMask, 16) & 0XF )<< 56)\
                    | (int(self.SliceId, 16) << 48)\
                    | (int(self.EnAllCores, 16) << 47)\
                    | (int(self.EnAllSlices, 16) << 46)\
                    | (int(self.CoreId, 16) << 42)\
                    | (1 <<22)\
                    | ((int(self.UMask, 16) & 0xFF) << 8)\
                    | int(self.EventCode, 16)

                    evStr = 'l3/' + hex(evStr)
            else:
                # Command to collect using Linux perf. In case of report generation following is used
                # for both windows and Linux. Reporter is OS independent
                if (runInfo.isL3SliceIdThreadMaskAvailable):
                    if (runInfo.family == 0x17):
                        evStr = 'amd_l3/event=' + str(self.EventCode)\
                                                + ',umask='+ str(self.UMask)\
                                                + ',slicemask='+ str(self.SliceId)\
                                                + ',threadmask='+ str(self.ThreadMask) + '/ '

                    elif (runInfo.family == 0x19):
                        coreIdStr = ''
                        threadMaskStr = ''
                        sliceIdStr = ''
                        enAllCoresStr = ''
                        enAllSliceStr = ''

                        if 'UNKNOWN' not in str(self.CoreId):
                            coreIdStr = ',coreid='+ str(self.CoreId)
                        if 'UNKNOWN' not in str(self.ThreadMask):
                            threadMaskStr = ',threadmask='+ str(self.ThreadMask)
                        if 'UNKNOWN' not in str(self.SliceId):
                            sliceIdStr = ',sliceid=' + str(self.SliceId)
                        if 'UNKNOWN' not in str(self.EnAllCores):
                            enAllCoresStr = ',enallcores='+ str(self.EnAllCores)
                        if 'UNKNOWN' not in str(self.EnAllSlices):
                            enAllSliceStr = ',enallslices='+ str(self.EnAllSlices)

                        evStr = 'amd_l3/event=' + str(self.EventCode)\
                                + ',umask='+ str(self.UMask)\
                                + coreIdStr \
                                + threadMaskStr \
                                + sliceIdStr \
                                + enAllCoresStr \
                                + enAllSliceStr +'/ '

                else:
                    evStr = 'amd_l3/event=' + str(self.EventCode)\
                            + ',umask='+ str(self.UMask) + '/ '

        return evStr


    def __prepareDFPerfCTL(self, runInfo, params):
        evStr = ''
        if (params.isUncoreDriver and params.collect):
            if runInfo.family == 0x19 and (runInfo.model >> 4) == 0x1:
                # Eventcode = [0-7][32-37]
                # Umask = [8-15][24-27]
                evCtl = int(self.EventCode, 16) & 0xFF \
                    |  (int(self.UMask, 16) & 0xFF) << 8 \
                    |  ( 1 << 22) \
                    |  (int(self.UMask, 16) & 0xF00) << 16 \
                    |  (int(self.EventCode, 16) & 0x3F00) << 24
            else:
                # Eventcode = [0-7][32-35]
                # Umask = [8-15]
                evCtl = (int(self.EventCode, 16) & 0xFF) \
                    | (int(self.EventCode, 16) & 0xF00) << 24\
                    | (int(self.EventCode, 16) & 0x3000) << 47\
                    | (1 << 22)\
                    | (int(self.UMask, 16) & 0xFF) << 8

            evStr = 'df/' + hex(evCtl)

        else:
            # Command to collect using Linux perf. In case of report generation following is used
            # for both windows and Linux. Reporter is OS independent
            evStr = 'amd_df/event=' + str(hex (int (self.EventCode,16))) + ',umask='+ str(hex (int (self.UMask,16))) + '/ '

        return evStr

class AMDuProfInterface:
    def __init__(self) -> None:
        scopeStr = os.getenv("AMDUPROF_SCOPE_STR")
        if scopeStr:
            if utils.IsWindows():
                uProfDir = Path(utils.GetApplicationPath()).parent / "AMDProfiler" / "Output" / "release" / "bin"
            if utils.IsLinux():
                uProfDir = Path(utils.GetApplicationPath()).parent / "AMDProfiler" / "Output_x86_64" / "release" / "bin"
        else:
            uProfDir = Path(utils.GetApplicationPath()).parent

        # locate uProfCLI and uProfPcm
        if utils.IsWindows():
            self.uProfCLIPath = next(uProfDir.glob("AMDuProfCLI*.exe")).name
            self.uProfPcmPath = next(uProfDir.glob("AMDuProfPcm*.exe")).name
        if utils.IsLinux():
            self.uProfCLIPath = uProfDir / "AMDuProfCLI"
            self.uProfPcmPath = uProfDir / "AMDuProfPcm"

    def getCLIPath(self):
        return str(self.uProfCLIPath)

    def getPcmPath(self):
        return str(self.uProfPcmPath)