#=====================================================================
# Copyright 2020 (c), Advanced Micro Devices, Inc. All rights reserved.
#
# AMDUtils.py - Utility functions.
#
# Developed by AMDuProf Profiler team.
#=====================================================================

import os
import sys
import re
import os.path
import tempfile
from os import path
from pathlib import Path
from datetime import date, datetime
import subprocess
import shutil
import platform
import glob
import ctypes
import ast
from ctypes import *
from AMDCpuFeatures import GetFamilyModel

if sys.version_info < (3, 0):
    import commands

try:
    import yaml
except ImportError:
    print('Use following command to install Yaml for Python\n\'sudo pip3 install pyyaml\' or \'sudo apt-get install python-yaml\'')
    sys.exit()

try:
    import yamlordereddictloader
except ImportError:
    print('Use following command to install yamlordereddictloader for Python\n\'pip3 install yamlordereddictloader\'')
    sys.exit()

import AMDClassDefinition as classDefs

g_msrEventList = [
 {
 "EventName": "irperf",
 "EventCode": "irperf",
 "BriefDescription": "Retired Instruction Count",
 "PublicDescription": "Retired Instruction Count",
 "EventCode": "0xfc",
 "Umask": "0xff",
 "Edge": "0",
 "CounterType": "MSR",
 "EventType": "LD"
 },
 {
 "EventName": "mperf",
 "EventCode": "mperf",
 "BriefDescription": "Max Performance Frequency Clock Count",
 "PublicDescription": "Max Performance Frequency Clock Count",
 "EventCode": "0xfd",
 "Umask": "0xff",
 "Edge": "0",
 "CounterType": "MSR",
 "EventType": "LD"
 } ,
 {
 "EventName": "aperf",
 "EventCode": "aperf",
 "BriefDescription": "Actual Performance Frequency Clock Count",
 "PublicDescription": "Actual Performance Frequency Clock Count",
 "EventCode": "0xfe",
 "Umask": "0xff",
 "Edge": "0",
 "CounterType": "MSR",
 "EventType": "LD"
 }
 ,
 {
 "EventName": "tsc",
 "EventCode": "tsc",
 "BriefDescription": "Timestamp Counter",
 "PublicDescription": "Timestamp Counter",
 "EventCode": "0xff",
 "Umask": "0xff",
 "Edge": "0",
 "CounterType": "MSR",
 "EventType": "LD"
 }
]

