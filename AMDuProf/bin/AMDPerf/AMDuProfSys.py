#!/usr/bin/env python3
#=====================================================================
# Copyright 2020 (c), Advanced Micro Devices, Inc. All rights reserved.
#
# AMDuProfSys.py - Main script for AMDPerf tool.
#              This tool is used to monitor Core, L3, DF PMC events
#              and report the computed metrics.
#
# Developed by AMDuProf Profiler team.
#=====================================================================
# list of packages required for this tool
#       pyyaml
#       yamlordereddictloader
#       tdqm
#       xlsxwriter
#       json
#=====================================================================


from time import sleep
import sys
import os
import getopt
import time
import threading
import subprocess
import sys
import glob
import re
from pathlib import Path

try:
    from tqdm import tqdm
    import xlsxwriter
    import yaml
    import json
except ImportError:
    reqModule = ["yamlordereddictloader",
                "pyyaml",
                "tqdm",
                "XlsxWriter"]
    installCmd = [sys.executable, "-m" , "pip", "install"]
    installCmd.extend(reqModule)

    installModuleMsg ="""
AMDuProfSys requires following Python libraries to be installed

yamlordereddictloader
pyyaml
tqdm
XlsxWriter

Proceed to install (Yes/no)?
"""

    print(installModuleMsg)
    resp = input() #Wait for user's input
    if "y" in resp.lower():
        subprocess.check_call(installCmd)
    else: #if no print installation Command
        print('Use following command to install required Python modules \n{}'.format(" ".join(installCmd)))
        sys.exit()

# Import project specific modules
import AMDUtils as utils
import AMDCpuFeatures as cpuFeatures
import AMDClassDefinition as classDefs
import AMDUmc as umcCollect
from AMDStatHandler import StatHandler

if utils.IsWindows():
    import AMDOSFeaturesWin as osFeatures
else:
    import AMDOSFeatures as osFeatures
#
# TODOs - features to add
#
# 0. Support for PMC Merge
# 1. Option to print the current multiplexing interval
# 2. Option to print the cpu runInfo
# 3. L3 & DF support
# 4. Generate report for the given set of core(s), ccx, ccd, numa, socket
# 5. Collect for the given set of ccx, ccd, numa, socket
# 6. Aggregated report for the given set of ccx, ccd, numa, socket
# 7. Do we need to specify -a with -C (this is perf's requirement)
# 8. -C may not work with --tid
# 9. Add family and model in events, config and metrics file
# 10. Proper bundling of config and events files
# 11. Option to generate machine parse-able format - TXT/CSV/MD. - is this required?
# 12. Add micro version & build number to tool version
# 13. Option to limit the precision
# 14. Timeseries for mem bw
# 15. structure to support config files for multiple families & report relevant data with -l
# 16. stderr of the launched application should be displayed
# 18. Support NMI disabled case
# 19. Why does perf stat doesn't profile only the launch app?
# 20. Add option to specify precision

# Global variables
DEFAULT_MUX_INTERVAL_UNCORE_DRIVER = 16
DEFAULT_LOG_INTERVAL_UNCORE_DRIVER = int(1 << 30)

gToolName = ''
gMajorVersion = 4
gMinorVersion = 0
startTs =0

gConfigDir = 'configs/'
g_collecting = False
g_eventGroups = 1
g_appRunning = False

list = []
eventList = []
metricDict = {}
eventCfgList = []
reportList = []
eventCmdList = []
outputStrList = []
reportMetricList = []
outputStream = []
profileCfgList = []
profileCfgDepthList = []

rawCmdStrList = []

# Predefined parameters
fCpuMhz = 0
fEventSets = 0

# One time call
g_family, g_model = cpuFeatures.GetFamilyModel()

# Group
g_aggr = classDefs.Aggregate()

# Print the Usage.
def Usage():
    if utils.IsLinux(): print(utils.LinuxUsage)
    elif utils.IsWindows() : print(utils.WinUsage)
    else: print("OS not supported")
    sys.exit()

def Version():
    print('%s version %d.%d' % (gToolName, gMajorVersion, gMinorVersion))
    sys.exit()

def SystemInfo(runInfo):
   print('System Information:')
   print('    Platform Name: ' + runInfo.modelName)
   print('    Family: ' + hex(runInfo.family))
   print('    Model: ' + hex(runInfo.model))
   print('    Sockets: ' + str(runInfo.sockets))
   print('    Threads Per Socket: ' + str(runInfo.threadPerSocket))
   print('    Cores Per Socket: ' + str(runInfo.coresPerSocket))
   print('    IRPERF: ' + str(runInfo.isIRPERF))

   if utils.IsLinux():
       numaCnt = 0
       print('    Numa Nodes: ' + str(runInfo.numaNodes))

       for cores in runInfo.numaCores:
           print('    Numa node' + str(numaCnt) +': ' + cores)
           numaCnt += 1

def HandleListOption(listOption, baseDir):

    for op in listOption.split(','):

        if ('*' == op[-1]):
            op = op[:-1]

        if 'core' in op:
            cfgDir = baseDir + 'core/'
            print('Available Core config files:')
            entries = os.listdir(cfgDir)

            for entry in entries:
                if op in entry:
                    print('    %s' % entry)
        elif 'df' in op:
            cfgDir = baseDir +  'df/'
            print('Available DF config files:')
            entries = os.listdir(cfgDir)

            for entry in entries:
                if op in entry:
                    print('    %s' % entry)
        elif 'l3' in op:
            cfgDir = baseDir +  'l3/'
            print('Available L3 config files:')
            entries = os.listdir(cfgDir)

            for entry in entries:
                if op in entry:
                    print('    %s' % entry)

        elif 'umc' in op:
            cfgDir = baseDir +  'umc/'
            print('Available UMC config files:')
            entries = os.listdir(cfgDir)

            for entry in entries:
                if op in entry:
                    print('    %s' % entry)
    sys.exit()

# Read raw binary event count values data file
def ReadPerfData(idx, ncpu, params, runInfo):
    global g_eventGroups
    totalEvents = 0
    recordCount = 0
    prevInstDict = {}
    foundHeader = False
    maskCount = len(params.mask[idx])

    if params.inputFile == '':
        return False

    for c in range(len(outputStream)):
        del outputStream[c][:]
    del outputStream[:]

    try:
        params.rawDataList[idx]
        rawFile = params.rawDataList[idx]
    except:
        print ('Invalid raw files: ' + params.rawDataList[idx])
        exit(0)

    print ('Raw data file:'+params.rawDataList[idx])
    data = utils.OpenFile(params.rawDataList[idx], 'r')

    if (data == None):
        print ('Could not open raw data file: '+rawFile)
        sys.exit()

    #for group by
    global g_aggr

    for _ in range(g_aggr.totalGroups):
        g_aggr.value.append([])

    g_aggr.valueInstance.append(1)
    g_aggr.valueInstance.append(runInfo.sockets)
    g_aggr.valueInstance.append(runInfo.numaNodes)
    #g_aggr.valueInstance.append(1)
    g_aggr.valueInstance.append(runInfo.ccxs)

    g_aggr.value[g_aggr.SYSTEM].append([])

    for s in range(runInfo.sockets):
      g_aggr.value[g_aggr.PACKAGE].append([])
    for n in range(runInfo.numaNodes):
      g_aggr.value[g_aggr.NUMA].append([])
    for c in range(runInfo.ccxs):
      g_aggr.value[g_aggr.CCX].append([])

    for line in data:
        if (line.startswith('# cmdline :')):

            if (idx == params.TYPE_L3):
                # Adjust for msr and core pmc groups
                g_eventGroups = line.count("-e") - 2
            else:
                # Adjust for msr group in core, df
                g_eventGroups = line.count("-e") - 1

            totalEvents = utils.GetEventCountFromCmd(line)

            if (params.verbose == True):
                print('Groups: ' + str(g_eventGroups) + ' Events: ' + str(totalEvents))

        if line.startswith('CPU') or line.startswith("UMC"):
            foundHeader = True
            continue
        if not foundHeader:
            continue

        # for time series
        instance = int(recordCount / (totalEvents * maskCount)) if (params.isTimeSeries) else 0
        recordCount += 1

        record = line.strip().split()
        core = record[0]
        thread = record[1]
        rawValue = int(record[2])
        value = [0,0]
        value[1] = rawValue
        ena = int(record[3])
        run = int(record[4])
        tm = record[5]
        ev = record[6]
        #print ('EV ' + ev)

        try:
            # if time-series and OS is Linux
            if params.isTimeSeries:
                if (core, ev) in prevInstDict:
                    prev = prevInstDict.get((core, ev))
                    deltaValue = rawValue - prev[0]
                    deltaEnableTime = ena - prev[1]
                    deltaRunTime = run - prev[2]
                else:
                    deltaValue = rawValue
                    deltaEnableTime = ena
                    deltaRunTime = run

                value[0] = deltaValue * (deltaEnableTime / deltaRunTime)
                prevInstDict[(core, ev)] = [rawValue, ena, run]
            else:
                value[0] = rawValue * ena / run
        except:
            value[0] = 0

        name = ''

        for counterType in params.cfgTypeList:
            for cmd in eventCmdList[counterType]:
                if cmd.cmd == ev:
                    name = cmd.name
                    break

        if params.hasUMC:
            name = record[7]
        recExists = False

        if (len(outputStream) < (instance + 1)):
              outputStream.append([])

              #indexing will be easy if we create for all
              for c in range(runInfo.totalCores):
                  outputStream[instance].append([])

        if (not params.isTimeSeries):

            # Accumulate the value if already exists, otherwise add a new entry

            rec = outputStream[0][int(core)]

            for i in range(len(rec)):
                if rec[i].name == name:
                    value[0] = str(int(value[0]) + int(rec[i].value[0]))
                    outputStream[0][int(core)][i] = classDefs.OutStream(core, thread, value, ena, run, tm, ev, name)
                    recExists = True
                    break

        if not recExists:

            outputStream[instance][int(core)].append(classDefs.OutStream(core, thread, value, ena, run, tm, ev, name))

            if ('system' in params.groupby):
                #For system level grouping
                for s in range(runInfo.sockets):
                    aggrFound = False
                    aggrRec = g_aggr.value[g_aggr.SYSTEM][s]
                    for i in range(len(aggrRec)):
                        if (name == aggrRec[i].name):
                            agvalue = [0,0]
                            agvalue[0] = str(int(value[0]) + int(aggrRec[i].value[0]))
                            aggrRec[i] = classDefs.OutStream(core, thread, agvalue, ena, run, tm, ev, name)
                            aggrFound = True

                    if not aggrFound:
                        g_aggr.value[g_aggr.SYSTEM][s].append(classDefs.OutStream(core, thread, value, ena, run, tm, ev, name))
                    break

            if ('package' in params.groupby):
                #For package level grouping
                for p in range(runInfo.sockets):
                    if int(core) in runInfo.socketCores[p]:
                        aggrFound = False
                        aggrRec = g_aggr.value[g_aggr.PACKAGE][p]
                        for i in range(len(aggrRec)):
                            if (name == aggrRec[i].name):
                                agvalue = [0,0]
                                agvalue[0] = str(int(value[0]) + int(aggrRec[i].value[0]))
                                aggrRec[i] = classDefs.OutStream(core, thread, agvalue, ena, run, tm, ev, name)
                                aggrFound = True

                        if not aggrFound:
                            g_aggr.value[g_aggr.PACKAGE][p].append(classDefs.OutStream(core, thread, value, ena, run, tm, ev, name))
                        break

            if ('numa' in params.groupby):
                #For numa level grouping
                for n in range(runInfo.numaNodes):
                    if int(core) in runInfo.numaCores[n]:
                        aggrFound = False
                        aggrRec = g_aggr.value[g_aggr.NUMA][n]
                        for i in range(len(aggrRec)):
                            if (name == aggrRec[i].name):
                                agvalue = [0,0]
                                agvalue[0] = str(int(value[0]) + int(aggrRec[i].value[0]))
                                aggrRec[i] = classDefs.OutStream(core, thread, agvalue, ena, run, tm, ev, name)
                                aggrFound = True

                        if not aggrFound:
                            g_aggr.value[g_aggr.NUMA][n].append(classDefs.OutStream(core, thread, value, ena, run, tm, ev, name))
                        break

            if ('ccx' in params.groupby):
                #For ccx level grouping
                for c in range(runInfo.ccxs):
                    if int(core) in runInfo.ccxCores[c]:
                        aggrFound = False
                        aggrRec = g_aggr.value[g_aggr.CCX][c]
                        for i in range(len(aggrRec)):
                            if (name == aggrRec[i].name):
                                agvalue = [0,0]
                                agvalue[0] = str(int(value[0]) + int(aggrRec[i].value[0]))
                                aggrRec[i] = classDefs.OutStream(core, thread, agvalue, ena, run, tm, ev, name)
                                aggrFound = True

                        if not aggrFound:
                            g_aggr.value[g_aggr.CCX][c].append(classDefs.OutStream(core, thread, value, ena, run, tm, ev, name))
                        break

    return True

