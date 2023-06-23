# =====================================================================
# Copyright 2021 (c), Advanced Micro Devices, Inc. All rights reserved.
#
# AMDStatHandler.py - AMDuProfCLI stat handler module
#
# Developed by AMDuProf Profiler team.
# =====================================================================

log = False
from io import TextIOWrapper
from struct import unpack
from pathlib import Path
from collections import OrderedDict
from copy import deepcopy
import sys
import os
import traceback

import AMDUtils as utils

# Header size is should same as PmcHeader
PMC_HEADER_SIZE = 128
PMC_SAMPLE_HDR_GROUP_ID_MASK = 0xFFFFFFFFFFFF
PMC_SAMPLE_HDR_ATTR_SHIFT = 48
PMC_SAMPLE_HDR_ATTR_MASK = 0xFFFF

# Header version should same as int PmcFileHeader.h
PMC_HEADER_MAGIC_NUMBER = 0xDECAFC0FFEE
PMC_HEADER_VERSION_MAJOR = 0x1
PMC_HEADER_VERSION_MINOR = 0x1
PMC_HEADER_VERSION_MAJOR_SHIFT = 32
PMC_HEADER_VERSION = PMC_HEADER_VERSION_MAJOR << PMC_HEADER_VERSION_MAJOR_SHIFT
PMC_HEADER_VERSION = PMC_HEADER_VERSION | PMC_HEADER_VERSION_MINOR

THREAD_ID = -1
ENA = 1e9  # Dummy value
TIME = 1e9  # Dummy value

TSC_BIT = 0x1
groupAttributesList = [0x1, 0x2, 0x4, 0x8, 0x10]
# [TSC, IRPERF, MPERF, APERF, FCLK]


def ReadUINT64(f):
    try:
        ret = unpack("<Q", f.read(8))[0]
    except:
        ret = None
    return ret


def ReadUINT32(f):
    try:
        ret = unpack("<I", f.read(4))[0]
    except:
        ret = None
    return ret


def ReadCharStr(f, numChar=64):
    """
    Returns "numchar" char characters.
    """
    data = f.read(numChar).decode("utf-8").strip("\x00")
    return data


def BitUnPack(val, startBit, length):
    """Returns integer at val[startBit : startBit+length-1]
    Eg:
    val = '0b 1 1 1 1'
                  ^ ^
    BitUnPack(val, startBit=0, length =2) = 0b11 or 3:int
    """
    ret = 0
    for i in range(length):
        if (1 << (i + startBit)) & val:
            ret += 1 << i
    return ret


def getBaseFilePath(outDirPath):
    """
    Returns output base path.
    Append extension ".ses", ".core",".df" etc accordingly
    """
    return os.path.join(
        os.path.abspath(outDirPath), os.path.basename(os.path.normpath(outDirPath))
    )


class StatHandler:
    def __init__(self, drvCmds, params, aggregate=True):
        self.dataFileList = []
        self.rawFileDataList = []
        self.globalAttrValueList = []

        try:
            self.ExecuteStat(drvCmds)
        except Exception as e:
            print("Error while running AMDuProfCLI stat\n :{}".format(e))
            print(traceback.print_exc())

        for file in self.dataFileList:
            print("Processing file\n{} ".format(file))
            rawFileInst = RawFile()
            rawFileInst.Convert(file)
            self.rawFileDataList.append(rawFileInst)

        # Find data with MSRs value
        for pmuData in self.rawFileDataList:
            if len(pmuData.attrValueList) > 0:
                self.globalAttrValueList = pmuData.attrValueList
                break

        for pmuData in self.rawFileDataList:
            pmuData.attrValueList = (
                (self.globalAttrValueList)
                if len(pmuData.attrValueList) == 0
                else pmuData.attrValueList
            )  # If MSR value present in raw file use it, else use MSR value from a different file (special case for L3)
            if aggregate:
                pmuData.Aggregate()
            pmuData.PrepareRawFile(params.outputFile, drvCmds)

            # For UMC, populate UMC count array in the session file
            if pmuData.groupType == 4:
                outDir = Path(params.outputFile)
                sesFilePath = outDir / (outDir.name + ".ses")
                self.UpdateSessionFile(sesFilePath, pmuData.fileHeader.umcMaskArr)
        utils.PrintGenReportCmd(getBaseFilePath(params.outputFile))

    @staticmethod
    def UpdateSessionFile(sesFilePath, umcMaskArr):
        """Update session file to add UMC count array"""
        umcCntArr = ",".join(list(map(lambda x: str(bin(x).count("1")), umcMaskArr)))
        with open(sesFilePath, "a") as f:
            f.writelines(f"\numcCntArray:{umcCntArr}")

    def ExecuteStat(self, drvCmds):
        print("Running AMDuProfCLI stat")
        statOutput = utils.GetCmdOutput(" ".join(drvCmds))
        if "Generated data files path" not in statOutput:
            print("\nCould not run AMDuProfCLI")
            for line in statOutput.split("\n"):
                print(line)
            sys.exit()
        # parse stat output and append all raw data files in a list
        for line in statOutput.split("\n"):
            outDirPrefix = "Generated data files path:"
            if outDirPrefix in line:
                outFilePath = os.path.join(line.strip(outDirPrefix), "countmode")
                for file in os.listdir(outFilePath):
                    self.dataFileList.append(os.path.join(outFilePath, file))


