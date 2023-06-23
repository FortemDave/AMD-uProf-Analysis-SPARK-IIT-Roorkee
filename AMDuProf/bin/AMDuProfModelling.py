#!/usr/bin/env python

#=====================================================================
# Copyright 2022 (c), Advanced Micro Devices, Inc. All rights reserved.
#
# AMDuProfPerfModel.py - Main script for performance modelling from
#                        the data collected using AMDuProfPcm tool
#
# Developed by AMDuProf Profiler team.
#=====================================================================
# list of packages required for this tool
#       matplotlib
#       numpy
#=====================================================================

import argparse
import datetime
import sys
import os
import platform
import getopt
import sys
import glob
from operator import attrgetter
import random

import csv

#from pandas import read_csv
from matplotlib import pyplot as plot
import  matplotlib.ticker as ticker
import numpy as np

# TODO: Later use dataclasses supported in Python 3.7
class SystemInfo:
    def __init__(self):
        self.family = 0x17
        self.model = 0x30
        self.nbrSockets = 1
        self.nbrCoreComplex = 1
        self.nbrCpus = 1            # Logical cores seen by the OS
        self.nbrCores = 1           # Physical cores  seen by the OS
        self.cpuFreqMHz = 1         # CPU Freq in MHz
        self.nbrMemChannels = 1
        self.memorySpeed = 0
        self.modelName = ''
        self.isZen4 = False

class ProfileData:
    def __init__(self):
        self.appName = ''
        self.data = []

class AppRooflineData:
    def __init__(self):
        self.type = ''
        self.name = ''
        self.throughput = 1.0
        self.bandwidth = 1.0
        self.ai = 0.0
        self.color = 'red'
        self.throughputTitle = "Throughput"
        self.aiTitle = "AI"

class ComputePeakData:
    def __init__(self, type):
        self.type = type
        self.name = ""
        self.isFPOps = True
        self.peakOps = 0.0
        self.color = "black"

class MemoryPeakData:
    def __init__(self, type):
        self.type = type
        self.name = ""
        self.peakBW = 0.0
        self.color = "black"

def PrintVersion():
    print('Version')
    sys.exit()

#
#   Utility functions
#
# TODO: These Utility functions return Max Theoretical Values. Need to get the FLOPs by running targeted benchmark
#       Need to return maximum achieveable values by running targeted benchmarks
#

def PeakMemBW(args, nbrChannels):
    peak_bw = lambda mchannel : ( 8. * mchannel * args.memspeed ) / 1000
    peakMemBW = peak_bw(nbrChannels)
    return peakMemBW

def PeakL3BW(args, nbrCoreComplex):
    peak_l3bw = lambda nbrCcx : ( 32.0 * nbrCcx * args.l3freq ) / 1000
    peakL3BW = peak_l3bw(nbrCoreComplex)
    return peakL3BW

# TODO: Currently for peak theorethical FLOP, using P0 Freq.
def PeakSPFlops(args, nbrCores):
    peak_fp = lambda nCores  : nCores * args.fmaUnits * (args.fpWidth / args.spDataWidth) * args.flopsPerLane * args.frequency
    peakFlops = peak_fp(nbrCores)
    return peakFlops

def PeakDPFlops(args, nbrCores):
    peak_fp = lambda nCores  : nCores * args.fmaUnits * (args.fpWidth / args.dpDataWidth) * args.flopsPerLane * args.frequency
    peakFlops = peak_fp(nbrCores)
    return peakFlops