# Read Event File
def ReadEventFiles(basePath, params):
    """Locates event file for each profile type(currently for all) and add all the events to the global List eventList.

    :param basePath: ApplicationPath/data/<platform>/
    :type basePath: String
    :param params: General runtime info
    :type params: AMDClassDefinition.CommonParams

    :returns: None

    TODO
        Process events for required profile types only, not all.
    """
    # Read event files from event directory
    eventDirList = []

    if(os.path.exists(basePath + '/events/core/')):
        eventDirList.append(basePath + '/events/core/')

    if(os.path.exists(basePath + '/events/df/')):
        eventDirList.append(basePath + '/events/df/')

    if(os.path.exists(basePath + '/events/l3/')):
        eventDirList.append(basePath + '/events/l3/')

    if(os.path.exists(basePath + '/events/umc/')):
        eventDirList.append(basePath + '/events/umc/')

    if (params.collect and params.hasL3 and not params.isL3SliceIdThreadMaskAvailable):
        print ('Warning: Slice mask and Thread mask are not supported by the current Kernel')

    if params.collect and (params.hasCore or params.hasL3) and not params.isUncoreDriver:
        if (not osFeatures.IsAPERFEnabled() or not osFeatures.IsMPERFEnabled()):
            print ('Error: Core or L3 profiling can not be proceed as MPERF or APERF is not possible')
            print ('Hint: try running sudo sh -c \'echo -1 >/proc/sys/kernel/perf_event_paranoid\'')
            sys.exit()

    # Add architecture msr based events
    for ev in utils.GetMsrEvents():
        eventList.append(classDefs.PMCEvent(ev))

    for eventDir in eventDirList:
        for fileName in os.listdir(eventDir):

            #Get the correct L3 event file
            if params.isL3SliceIdThreadMaskAvailable and ('l3_event_ext.json' in fileName):
                continue
            elif not params.isL3SliceIdThreadMaskAvailable and ('l3_slice_thread_event_ext.json' in fileName):
                continue

            #print 'Event File', fileName

            with open(eventDir + fileName) as eventFile:
                try:
                    data = json.load(eventFile)
                except Exception as e:
                    print ('Error reading event file: ' + eventDir + fileName + str(e))
                    exit(0)

            for eventData in data['events']:
                if '_filter0x' in eventData:
                    continue
                eventList.append(classDefs.PMCEvent(eventData))

# Read Metric File
def ReadMetrics(basePath, runInfo):
    """Locates metric file for each profile type(currently for all) and add all the metrics to the global Dict metricDict.

    :param basePath: ApplicationPath/data/<platform>/
    :type basePath: String
    :param runInfo: System info
    :type params: AMDClassDefinition.RunInfo

    :returns: None

    TODO
        Process metrics for required profile types only, not all.
    """

    metDirList = []
    if(os.path.exists(basePath + '/events/core/')):
        metDirList.append(basePath + '/metrics/core/')

    if(os.path.exists(basePath + '/events/df/')):
        metDirList.append(basePath + '/metrics/df/')

    if(os.path.exists(basePath + '/events/l3/')):
        metDirList.append(basePath + '/metrics/l3/')

    if(os.path.exists(basePath + '/events/umc/')):
        metDirList.append(basePath + '/metrics/umc/')

    for metricsDir in metDirList:
        for fileName in os.listdir(metricsDir):
            #Get the correct L3 event file
            if runInfo.isL3SliceIdThreadMaskAvailable and ('l3_metrics.json' in fileName):
                continue
            elif not runInfo.isL3SliceIdThreadMaskAvailable and ('l3_slice_thread_metrics.json' in fileName):
                continue

            with open(metricsDir + fileName) as metricFile:
                try:
                    metricStream = json.load(metricFile)
                except Exception as e:
                    print ('Error reading metric file: ', fileName, str(e))
                    exit(0)

            for metricData in metricStream['metric']:
                cfgName = fileName.replace('_metric.json', '')
                metricObj = classDefs.Metric(metricData, cfgName, runInfo)
                metricDict[metricObj.Abbreviation] = metricObj

def CheckSupportedPlatform(family, modelLow, modelHigh):
    if (family == g_family):
        if (g_model <= modelHigh) and (modelLow <= g_model):
            return True

    return False

def ReadConfig(params):
    """Reads config YAML files and append event groups in global List eventCfgList[] and to be reported metrics in reportList[]
    :param params: General runtime info
    :type params: AMDClassDefinition.CommonParams

    :returns: None
    """
    for cfg in params.cfgList:

        if ('core_config' in cfg):
            params.hasCore = True
        if ('l3_slice' in cfg):
            params.hasL3 = True
        if ('df_config' in cfg):
            params.hasDF = True

        if (params.verbose == True):
            print ('configFile:'+ cfg)

        cfgData = utils.LoadYaml(cfg)

        for item, cat in cfgData.items():
            if item == 'cpu':
                family = 0
                modelLow = 0
                modelHigh = 0
                corepmcs = 0
                dfpmcs = 0
                l3pmcs = 0
                umcpmcs = 0

                for c in cat:
                    if 'family' in c:
                        family = c.split(':')[1]
                    elif 'modelLow' in c:
                        modelLow = c.split(':')[1]
                    elif 'modelHigh' in c:
                        modelHigh = c.split(':')[1]
                    elif 'corepmcs' in c:
                        corepmcs = c.split(':')[1]
                    elif 'dfpmcs' in c:
                        dfpmcs = c.split(':')[1]
                    elif 'l3pmcs' in c:
                        l3pmcs = c.split(':')[1]
                    elif 'umcpmcs' in c:
                        umcpmcs = c.split(':')[1]

            if (True == params.collect):
                if (False == CheckSupportedPlatform(family, modelLow, modelHigh)):
                    print ('Platform not supported')
                    sys.exit()

            if item == 'events':
                for grp, x in cat.items():
                    if len(params.collectGroup) == 0 or grp in params.collectGroup:
                        configFile = os.path.basename(cfg)[:-5]+'_cfg'
                        eventCfgList.append(classDefs.GrpEvents(grp, x, configFile))

            if item == 'reports':
                for report in cat:
                    reportList.append(classDefs.ReportData(report, os.path.basename(cfg)[:-5]))

# Get event with the event name
def GetEvent(name):
    for event in eventList:
        if name == event.EventName:
            return event

    print('Unknown Event', name)

    return None

# Prepare report string
def ReportStr(m, line):
    if m is not None:
        # line.append(m.Name)
        line.append(m.Abbreviation)

        # print m.Child
        if m.Child != '':
            line.append('{')

            for c in m.Child.split(','):
                newChild = metricDict.get(c)
                ReportStr(newChild, line)

            if line[-1] == ',':
                line = line[:-1]

            line.append('}')

# Prepare counter header
def GetCounterHeader(params, runInfo, cfgName, maxDepth, cores, isCsv = False):
    buf = ''
    if (isCsv):
        buf = buf + '#'+cfgName+','
    else:
        for n in range(0, maxDepth):
            buf = buf + ' level:' + str(n) + ','

    family, model = hex(runInfo.family),  hex(runInfo.model >> 4)
    if params.hasUMC and (family == "0x19" and model == "0x1"):
        for core in cores:
            buf += f"socket:{core//params.umcCount}-umc:{core%params.umcCount},"
        return buf

    aggrStr = ''
    aggrDisp = True if params.groupby != '' else False

    if aggrDisp:
        for g in range(g_aggr.totalGroups):
            if g_aggr.valueStr[g] not in params.groupby:
                continue
            for s in range(g_aggr.valueInstance[g]):
                aggrStr += g_aggr.valueStr[g] + ':'+ str(s)+ ','
        buf += aggrStr.rstrip(',')
        return buf

    devIdx = 0
    for c in cores:
        if 'umc' in cfgName:
            for umc in range(params.umcCount):
                buf += ' socket:' + str(devIdx) + '-umc:' + str(umc) +','
            devIdx += 1
        else:
            buf += ' core:' + str(c) + ','

    buf = buf.rstrip(',')

    return buf