LinuxUsage ="""

AMDuProf System Analyzer
AMDuProfSys.py is a command-line tool to monitor CPU performance metrics of AMD processors.

 Usage:
   AMDuProfSys.py [--version] [--help] [--mux-interval-core] [--mux-interval-l3] [--mux-interval-df] [--enable-irperf] [--system-info ] [--verbose]
   AMDuProfSys.py COMMAND [<options>] <PROGRAM> [<ARGS>]

 Following are supported commands:
   collect   -  To launch the given application and to monitor the raw events.
   report    -  To generate the profile report with computed metrics.

   PROGRAM   - The launch application to be monitored.
   ARGS      - The list of arguments for the launch application.

 Generic options:
   -h, --help                Display this usage this tools
   -v, --version             Print the version
  --system-info              System information
  --enable-irperf            Enable irperf requires root priviledge
  --mux-interval-core <ms>   Set the multiplexing interval in millisecond
  --mux-interval-l3 <ms>     Set the multiplexing interval in millisecond
  --mux-interval-df <ms>     Set the multiplexing interval in millisecond
                             default MUX interval is 4ms

 Collect command options:
       --config <file>       Config file or options core,df,l3, umc for event sets and metrics
   -r  --collect-raw <file>   Collect events using raw events file
       --use-amd-driver      Collect events using AMDuProf Driver
   -a, --all-cpus            System-wide collection from all CPUs
   -C, --cpu <CPUs>          List of CPUs to monitor. Multiple CPUs can be provided as
                             comma separated list with no space: 0,1. Ranges of CPUs
                             are specified with -: 0-2. Note for UMC -C stands for the UMC bus for each socket.
   -o, --output <file>       Output file name to save the raw event count vales
       --no-inherit          Child tasks will not be monitored
   -p, --pid <pid>           Monitor events on existing process(es). Multiple PIDs are can be
                             provided as comma separated list. Available only in Linux for core metrics.
   -t, --tid <tid>           Monitor events on existing thread(s). Multiple TIDs can be provided
                             as comma separated list. Available only in Linux for core metrics.
   -I, --interval <n>        Interval at which raw event count deltas will be stored in the file
   -d, --duration            Profile duration in seconds
                             Note: this option will not work if launch application is specified.
   -V, --verbose             Verbose (show additional counter open errors, etc)

 Report command options:
   -i, --input-file <file>           Input file for event configuration and set of metrics to report
       --config <file>               Config file or options core,df,l3 for event sets and metrics
   -o, --output <file>               Output file name for xls sheet
   -f, --format                      Output file format xls or csv. Default file format is csv.
       --group-by <system,
                   package,numa,ccx>  Aggregate result based on group selected. Default is none
       --set-precision <n>           Set floating point precision for reported metrics. Default is 2
   -T, --time-series                 Genarate per core time series report. Only csv format supported

 Examples:
 1. Monitor the entire system to collect the metrics defined in config file and generate the profile report:
       $ ./AMDuProfSys.py collect --config core -a sleep 5

 2. Launch the program with core affinity set to core 0 and monitor that core and generate profile report:
       $ ./AMDuProfSys.py collect --config core -C 0 taskset -c 0 /tmp/scimark2

 3. Launch the program and monitor it to generate profile report:
    Note: -a or -C option is required as multiplexing works only then.
       $ ./AMDuProfSys.py collect --config core -a /tmp/scimark2

 4. Collect and generate report in two steps
    To generate a binary datafile sci_perf.data containing raw event count values
       $ ./AMDuProfSys.py collect --config data/0x17_0x3/configs/core/core_config.yaml -C 0 -o sci_perf taskset -c 0 scimark2

    To generate a report file sci_perf.xlsx containing computed metrics.
       $ ./AMDuProfSys.py report -i sci_perf/sci_perf.ses -o sci_perf

 5. Collect using multiple config files and generate report in two steps
    To generate a binary datafile sci_perf.data containing raw event count values
       $ ./AMDuProfSys.py collect --config core,l3,df -C 0-10 -o sci_perf taskset -c 0 scimark2
       NOTE: -C, -a option can be used only with the core counters
    To generate a report file sci_perf.xlsx containing computed metrics.
       $ ./AMDuProfSys.py report  -i sci_perf/sci_perf.ses -o all_events

 6. Collect using raw configs
        $ ./AMDuProfSys.py collect --config <core,l3,df> -r <raw config file> -o temp -d 5

 7. Collect using AMDuProf Driver
        $ ./AMDuProfSys.py collect --config df --use-amd-driver -o sys_out -d 10

 8. Update the multiplexing interval
       # ./AMDuProfSys.py --mux-interval-core 16
       Note: This need root access

"""

WinUsage ="""

AMDuProf System Analyzer
AMDuProfSys.py is a command-line tool to monitor CPU performance metrics of AMD processors.

 Usage:
   AMDuProfSys.py [--version] [--help] [--system-info ] [--verbose]
   AMDuProfSys.py COMMAND [<options>] <PROGRAM> [<ARGS>]

 Following are supported commands:
   collect   -  To launch the given application and to monitor the raw events.
   report    -  To generate the profile report with computed metrics.

   PROGRAM   - The launch application to be monitored.
   ARGS      - The list of arguments for the launch application.

 Generic options:
   -h, --help                Display this usage this tools
   -v, --version             Print the version
  --system-info              System information

 Collect command options:
       --config <file>       Config file or option "core" for event sets and metrics
   -r --collect-raw <file>   Collect events using raw events file
   -a, --all-cpus            System-wide collection from all CPUs
   -C, --cpu <CPUs>          List of CPUs to monitor. Multiple CPUs can be provided as
                             comma separated list with no space: 0,1.
   -o, --output <file>       Output file name to save the raw event count vales
   -d, --duration            Profile duration in seconds
                             Note: this option will not work if launch application is specified.
   -V, --verbose             Verbose (show additional counter open errors, etc)

 Report command options:
   -i, --input-file <file>           Input file for event configuration and set of metrics to report
       --config <file>               Config file or option "core" for event sets and metrics
   -o, --output <file>               Output file name for xls sheet
   -f, --format                      Output file format xls or csv. Default file format is csv.
       --group-by <system,
                   package,ccx>  Aggregate result based on group selected. Default is none
       --set-precision <n>           Set floating point precision for reported metrics. Default is 2

 Examples:
 1. Monitor the entire system to collect the metrics defined in config file and generate the profile report:
       $ python AMDuProfSys.py collect --config core -a -o path//OutputDirectory app/scimark2

 2. Launch system wide profile for 10s:
       $ python AMDuProfSys.py collect --config core -a -d 10 -o path//OutputDirectory

 3. Launch the program and ...
       Collect data for core 0
       $ python AMDuProfSys.py collect --config core -C 0 -o Path//To//OutputDirectory app/scimark2

       Collect data for core 0-10
       $ python AMDuProfSys.py collect --config core -C 0-10 -o Path//To//OutputDirectory app/scimark2

       Collect data for core 0 and 16
       $ python AMDuProfSys.py collect --config core -C 0,16 -o Path//To//OutputDirectory app/scimark2

 4. Collect using raw configs
        $ python AMDuProfSys.py collect --config <core,l3,df> -r <raw config file> -o temp -d 5

 5. Generate report
       Session file (.ses) generated by AMDuProfSys is required to generate the report
       $ python AMDuProfSys.py report -i Path//To//OutputDirectory//OutputDirectory.ses -o sci_perf
       CSV report "sci_perf.csv" will be inside Path//To//OutputDirectory/
"""