def PeakFlops(args, nbrCores, typeStr):
    peakFlops = 0.0

    if typeStr == "SP FP":
        peakFlops = nbrCores * args.fmaUnits * (args.fpWidth / args.spDataWidth) * args.flopsPerLane * args.frequency
    elif typeStr == "DP FP":
        peakFlops = nbrCores * args.fmaUnits * (args.fpWidth / args.dpDataWidth) * args.flopsPerLane * args.frequency
    elif typeStr == "SP FP noFMA":
        peakFlops = nbrCores * (args.fpWidth / args.spDataWidth) * args.flopsPerLane * args.frequency
    elif typeStr == "DP FP noFMA":
        peakFlops = nbrCores * (args.fpWidth / args.dpDataWidth) * args.flopsPerLane * args.frequency
    elif typeStr == "SP FP noSIMD":
        peakFlops = nbrCores * args.fmaUnits * args.flopsPerLane * args.frequency
    elif typeStr == "DP FP noSIMD":
        peakFlops = nbrCores * args.fmaUnits * args.flopsPerLane * args.frequency
    elif typeStr == "SP FP noSIMD noFMA":
        peakFlops = nbrCores * args.flopsPerLane * args.frequency
    elif typeStr == "DP FP noSIMD noFMA":
        peakFlops = nbrCores * args.flopsPerLane * args.frequency
    
    return peakFlops

def GetMaxComputeRoof(args, sysInfo):
    computeRoofs = GetComputeCapacityRoofDataList(args, sysInfo)
    maxComputeRoof = max(computeRoofs, key=attrgetter('peakOps'))
    return maxComputeRoof

def GetMinComputeRoof(args, sysInfo):
    computeRoofs = GetComputeCapacityRoofDataList(args, sysInfo)
    minComputeRoof = min(computeRoofs, key=attrgetter('peakOps'))
    return minComputeRoof

def GetMaxMemoryRoof(args, sysInfo):
    memRoofs = GetMemoryCapacityRoofDataList(args, sysInfo)
    maxMemRoof = max(memRoofs, key=attrgetter('peakBW'))
    return maxMemRoof

def GetMinMemoryRoof(args, sysInfo):
    memRoofs = GetMemoryCapacityRoofDataList(args, sysInfo)
    minMemRoof = min(memRoofs, key=attrgetter('peakBW'))
    return minMemRoof

# Get the number cores, memory-channels to scale roof values
def GetDataToScaleRoofs(args, sysInfo):
    # number of CPU cores to scale roof values 
    if args.allCores is True:
        nbrCpus = sysInfo.nbrCpus            # logical threads
        nbrCores = sysInfo.nbrCores         # physical cores
        nbrCcx = sysInfo.nbrCoreComplex
        # nbrMemChannels = sysInfo.nbrSockets * sysInfo.nbrMemChannels
        nbrMemChannels = sysInfo.nbrMemChannels
    elif args.singleThreaded is True:
        # single-threaded case
        nbrCores = 1
        nbrCpus = 1
        nbrCcx = 1
        nbrMemChannels = 1
    else:
        # specific threads case
        nbrCpus = args.cpus
        nbrCores = args.cores
        # TODO: - how to get the corresponsing list of CCX to consider ?
        nbrCcx = sysInfo.nbrCoreComplex
        # TODO - how to get the nbr of channels for set of threads ?
        nbrMemChannels = sysInfo.nbrMemChannels

    return nbrCpus, nbrCores, nbrCcx, nbrMemChannels 