# table Cell
def TableCell(workbook, color='#FFFFFF'):
    format = workbook.add_format()
    format.set_bg_color(color)
    format.set_left()
    format.set_right()
    format.set_top()
    format.set_bottom()
    format.set_text_wrap()

    return format

# Table Header
def TableHeader(workbook):
    format = workbook.add_format()
    format.set_bold()
    format.set_bg_color('#C0C0C0')
    format.set_left()
    format.set_right()
    format.set_top()
    format.set_bottom()
    format.set_text_wrap()

    return format

def ReadPlatformFromSessionFile(sessionFile):
    outFile = utils.OpenFile(sessionFile, 'r')

    for line in outFile:
        if 'family:' in line:
            family = line.split(':')[1].rstrip()
        if 'model:' in line:
            model = line.split(':')[1].rstrip()
            break
    return [family, model]

def ReadProfileSessionInfo(params):
    global fEventSets
    idx = 0
    sessionInfo = classDefs.SessionInfo()

    # Read from perf data
    outFile = utils.OpenFile(params.inputFile, 'rb')
    sessionInfo.date = utils.GetDateTime(False)

    for line in outFile:
        if '#' != line[0]:
            break

        if (idx > 4):

            if 'event : name' in line:

                if 'type = 4' in line:
                    sessionInfo.hasCore = True

                if 'type = 8' in line:
                    sessionInfo.hasDF = True

                if 'type = 9' in line:
                    sessionInfo.hasL3 = True

            if 'nrcpus online' in line:
                sessionInfo.ncpu = int(line.split(':')[1].lstrip())

            if 'cmdline' in line:
                configured = False
                # get list of events
                if '-a' in line:
                    sessionInfo.cores = range(sessionInfo.ncpu)
                    configured = True
                if '-C' in line:
                    sessionInfo.cores = utils.GetCpuRange(line.split('-C')[1].split(' ')[1])
                    configured = True
                    # print cores
                if configured == False:
                    sessionInfo.cores = [-1]

            if 'group:' in line:
                fEventSets += 1

        idx += 1

    utils.CloseFile(outFile)
    return sessionInfo

# Write the overview sheet
def WriteOverviewSheet(workbook, runInfo, sessionInfo):
    row = 0

    overviewSheet = workbook.add_worksheet("overview")
    overviewSheet.write(row, 0, 'Profile Date', TableCell(workbook))
    overviewSheet.write(row, 1, sessionInfo.date, TableCell(workbook))
    row +=1

    overviewSheet.set_column('A:A', 20)
    overviewSheet.set_column('B:B', 40)
    overviewSheet.write(row, 0, 'System Profiler', TableCell(workbook))
    overviewSheet.write(row, 1, 'AMDuProfSys', TableCell(workbook))
    row += 1

    overviewSheet.write(row, 0, 'CPU Family', TableCell(workbook))
    overviewSheet.write(row, 1, hex(runInfo.family), TableCell(workbook))
    row += 1
    overviewSheet.write(row, 0, 'CPU Model', TableCell(workbook))
    overviewSheet.write(row, 1, hex(runInfo.model), TableCell(workbook))
    row += 1
    overviewSheet.write(row, 0, 'Processor Name', TableCell(workbook))
    overviewSheet.write(row, 1, runInfo.modelName, TableCell(workbook))
    row += 1
    overviewSheet.write(row, 0, 'Online CPU', TableCell(workbook))
    overviewSheet.write(row, 1, str(runInfo.totalCores), TableCell(workbook))
    row += 1
    overviewSheet.write(row, 0, 'Sockets', TableCell(workbook))
    overviewSheet.write(row, 1, str(runInfo.sockets), TableCell(workbook))
    row += 1
    overviewSheet.write(row, 0, 'Numa Nodes', TableCell(workbook))
    overviewSheet.write(row, 1, str(runInfo.numaNodes), TableCell(workbook))
    row += 1
    overviewSheet.write(row, 0, 'CPU Frequency', TableCell(workbook))
    overviewSheet.write(row, 1, str(runInfo.cpuFreq), TableCell(workbook))
    row += 1

    for n in range(len(runInfo.node)):
      overviewSheet.write(row, 0, 'Node'+n+' CPUs', TableCell(workbook))
      overviewSheet.write(row, 1, runInfo.node[n], TableCell(workbook))
      row += 1

    overviewSheet.write(row, 0, 'Core Mask', TableCell(workbook))
    overviewSheet.write(row, 1, runInfo.coreMask, TableCell(workbook))
    row += 1
    overviewSheet.write(row, 0, 'DF Mask', TableCell(workbook))
    overviewSheet.write(row, 1, runInfo.dfMask, TableCell(workbook))
    row += 1
    overviewSheet.write(row, 0, 'L3 Mask', TableCell(workbook))
    overviewSheet.write(row, 1, runInfo.l3Mask, TableCell(workbook))
    row += 1
    overviewSheet.write(row, 0, 'UMC Mask', TableCell(workbook))
    overviewSheet.write(row, 1, runInfo.umcMask, TableCell(workbook))
    row += 1
    overviewSheet.write(row, 0, 'Command used', TableCell(workbook))
    overviewSheet.write(row, 1, runInfo.commandLine, TableCell(workbook))

def CheckInputFiles(params, isReport):
    if (True == isReport):
        if not ((len(params.cfgList) > 0) or (params.genRawEvent == True)):
          print('Specify the config file using option --config <config file> or --raw_events <file name>')
          sys.exit()
    else:
        if not ((len(params.cfgList) > 0) or (params.collectRaw == True)):
          print('Specify the config file using option --config <config file> or --raw <file name>')
          sys.exit()

        if params.inputFile == '':
            print('Specify the raw binary file using option -i <input file>')

def ExecuteApp(app, idx):
    global g_appRunning
    g_appRunning = True
    process = subprocess.Popen(app, shell=True)

    # This a blocking call. Hence application is launched in a separate thread
    process.communicate()
    g_appRunning = False

def ExecuteLinuxPerf(seqId, idx, app, cpuMaskStr, params):
    """Prepares perf command for core,df,l3 and executes it.
    Collects umc data by launching application in a separate thread.

    :param seqId: Sequence Id , if seqId!=0, then program should sleep for sometime to avoid race conditions.
    :type seqId: int
    :param idx: Profile type ie, idx 0=core, idx 1=df , idx 2=l3, idx 3=umc
    :type idx: int
    :param app: Command to launch the application
    :type app: String
    :param cpuMaskStr: Cpu mask for current profile type.
    :type cpuMaskStr: String
    :param params: General runtime info
    :type params: AMDClassDefinition.CommonParams

    :returns: None
    """
    eventCnt = 1
    msr = '\'{'
    pmcs = '{'
    cmds = ''
    coreInL3 = ''
    umcEventList = []
    mergeEvent = []
    global g_collecting
    global startTs
    completeGrp = False
    hwCnt = utils.GetAvailablePmcs(idx)
    outPath = params.outputFile

    if params.collectRaw:
        if len(rawCmdStrList[idx]) ==0:
            return
        rawCmds = rawCmdStrList[idx]

    else:
        for ev in eventCmdList[idx]:
            if (idx == params.TYPE_UMC):
                grpIdx = int(ev.name.split('_0')[1])

                if '0x80000000' == ev.cmd:
                    ev.cmd = '0x82000000'
                if len(umcEventList) < (grpIdx + 1):
                    umcEventList.append([])
                    umcEventList[grpIdx].append(ev)
                else:
                    umcEventList[grpIdx].append(ev)

            if (idx == params.TYPE_L3) and ('retired_instructions' in ev.name):
                coreInL3 = ' -e \'{'+ev.cmd+'}\' '
            elif ('msr' in ev.cmd):
                if (ev.cmd not in msr):
                    msr += ev.cmd + ', '
            else:
                if ('Yes' in ev.mergeEvent):
                    mergeEvent.append(ev.cmd)
                else:
                    pmcs += ev.cmd

                    if ((eventCnt % hwCnt) == 0):
                        pmcs += '}\' -e \'{'
                        completeGrp = True
                    else:
                        pmcs += ', '
                        completeGrp = False
                    eventCnt += 1

        pmcs = pmcs[:-2] if (False == completeGrp) else pmcs[:-8]

        pmcs += '}\' '
        # perf is in undefined state if we combine merge event group and other event group
        # individual group works fine
        #mergeHw = hwCnt/2
        #mergeCnt = 1
        #completeGrp = False
        #if (len(mergeEvent) > 0):
        #    pmcs += '-e \'{'
        #    for m in mergeEvent:
        #        pmcs += m
        #        if ((mergeCnt % mergeHw) == 0):
        #            pmcs += '}\' -e \'{'
        #           completeGrp = True
        #        else:
        #            pmcs += ', '
        #            completeGrp = False
        #        mergeCnt += 1
        #    pmcs = pmcs[:-2] if (False == completeGrp) else pmcs
        #    pmcs += '}\' '
        for m in mergeEvent:
            pmcs += '-e \'{' + m + '}\' '

        rawCmds = ' -e ' + msr[:-2] + '}\' '+coreInL3+' -e \'' + pmcs

    cmds = osFeatures.GetPerf() + ' stat record ' + rawCmds

    if (params.genRawEvent):
        rawCmdStrList[idx] = rawCmds
    else:

        resultPath = utils.getTempFilePath('result_' + str(idx) +'.out')

        if (len(cpuMaskStr) > 0):
            cmds += cpuMaskStr

        if params.interval != 0:
            cmds += f' -I {params.interval} '

        cmds += params.pid
        cmds += params.tid
        cmds += params.inherit

        fileName = 'data.' + utils.GetTypeStr(idx)
        cmds += ' -o ' + fileName

        if (app != ''):
            if (seqId == 0):
                cmds += app
            else:
                cmds += ' ' + utils.GetApplicationPath() + '/AMDDummySleep.py'

        # Add duration
        elif (params.duration != 0):
            cmds += ' sleep ' + params.duration
        else:
            print ("Error: Profile duration is not set")
            sys.exit()

        if ((False == params.verbose) or (idx == params.TYPE_UMC)):
            cmds += ' 2>' + str(resultPath)
        else:
           print(cmds)

        g_collecting = True

        perfCmdFileName  = f"cmds{str(idx)}.sh"
        perfCmdPath = utils.getTempFilePath(perfCmdFileName)
        cHld = utils.OpenFile(perfCmdPath, "w")
        cHld.write(cmds)
        cHld.close()

        if idx != 3:
            os.system('bash '+ str(perfCmdPath))

        if (params.collect) or params.collectRaw:
            outFileName = outPath + '/' + os.path.basename(params.outputFile) + ('.' + utils.GetTypeStr(idx))

            if idx == 3:
                # Prepare umc event list
                elapseTime = 0
                durationMs = 0
                params.samplingPeriod = params.interval if (params.interval > 0) else 1000
                params.rawFileHld = utils.OpenFile(outFileName, "w")
                umcCollect.InitUmc(params, umcEventList, cmds)

                if (app == ''):
                    durationMs = int(params.duration) * 1000
                else:
                    appThread = threading.Thread(target=ExecuteApp, args=(app, 0))
                    appThread.start()

                while (1):
                    umcCollect.ReadMultiplexCounters(params, umcEventList)
                    elapseTime += params.samplingPeriod

                    if app != '':
                        if (g_appRunning == False):
                            break

                    elif (durationMs != 0) and (elapseTime >= durationMs):
                        break

                umcCollect.FinalizeUmc(params, umcEventList)
                utils.CloseFile(params.rawFileHld)
            else:
                # Check if there is no error from perf side
                resultPath = utils.getTempFilePath('result_' + str(idx) + '.out')
                resultOut = utils.OpenFile(resultPath, 'r')

                if None != resultOut:
                    for line in resultOut:
                        if 'Workload failed:' in line:
                            print('Collection incomplete as there is error running the workload:', app)
                            utils.DeleteTempDir()
                            os._exit(1)

                rawCmds = osFeatures.GetPerf() + ' script -i' +fileName+ ' --header> '+ outFileName
                result = utils.GetCmdOutput(rawCmds)

                if ('failed' in result):
                    print(result)
                    print('Run with -V option to get details')
                    os._exit(1)

            print('Generated raw file: ' + outFileName)
        try:
            envHld = open(utils.getTempFilePath(fileName="env.txt"),'w')
            envHld.write('1')
            envHld.close()
        except Exception as e:
            print("Error: {}".format(e))
            sys.exit()

        g_collecting = False