class RawFile:
    def __init__(self):
        self.grpDataMap = {}
        self.eventValueList = []  # List of EventConfigData
        self.attrValueList = []

        self.aggreEventData = OrderedDict()
        self.aggreAttrData = OrderedDict()
        self.groupType = 0

    def Convert(self, file):
        with open(file, "rb") as bufReader:
            self.f = bufReader
            self.InterpretBinaryFile()

    def InterpretBinaryFile(self):
        self.fileHeader = ReadFileHeader(self.f)
        for _ in range(self.fileHeader.numConfigGrps):
            grpData = ReadConfigGroup(self.f)
            self.groupType = grpData.groupType
            self.grpDataMap[grpData.groupID] = grpData
        while True:
            sampleInstance = ReadSample(self)
            if not sampleInstance.sampleHeader:  # EOF condition
                break

    def Aggregate(self):
        if self.groupType == 4:
            self.AggregateUMC()
        else:
            self.AggregateCoreL3DF()

    def AggregateCoreL3DF(self):
        """Attributes and event values are aggregated per cpu."""
        for attr in self.attrValueList:
            attrData = deepcopy(attr)
            if (attrData.coreId, attrData.attrCode) in self.aggreAttrData:
                self.aggreAttrData[
                    (attrData.coreId, attrData.attrCode)
                ].value += attrData.value
            else:
                self.aggreAttrData[(attrData.coreId, attrData.attrCode)] = attrData

        for ev in self.eventValueList:
            eventData = deepcopy(
                ev
            )  # deepcopy required as eventValueList have mutable attributes
            if (eventData.coreId, eventData.eventConfigRaw) in self.aggreEventData:
                self.aggreEventData[
                    (eventData.coreId, eventData.eventConfigRaw)
                ].value += eventData.value

                self.aggreEventData[
                    (eventData.coreId, eventData.eventConfigRaw)
                ].runTime += eventData.runTime
            else:
                self.aggreEventData[
                    (eventData.coreId, eventData.eventConfigRaw)
                ] = eventData

    def AggregateUMC(self):
        """Aggregate UMC data.
        Events with same event id but different names should be aggregated separately.
        """
        for attr in self.attrValueList:
            attrData = deepcopy(attr)
            if (attrData.coreId, attrData.attrCode) in self.aggreAttrData:
                self.aggreAttrData[
                    (attrData.coreId, attrData.attrCode)
                ].value += attrData.value
            else:
                self.aggreAttrData[(attrData.coreId, attrData.attrCode)] = attrData

        for ev in self.eventValueList:
            eventData = deepcopy(ev)
            if (
                eventData.coreId,
                eventData.eventConfigRaw,
                eventData.name,
            ) in self.aggreEventData:
                self.aggreEventData[
                    (eventData.coreId, eventData.eventConfigRaw, eventData.name)
                ].value += eventData.value

                self.aggreEventData[
                    (eventData.coreId, eventData.eventConfigRaw, eventData.name)
                ].runTime += eventData.runTime
            else:
                self.aggreEventData[
                    (eventData.coreId, eventData.eventConfigRaw, eventData.name)
                ] = eventData

    def PrepareUmcRawFileData(self, f: TextIOWrapper):
        """Prepare UMC data buffer"""
        buf = ""
        header = ["UMC", "THREAD", "VAL", "ENA", "RUN", "TIME", "EVENT", "NAME"]
        for hd in header:
            buf += "{0:25}".format(hd)
        f.write(buf + "\n")
        for x in self.aggreAttrData.values():  # Write MSRs
            cur_row = [
                str(x.coreId),
                str(THREAD_ID),
                str(x.value),
                str(self.aggreAttrData[(x.coreId, TSC_BIT)].value),
                str(self.aggreAttrData[(x.coreId, TSC_BIT)].value),
                str(str(self.aggreAttrData[(x.coreId, TSC_BIT)].value)),
                self.DecodeAttrName(x.attrCode),
                "tsc",  # umc supports tsc attribute only
            ]
            buf = ""
            for val in cur_row:
                buf += "{0:25}".format(val)
            f.write(buf + "\n")

        for x in self.aggreEventData.values():
            cur_row = [
                str(x.coreId),
                str(THREAD_ID),
                str(x.value),
                str(self.aggreAttrData[(x.coreId, TSC_BIT)].value),
                str(x.runTime),
                str(self.aggreAttrData[(x.coreId, TSC_BIT)].value),
                self.DecodeEventName(x.eventConfigRaw, self.groupType),
                x.name,
            ]
            buf = ""
            for val in cur_row:
                buf += "{0:25}".format(val)
            f.write(buf + "\n")
        return f

    def PrepareCoreL3DFData(self, f: TextIOWrapper):
        buf = ""
        header = ["CPU", "THREAD", "VAL", "ENA", "RUN", "TIME", "EVENT"]
        for hd in header:
            buf += "{0:25}".format(hd)
        f.write(buf + "\n")

        for x in self.aggreAttrData.values():  # Write MSRs
            cur_row = [
                str(x.coreId),
                str(THREAD_ID),
                str(x.value),
                str(self.aggreAttrData[(x.coreId, TSC_BIT)].value),
                str(self.aggreAttrData[(x.coreId, TSC_BIT)].value),
                str(str(self.aggreAttrData[(x.coreId, TSC_BIT)].value)),
                self.DecodeAttrName(x.attrCode),
            ]
            buf = ""
            for val in cur_row:
                buf += "{0:25}".format(val)
            f.write(buf + "\n")

        for x in self.aggreEventData.values():
            cur_row = [
                str(x.coreId),
                str(THREAD_ID),
                str(x.value),
                str(self.aggreAttrData[(x.coreId, TSC_BIT)].value),
                str(x.runTime),
                str(self.aggreAttrData[(x.coreId, TSC_BIT)].value),
                self.DecodeEventName(x.eventConfigRaw, self.groupType),
            ]
            buf = ""
            for val in cur_row:
                buf += "{0:25}".format(val)
            f.write(buf + "\n")
        return f

    def PrepareRawFile(self, outDirPath, drvCmds):
        baseFilePath = getBaseFilePath(outDirPath)
        suf = ".data"
        if self.groupType == 1:
            suf = ".core"
        elif self.groupType == 2:
            suf = ".l3"
        elif self.groupType == 3:
            suf = ".df"
        elif self.groupType == 4:
            suf = ".umc"
        filePath = baseFilePath + suf
        print("Generated raw file: {}".format(filePath))
        with open(filePath, "w") as f:
            buf = "# Driver Version : "
            buf += str(self.fileHeader.version)
            f.write(buf + "\n")

            buf = "# cmdline : "
            buf += " ".join(drvCmds)
            f.write(buf + "\n")

            if self.groupType == 4:
                self.PrepareUmcRawFileData(f)
            else:
                self.PrepareCoreL3DFData(f)

    def DecodeEventName(self, eventCfg, groupType):
        if self.groupType == 1:
            return self.DecodeCoreName(eventCfg)
        elif self.groupType == 2:
            return self.DecodeL3Name(eventCfg)
        elif self.groupType == 3:
            return self.DecodeDfName(eventCfg)
        elif self.groupType == 4:
            return self.DecodeUmcName(eventCfg)
        else:
            return None

    @staticmethod
    def DecodeCoreName(eventCfg):
        eventCfg = hex(eventCfg)
        eventCfg = eventCfg[2:]  # Trim 0x from start and  remove leading zeros
        if eventCfg[1] == "1":
            eventCfg += ":u"
            ls = list(eventCfg)
            ls[1] = "3"
            eventCfg = "".join(ls)
        elif eventCfg[1] == "2":
            eventCfg += ":k"
            ls = list(eventCfg)
            ls[1] = "3"
            eventCfg = "".join(ls)
        eventCfg = "r" + eventCfg
        return eventCfg

    def DecodeL3Name(self, eventCfg):
        family = hex(self.fileHeader.family)
        if family == "0x17":
            # 0-7: event code, 8-15: mask, 48-51: Slice id, 56-63: Thread mask
            event = BitUnPack(eventCfg, startBit=0, length=8)
            umask = BitUnPack(eventCfg, startBit=8, length=8)
            threadMask = BitUnPack(eventCfg, startBit=56, length=8)
            sliceMask = BitUnPack(eventCfg, startBit=48, length=4)
            eventName = "amd_l3/event={},umask={},slicemask={},threadmask={}/".format(
                str(hex(event)),
                str(hex(umask)),
                str(hex(sliceMask)),
                str(hex(threadMask)),
            )

        if family == "0x19":
            # 0-7: event code, 8-15: mask, 42-44: core id, 46:enallslice, 47:enallcore 48-50: Slice id, 56-63: Thread mask
            event = BitUnPack(eventCfg, startBit=0, length=8)
            umask = BitUnPack(eventCfg, startBit=8, length=8)
            coreId = BitUnPack(eventCfg, startBit=42, length=3)
            threadMask = BitUnPack(eventCfg, startBit=56, length=8)
            sliceId = BitUnPack(eventCfg, startBit=48, length=3)
            enallCores = BitUnPack(eventCfg, startBit=47, length=1)
            enallSlices = BitUnPack(eventCfg, startBit=46, length=1)
            eventName = "amd_l3/event={},umask={},coreid={},threadmask={},sliceid={},enallcores={},enallslices={}/".format(
                str(hex(event)),
                str(hex(umask)),
                str(hex(coreId)),
                str(hex(threadMask)),
                str(hex(sliceId)),
                str(hex(enallCores)),
                str(hex(enallSlices)),
            )

        return eventName

    def DecodeDfName(self, eventCfg):
        family, model = hex(self.fileHeader.family), hex(self.fileHeader.model >> 4)
        if family == "0x19" and model == "0x1":
            # Eventcode = [0-7][32-37]
            # Umask = [8-15][24-27]
            eventCode = BitUnPack(eventCfg, startBit=0, length=8) | (
                BitUnPack(eventCfg, startBit=32, length=6) << 8
            )
            uMask = BitUnPack(eventCfg, startBit=8, length=8) | (
                BitUnPack(eventCfg, startBit=24, length=4) << 8
            )
        else:
            # Eventcode = [0-7][32-35]
            # Umask = [8-15]
            eventCode = BitUnPack(eventCfg, startBit=0, length=8) | (
                (BitUnPack(eventCfg, startBit=32, length=4)) << 8
            )
            uMask = BitUnPack(eventCfg, startBit=8, length=8)
        return (
            "amd_df/event=" + str(hex(eventCode)) + ",umask=" + str(hex(uMask)) + "/ "
        )

    @staticmethod
    def DecodeUmcName(eventCfg):
        return f"umc/{hex(eventCfg)}"

    @staticmethod
    def DecodeAttrName(attrCode):
        if attrCode == 0x1:
            return "msr/tsc/"
        elif attrCode == 0x2:
            return "msr/irperf/"
        elif attrCode == 0x4:
            return "msr/mperf/"
        elif attrCode == 0x8:
            return "msr/event=0x01/"  # aperf

        return ""