def ReadPcmData(args):
    file = args.input_file

    sysInfo = SystemInfo()
    profileData = ProfileData()

    with open(file, mode='r') as csvFile:
        dataIdx = -1
        csvReader = csv.reader(csvFile)

        tpAvbl = False
        bwAvbl = False

        for row in csvReader:
            if not row:
                continue

            key = row[0]

            if key == "[System Info]" or key == "[Profile Data]" or key == "AMDuProfPcm Report":
                continue

            value = row[1]

            if key == "Application":
                profileData.appName = str(value)
            elif key == "Family":
                sysInfo.family = int(value)
            elif key == "Model":
                sysInfo.model = int(value)
            elif key == "Sockets":
                sysInfo.nbrSockets = int(value)
            elif key == "CoreComplex":
                sysInfo.nbrCoreComplex = int(value)
            elif key == "Threads":
                sysInfo.nbrCpus = int(value)
            elif key == "Cores":
                sysInfo.nbrCores = int(value)
            elif key == "CpuFreqMHz":
                sysInfo.cpuFreqMHz = float(value)
            elif key == "MemoryChannels":
                sysInfo.nbrMemChannels = int(value)
            elif key == "MemorySpeed":
                sysInfo.memorySpeed = int(value)
            elif key == "ModelName":
                sysInfo.modelName = str(value)
            elif key == "Type":
                dataIdx += 1
                profileData.data.append(AppRooflineData())
                color="#"+''.join([random.choice('0123456789ABCDEF') for i in range(6)])
                profileData.data[dataIdx].color = color
            elif key == "Name":
                # if -a or --app-name is given by the user, then it.
                profileData.data[dataIdx].name = str(value)
                if args.app_name is not None:
                    profileData.data[dataIdx].name = args.app_name
            elif key == "Throughput":
                profileData.data[dataIdx].throughput = float(value)
                tpAvbl = True
            elif key == "Bandwidth":
                profileData.data[dataIdx].bandwidth = float(value)
                bwAvbl = True

            if tpAvbl is True and bwAvbl is True:
                tp = profileData.data[dataIdx].throughput
                bw = profileData.data[dataIdx].bandwidth
                ai = round((tp / bw), 4)
                profileData.data[dataIdx].ai = ai
                tpAvbl = False
                bwAvbl = False

    if sysInfo.family == 0x19 and ((sysInfo.model >= 0x10 and sysInfo.model <= 0x1F) or (sysInfo.model >= 0x60 and sysInfo.model <= 0x6F)):
        sysInfo.isZen4 = True

    return sysInfo, profileData

# Add system AI. TODO: Revisit to generalize this code
def AddSystemAI(args, sysInfo, profileData):
    dataIdx = 1
    profileData.data.append(AppRooflineData())
    color="#"+''.join([random.choice('0123456789ABCDEF') for i in range(6)])
    profileData.data[dataIdx].color = color
    profileData.data[dataIdx].name = "System"
    peakSpFlop = GetComputeCapacitylRoofData(args, sysInfo, "SP FP")
    peakDramBw = GetMemoryCapacitylRoofData(args, sysInfo, "DRAM")
    profileData.data[dataIdx].throughput = peakSpFlop.peakOps
    profileData.data[dataIdx].bandwidth = peakDramBw.peakBW
    profileData.data[dataIdx].ai = round((profileData.data[dataIdx].throughput / profileData.data[dataIdx].bandwidth), 4)
    profileData.data[dataIdx].throughputTitle = None
    profileData.data[dataIdx].aiTitle = "AI (SP FP)" 

    dataIdx += 1
    profileData.data.append(AppRooflineData())
    color="#"+''.join([random.choice('0123456789ABCDEF') for i in range(6)])
    profileData.data[dataIdx].color = color
    profileData.data[dataIdx].name = "System"
    peakDpFlop = GetComputeCapacitylRoofData(args, sysInfo, "DP FP")
    profileData.data[dataIdx].throughput = peakDpFlop.peakOps
    profileData.data[dataIdx].bandwidth = peakDramBw.peakBW
    profileData.data[dataIdx].ai = round((profileData.data[dataIdx].throughput / profileData.data[dataIdx].bandwidth), 4)
    profileData.data[dataIdx].throughputTitle = None
    profileData.data[dataIdx].aiTitle = "AI (DP FP)" 

    if not args.stream is None:
        if not args.hpl is None:
            dataIdx += 1
            profileData.data.append(AppRooflineData())
            color="#"+''.join([random.choice('0123456789ABCDEF') for i in range(6)])
            profileData.data[dataIdx].color = color
            profileData.data[dataIdx].name = "STREAM+HPL"
            maxBw = GetMemoryCapacitylRoofData(args, sysInfo, "STREAM")
            maxFlop = GetComputeCapacitylRoofData(args, sysInfo, "HPL")
            profileData.data[dataIdx].throughput = maxFlop.peakOps
            profileData.data[dataIdx].bandwidth = maxBw.peakBW
            profileData.data[dataIdx].ai = round((profileData.data[dataIdx].throughput / profileData.data[dataIdx].bandwidth), 4)
            profileData.data[dataIdx].throughputTitle = None
            profileData.data[dataIdx].aiTitle = "AI (STREAM+HPL)"

        if not args.gemm is None:
            dataIdx += 1
            profileData.data.append(AppRooflineData())
            color="#"+''.join([random.choice('0123456789ABCDEF') for i in range(6)])
            profileData.data[dataIdx].color = color
            profileData.data[dataIdx].name = "STREAM+[SD]GEMM"
            maxBw = GetMemoryCapacitylRoofData(args, sysInfo, "STREAM")
            maxFlop = GetComputeCapacitylRoofData(args, sysInfo, "GEMM")
            profileData.data[dataIdx].throughput = maxFlop.peakOps
            profileData.data[dataIdx].bandwidth = maxBw.peakBW
            profileData.data[dataIdx].ai = round((profileData.data[dataIdx].throughput / profileData.data[dataIdx].bandwidth), 4)
            profileData.data[dataIdx].throughputTitle = None
            profileData.data[dataIdx].aiTitle = "AI (STREAM+[SD]GEMM)"