uProfSysTmpDir = ""

def IsWindows():
	return (sys.platform == 'win32')

def IsLinux():
	return sys.platform.startswith('linux')

def IsFreeBSD():
	return sys.platform.startswith('freebsd12')

def GetApplicationPath():
    return os.path.abspath(os.path.dirname(__file__))

def HasRootPrivilege():
    return os.geteuid() == 0

def OpenFile(fileName, mode):
    fd = None
    try:
        fd = open(fileName, mode)
    except IOError:
        print("Unable to open file ",fileName)
        fd = None

    return fd

def CloseFile(fd):
    fd.close()

def IsFileReadable(inp):
    ret = True

    if OpenFile(inp, 'rb') is None:
        ret =  False

    return ret

def IsFileExists(path):
    return os.path.isfile(path)

def IsDirectoyExists(path):
    return os.path.isdir(path)

def IsDirectoyWritable(path):
    if (path == ''):
        path ='./'

    if os.access(path, os.W_OK) == True:
        return True
    else:
        return False

def GetCmdOutput(cmd):
    if sys.version_info < (3, 0):
        return commands.getoutput(cmd)
    else:
        return subprocess.getoutput(cmd)

def getTempFilePath(fileName):
    """
    Returns path of the file stored in
    OS spcific temp dir with name provided in args.

    It also add pid of uProfSys main process as prefix to the temp file names.
    """

    # create dir .AMDuProfSys at OS specific temp directory
    global uProfSysTmpDir
    tmpDirName = f"{os.getpid()}_AMDuProfSys"
    uProfSysTmpDir = Path(tempfile.gettempdir()).joinpath(tmpDirName)
    uProfSysTmpDir.mkdir(exist_ok=True, parents=True)

    fileName = f"{os.getpid()}_{fileName}"
    filePath = uProfSysTmpDir.joinpath(fileName)

    return filePath

def IsStrNumeric(data):
    return data.isnumeric()

# Replace whole the key with the replaceStr in the given string
def Replace(inpStr, key, replaceStr):
    inp = inpStr.replace(':', '_')
    k = key.replace(':', '_')
    return inp.replace('(' + k + ')', replaceStr)

def LoadYaml(fileName):

    try:
        if not path.exists(fileName):
            print('Config file does not exists: ' + fileName)
            sys.exit()
        else:
            return yaml.load(open(fileName), Loader=yamlordereddictloader.Loader)
    except yaml.YAMLError:
        print('Invalid config path: '+ fileName)
        sys.exit()

# Get cpu mask range in 0,3,4,10-20 format
def GetCpuRange(coreList):
    cores = None

    for m in coreList.split(','):
        if '-' in m:
            low = int(m.split('-')[0])
            high = int(m.split('-')[1])

            if None == cores:
                cores = list(range(low, high + 1))
            else:
                cores += list(range(low, high + 1))
        else:
            if None == cores:
                cores = list(range(int(m), int(m) + 1))
            else:
                cores.append(int(m))

    return cores