def PrepareAMDuProfCliRawEvSet(seqId, idx, params):
    """Prepares raw event set for each profile type.
    Format: -e "event1,event2,event3" -e "event4,event5" -e "event6"

    :param seqId: Sequence number of current profile type.
    :type seqId: int
    :param idx: Profile type ie, idx 0=core, idx 1=df , idx 2=l3, idx 3=umc
    :type idx: int
    :param params: General runtime info
    :type params: AMDClassDefinition.CommonParams

    :returns: None
    """
    if params.collectRaw:
        return rawCmdStrList[idx]
    eventCnt = 1
    msr = ''
    pmcs = ''

    prefix = '\"'
    postfix = prefix
    corePostfix = postfix
    pmcIntertext = '\" -e "'
    msrPostfix = '\"'
    affintyOpt = " --affinity 0 "
    cmds = ''
    coreInL3 = ''
    umcEventList = []
    mergeEvent = []
    global g_collecting
    global startTs
    completeGrp = False
    grpCount = 0
    hwCnt = utils.GetAvailablePmcs(idx)

    for ev in eventCmdList[idx]:
        if (idx == params.TYPE_L3) and ('retired_instructions' in ev.name):
            coreInL3 = ' -e \"'+ev.cmd+'\" '
        elif ('msr' in ev.cmd):
            if (seqId == 0) and (ev.cmd not in msr):
                msr += ev.cmd + ','
        else:
            if ('Yes' in ev.mergeEvent):
                mergeEvent.append(ev.cmd)
            else:
                pmcs += ev.cmd

                if ((eventCnt % hwCnt) == 0):
                    pmcs += pmcIntertext
                    completeGrp = True
                    grpCount+=1
                else:
                    pmcs += ','
                    completeGrp = False
                eventCnt += 1

    if msr != '':
        msr = ' -e \"' + msr[:-1] + '\"'
    pmcs = pmcs.rstrip(',') if (False == completeGrp) else pmcs[:-6]

    if(len(mergeEvent) > 0):
        pmcs += corePostfix
        for m in mergeEvent:
            pmcs += ' -e ' + prefix + m + corePostfix
            grpCount+=1

        pmcs = pmcs[:-1]
        postfix = corePostfix

    evSetRaw = coreInL3 +' -e ' + prefix + pmcs + postfix
    if (params.genRawEvent):
        rawCmdStrList[idx] = evSetRaw
    return evSetRaw

def IsAvailableEvent(eventName, runInfo):
    """Checks if a particular event(currently IRPERF only) is available.

    :param eventName: Event name that needs to be checked
    :type eventName: str
    :param runInfo: System information
    :type runInfo: AMDClassDefinition.RunInfo

    :returns: True if event is available, else False.
    :rtype: bool

    """
    if eventName == "irperf" and not runInfo.isIRPERF:
        return False

    return True

def ProcessRawEventFile(params):

    idx = 0
    with open(params.rawEventFile) as f:
        for cmds in f.readlines():
            rawCmdStrList[idx] = cmds[:-1]
            idx +=1


def ProcessEvents(params, runInfo):
    """
    Initialize AMDClassDefinition.EventCmd parameters for events in eventList[] and append in eventCmdList[] grouped by profile type.
    """
    for idx in params.cfgTypeList:
        eventCmdList.append([])

    if (params.rawEventFile == ''):
        # parse config eventList
        for grp in eventCfgList:

            for event in grp.events:
                #print(event)
                scope = ''
                eventName = event

                for ev in eventList:

                    if eventName.split(':')[0] == ev.EventName:
                        #print('EV NAME', ev.EventName)

                        if ':' in eventName:
                            scope = eventName.split(':')[1]

                        evCmd, counterType = ev.PreparePerfCTL(scope, runInfo, params)
                        #print(ev.EventName, counterType)

                        if (counterType == 'Core'):
                            params.hasCore = True
                        elif (counterType == 'DF'):
                            params.hasDF = True
                        elif (counterType == 'L3'):
                            params.hasL3 = True
                        elif (counterType == 'UMC'):
                            params.hasUMC = True
                        if IsAvailableEvent(eventName, runInfo):
                            #print(ev.EventName, 'CMD', evCmd)
                            eventCmdList[utils.GetTypeIndex(grp.cfg)].append(classDefs.EventCmd(eventName, evCmd.strip(), ev.EventType, ev.MergeEvent, counterType))
                        break