#
#   Compute Limits
#

def GetComputeCapacitylRoofData(args, sysInfo, type):
    peakData = ComputePeakData(type)
    peakOps = 0
    nbrCpus, nbrCores, nbrCcx, nbrMemChannels = GetDataToScaleRoofs(args, sysInfo)

    if type == "SP FP":
        peakOps = PeakSPFlops(args, nbrCores)

        peakData.isFPOps = True
        peakData.name = "SP FP Peak" # Max therotical Single & Double Precision FP Ops
        peakData.color = "black"
        peakData.peakOps = peakOps

    if type == "DP FP":
        peakOps = PeakDPFlops(args, nbrCores)

        peakData.isFPOps = True
        peakData.name = "DP FP Peak" # Max therotical Single & Double Precision FP Ops
        peakData.color = "black"
        peakData.peakOps = peakOps

    elif type in [ "SP FP noFMA", "SP FP noSIMD", "SP FP noSIMD noFMA", "DP FP noFMA", "DP FP noSIMD", "DP FP noSIMD noFMA" ]:
        peakOps = PeakFlops(args, nbrCores, type)
        peakData.isFPOps = True
        peakData.name = str(type + " Peak")
        peakData.color = "lightgrey"
        peakData.peakOps = peakOps

    elif type == "HPL":
        peakData.isFPOps = True
        peakData.name = "HPL"       # Flops achieved by HPL
        peakData.color = "lightgrey"
        peakData.peakOps = args.hpl

    elif type in [ "GEMM", "DGEMN", "SGEMM" ]:
        peakData.isFPOps = True
        peakData.name = type        # Flops achieved by GEMM/DGEMM/SGEMM
        peakData.color = "lightgrey"
        peakData.peakOps = args.gemm

    elif type == "INT":
        print('Yet to add support for INT operatons')
        sys.exit()

    return peakData

def GetComputeCapacityRoofDataList(args, sysInfo):
    idx = 0
    computeLimitRoofsList = []

    size = len(args.computeCapacityRoofs)
    for idx in range(size):
        typeStr = args.computeCapacityRoofs[idx]
        peekData = GetComputeCapacitylRoofData(args, sysInfo, typeStr)
        computeLimitRoofsList.append(peekData)

    return computeLimitRoofsList


#
#   Memory Limits
#

# Diagonal Roof lines - memory capacity limit
def GetMemoryCapacitylRoofData(args, sysInfo, type):
    peak_fp = lambda nthread  : nthread * ( args.reqwidth / args.prec ) * args.fma * args.frequency

    peakData = MemoryPeakData(type)

    nbrCpus, nbrCores, nbrCcx, nbrMemChannels = GetDataToScaleRoofs(args, sysInfo)

    if type == "DRAM":
        peakMemBW = PeakMemBW(args, nbrMemChannels)

        peakData.name = "DRAM BW" # Max therotical DRAM BW
        peakData.peakBW = peakMemBW

    elif type == "STREAM":
        assert not args.stream is None, "Need to specify --stream <bandwidth score in GB/s>"

        peakData.name = "STREAM" # Bandwidth achieved by STREAM benchmark
        peakData.peakBW = args.stream
        peakData.color = 'lightgrey'

    elif type == "L3":
        peakL3BW   = PeakL3BW(args, nbrCcx)

        peakData.name = "L3 BW" # Max therotical L3 BW
        peakData.peakBW = peakL3BW
    # TODO: add L2 & L1

    return peakData