class ReadFileHeader:
    def __init__(self, f):
        headerData = unpack("<3Q2I3Q6I6Q", f.read(PMC_HEADER_SIZE))
        # Should be inline with PmcHeader
        self.magicNumber = headerData[0]
        self.version = headerData[1]

        if not (
            (PMC_HEADER_MAGIC_NUMBER == self.magicNumber)
            and (PMC_HEADER_VERSION == self.version)
        ):
            sys.exit("Error: Raw file version doesn't match")

        self.sizeHeader = headerData[2]
        self.family = headerData[3]
        self.model = headerData[4]
        self.timeStamp = headerData[5]
        self.pStateReg = headerData[6]
        self.temp_freq = headerData[7]

        self.pmcPerUmc = headerData[8]
        self.umcMaskArrSize = headerData[9]
        self.umcMaskArr = [
            headerData[10],
            headerData[11],
            headerData[12],
            headerData[13],
        ]
        self.numConfigGrps = headerData[14]

        if log:
            print("Magic Number {}".format(hex(self.magicNumber)))
            print("Family : {}".format(self.family))
            print("Model: {}".format(self.model))
            print("Temp frequency: {}".format(self.temp_freq))
            print("UMC pmc per umc: {}".format(self.pmcPerUmc))
            print("UMC mask array size: {}".format(self.umcMaskArrSize))
            print("UMC mask array: {}".format(self.umcMaskArr[: self.umcMaskArrSize]))
            print("Num of config groups: {}".format(self.numConfigGrps))