def CollectData(params, runInfo):
    """Main collector function.
    2. Process Raw events and profile type(core, df, l3, umc) masks.
    3. For each profile type launches a thread to collect data using ExecuteLinuxPerf().

    :param params: General runtime info
    :type params: AMDClassDefinition.CommonParams
    :param runInfo: System info
    :type params: AMDClassDefinition.RunInfo

    :returns: None
    """
    global fEventSets
    argIdx = 0
    cpuMaskStr = []
    drvCmds = ''

    # Command array for core, l3, df, umc
    for idx in params.cfgTypeList:
        cpuMaskStr.append([])

    #perf = osFeatures.OSPerfFeatures()

    fEventSets = len(eventCfgList) # number of groups

        # read events from raw_config.raw

    if (params.coreMask == '0') or ((params.coreMask != '') and (params.coreMask != '-a')):
        cpuMaskStr[params.TYPE_CORE] = ' -C ' + params.coreMask

    elif (params.coreMask == '-a'):
        cpuMaskStr[params.TYPE_CORE] = ' -a'

    if (params.hasDF):
        params.dfMask = osFeatures.GetDFCoreMask()
        cpuMaskStr[params.TYPE_DF] = ' -C ' + params.dfMask

    if params.hasL3:
        params.l3Mask = osFeatures.GetL3CoreMask()
        cpuMaskStr[params.TYPE_L3] = ' -C ' + params.l3Mask

    if params.hasUMC and not params.isUncoreDriver:
        params.umcMask = ''
        if params.collect:
            umcCollect.InitPci()
            umcDev = ''

            for n in range(osFeatures.GetIODCoreMask(runInfo)):
                umcDev += hex(umcCollect.GetBusNumber(n))+','

            umcDev = umcDev[:-1]
            params.umcMask = umcDev
        else:
            params.umcMask = runInfo.umcMask

        #print 'umcDev', umcDev
        params.umcCount = int(runInfo.umcCount)

        for s in runInfo.socketCores:
           params.iodCoreMask.append(s[0])

        if params.collect:
            umcCollect.ClosePci()

        cpuMaskStr[params.TYPE_UMC] = ' -C ' + params.umcMask

    app = ''
    while argIdx < len(params.appArgv):
        app += (' ' + params.appArgv[argIdx])
        argIdx += 1

    if params.collect or params.collectRaw:
        if utils.IsLinux():
            osFeatures.CheckNMIWatchdog(params.isUncoreDriver)

        if not params.isUncoreDriver:
            osFeatures.CheckPerfEventParanoid()

            # Following FIXED counters are required:
                # Core - TSC, IRPERF, APERF, MPERF
                # L3   - TSC, IRPERF, APERF
                # DF   - TSC
                # UMC  - TSC
            if (params.hasCore or params.hasL3) and params.verbose :
                if runInfo.isIRPERF == False:
                    print('Note: IRPERF is not available. Retired Instruction will be used instead')
                else:
                    print('Note: IRPERF is considered for all metrics calculation')

        if app != '':
            print('Collecting profile data for' + app + '...')
        else:
            print('Collecting system wide profile data...')

        if (not params.genRawEvent):
            utils.WriteRunInfo(params, runInfo, eventCmdList, rawCmdStrList)

        seqId = 0

        if params.isUncoreDriver:
            scopeStr = os.getenv("AMDUPROF_SCOPE_STR")
            evSetRaw = str()

            if scopeStr != None:
                if utils.IsWindows():
                    drvCmds = utils.GetApplicationPath() + '/../AMDProfiler/Output/release/bin/AMDuProfCLI stat'
                else:
                    # This is to test in Linux
                    drvCmds = utils.GetApplicationPath() + '/../AMDProfiler/Output_x86_64/release/bin/AMDuProfCLI stat'
            else:
                if utils.IsWindows():
                    uprofCLIPath = glob.glob(utils.GetApplicationPath() + '\\..\\AMDuProfCLI*.exe')[0]
                    uProfCliCmd = os.path.basename(uprofCLIPath)
                if utils.IsLinux():
                    uprofCLIPath = utils.GetApplicationPath() + '/../AMDuProfCLI'
                    uProfCliCmd = uprofCLIPath

                drvCmds = '{} stat'.format(uProfCliCmd)

        perfThreads = []
        for idx in params.cfgTypeList:
            if (not params.collectRaw and len(eventCmdList[idx]) == 0):
                continue
            if (params.collectRaw and len(rawCmdStrList[idx]) == 0):
                continue

            if not params.isUncoreDriver:
                thread = threading.Thread(target= ExecuteLinuxPerf, args=(seqId, idx, app, cpuMaskStr[idx], params))
                perfThreads.append(thread)
                seqId += 1
                thread.start()

                if (params.genRawEvent):
                    thread.join()
            else:
                if idx == params.TYPE_UMC:
                    evSetRaw += umcCollect.PrepareStatEvSet(params, eventCmdList)
                else:
                    evSetRaw += PrepareAMDuProfCliRawEvSet(seqId, idx, params)
                seqId += 1

        # join linux-perf threads for different PMUs
        for thread in perfThreads:
            thread.join()
        if (params.genRawEvent):

            # Write raw event list
            if (params.genRawEvent == True):

                if (params.outputFile == ''):
                    params.outputFile = 'raw_config'

                path = params.outputFile + '.raw'
                rawHld = open(path, 'w')

                for i in params.cfgTypeList:
                    if (len(rawCmdStrList[i]) > 0):
                        rawHld.write(rawCmdStrList[i])
                        rawHld.write('\n')
                    else:
                        rawHld.write('')
                        rawHld.write('\n')

                print('Raw event file generated: ' + path)

                rawHld.close()
                sys.exit()

        # print Report command for linux-perf
        if not params.isUncoreDriver and not params.genRawEvent:
            outDir = Path(params.outputFile)
            outFileName = outDir / (outDir.name + ".ses")
            utils.PrintGenReportCmd(outFileName)

        if params.isUncoreDriver:
            evSetFilePath = utils.WriteEvSetToFile(evSetRaw.strip(" ").rstrip(" "))
            drvCmds += " -i " + str(evSetFilePath) + " "

            muxIntervalCmd = " --count-mode-mux-interval "
            if params.uncoreDriverMuxInterval:
                muxIntervalCmd += str(params.uncoreDriverMuxInterval)
            else:
                muxIntervalCmd += str(DEFAULT_MUX_INTERVAL_UNCORE_DRIVER)
            drvCmds += muxIntervalCmd

            logIntervalCmd = " --count-mode-log-interval "
            if params.interval:
                logIntervalCmd += str(params.interval)
            else:
                logIntervalCmd += str(DEFAULT_LOG_INTERVAL_UNCORE_DRIVER)
            drvCmds += logIntervalCmd

            # Mask is supported only for core PMCs. This is limitation on Linux perf. Hence kept
            # the behaviour same
            if (len(cpuMaskStr[0]) > 0):
                cpuMask = cpuMaskStr[0].replace('-C', '--cpu')
                drvCmds += cpuMask

            drvCmds += ' -o ' + params.outputFile

            if (app != ''):
                drvCmds += app

            # Add duration
            elif (params.duration != 0):
                if utils.IsWindows():
                    drvCmds += ' -d ' + params.duration
                else:
                    drvCmds += ' sleep ' + params.duration
            else:
                print ("Error: Profile duration is not set")
                sys.exit()

            #if (False == params.verbose):
            #    drvCmds += ' 2>/dev/null'

            if (params.verbose):
                print(drvCmds)

            #os.system(drvCmds)
            if params.collect or params.collectRaw:
                StatHandler(drvCmds.split(), params)

    # clean the temporary files
    utils.DeleteTempDir()

def Report(params, runInfo, sessionInfo, xls):
    global fCpuMhz
    maxDepth = 1
    errorCount = 0
    fTimerMhz=fCpuMhz = runInfo.cpuFreq
    umcOutStream = None
    xls = False
    aggrDisp = True if params.groupby != '' else False
    processedMetricsList = [dict() for x in range(runInfo.threadPerSocket * runInfo.sockets)]

    if (params.format == 'XLS'):
        xls = True
        params.outputFile += '.xlsx'

    for cfg in params.cfgList:
        cfgFile = os.path.basename(cfg.lstrip()).split('.')[0]
        profileCfgList[utils.GetTypeIndex(cfgFile)].append(classDefs.XlsxSheets(cfgFile))

    if xls:
        workbook = xlsxwriter.Workbook(params.outputFile)
        workbook.add_format({'bold': True})

        # Write overview sheet
        WriteOverviewSheet(workbook, runInfo, sessionInfo)

    # Generate report for code, df, l3 in each loop
    for idx in params.cfgTypeList:
        totalMetrics = len(reportMetricList[idx])

        if ((len(params.mask[idx]) == 0) or (totalMetrics == 0) or (len (params.rawDataList[idx]) == 0)):
            continue

        print('Reporting started...\nTotal metric: ' + str(totalMetrics))

        # Read raw binary event count file and prepare the output list
        if (idx == 3 and not params.isUncoreDriver):
            umcOutStream, evGroupCnt, eventCount = umcCollect.ReadUmcData(idx, sessionInfo.ncpu, params, runInfo, eventCmdList)
        else:
            ReadPerfData(idx, sessionInfo.ncpu, params, runInfo)

        if xls:
            cfgSheet = workbook.add_worksheet(utils.GetTypeStr(idx) + '_config')
            dataSheet = workbook.add_worksheet(utils.GetTypeStr(idx) + '_report')
            cfgRow = 0
            dataRow = 0

            # Selected counter list to the xls
            cfgSheet.write(cfgRow, 0, 'EventName', TableHeader(workbook))
            cfgSheet.write(cfgRow, 1, 'Description', TableHeader(workbook))
            cfgSheet.set_column(0, 0, 40)
            cfgSheet.set_column(1, 1, 60)
            cfgRow += 1

        # Pocess all config files
        for cfg in tqdm(profileCfgList[idx], file = sys.stdout):
            coreOutList = []

            if xls:
                cfgRow += 1
                cfgSheet.write(cfgRow, 0, cfg.cfgSheetName, TableHeader(workbook))
                cfgRow += 1

                cfg.cfgSheet = cfgSheet
                cfg.dataSheet = dataSheet

                # Get the depth for the cfg
                for c in profileCfgDepthList:
                    if cfg.name in c.name:
                        maxDepth = c.depth

                if ('df' in cfg.dataSheetName):
                    cfg.dataSheet.set_column(0, maxDepth - 1, 30)
                else:
                    cfg.dataSheet.set_column(0, 0, 20)
                    cfg.dataSheet.set_column(1, maxDepth - 1, 15)

                cfg.dataSheet.set_column(maxDepth, maxDepth + 500, 20)
                cfg.dataSheet.freeze_panes(0, maxDepth)

                for grp in eventCfgList:
                    if (grp.cfg == cfg.cfgSheetName):
                        for e in grp.events:
                            ev = GetEvent(e.split(':')[0])

                            if ev is not None:
                                desc = ev.BriefDescription if ev.BriefDescription is not None else e
                                cfg.cfgSheet.write(cfgRow, 0, e, TableCell(workbook))
                                cfg.cfgSheet.write(cfgRow, 1, desc, TableCell(workbook))
                                cfgRow += 1
                            else:
                                print('Event not supported: ' + e.split(':')[0])
                                sys.exit()

            # Add a blank line before data table
            coreOutList.append(classDefs.XLSXLine(GetCounterHeader(params, runInfo, cfg.name,maxDepth, params.mask[idx], not xls), 'bold', cfg.name))

            # Evaluate all metrics
            for mPair in reportMetricList[idx]:
                isNonPrinting = False
                if mPair.cfg != cfg.name:
                    continue

                # print ln
                m = metricDict.get(mPair.nameStr.replace(',', ''))

                if m == None:
                    print ('Unexpected error decoding metrics')
                    exit(0)
                if m.Name.startswith('#Section') or m.Name.startswith('Section:'):
                    sectionHdr = m.Name
                    for n in range(maxDepth + len(params.mask[idx]) - 1):
                        sectionHdr += ','
                    coreOutList.append(classDefs.XLSXLine(sectionHdr, 'number', m.cfg))
                if m.Name.startswith('Blank'):
                    continue
                elif m.Name.startswith('NonPrinting'):
                    isNonPrinting = True
                else:
                    ln = mPair.nameStr

                pos = len(ln.split(',')) - 1
                ln = ''

                # padding commas
                if not isNonPrinting:
                    if xls:
                        for n in range(0, maxDepth):
                            if n == pos:
                                ln += mPair.name
                            ln += ','
                    else:
                        for n in range(0, pos):
                            ln += '... '
                        ln += mPair.name + ','

                # For section/blank expression
                if len(m.Expression) == 0:
                    continue

                if m is not None:
                    # Value is already normalized. So fEventSets is set to 1
                    m.Expression = m.Expression.replace('(fEventSets)', str(1))
                    m.Expression = m.Expression.replace('(EventSets)', str(1))

                    if aggrDisp:
                        for g in range(g_aggr.totalGroups):
                            for s in range(g_aggr.valueInstance[g]):
                                if g_aggr.valueStr[g] not in params.groupby:
                                    continue

                                exp = m.Expression
                                useRaw = m.UseRaw

                                # Check for any metrics which is already calculated. It could be nonprint metrics
                                # or already calculated metrics
                                # All such metrics names are CamelCase
                                tokens = re.findall(r"[\w']+", exp)

                                for n in tokens:
                                    if (len(n) > 0) and not utils.IsNumber(n) and (n.lower() != n):
                                         #print('Finding', n)
                                         if n in processedMetricsList[g]:
                                             exp = exp.replace(n, processedMetricsList[g][n])

                                for v in g_aggr.value[g][s]:
                                    exp = utils.Replace(exp, v.name, str(v.value[useRaw]))

                                    if utils.IsExprDecoded(exp):
                                        break
                                try:
                                    val = str(eval(exp))

                                    # Add all processed metrics to the processedMetricsList
                                    # print('Adding', m.Abbreviation)
                                    processedMetricsList[g][m.Abbreviation] = val

                                    if not isNonPrinting:
                                        ln += utils.FormatMetricValue(val, params.precision) + ','
                                except ZeroDivisionError:
                                    #print 'Issue evaluating the expression:', exp, expression
                                    #sys.exit()
                                    val = '0'
                                    ln += '0' + ','

                    for core in params.mask[idx]:
                        exp = m.Expression
                        useRaw = m.UseRaw

                        if (idx == 3 and not params.isUncoreDriver):
                            bus = umcCollect.GetUmcMaskIdx(params, core)
                            for clk in range(len(umcOutStream[0][bus])):
                                exp = m.Expression

                                for grp in range(len(umcOutStream[0][bus][clk])):
                                    for umcEv in range(len(umcOutStream[0][bus][clk][grp])):
                                        exp = utils.Replace(exp, umcOutStream[0][bus][clk][grp][umcEv].name, str(umcOutStream[0][bus][clk][grp][umcEv].value[useRaw]))
                                try:
                                    ln += str(eval(exp)) + ','
                                except ZeroDivisionError:
                                    ln += '0,'
                        else:
                            # Check for any metrics which is already calculated. It could be nonprint metrics
                            # or already calculated metrics
                            # All such metrics names are CamelCase
                            tokens = re.findall(r"[\w']+", exp)

                            for n in tokens:
                                if (len(n) > 0) and not utils.IsNumber(n) and (n.lower() != n):
                                     #print('Finding', n)
                                     if n in processedMetricsList[core]:
                                         exp = exp.replace(n, processedMetricsList[core][n])

                            for v in outputStream[0][int(core)]:
                                exp = utils.Replace(exp, v.name.strip(), str(v.value[useRaw]))
                                if utils.IsExprDecoded(exp):
                                    break
                            try:
                                val = str(eval(exp))

                                # Add all calculated metrics in the processedMetricsList
                                # print('Adding', m.Abbreviation)
                                processedMetricsList[core][m.Abbreviation] = val

                                if not isNonPrinting:
                                    ln += utils.FormatMetricValue(val, params.precision) + ','

                            except ZeroDivisionError:
                                #print 'Issue evaluating the expression:', exp, expression
                                #sys.exit()
                                val = '0'
                                ln += '0' + ','
                                processedMetricsList[core][m.Abbreviation] = val
                            except NameError:
                                if (idx != 1) or (params.verbose):
                                    # Skip error for DF filter mask
                                    print("Expression Error: ", m.Abbreviation, exp)

                                if (params.verbose):
                                    errorCount += 1
                                elif idx != 1:
                                    sys.exit()
                            except SyntaxError:
                                   print('Syntax Error: ', exp)
                            except:
                                ln += ' ,'
                                print('Unhandled Error: ', exp)

                    ln = ln[:-1]
                    #print ln
                    if not isNonPrinting:
                        coreOutList.append(classDefs.XLSXLine(ln, 'number', m.cfg))
                    ln = ''
                else:
                    # For raw counters
                    for core in params.mask[idx]:
                        for v in outputStream[0][core]:
                            if (core == int(v.core)) and (mPair.nameStr == v.name):
                                try:
                                    val = str(v.value[0])
                                except ZeroDivisionError:
                                    val = '0'
                                ln += utils.FormatMetricValue(val, params.precision) + ','
                    ln = ln[:-1]
                    coreOutList.append(classDefs.XLSXLine(ln, 'number', 'x'))
                    # Evaluate all metrics

            color = '#C1E0FF'
            records = len(coreOutList)

            if xls:
                cfg.dataSheet.write(dataRow, 0, cfg.cfgSheetName, TableHeader(workbook))
                dataRow += 1

                # Write the counter reading in xls
                for ln in range(records):
                    col = 0

                    metName = coreOutList[ln].line.split(',')[0]
                    if metName.startswith('#Section:') or metName.startswith('Section:'):
                        dataRow += 1
                        cfg.dataSheet.write(dataRow, col, coreOutList[ln].line.split(',')[0], '#FFFFFF')

                    # If parent with a child then add a blank line
                    if coreOutList[ln].line.split(',')[0] != '':
                        if ((ln + 1) < records) and (coreOutList[ln + 1].line.split(',')[0] == ''):
                            dataRow += 1
                            color = utils.GetColorCode(dataRow)

                    for c in coreOutList[ln].line.split(','):
                        if coreOutList[ln].style == 'bold':
                            cfg.dataSheet.write_row(dataRow, col, coreOutList[ln].line.split(',')[0:], TableHeader(workbook))
                            break
                        else:
                            try:
                                val = float(c)
                            except:
                                val = c
                            cfg.dataSheet.write(dataRow, col, val, TableCell(workbook, color))
                        col += 1
                    dataRow += 1
                dataRow += 1

            # CSV file write
            else:
                outFileName = params.outputFile + '_' + utils.GetTypeStr(idx)+'.csv'
                outFile = utils.OpenFile(outFileName, "w")

                for ln in range(records):
                    metName = coreOutList[ln].line
                    if ln != 0 and (metName.startswith("#Section") or metName.startswith("Section")) :
                        outFile.write('\n')
                    outFile.write(coreOutList[ln].line + '\n')

                outFile.close()
                print('Generated report file: ' + outFileName)
    if xls:
        workbook.close()
        print('Generated report file: ' + params.outputFile)


    if (params.verbose and errorCount > 0):
        print('Total error metrics: ', errorCount, 'of', totalMetrics)