def GetMemoryCapacityRoofDataList(args, sysInfo):
    idx = 0
    memoryLimitRoofsList = []

    size = len(args.memoryCapacityRoofs)

    for idx in range(size):
        typeStr = args.memoryCapacityRoofs[idx]
        peekData = GetMemoryCapacitylRoofData(args, sysInfo, typeStr)
        memoryLimitRoofsList.append(peekData)

    return memoryLimitRoofsList

#
#   Plot primitives
#

def InitializePlot(sysInfo, data):
    #plot.clf()

    title1 = str('sockets(%d), cpus(%d), base frequency(%.2f MHz)' % (sysInfo.nbrSockets, sysInfo.nbrCpus, sysInfo.cpuFreqMHz))
    title = 'Classic Roofline\n' + sysInfo.modelName + '\n' + title1
    fig, ax = plot.subplots()
    fig.suptitle(title)

    xlabel = 'Arithmetic Intensity [FLOP/Byte]'
    ylabel = 'Throughput [GFLOPS]'
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)

    return fig, ax

def LabelLine(ax, line, label, x, y, color='black', size=12):
    xdata, ydata = line.get_data()
    x1 = xdata[0]
    x2 = xdata[-1]
    y1 = ydata[0]
    y2 = ydata[-1]

    txt = ax.annotate(label, xy=(x, y), xytext=(-10, 0),
                        textcoords='offset points',
                        color=color,
                        horizontalalignment='left',
                        verticalalignment='bottom')

    pt1 = ax.transData.transform_point((x1, y1))
    pt2 = ax.transData.transform_point((x2, y2))

    rise = (pt2[1] - pt1[1])
    run = (pt2[0] - pt1[0])

    slope = np.degrees(np.arctan2(rise, run))
    txt.set_rotation(slope)

    return txt

# plot the horizontal roofline 
def PlotHorizontalRoofline(computeRoof, fig, ax, minX, maxX, minAI, maxAI):
    title = computeRoof.name
    peakOps = computeRoof.peakOps
    roofColor = computeRoof.color

    if computeRoof.isFPOps is True:
        unit = "GFLOPS"
    else:
        unit = "GINTOPS"

    ax.hlines(peakOps, minX, minAI, color=roofColor, linestyle='dotted', linewidth=1)
    ax.hlines(peakOps, minAI, maxX, color=roofColor, linestyle='-', linewidth=1)

    titleStr = title + ' %.2f ' + unit
    #ax.annotate(str(titleStr) % (peakOps), ((maxAI + 1), peakOps + 2))
    ax.annotate(str(titleStr) % (peakOps), ((maxAI + 1), peakOps + 2), color=roofColor)


def PlotDiagonalRoofline(memoryRoof, fig, ax, minX, maxX, maxFlops):
    type = memoryRoof.type
    name = memoryRoof.name
    peakBw = memoryRoof.peakBW
    dcolor = memoryRoof.color   # diagonal roof

    #x = [0.001, ai]
    #y = [0.001 * peakBw, peakOps]
    x = [minX, maxX]
    y = [round((minX * peakBw), 4), round((maxX * peakBw), 4)]

    ax.set_xscale('log')
    ax.set_yscale('log')

    line, =  ax.loglog(x, y, color=dcolor, linestyle='-', linewidth=1)

    ax.xaxis.set_major_formatter(ticker.StrMethodFormatter('{x:.3f}'))
    ax.yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:.2f}'))

    # Annotate
    #X = 0.01
    #Y =  (1.01) * (0.01 * peakBw)
    X = round((minX * 5), 2)
    Y = (1.01) * (X * peakBw)

    labelStr = str(name + ' %.2f GB/sec') % peakBw 
    #LabelLine(ax, line, labelStr, X, Y, color='black')
    LabelLine(ax, line, labelStr, X, Y, color=dcolor)