def PrepareUProfCLIEventOption(eventCode, unitMask, scope):
    evCmd = 'event=pmcx'

    evCmd += eventCode[2:]
    if scope == ':u':
        evCmd += ',user=1,os=0'
    elif scope == ':k':
        evCmd += ',os=1,user=0'
    else:
        evCmd += ',os=1,user=1'
    evCmd += ','

    if unitMask != "0x0":
        evCmd += 'umask='
        evCmd += unitMask + ','

    evCmd += 'interval=0'

    command = '-e ' + evCmd
    return command
    #command += ' -o out'

def GetColorCode(idx):
    arr = ['#EBFFD9', '#DAF6FE', '#FEFADA', '#C6FEEA', '#C1C4E5', '#FED6F3', '#FFDED5', '#C2D4E4', '#FFDDDD', '#E9D5FF']
    arrLen = len(arr)
    return arr[idx % arrLen]

# FIXME - is this working as expected
def ConvertMsToHMSm(ms):
    temp = int(ms)
    exMilli = temp % 1000
    temp = int(temp / 1000)
    ExSeconds = temp % 60
    temp = int(temp / 60)
    ExMinutes = temp % 60
    temp = int(temp / 60)
    ExHhours = int(temp) % 24

    ts = str(ExHhours) + 'H:' + str(ExMinutes) + 'M:' + str(ExSeconds) + 'S:' + str(exMilli) + 'm'
    return ts

# All expressions are in lower case
def IsExprDecoded(exp):

    for c in exp:
        if (c > 'a') and (c < 'z'):
            return False
    return True

# Check for valid core
def IsValidCore(mask, cpus):
    result = True

    if mask == '-a':
        return result

    if (mask[0] == '-') or (',-' in mask):
        result = False
    else:
        for core in re.split('[-,]', mask):

            if (int(core) < 0) or (cpus <= int(core)):
                result = False
                break

    if not result:
        print('Invalid core. Accepted range is: 0 - ' + str(cpus - 1))

    return result

# index based on profile type core, df, l3
def GetTypeIndex(cfgType):
    idx = 0
    if 'core' in cfgType.lower():
        idx = 0
    elif 'df' in cfgType.lower():
        idx = 1
    elif 'l3' in cfgType.lower():
        idx = 2
    elif 'umc' in cfgType.lower():
        idx = 3

    return idx

# index based on profile type core, df, l3
def GetTypeStr(idx):
    typeStr = 'core'
    if 0 == idx:
        typeStr = 'core'
    elif 1 == idx:
        typeStr = 'df'
    elif 2 == idx:
        typeStr = 'l3'
    elif 3 == idx:
        typeStr = 'umc'

    return typeStr

def GetAvailablePmcs(idx):
    hwCnt = 0
    family, model = GetFamilyModel()
    model = hex(int(model, 16) >> 4)
    if 0 == idx:
        hwCnt = 6
        if IsLinux():
            nmi_watchdog = ReadTextFromFile("/proc/sys/kernel/nmi_watchdog")
            if (nmi_watchdog == '1'):
                hwCnt = 5
    elif 1 == idx:
        # Stones: 16 DF PMCs
        if family == "0x19" and model == "0x1":
            hwCnt = 16
        else:
            hwCnt = 4
    elif 2 == idx:
        hwCnt = 6
    elif 3 == idx:
        # Stones: 4 UMC PMCs
        if family == "0x19" and model == "0x1":
            hwCnt = 4
        else:
            hwCnt = 5

    return hwCnt

def GetNodeName():
    #return os.uname()[1]
    return ''

def GetDateTime(isFileName = True):
    dt = datetime.now()

    if (isFileName):
        dt = dt.strftime("%d%m%Y_%H%M%S")
    else:
        dt = dt.strftime("%d/%m/%Y:%H/%M/%S")

    return dt

def GetEventCountFromCmd(cmd):
    count = cmd.count('msr/')
    count += cmd.count('amd_df/')
    count += cmd.count('amd_l3/')
    count += cmd.count('r4')
    count += cmd.count('r1')
    count += cmd.count('r2')
    return count

def IsRootAccess():
    return os.geteuid() == 0