class ReadConfigGroup:
    def __init__(self, f):
        self.groupConfigList = []
        self.groupAttrList = []
        self.groupConfigNameList = []

        self.groupHeader = ReadUINT64(f)
        self.groupType = BitUnPack(self.groupHeader, startBit=0, length=8)
        self.groupConfigCnt = BitUnPack(self.groupHeader, startBit=8, length=8)
        self.groupAttr = BitUnPack(self.groupHeader, startBit=16, length=16)
        self.groupID = BitUnPack(self.groupHeader, startBit=32, length=32)

        # Read name for each attribute
        # name =( 64 bytes for each name, null terminated string)
        for mask in groupAttributesList:
            if mask & self.groupAttr:
                self.groupAttrList.append(ReadCharStr(f))

        # Interpret group configurations
        for _ in range(self.groupConfigCnt):
            self.groupConfigList.append(ReadUINT64(f))
            self.groupConfigNameList.append(ReadCharStr(f))  # Read event configs name

        if log:
            print("========================================================")
            print("Group ID: {}".format(self.groupID))
            print("Group config count: {}".format(self.groupConfigCnt))
            print("Group Type: {}".format(self.groupType))
            print("Group Attribute: {}".format(self.groupAttr))
            for idx, name in enumerate(self.groupAttrList):
                print("Name {}: {}".format(idx + 1, (name)))
            print("Group event configurations")
            for idx, config in enumerate(self.groupConfigList):
                print(
                    "Event {}: {} -> {}".format(
                        idx + 1, self.groupConfigNameList[idx], hex(config)
                    )
                )
            print("========================================================")