def WriteReport(outFileName, metricHeader, data):
    outFile = utils.OpenFile(outFileName, "w")

    if (None != outFile):
        outFile.write(metricHeader)
        outFile.write('\n')

        for line in data:
            outFile.write(line)
    else:
        print('Failed to create output file:'+ outFileName)
        sys.exit()

    outFile.close()

def CsvTimeSeriesReportUmc(idx, params, runInfo, sessionInfo, cfgName):
    coreOutList = []
    outFileName = []
    timeSeriesStream, evGroupCnt, eventCount = umcCollect.ReadUmcData(idx, sessionInfo.ncpu, params, runInfo, eventCmdList)

    # Create time series for each umc
    for inst in range(len(timeSeriesStream)):
        socket = 0
        for bus in params.mask[idx]:
            busId = umcCollect.GetUmcMaskIdx(params, bus)

            if inst == 0:
                outFileName.append([])
                coreOutList.append([])

            for clk in range(params.umcCount):
                if inst == 0:
                    outFileName[busId].append([])
                    coreOutList[busId].append([])

                metricHeader = ' '
                getMetricName = True

                # Time series files for each clk
                for mPair in reportMetricList[idx]:
                    if cfgName not in mPair.cfg:
                        continue

                    # print ln
                    m = metricDict.get(mPair.nameStr.replace(',', ''))
                    useRaw = m.UseRaw

                    if (getMetricName):
                        if m.Name.startswith('Blank'):
                            metricHeader += ' ,'
                        else:
                            metricHeader += m.Name + ','
                    ln = ''

                    if m is not None:
                        # Value is already normalized. So fEventSets is set to 1
                        exp = m.Expression.replace('(fEventSets)', str(1))

                    exp = m.Expression
                    useRaw = m.UseRaw

                    for grp in range(len(timeSeriesStream[inst][busId][clk])):
                        for umcEv in range(len(timeSeriesStream[inst][busId][clk][grp])):
                            exp = utils.Replace(exp, timeSeriesStream[inst][busId][clk][grp][umcEv].name, str(timeSeriesStream[inst][busId][clk][grp][umcEv].value[useRaw]))
                    try:
                        if  m.Name.startswith('Blank'):
                            ln += ' ,'
                        else:
                            ln += str(eval(exp)) + ','
                    except ZeroDivisionError:
                        ln += '0,'
                    except NameError:
                        print("Expression Error: " + exp)
                        sys.exit()

                    coreOutList[busId][clk].append(ln)

                getMetricName = False
                coreOutList[busId][clk].append('\n')

                # Construct output file name only once
                if inst == 0:
                    outFileName[busId][clk] = params.outputFile[:-4]+'_'+ cfgName +'_socket'+ str(socket)+ '_umc' + str(clk) + '.csv'

            # One bus per socket
            socket += 1

    for busId in range(len(outFileName)):
        for clk in range(len(outFileName[busId])):
            WriteReport(outFileName[busId][clk], metricHeader, coreOutList[busId][clk])

# For time series following are considered
# -Single config file to profile
# -CSV output only
def CsvTimeSeriesReport(params, runInfo, sessionInfo):
    global fCpuMhz
    fTimerMhz = fCpuMhz = runInfo.cpuFreq

    for cfg in params.cfgList:
        cfgFile = os.path.basename(cfg)[:-5]
        profileCfgList[utils.GetTypeIndex(cfgFile)].append(classDefs.XlsxSheets(cfgFile))

    # Generate report for code, df, l3 in each loop
    for idx in params.cfgTypeList:

        if (len(params.mask[idx]) == 0):
            continue

        coreOutList = []
        metricHeader = []
        del coreOutList[:]
        del metricHeader[:]

        if (3 != idx):
            # Read raw binary event count file and prepare the output list
            ReadPerfData(idx, sessionInfo.ncpu, params, runInfo)

        for cfg in tqdm(profileCfgList[idx]):
            # Pocess all config files
            metricHeader = ''

            processedInstMetricsList = [[dict() for x in range(runInfo.threadPerSocket * runInfo.sockets)] for y in range(len(outputStream)-1)]

            if (3 == idx):
                CsvTimeSeriesReportUmc(idx, params, runInfo, sessionInfo, cfg.name)
                continue

            # Create time series for each core
            for core in params.mask[idx]:
                getMetricName = True
                metricHeader = '#Time series report for:'+ cfg.name + str(core)+'\n'

                for inst in range(len(outputStream)-1):
                    # Evaluate all metrics
                    for mPair in reportMetricList[idx]:
                        isNonPrinting = False
                        if cfg.name not in mPair.cfg:
                            continue

                        # print ln
                        m = metricDict.get(mPair.nameStr.replace(',', ''))

                        if m == None:
                            print ('Unexpected error decoding metrics: ' + mPair.nameStr)
                            exit(0)

                        useRaw = m.UseRaw

                        if m.Name.startswith('NonPrinting'):
                            isNonPrinting = True
                        if m.Name.startswith('#Section') or m.Name.startswith('Section'):
                            continue

                        if (not isNonPrinting and getMetricName):
                            metricHeader += m.Name + ','
                        ln = ''

                        if m is not None:
                            # Value is already normalized. So fEventSets is set to 1
                            exp = m.Expression.replace('(fEventSets)', str(1))
                            exp = exp.replace('(EventSets)', str(1))

                            # Check for any metrics which is already calculated. It could be nonprint metrics
                            # or already calculated metrics
                            # All such metrics names are CamelCase
                            tokens = re.findall(r"[\w']+", exp)

                            for n in tokens:
                                if (len(n) > 0) and not utils.IsNumber(n) and (n.lower() != n):
                                    if n in processedInstMetricsList[inst][core]:
                                        exp = exp.replace(n, processedInstMetricsList[inst][core][n])

                            for v in outputStream[inst][core]:
                                exp = utils.Replace(exp, v.name.strip(), str(v.value[useRaw]))

                                if utils.IsExprDecoded(exp):
                                    break
                            try:
                                #print exp
                                val = ''
                                try:
                                    val = str(eval(exp))
                                except NameError:
                                    print("Expression Error: " + exp)
                                    sys.exit()
                                except:
                                    val = '0'

                                # check if expression itself is NonPrinting
                                # print('Adding', m.Abbreviation)
                                processedInstMetricsList[inst][core][m.Abbreviation] = val
                                if not isNonPrinting:
                                    ln += utils.FormatMetricValue(val, params.precision) + ','
                            except ZeroDivisionError:
                                #print ('Issue evaluating the expression:' + exp + m.Expression)
                                #sys.exit()
                                val = '0'
                                ln += '0' + ','

                            #ln = ln[:-1]
                            #print ln
                            coreOutList.append(ln)
                            ln = ''
                    coreOutList.append('\n')
                    getMetricName = False
                outFileName = params.outputFile + '_' + cfg.name + '_core' + str(core) +'.csv'
                outFile = utils.OpenFile(outFileName, "w")

                if (None != outFile):

                    outFile.write(metricHeader)
                    outFile.write('\n')
                    for line in coreOutList:
                        outFile.write(line)
                    del coreOutList[:]
                    print('Generated report file: ' + outFileName)
                else:
                    print('Failed to create output file:'+ outFileName)
                    sys.exit()

                outFile.close()