def IsLinux():
    return platform.system()=="Linux"

def UseDriver():
    #   Unused
    ret = False

    if IsWindows():
        ret = True
    else:
        scopeStr = os.getenv("AMDUPROF_USE_SYS_DRIVER")

        if 'yes' == scopeStr:
            ret = True

    return ret

def DeleteTempDir():
    """
    Deletes temp dir created by uProfSys.
    Only removes dir created by current process
    """
    global uProfSysTmpDir
    try:
        shutil.rmtree(uProfSysTmpDir)
    except NotADirectoryError:
        os.remove(uProfSysTmpDir)
    except Exception as e:
        pass

def P0StateFreq():
    if IsLinux():
        try:
            libUtils = ctypes.CDLL(GetApplicationPath() + '/libutils.so')
            freq = libUtils.GetP0StateFreq() / 100

        except:
            print('Not able to load libutils.so')

    else:
        try:
            winLib = cdll.LoadLibrary(GetApplicationPath() + '\AMDuProfSysUtils.dll')
            freq = winLib.GetP0StateFreq() / 100

        except:
            print('Not able to load AMDuProfSysUtils.dll')
            sys.exit()

    return freq

def WriteRunInfo(params, runInfo, eventCmdList, rawCmdStrList):
    buff = 'onlineCpu:'+ str(runInfo.totalCores) +'\n'
    buff += 'isUncoreDriver:'+ str(params.isUncoreDriver) +'\n'
    buff += 'threadPerSocket:'+ str(runInfo.threadPerSocket) +'\n'
    buff += 'coresPerSocket:'+ str(runInfo.coresPerSocket) +'\n'
    buff += 'sockets:'+ str(runInfo.sockets) +'\n'
    buff += 'socketCores:'+ str(runInfo.socketCores) +'\n'
    buff += 'numaNodes:'+ str(runInfo.numaNodes) +'\n'
    buff += 'numaCores:'+ str(runInfo.numaCores) +'\n'
    buff += 'ccx:'+ str(runInfo.ccxs) +'\n'
    buff += 'ccxCores:'+ str(runInfo.ccxCores) +'\n'
    buff += 'family:'+ hex(runInfo.family) +'\n'
    buff += 'model:'+ hex(runInfo.model) +'\n'
    buff += 'modelName:'+ runInfo.modelName +'\n'
    buff += 'isIRPERF:'+ str(int(runInfo.isIRPERF)) +'\n' 

    # Get p0 State frequency
    p0 = P0StateFreq()

    buff += 'cpuFreq:'+ str(p0) +'\n'

    idx = 0
    for cores in runInfo.node:
        buff += 'node'+str(idx)+': '+ cores   + '\n'
        idx += 1

    buff += 'firstCore: '

    for core0 in runInfo.numaFirstCore:
      buff += str(core0)  +' '

    buff += '\n'

    if (params.hasCore):
        buff += 'Core Mask:'+ params.coreMask + '\n'
    else:
        buff += 'Core Mask:' + '\n'

    buff += 'DF Mask:'+ params.dfMask + '\n'
    buff += 'L3 Mask:'+ params.l3Mask + '\n'
    if params.hasUMC:
        if params.isUncoreDriver:
            # Zen4 onwards assuming 2 UMCs per socket.
            buff += 'UMC Mask:'+ ",".join(str(socket) for socket in range(2*runInfo.sockets)) + '\n'
        else:
            buff += 'UMC Mask:'+ params.umcMask + '\n'

    buff += 'commandLine:' + params.commandLine + '\n'

    baseFileName = CreateOutputDirectory(params)

    filePath = baseFileName + '.ses'

    buff += '\n'
    rawFiles = ''

    for idx in params.cfgTypeList:
        if (not params.collectRaw and len(eventCmdList[idx]) == 0):
            rawFiles += ','
        elif (params.collectRaw and len(rawCmdStrList[idx]) == 0):
            rawFiles += ','
        elif (params.TYPE_CORE == idx):
            rawFiles += (baseFileName + '.core,')

        elif (params.TYPE_DF == idx):
            rawFiles += (baseFileName + '.df,')

        elif (params.TYPE_L3 == idx):
            rawFiles += (baseFileName + '.l3,')

        elif (params.TYPE_UMC == idx):
            rawFiles += (baseFileName + '.umc,')

    # For process profiling only with core
    if (rawFiles == '') and ((params.coreMask == '') and (params.dfMask == '') and (params.l3Mask == '')):
        rawFiles += (baseFileName + '.core,')

    buff += 'isL3SliceIdThreadMaskAvailable:' + str(runInfo.isL3SliceIdThreadMaskAvailable) + '\n'
    buff += 'umcCount:' + str(runInfo.umcCount) + '\n'
    buff += 'rawFiles:' + rawFiles[:-1]
    buff += '\nconfigs:'

    for cfg in params.cfgList:
        buff += 'configs' + cfg.split('configs')[1]+ ','
    
    buff = buff[:-1]

    runInfoHld = OpenFile(filePath, "w")
    try:
        runInfoHld.write(buff)
        runInfoHld.close()
    except:
        print ('Runinfo file is not able to find at:' + filePath)
        sys.exit()