class ReadSample:
    def __init__(self, RawFileInstance: RawFile):
        self.sampleHeader = ReadUINT64(RawFileInstance.f)
        if not self.sampleHeader:  # EOF condition
            return
        self.timeStamp = ReadUINT64(RawFileInstance.f)
        self.coreId = ReadUINT32(RawFileInstance.f)
        self.socketId = ReadUINT32(RawFileInstance.f)
        self.enableTime = ReadUINT64(RawFileInstance.f)

        if log:
            print("**********************************")
            print("Sample Header: {}".format(self.sampleHeader))
            print("Time stamp: {}".format(self.timeStamp))
            print("Core ID: {}".format(self.coreId))
            print("Socket ID: {}".format(self.socketId))
            print("Enable Time: {}".format(self.enableTime))

        for _ in range(RawFileInstance.fileHeader.numConfigGrps):
            ReadConfigGroupValue(RawFileInstance.f, RawFileInstance, self)

        if log:
            print("**********************************")


class ReadConfigGroupValue:
    def __init__(self, f, RawFileInstance: RawFile, ReadSampleInstance: ReadSample):
        self.groupAttrList = []
        self.groupConfigList = []
        evRunTime = 0
        grpHeader = ReadUINT64(f)
        self.groupId = grpHeader & PMC_SAMPLE_HDR_GROUP_ID_MASK
        self.groupAttr = (
            grpHeader >> PMC_SAMPLE_HDR_ATTR_SHIFT
        ) & PMC_SAMPLE_HDR_ATTR_MASK
        self.pmuCnt = 1  # For Core,L3 and DF pmuCount will be 1

        # special case UMC
        if RawFileInstance.groupType == 4:
            # A socket can have multiple UMCs
            # UMC count per socket is number of enabled bits in umcMaskArr[ socketID ]
            umcMask = RawFileInstance.fileHeader.umcMaskArr[ReadSampleInstance.socketId]
            self.pmuCnt = bin(umcMask).count("1")
            self.processUMCGroupData(f, RawFileInstance, ReadSampleInstance)
        else:
            self.processCoreL3DFGroupData(f, RawFileInstance, ReadSampleInstance)

        if log:
            print("Group ID: {}".format(self.groupId))
            print(f"PMU count: {self.pmuCnt}")
            if self.groupAttrList:
                print("Group attribute values")
                for idx, config in enumerate(self.groupAttrList):
                    print("Attribute {}: {}".format(idx + 1, (config)))
            print("Group event configurations values")
            for idx, config in enumerate(self.groupConfigList):
                print(
                    "Event {}: {}".format(
                        hex(
                            RawFileInstance.grpDataMap[self.groupId].groupConfigList[
                                idx
                                % RawFileInstance.grpDataMap[
                                    self.groupId
                                ].groupConfigCnt
                            ]
                        ),
                        (config),
                    )
                )

    def processUMCGroupData(
        self, f, RawFileInstance: RawFile, ReadSampleInstance: ReadSample
    ):
        evRunTime = 0
        for mask in groupAttributesList:
            if mask & self.groupAttr:
                value = ReadUINT64(f)
                if mask == TSC_BIT:
                    evRunTime = value
                for pmuId in range(self.pmuCnt):
                    # TSC values will be same for different UMC's per socket
                    # Storing separate TSC values for each UMC
                    ipID = ReadSampleInstance.socketId * self.pmuCnt + pmuId
                    RawFileInstance.attrValueList.append(
                        GroupAttribute(
                            ipID,
                            value,
                            mask,
                        )
                    )

                self.groupAttrList.append(value)

        for pmuId in range(self.pmuCnt):
            for idx in range(RawFileInstance.grpDataMap[self.groupId].groupConfigCnt):
                value = ReadUINT64(f)
                umcID = ReadSampleInstance.socketId * self.pmuCnt + pmuId
                RawFileInstance.eventValueList.append(
                    EventConfigData(
                        umcID,
                        value,
                        evRunTime,
                        RawFileInstance.grpDataMap[self.groupId].groupConfigList[idx],
                        RawFileInstance.grpDataMap[self.groupId].groupConfigNameList[
                            idx
                        ],
                    )
                )
                self.groupConfigList.append(value)

    def processCoreL3DFGroupData(
        self, f, RawFileInstance: RawFile, ReadSampleInstance: ReadSample
    ):
        for mask in groupAttributesList:
            if mask & self.groupAttr:
                value = ReadUINT64(f)
                if mask == TSC_BIT:
                    evRunTime = value
                RawFileInstance.attrValueList.append(
                    GroupAttribute(
                        ReadSampleInstance.coreId,
                        value,
                        mask,
                    )
                )
                self.groupAttrList.append(value)

        for pmuId in range(self.pmuCnt):
            for idx in range(RawFileInstance.grpDataMap[self.groupId].groupConfigCnt):
                value = ReadUINT64(f)
                RawFileInstance.eventValueList.append(
                    EventConfigData(
                        ReadSampleInstance.coreId,
                        value,
                        evRunTime,
                        RawFileInstance.grpDataMap[self.groupId].groupConfigList[idx],
                        RawFileInstance.grpDataMap[self.groupId].groupConfigNameList[
                            idx
                        ],
                    )
                )
                self.groupConfigList.append(value)


class EventConfigData:
    def __init__(self, coreId, value, runTime, eventConfigRaw, name):
        self.coreId = coreId
        self.value = value
        self.runTime = runTime
        self.eventConfigRaw = eventConfigRaw
        self.name = name


class GroupAttribute:
    def __init__(self, coreId, value, attrCode):
        self.coreId = coreId
        self.value = value
        self.attrCode = attrCode