def PlotAIPoint(aiData, fig, ax):
    name = aiData.name
    ptColor = aiData.color
    appFlop = aiData.throughput
    appBW   = aiData.bandwidth
    #appAI = appFlop / appBW
    appAI = aiData.ai
    throughputStr = aiData.throughputTitle
    aiStr = aiData.aiTitle

    labelStr = str(name + ' ' + aiStr +  ' : %.2f FLOP/B ' % (appAI))
    if throughputStr is not None:
        labelStr += str(throughputStr + ': %.2f GFLOPS' % (appFlop))
    ax.scatter([appAI], [appFlop], c=ptColor, alpha=0.5, label=labelStr)


def FinalizePlot(args, sysInfo, fig, ax):
    ax.legend(fontsize='x-small', loc='lower right', bbox_to_anchor=(0.5, 0.5))
    ax.grid(True, linewidth=0.25, color='gray', linestyle='-')

    plot.legend()

    # Save the plot in pdf
    if args.save_pdf is True or args.output_dir is not None:
        ts = datetime.datetime.now().strftime("%Y-%m-%d-%Hh%Mm%Ss")

        if args.output_dir is not None:
            fname = os.path.join(args.output_dir, 'AMDuProf_roofline-%s.pdf' % ts)
        else:
            fname = os.path.join('/tmp/', 'AMDuProf_roofline-%s.pdf' % ts)

        print("Saving plot in file " + str(fname))
        plot.savefig(fname)
    else:
        plot.show()

def GetMinX(args, sysInfo, profileData):
    minAppData = min(profileData.data, key=attrgetter('throughput'))
    minAppThroughput = minAppData.throughput

    minComputeRoof = GetMinComputeRoof(args, sysInfo)
    maxMemRoof = GetMaxMemoryRoof(args, sysInfo)
    minMemRoof = GetMinMemoryRoof(args, sysInfo)
    minAI = minComputeRoof.peakOps / maxMemRoof.peakBW
    minX = 0.001

    thresholdMinAppTp = round((minAppThroughput * 0.9), 4)

    step = 8.0
    for i in range(16):
        minX = minAI / step
        tmpThroughput = round((minX * minMemRoof.peakBW), 4)

        #if tmpThroughput < minAppThroughput:
        if tmpThroughput < thresholdMinAppTp:
            break
        else:
            step += 16.0

    return round(minX, 4)

def GetMaxX(profileData, maxAI):
    maxAppData = max(profileData.data, key=attrgetter('ai'))
    maxAppAI = maxAppData.ai
    maxX = maxAI

    thresholdMaxAI = round((maxAppAI * 1.1), 4)

    step = 8.0
    for i in range(16):
        maxX = round((maxAI * step), 4)

        if maxX > thresholdMaxAI:
            break
        else:
            step += 16.0

    return maxX

# Return Max Peak AI across all the roofs
def GetMaxAI(args, sysInfo):
    maxComputeRoof = GetMaxComputeRoof(args, sysInfo)
    minMemRoof = GetMinMemoryRoof(args, sysInfo)

    maxAI = maxComputeRoof.peakOps / minMemRoof.peakBW

    return maxAI

#
#   High Level functions to plot roofline
#

def PlotComputeCapacityRooflines(args, sysInfo, fig, ax, minX, maxX, maxAI):
    # Figure out the peak horizontal rooflines to plot
    computeRoofs = GetComputeCapacityRoofDataList(args, sysInfo)
    maxMemRoof = GetMaxMemoryRoof(args, sysInfo)

    ax.set_xlim(minX, maxX)

    # plot the horizontal roofline for "DRAM AI"
    for aComputeRoof in computeRoofs:
        minAI = aComputeRoof.peakOps / maxMemRoof.peakBW
        PlotHorizontalRoofline(aComputeRoof, fig, ax, minX, maxX, minAI, maxAI)