def ReadTextFromFile(path):
    """Used to read Linux System files
    Returns first line from the file
    """
    data = Path(path).read_text()
    # remove newline character
    data = data.strip('\n')
    return data

def ReadRunInfo(params):
    filePath = params.inputFile
    runInfoHld = OpenFile(filePath, "r")

    if (runInfoHld == None):
        print ('Missing Runinfo file:' + filePath)
        sys.exit()

    runInfo = classDefs.RunInfo()

    for ln in runInfoHld:
        if ('onlineCpu' == ln.split(':')[0]):
            runInfo.totalCores = int(ln.split(':')[1].strip())

        elif ('threadPerSocket' == ln.split(':')[0]):
            runInfo.threadPerSocket = int(ln.split(':')[1].strip())

        elif ('coresPerSocket' == ln.split(':')[0]):
            runInfo.coresPerSocket = int(ln.split(':')[1].strip())

        elif ('sockets' == ln.split(':')[0]):
            runInfo.sockets = int(ln.split(':')[1].strip())

        elif ('numaNodes' == ln.split(':')[0]):
            runInfo.numaNodes = int(ln.split(':')[1].strip())

        elif ('family' == ln.split(':')[0]):
            runInfo.family = int(ln.split(':')[1].strip(), 16)

        elif ('model' == ln.split(':')[0]):
            runInfo.model = int(ln.split(':')[1].strip(), 16)

        elif ('isUncoreDriver' == ln.split(':')[0]):
            runInfo.isUncoreDriver = True if ln.split(':')[1].strip() == "True" else False

        elif ('isIRPERF' == ln.split(':')[0]):
            runInfo.isIRPERF = int(ln.split(':')[1].strip(), 16)

        elif ('socketCores' == ln.split(':')[0]):
            arryStr = ln.split(':')[1].strip()
            runInfo.socketCores = ast.literal_eval(arryStr)

        elif ('numaCores' == ln.split(':')[0]):
            arryStr = ln.split(':')[1].strip()
            numaArray = ast.literal_eval(arryStr)

            for n in numaArray:
                runInfo.numaCores.append(GetCpuRange(n))

        elif ('ccx' == ln.split(':')[0]):
            runInfo.ccxs = int(ln.split(':')[1].strip())

        elif ('ccxCores' == ln.split(':')[0]):
            arryStr = ln.split(':')[1].strip()
            ccxArray = ast.literal_eval(arryStr)

            for n in ccxArray:
                if runInfo.isUncoreDriver:
                    #Windows/Uncore ccxArray format [[0,1,2..15] [16,17..31] ...]
                    runInfo.ccxCores.append(n)
                else:
                    #Linux ccxArray format : ['0-7,128-135', '8-15,136-143']
                    #TODO common .ses file format
                    runInfo.ccxCores.append(GetCpuRange(n))

        elif ('modelName' == ln.split(':')[0]):
            runInfo.modelName = ln.split(':')[1].strip()

        elif ('cpuFreq' == ln.split(':')[0]):
            runInfo.cpuFreq = float(ln.split(':')[1].strip()[:-1])

        elif ln.split(':')[0].startswith('node'):
            runInfo.node.append(ln.split(':')[1].strip())

        elif ('Core Mask' == ln.split(':')[0]):
            runInfo.coreMask = ln.split(':')[1].strip()

        elif ('DF Mask' == ln.split(':')[0]):
            runInfo.dfMask = ln.split(':')[1].strip()

        elif ('L3 Mask' == ln.split(':')[0]):
            runInfo.l3Mask = ln.split(':')[1].strip()

        elif ('UMC Mask' == ln.split(':')[0]):
            runInfo.umcMask = ln.split(':')[1].strip()

        elif ('commandLine' == ln.split(':')[0]):
            runInfo.commandLine = ln.split(':')[1].strip()

        elif ('rawFiles' == ln.split(':')[0]):
            rawFilePathList=ln[ln.index(':')+1:].split(',') # Parse "rawFiles:[]" from session file
            for f in rawFilePathList:
                runInfo.rawDataFiles.append(f.strip())

        elif ('configs' == ln.split(':')[0]):
            buildScope = os.getenv("AMDUPROF_SCOPE_STR")

            if buildScope == None:
                buildScope = '/'
            else:
                buildScope = '/' + buildScope + '/'

            for cfg in ln.split(':')[1].split(','):
                cfgPath = GetApplicationPath() + '/data/' + hex(runInfo.family) + '_' + hex(runInfo.model >> 4) + buildScope + cfg.strip()
                runInfo.cfgList.append(cfgPath)

        elif ('isL3SliceIdThreadMaskAvailable' == ln.split(':')[0]):
            runInfo.isL3SliceIdThreadMaskAvailable = True if 'True' == ln.split(':')[1].strip() else False

        elif ('umcCount' == ln.split(':')[0]):
            runInfo.umcCount = ln.split(':')[1].strip()

        elif ("umcCntArray" == ln.split(':')[0]):
            runInfo.umcCntArr = list(map(lambda x: int(x), ln.split(':')[1].strip().split(",")))
            totUMC = 0
            for socketId in range(runInfo.sockets):
                totUMC += int(runInfo.umcCntArr[socketId])
            runInfo.umcMask = ",".join(map(lambda x: hex(x), list(range(totUMC))))
    if ('-a' in runInfo.coreMask):
        runInfo.coreMask = '0-'+ str(runInfo.totalCores - 1)

    if (runInfo.dfMask != ''):
            runInfo.dfs = GetCpuRange(runInfo.dfMask)

    runInfoHld.close()

    return runInfo