class Reporter():

    def __init__(self, params):
        self.params = params
        self.ts = 0

    def LogStartTime(self):
        return int(round(time.time() * 1000))

    def DisplaySummary(self):
        print('Reporting time:'+ utils.ConvertMsToHMSm(int(round(time.time() * 1000)) - self.ts))

    def Report(self, runInfo):
        self.ts = self.LogStartTime()
        CheckInputFiles(self.params, True)

        # Check if raw file is accessible
        if not utils.IsFileReadable(self.params.inputFile):
            print('No read permission for the raw file: %s' % self.params.inputFile)
            sys.exit()

        if self.params.isOutputFile == False:
            self.params.outputFile = self.params.inputFile[:-4]

        # Prepare raw input file names
        for rfile in runInfo.rawDataFiles:
            if '.core' in rfile:
                self.params.rawDataList[0] = rfile

            if '.df' in rfile:
                self.params.rawDataList[1] = rfile

            if '.l3' in rfile:
                self.params.rawDataList[2] = rfile

            if '.umc' in rfile:
                self.params.rawDataList[3] = rfile

        # Read session info from the ReadProfileSessionInfo
        sessionInfo = ReadProfileSessionInfo(self.params)

        if (runInfo.coreMask.rstrip() == '-a'):
            self.params.mask[self.params.TYPE_CORE].append(-1)
        elif (runInfo.coreMask != ''):
            for c in utils.GetCpuRange(runInfo.coreMask):
                self.params.mask[self.params.TYPE_CORE].append(int(c))

        if (runInfo.dfMask != ''):
            for c in runInfo.dfMask.split(','):
                self.params.mask[self.params.TYPE_DF].append(int(c))

        if (runInfo.l3Mask != ''):
            for c in runInfo.l3Mask.split(','):
                self.params.mask[self.params.TYPE_L3].append(int(c))

        if (runInfo.umcMask != ''):
            for c in runInfo.umcMask.split(','):
                self.params.mask[self.params.TYPE_UMC].append(int(c,16))

        if ((runInfo.coreMask == '') and (runInfo.dfMask == '') and (runInfo.l3Mask == '') and (runInfo.umcMask == '')):
            self.params.mask[self.params.TYPE_CORE].append(-1)
            runInfo.coreMask = '-1'

        if (runInfo.coreMask.rstrip() == '') and (runInfo.rawDataFiles[self.params.TYPE_CORE] != ''):
            self.params.mask[self.params.TYPE_CORE].append(-1)

        if (self.params.isTimeSeries):
            CsvTimeSeriesReport(self.params, runInfo, sessionInfo)
        else:
            Report(self.params, runInfo, sessionInfo, True)

        self.DisplaySummary()