def PlotMemoryCapacityRooflines(args, sysInfo, fig, ax, minX):
    # Figure out the peak diagonal rooflines to plot
    memoryRoofs = GetMemoryCapacityRoofDataList(args, sysInfo)

    maxComputeRoof = GetMaxComputeRoof(args, sysInfo)
    minComputeRoof = GetMinComputeRoof(args, sysInfo)

    maxMemRoof = max(memoryRoofs, key=attrgetter('peakBW'))
    minMemRoof = min(memoryRoofs, key=attrgetter('peakBW'))

    minAI = minComputeRoof.peakOps / maxMemRoof.peakBW
    maxFlops = maxComputeRoof.peakOps

    # plot the diagonal rooflines for memory capacity limits
    for aMemoryRoof in memoryRoofs:
        maxAI = maxComputeRoof.peakOps / aMemoryRoof.peakBW
        maxX = maxAI
        PlotDiagonalRoofline(aMemoryRoof, fig, ax, minX, maxX, maxFlops)


def PlotArithmeticIntensityPoints(args, sysInfo, profileData, fig, ax):
    for aiPoint in profileData.data:
        PlotAIPoint(aiPoint, fig, ax)


def PlotRoofline(args, sysInfo, profileData):
    fig, ax = InitializePlot(sysInfo, profileData)
    fig.set_figwidth(8)
    fig.set_figheight(6)

    maxAI = GetMaxAI(args, sysInfo)
    minX = GetMinX(args, sysInfo, profileData)
    maxX = GetMaxX(profileData, maxAI)

    # Add System AI info
    AddSystemAI(args, sysInfo, profileData)

    # Plot peak horizontal rooflines - Compute Capacity limits
    PlotComputeCapacityRooflines(args, sysInfo, fig, ax, minX, maxX, maxAI)

    # Plot peak diagonal rooflines - Memory Capacity limits
    PlotMemoryCapacityRooflines(args, sysInfo, fig, ax, minX)

    PlotArithmeticIntensityPoints(args, sysInfo, profileData, fig, ax)

    FinalizePlot(args, sysInfo, fig, ax)


def ProcessOptions(args, sysInfo):
    args.frequency  = sysInfo.cpuFreqMHz / 1000.0
    args.l3freq     = args.frequency

    # number of CPU cores to scale roof values 
    args.singleThreaded = False
    args.allCores = False

    if args.cores == 0:
        args.singleThreaded = False
        args.allCores = True
    elif args.cores == 1:
        args.singleThreaded = True
        args.allCores = False

    # Operations to plot CPU Compute capacity limits - Maximum achieveable performance (x-axis)
    #   - Float or INT or Hybrid (Float and INT) Operations
    #   - For Float operations, multiple peaks can be plotted
    #       - SP FP
    #       - DP FP
    args.computeCapacityRoofs = []
    if args.operations == 'float':
        args.computeCapacityRoofs.append('SP FP')
        args.computeCapacityRoofs.append('DP FP')

        if not args.hpl is None:
            args.computeCapacityRoofs.append('HPL')
        if not args.gemm is None:
            args.computeCapacityRoofs.append('GEMM')

        if args.sp_roofs is True:
            args.computeCapacityRoofs.append('SP FP noSIMD')
            args.computeCapacityRoofs.append('SP FP noFMA')
            args.computeCapacityRoofs.append('SP FP noSIMD noFMA')
        if args.dp_roofs is True:
            args.computeCapacityRoofs.append('DP FP noSIMD')
            args.computeCapacityRoofs.append('DP FP noFMA')
            args.computeCapacityRoofs.append('DP FP noSIMD noFMA')

    elif args.operations == 'int':
        print('Yet to add support for INT operatons')
        sys.exit()
    elif args.operations == 'hybrid':
        print('Yet to add support for INT operatons')
        args.computeCapacityRoofs.append('SP FP')
        args.computeCapacityRoofs.append('DP FP')

    # FP Roofline
    # TODO: This should be based on family & model
    args.fmaUnits = 2       # FMA units per core; This is for All Zen cores
    args.fpWidth    = 256   # FMA unit width; Zen2 & Zen3
    args.spDataWidth = 32   # SP data width
    args.dpDataWidth = 64   # DP data width
    args.flopsPerLane = 2   # 2 FLOPS Per lane

    if sysInfo.isZen4 is True:
        args.fpWidth = 256  # 256b data path

    # Memory capacity limits
    args.memoryCapacityRoofs = []

    if args.memory_roofs == "dram":
        args.memoryCapacityRoofs.append('DRAM')
    elif args.memory_roofs == "stream":
        args.memoryCapacityRoofs.append('DRAM')
        args.memoryCapacityRoofs.append('STREAM')
        assert not args.stream is None, "Need to provide --stream <bandwidth score in GB/s>"
    elif args.memory_roofs == "cache":
        print('Yet to add support for memory capacity rooflines for cache hierarchies')
        sys.exit()
    elif args.memory_roofs == "all":
        print('Yet to add support for memory capacity rooflines for cache hierarchies')
        args.memoryCapacityRoofs.append('DRAM')