def CreateOutputDirectory(params):
    # create profile run folder
    baseDir = os.path.dirname(params.outputFile)

    # Create output folder if doesn't exists
    if (params.isOutputFile == False):
        params.outputFile = 'AMDuProfSys_' + GetDateTime()+GetNodeName()
    #else:
        #params.outputFile += '_' + GetNodeName()

    if (IsDirectoyWritable(baseDir)):
        if (not IsDirectoyExists(params.outputFile)):
            os.system('mkdir ' + params.outputFile)
    else:
        print('You don not have privilege to create output directory')

    return os.path.join(os.path.abspath(params.outputFile) , os.path.basename(params.outputFile))

def PrintGenReportCmd(outFileName):
    uProfSysPath = os.path.join(GetApplicationPath(),'AMDuProfSys.py')
    sesFilePath = os.path.splitext(outFileName)[0]+'.ses'
    reportCmdPrefix = "python" if IsWindows() else ""
    print("To generate report use")
    print("{} \"{}\" report -i \"{}\"".format(reportCmdPrefix,uProfSysPath, sesFilePath)) #Wrap path with double quotes otherwise wont work for paths like C:\Program Files\AMD\AMDuProf\bin\..

def FormatMetricValue(value, precision):
    return "{:.{p}f}".format(float(value),p =precision)

def WriteEvSetToFile(evSetRaw):
    """Utility function to dump event set data into a file.
    """
    evSetFilePath = getTempFilePath(fileName="statEventSet.raw")
    try:
        with open(evSetFilePath,"w",encoding="ascii") as evSetFile:
            evSetFile.write(evSetRaw)
    except Exception as e:
        print("could not write raw stat command into {} due to \n{}".format(evSetFilePath,sys.exc_info()[0]))

    return evSetFilePath

def IsNumber(num):
    num_format = re.compile("^[\-]?[1-9][0-9]*\.?[0-9]+$")
    isnumber = re.match(num_format, num)
    return isnumber


def GetMsrEvents():
    return g_msrEventList