def main(argv):

    #Check if Linux perf tool is available
    if utils.IsLinux() and not cpuFeatures.IsLinuxPerfAvailable():
        print("Error: Linux Perf tool not found \nMake sure perf is installed and running Eg. perf --version")
        sys.exit()

    global gToolName
    global startTs
    global g_collecting
    params = classDefs.CommonParams()
    params.format = 'CSV'
    startTs = int(round(time.time() * 1000))
    # Local variables
    getReport = True
    maxDepth = 0
    opts = ''
    collectCfgStr = False

    # Get the command string
    for arg in argv:
        params.commandLine += arg + ' '

    try:
        envHld = open(utils.getTempFilePath(fileName="env.txt"),'w')
        envHld.write('0')
        envHld.close()
    except Exception as e:
        print("Error: {}".format(e))
        sys.exit()

    for _ in params.cfgTypeList:
        params.mask.append([])
        params.rawDataList.append([])
        profileCfgList.append([])
        rawCmdStrList.append([])
        reportMetricList.append([])

    # Set the name of the tool
    gToolName = os.path.basename(__file__)

    # if there is no arguments, show the usage
    if len(argv) == 0:
        Usage()
        sys.exit()

    # Read platform type if environment is set. This is for local build only
    buildScope = os.getenv("AMDUPROF_SCOPE_STR")

    if buildScope == None:
        buildScope = ''
    else:
        buildScope = '/' + buildScope

    # default base path
    #basePath = utils.GetApplicationPath() + '/data/' + hex(runInfo.family)+'_'+ hex(runInfo.model >> 4) + buildScope

    try:
        # if collect is not specified consider collect by default
        if '--config' == argv[0]:
            argv.insert(0, 'collect')

        if 'collect' == argv[0]:
            getReport = False

            basePath = utils.GetApplicationPath() + '/data/' + g_family + '_' + hex(int(g_model, 16) >> 4) + buildScope
            if len(argv) > 1:
                argv = argv[1:]

        elif 'report' == argv[0]:
            params.collect = False

            if len(argv) > 1:
                argv = argv[1:]
        else:
            if not any( generic_opt in argv[0]
            for generic_opt in ["h","help","v","version","system-info","enable-irperf","mux-interval"]):
                print('Error: \"'+argv[0]+'\" Option not supported')
                sys.exit()

        # handle --config file before passing it to getopt. It requires special handling
        argvStripped = []
        configStr = ''
        for arg in argv:
            if ('--config' == arg) or ('-s' == arg):
                collectCfgStr = True
            else:
                if (collectCfgStr):
                    configStr = arg
                    collectCfgStr = False
                else:
                    argvStripped.append(arg)

        opts, args = getopt.getopt(argvStripped, "VThgi:C:G:I:m:r:o:p:t:f:d:s:H:x:al:v",
                                   ["version", "verbose", "pass", "all-cpus", "cpu=", "system-info", "enable-irperf", "mux-interval-core=", "mux-interval-l3=", "mux-interval-df=", "mux-interval-umc=", "help", "list=",
                                    "input-file=", "output-file=", "pid=", "tid=", "config=", "no-inherit=",
                                    "interval=", "duration=" , "collect-raw=", "format=", "raw-events","group-by=","time-series","mux-interval=","set-precision=","use-amd-driver","collect-group="])
    except getopt.GetoptError as err:
        print(str(err))
        print('Run %s -h for help' % gToolName)
        sys.exit()

    argIdx = 0

    for opt, arg in opts:
        if opt in ("-v", "--version"):
            Version()
        elif opt in ("","--use-amd-driver"):
            #FIXME
            global osFeatures
            import AMDOSFeaturesWin as osFeatures
            runInfo = osFeatures.PrepareRunInfo()
            params.isUncoreDriver = True
            argIdx += 1
        elif opt in ("-x", "--pass"):
            params.passCmd = arg
            argIdx += 1
        elif opt in ("-a", "--all-cpus"):
            params.swp = True
            params.coreMask = '-a'
            argIdx += 1
        elif opt in ("-h", "--help"):
            Usage()
        elif opt in ("-o", "--output-file"):
            # Check for valid path
            path = os.path.dirname(arg)

            if not utils.IsDirectoyWritable(path):
                print('Invalid path or path not accessible:'+ path)
                print('Provide a valid path after -o, --output option')
                sys.exit()
            params.outputFile = os.path.abspath(arg)
            params.isOutputFile = True
            argIdx += 2
        elif opt in ("-C", "--cpu"):
            params.coreMask = arg
            argIdx += 2
        elif opt in ("-I", "--interval"):
            params.interval = int(arg)
            argIdx += 2
        elif opt in ("-d", "--duration"):
            params.duration = arg
            argIdx += 2
        elif opt in ("-p", "--pid"):
            params.pid = ' --pid ' + str(arg)
            argIdx += 2
        elif opt in ("-t", "--tid"):
            params.tid = ' --tid ' + str(arg)
            argIdx += 2
        elif opt in ("-n", "--no-inherit"):
            params.inherit = ' --no-inherit'
            argIdx += 1
        elif opt in ("", "--system-info"):
            runInfo=osFeatures.PrepareRunInfo(True)
            SystemInfo(runInfo)
            sys.exit()

        elif utils.IsLinux() and opt in ("", "--enable-irperf"):
            # Required root access
            cpuFeatures.EnableIRPERF()
            sys.exit()
        elif opt in ("","--mux-interval"):
            params.uncoreDriverMuxInterval = int(arg)
            argIdx += 2
        elif opt in ("", "--mux-interval-core"):
            osFeatures.SetMultiplexingInterval(int(arg), 'core')
            sys.exit()
        elif opt in ("", "--mux-interval-l3"):
            osFeatures.SetMultiplexingInterval(int(arg), 'l3')
            sys.exit()
        elif opt in ("", "--mux-interval-df"):
            osFeatures.SetMultiplexingInterval(int(arg), 'df')
            sys.exit()
        elif opt in ("", "--mux-interval-umc"):
            osFeatures.SetMultiplexingInterval(int(arg), 'umc')
            sys.exit()
        elif opt in ("-r", "--collect-raw"):
          params.collectRaw = True
          params.rawEventFile = arg
          argIdx += 2
        elif opt in ("-f", "--format"):
          if (arg.lower() == 'csv'):
              params.format = 'CSV'
          elif (arg == 'xls'):
              params.format = 'XLS'
          else:
              print ('Invalid format. Supported formats are csv or xls')
              sys.exit()
          argIdx += 2
        elif opt in ("-g", "--gen-raw-events"):
          params.genRawEvent = True
          getReport = False
          argIdx += 1
        #elif opt in ("-s", "--config"):
            # Should not come here as it is handled above
        elif opt in ("-i", "--input-file"):
            # Raw input file
            if os.path.isfile(arg) and '.ses' in arg:
                params.inputFile = arg

                #read family and model from session file and prepare the base path
                platform = ReadPlatformFromSessionFile(params.inputFile)
                basePath = utils.GetApplicationPath() + '/data/' + platform[0]+'_'+ hex(int(platform[1],16) >> 4) + buildScope

            else:
                print('Provide a valid session (.ses) file to generate report: '+ arg)
                sys.exit()
            argIdx += 2
        elif opt in ("-l", "--list"):
            HandleListOption(arg, basePath)
            argIdx += 1
        elif opt in ("-V", "--verbose"):
            params.verbose = True
            argIdx += 1
        elif opt in ("-G", "--group-by"):
            params.groupby = arg.lower()
            argIdx += 2
        elif opt in ("-T", "--time-series"):
            # Time-series supported only with linux-perf
            if utils.IsWindows() or params.isUncoreDriver:
                print("Time series analysis only supported on Linux with linux-perf")
                sys.exit()
            params.isTimeSeries = True
            argIdx += 1
        elif opt in ("","--set-precision"):
            params.precision = int(arg)
            argIdx += 2
        elif opt in ("","--collect-group"):
            params.collectGroup = arg.split(",")
            argIdx +=2
        else:
            print('Unsupported option - %s' % opt)
            sys.exit()

    params.appArgv = argvStripped[argIdx:]
    params.argv = argvStripped
    if params.collect or params.collectRaw:
        runInfo = osFeatures.PrepareRunInfo()
        if params.coreMask and not utils.IsValidCore(params.coreMask, runInfo.totalCores):
                sys.exit()

    # configStr while collecting
    if (configStr != ''):
        isShortCode = False
        configPath = utils.GetApplicationPath() +'/data/' + g_family + '_' + hex(int(g_model, 16) >> 4) + buildScope
        configList = configStr.split(',')

        # DF and UMC can't be collected together
        if "df" in configList and "umc" in configList:
            print("Error: DF and UMC can't be collected together")
            sys.exit()

        if 'core' in configList:
            cfg = configPath + '/configs/core/core_config.yaml'
            params.cfgList.append(cfg)
            isShortCode = True
            params.hasCore = True

        if 'l3' in configList:
            params.hasL3 = True

            #Get the correct L3 config file
            if runInfo.isL3SliceIdThreadMaskAvailable:
                cfg = configPath +  '/configs/l3/l3_slice_thread_config.yaml'
            else:
                cfg = configPath +  '/configs/l3/l3_config.yaml'

            params.cfgList.append(cfg)
            isShortCode = True

        if 'df' in configList:
            cfg = configPath +  '/configs/df'

            if not os.path.exists(cfg):
                print("Error: Config file doesn't exist: " + cfg)
                sys.exit()

            files = os.listdir(cfg)
            isShortCode = True
            params.hasDF = True
            for f in files:
                params.cfgList.append(cfg + '/' + f)

        if 'umc' in configStr:
            # On Stones use Uncore driver for UMC
            family, model = hex(runInfo.family),  hex(runInfo.model >> 4)
            if family == "0x19" and model == "0x1":
                params.isUncoreDriver = True

            if (not params.isUncoreDriver) and (not utils.IsRootAccess()):
                print ("Error: UMC config required root permission to collect data")
                sys.exit()

            #Get the correct umc config file
            cfg = configPath +  '/configs/umc/umc_config.yaml'
            params.cfgList.append(cfg)
            isShortCode = True
            params.hasUmc = True

        if not isShortCode:
            for opt in configList:
                if opt[-1] == '*':
                    continue
                    # for name in commands.getoutput('ls '+opt).split('\n'):
                    #     params.cfgList.append(name)
                else:
                    params.cfgList.append(opt)
    if params.collectRaw:
        params.collect = False
        ProcessRawEventFile(params)
        CollectData(params, runInfo)
        sys.exit()

    # if collecting from the local machine
    if params.collect:
        isFixedEventsAvlbl = osFeatures.IsValidAPERF() and osFeatures.IsValidMPERF()

        if not params.isUncoreDriver and not isFixedEventsAvlbl:
            print("APerf, MPerf are not available. Profiling is not possible")
            print ('Hint: try running sudo sh -c \'echo -1 >/proc/sys/kernel/perf_event_paranoid\'')
            sys.exit()

        # --pid and -a not possible together
        if params.pid != '' and params.swp:
            print("Error: Process profiling not possible with system wide profiling")
            sys.exit()
        params.isL3SliceIdThreadMaskAvailable = runInfo.isL3SliceIdThreadMaskAvailable
        params.isIRPERF = runInfo.isIRPERF

    # if command contains only report, get the run info
    dfClkfound = False
    dfProfiling = False
    if not params.collect:
       runInfo = utils.ReadRunInfo(params)

       for cfg in runInfo.cfgList:
           params.cfgList.append(cfg)

       #check if df profiling is selected
       dfClkfound = False

       for n in runInfo.rawDataFiles:
          if '.df' in n:
              dfProfiling = True
              for cfg in params.cfgList:
                  if 'df_clks' in cfg:
                      dfClkfound = True

    # Add default df config file
    if ('df_' in configStr):
        dfClkfound = False
        dfProfiling = True
        for n in params.cfgList:
            if 'df_clks_config.yaml' in n:
                dfClkfound = True

    if (dfProfiling == True) and (False == dfClkfound):
        defaultDf = basePath + '/configs/df/df_clks_config.yaml'

        if os.path.exists(defaultDf):
            params.cfgList.append(defaultDf)

    # Add default config if list is empty
    if (len(params.cfgList) == 0):
        if os.path.exists(defaultDf):
            params.cfgList.append(basePath + '/configs/core/core_config.yaml')

    if (params.coreMask != ''):
        isCoreCfg = False
        for cfg in params.cfgList:
            if ('core_config' in cfg):
                isCoreCfg = True

        if (False == isCoreCfg):
            params.coreMask = ''

        # Check if all paths are valid
        for path in params.cfgList:
            if (False == utils.IsFileReadable(path)):
                print ('Invalid path: '+ path)
                sys.exit()

    if getReport:
        # Read the runInfo from runinfo file and session file
        runInfo = utils.ReadRunInfo(params)
        params.hasCore = True if runInfo.coreMask != '' else False
        params.hasDF = True if runInfo.dfMask != '' else False
        params.hasL3 = True if runInfo.l3Mask != '' else False
        params.hasUMC = True if runInfo.umcMask != '' else False
        params.umcCount = int(runInfo.umcCount)
        family, model = hex(runInfo.family),  hex(runInfo.model >> 4)
        if params.hasUMC and (family == "0x19" and model == "0x1"):
            params.isUncoreDriver = True
            params.umcCount = runInfo.umcCntArr[0]
        params.umcMask = runInfo.umcMask
        params.isL3SliceIdThreadMaskAvailable = runInfo.isL3SliceIdThreadMaskAvailable
        params.isIRPERF = runInfo.isIRPERF

        if runInfo.isUncoreDriver and params.isTimeSeries:
            print("Error: Time-series report not supported with AMDuProf Driver")
            sys.exit()

    # Read all data files
    if ((len (params.cfgList) > 0) and (not params.collectRaw)):

        #Read config file
        ReadConfig(params)
        maxDepth = 1

        # Read event File
        ReadEventFiles(basePath, params)
        ProcessEvents(params, runInfo)
    if params.collect:
        CollectData(params, runInfo)

    if getReport:
        if not params.collect:
            print('') # Do nothing

        elif params.collect:
            # both collect and report together. Need to wait till collection is completed
            while (g_collecting):
                sleep (0.5)

            if (params.isOutputFile == False):
                params.outputFile = params.outputFile + '/'+params.outputFile +utils.GetNodeName()
                params.inputFile = params.outputFile +'.ses'
            else:
                params.outputFile = params.outputFile + '/'+params.outputFile
                params.inputFile = params.outputFile +'.ses'

            # Read the runInfo from runinfo file and session file
            runInfo = utils.ReadRunInfo(params)

        # Read metrics
        ReadMetrics(basePath, runInfo)

        prevCfg = ''

        for r in reportList:
            if prevCfg != r.cfg:
                maxDepth = 1

            # Find metric for r
            line = []
            m = metricDict.get(r.name)

            if None != m:
                ReportStr(m, line)
            else:
                line.append(r.name)

            depth = 0
            for s in line:
                if s == '{':
                    depth += 1
                    maxDepth = depth if maxDepth < depth else maxDepth
                elif s == '}':
                    depth = depth - 1
                else:
                    fstr = ''
                    for n in range(1, depth):
                        fstr += ','
                    fstr += s
                    f = metricDict.get(s)
                    name = f.Name if (f is not None) else fstr
                    reportMetricList[utils.GetTypeIndex(r.cfg)].append(classDefs.ExpName(fstr, name, r.cfg))

            profileCfgDepthList.append(classDefs.CfgDepth(r.cfg, maxDepth))
            prevCfg = r.cfg

            del line[:]
        #for x in reportMetricList[1]:
          #print 'CFG:',x.cfg, 'CFGNAME:',x.name, 'NAMESTR:',x.nameStr
        # Generate report
        reporter = Reporter(params)
        reporter.Report(runInfo)
    # clean the temporary files
    # utils.DeleteTempDir()

if __name__ == "__main__":
    main(sys.argv[1:])