def ParseArgs():
    # initialize the args parser
    argParser = argparse.ArgumentParser()

    # add options
    # argParser.add_argument("-f", "--frequency", help="core frequency (GHz)", type=float, default=2.45) 
    argParser.add_argument("-s", "--memspeed", help="memory speed (MHz)", type=int, default=0) 
    argParser.add_argument("-i", "--input-file", help="specify the input profile data file path collected using AMDuProfPcm with roofline option", type=str) 
    argParser.add_argument("-o", "--output-dir", help="specify the output dir to save the plot into PDF. Use with -S option", type=str) 
    argParser.add_argument("-p", "--plot", help="plot timeseries or roofline", type=str, choices=['timeseries', 'roofline'], default='roofline') 
    argParser.add_argument("-c", "--cores", help="Choose number of CPU cores to scale roof values", type=int, default=0) 

    argParser.add_argument("-O", "--operations", help="Build compute limit rooflines for this operations", type=str, choices=['float', 'int', 'hybrid'], default='float') 
    argParser.add_argument("-M", "--memory-roofs", help="Specify memory limit rooflines. DRAM is fixed", type=str, choices=['dram', 'cache', 'all'], default = 'dram') 

    argParser.add_argument("-x", "--stream", help="STREAM score", type=float, default=None)
    argParser.add_argument("-y", "--hpl", help="HPL score", type=float, default=None)
    argParser.add_argument("-z", "--gemm", help="[SD]GEMM score", type=float, default=None)

    argParser.add_argument("--sp-roofs", help="Plot max peak roof for single-precision noSIMD and noFMA", action='store_true', default=False) 
    argParser.add_argument("--dp-roofs", help="Plot max peak roof for double-precision noSIMD and noFMA", action='store_true', default=False) 

    argParser.add_argument("-v", "--version", help="print the version", action='store_true', default=False) 

    argParser.add_argument("-S", "--save-pdf", help="Save into PDF", action='store_true', default=False) 
    argParser.add_argument("-a", "--app-name", help="Application name to print in the plot", type=str) 

    args = argParser.parse_args()

    if args.memory_roofs == 'dram':
        if args.stream is not None :
            args.memory_roofs = 'stream'
            if args.hpl is None and args.gemm is None:
                print('Error: Specify --hpl|gemm <GFLOPS score> along with --stream option.')
                sys.exit()

    return args


def main():
    global gScript

    # Set the name of this script
    gScript = os.path.basename(__file__)

    args = ParseArgs()

    if args.version is True:
        PrintVersion()

    if args.input_file is not None:
        if args.plot == 'timeseries':
            print('Timeseries plotting is not yet supported')
            sys.exit()
        elif args.plot == 'roofline':
            sysInfo, data = ReadPcmData(args)

            if sysInfo.memorySpeed == 0 and args.memspeed == 0:
                print("Use --memspeed option to specify DRAM speed. Either use dmidecode or lshw command to get the memory speed.")
                exit(-1)
            elif sysInfo.memorySpeed > 0:
                args.memspeed = sysInfo.memorySpeed

            ProcessOptions(args, sysInfo)
            PlotRoofline(args, sysInfo, data)

if __name__ == "__main__":
    main()

