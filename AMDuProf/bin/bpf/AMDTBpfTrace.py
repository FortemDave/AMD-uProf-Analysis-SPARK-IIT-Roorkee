#==================================================================================
# Copyright (c) 2021 , Advanced Micro Devices, Inc.  All rights reserved.
#
# author AMD Developer Tools Team
# file AMDTBpfTrace.py
# brief Os trace collection using bcc library
#==================================================================================

#!/usr/bin/python
from bcc import ArgString, BPF
import argparse
import signal
import sys
import enum
import ctypes as ct
import csv
import os
from AMDTBpfKernel import *
import json

AMDT_UNKNOWN_TIMESTAMP  = int(0xffffffffffffffff) #18446744073709551615
AMDT_UNKNOWN_TGID       = int(0xffffffff)         #4294967295
AMDT_UNKNOWN_PID        = int(0xffffffff)         #4294967295
AMDT_UNKNOWN_CORE_ID    = int(0xffffffff)         #4294967295
AMDT_UNKNOWN_STACK_ID   = -1
AMDT_IDLE_THREAD        = 0
AMDT_FALSE              = 0
AMDT_TRUE               = 1
AMDT_MAX_SYSCALLS       = 1024

AMDT_LIBTRACE_FUNCTION_START = 0x4000    # TODO: while implementing the libtrace, need to check this value.
AMDT_CPUIDLE_DEFAULT_THRESHOLD = 10000   #nsec
AMDT_SYSCALL_DEFAULT_THRESHOLD = 10000   #nsec
AMDT_FUNCCOUNT_DEFAULT_THRESHOLD = 100000 #nsec
AMDT_PTHREAD_DEFAULT_THRESHOLD = 0       #nsec
AMDT_MEMSIZE_DEFAULT_THRESHOLD = 1024    #bytes
AMDT_IOTRACE_DEFAULT_THRESHOLD = 1024    #bytes

AMDT_MAX_THREADS_SWP = 32768
AMDT_MAX_THREADS_APP = 1024

FILE_NAME_LENGTH = 255
AMDT_PID_STR_SIZE = 2048
AMDT_PROBE_LIMIT = 1000

#This enum is used to identify the events configured by User through command line.
#This enum is used to identify the type of data sent from kernel to user space through Perf Buffer.
class AMDTOsTraceDataTypes(enum.Enum):
    AMDT_OS_TRACE_DATA_TYPE_SCHEDULE = 1
    AMDT_OS_TRACE_DATA_TYPE_CPUIDLE = 2
    AMDT_OS_TRACE_DATA_TYPE_CPUFREQ = 3
    AMDT_OS_TRACE_DATA_TYPE_DISKIO = 4
    AMDT_OS_TRACE_DATA_TYPE_PAGEFAULT = 5
    AMDT_OS_TRACE_DATA_TYPE_SYSCALL = 6
    AMDT_OS_TRACE_DATA_TYPE_PTHREAD = 7
    AMDT_OS_TRACE_DATA_TYPE_MEMTRACE = 8
    AMDT_OS_TRACE_DATA_TYPE_IOTRACE = 9
    AMDT_OS_TRACE_DATA_TYPE_LIBTRACE = 10
    AMDT_OS_TRACE_DATA_TYPE_FUNCCOUNT = 11
    AMDT_OS_TRACE_DATA_TYPE_OPEN_SYSCALL = 12
    AMDT_OS_TRACE_DATA_TYPE_MMAP_SYSCALL = 13

#Modification of this requires the modification for "enum AMDTOsTraceFunctions" in AMDTBpfKernel.py
class AMDTOsTraceFunctions(enum.Enum):
    AMDT_PTHREAD_CREATE             = 0x01
    AMDT_PTHREAD_EXIT               = 0x02
    AMDT_PTHREAD_MUTEX_LOCK         = 0x03
    AMDT_PTHREAD_MUTEX_TRYLOCK      = 0x04
    AMDT_PTHREAD_MUTEX_TIMEDLOCK    = 0x05
    AMDT_PTHREAD_MUTEX_UNLOCK       = 0x06
    AMDT_PTHREAD_COND_WAIT          = 0x07
    AMDT_PTHREAD_COND_TIMEDWAIT     = 0x08
    AMDT_PTHREAD_COND_SIGNAL        = 0x09
    AMDT_PTHREAD_COND_BROADCAST     = 0x0A
    AMDT_PTHREAD_JOIN               = 0x0B
    AMDT_MALLOC                     = 0x0C
    AMDT_CALLOC                     = 0x0D
    AMDT_REALLOC                    = 0x0E
    AMDT_FREE                       = 0x0F
    AMDT_READ                       = 0x10
    AMDT_WRITE                      = 0x11
    AMDT_PREAD                      = 0x12
    AMDT_PWRITE                     = 0x13
    AMDT_AIO_READ                   = 0x14
    AMDT_AIO_WRITE                  = 0x15
    AMDT_IO_SUBMIT                  = 0x16
    AMDT_FUNCCOUNT_FUNCTION_START   = 0x17


g_nRecords    = 128     # No of records sent to user space from kernel at a time.
g_bufferSize  = 256     # Per Core Perf buffer size(in pages) to be used between Kernel and User space.
g_nCallStacks = 1024    # No of unique call stack entries to stored in stack map.
g_nOpenRecords = 16     # No of open system call records sent to user space from kernel at a time
g_wrFifoPath = ""       # fifo used for synchronization between uprof and Bpf program. BPF will write and uProf will read
g_rdFifoPath = ""       # fifo used for synchronization between uprof and Bpf program. BPF will read and uProf will write
g_wrFifo = None         # open file descriptor for writer fifo
g_rdFifo = None         # open file descriptor for reader fifo
g_trace  = None
g_kernel = b'kernel'

#For Each type of event there is a record.
#used to typecast to get data from perf buffer.
class SchedRecord(ct.Structure):
    _fields_ = [
        ("m_startTs",     ct.c_ulonglong),
        ("m_endTs",       ct.c_ulonglong),
        ("m_tgid",        ct.c_uint),
        ("m_pid",         ct.c_uint),
        ("m_state",       ct.c_ulonglong),    # state of a process
        ("m_voluntarySw", ct.c_bool)]

class CpuIdleRecord(ct.Structure):
    _fields_ = [
        ("m_startTs",     ct.c_ulonglong),
        ("m_endTs",       ct.c_ulonglong),
        ("m_cpuId",       ct.c_uint),
        ("m_state",       ct.c_uint)]    # c-state

class CpuFreqRecord(ct.Structure):
    _fields_ = [
        ("m_startTs",     ct.c_ulonglong),
        ("m_endTs",       ct.c_ulonglong),
        ("m_tgid",        ct.c_uint),
        ("m_pid",         ct.c_uint),
        ("m_cpuId",       ct.c_uint),
        ("m_state",       ct.c_uint)]    # p-state

class BlockIoRecord(ct.Structure):
    _fields_ = [
        ("m_insertTs",    ct.c_ulonglong),
        ("m_issueTs",     ct.c_ulonglong),
        ("m_completeTs",  ct.c_ulonglong),
        ("m_tgid",        ct.c_uint),
        ("m_pid",         ct.c_uint),
        ("m_size",        ct.c_ulonglong),
        ("m_operation",   ct.c_uint),
        ("m_major",       ct.c_uint),
        ("m_minor",       ct.c_uint)]

class PageFaultRecord(ct.Structure):
    _fields_ = [
        ("m_startTs",     ct.c_ulonglong),
        ("m_tgid",        ct.c_uint),
        ("m_pid",         ct.c_uint),
        ("m_address",     ct.c_ulonglong),
        ("m_ip",          ct.c_ulonglong),
        ("m_errCode",     ct.c_ulonglong),     # provides the reason for page fault
        ("m_isKernel",    ct.c_bool)]          # Kernel or user page fault

class SysCallRecord(ct.Structure):
    _fields_ = [
        ("m_startTs",     ct.c_ulonglong),
        ("m_endTs",       ct.c_ulonglong),
        ("m_sid",         ct.c_ulonglong),     # system call ID
        ("m_tgid",        ct.c_uint),
        ("m_pid",         ct.c_uint)]

class FuncCountRecord(ct.Structure):
    _fields_ = [
        ("m_startTs",     ct.c_ulonglong),
        ("m_endTs",       ct.c_ulonglong),
        ("m_fid",         ct.c_uint),     # function ID
        ("m_tgid",        ct.c_uint),
        ("m_pid",         ct.c_uint)]

class LibTraceRecord(ct.Structure):
    _fields_ = [
        ("m_startTs",     ct.c_ulonglong),
        ("m_tgid",        ct.c_uint),
        ("m_pid",         ct.c_uint),
        ("m_stackId",     ct.c_int),     # CallStack ID
        ("m_fid",         ct.c_uint)]    # function ID

class MemTraceRecord(ct.Structure):
    _fields_ = [
        ("m_startTs",     ct.c_ulonglong),
        ("m_endTs",       ct.c_ulonglong),
        ("m_tgid",        ct.c_uint),
        ("m_pid",         ct.c_uint),
        ("m_stackId",     ct.c_int),
        ("m_fid",         ct.c_uint),
        ("m_address",     ct.c_ulonglong),   # address of memory allocation
        ("m_size",        ct.c_ulonglong)]   # no of bytes

class PthreadRecord(ct.Structure):
    _fields_ = [
        ("m_startTs",     ct.c_ulonglong),
        ("m_endTs",       ct.c_ulonglong),
        ("m_tgid",        ct.c_uint),
        ("m_pid",         ct.c_uint),
        ("m_pthreadId",   ct.c_ulonglong),
        ("m_stackId",     ct.c_int),
        ("m_fid",         ct.c_uint),
        ("m_address",     ct.c_ulonglong),    # lock address
        ("m_status",      ct.c_ushort),       # lock status
        ("m_lockType",    ct.c_ushort)]       # lock type (mutex/CV)

class IoTraceRecord(ct.Structure):
    _fields_ = [
        ("m_startTs",     ct.c_ulonglong),
        ("m_endTs",       ct.c_ulonglong),
        ("m_tgid",        ct.c_uint),
        ("m_pid",         ct.c_uint),
        ("m_stackId",     ct.c_int),
        ("m_fid",         ct.c_uint),
        ("m_size",        ct.c_ulonglong), # read/write size
        ("m_ioType",      ct.c_ushort),    # read/write
        ("m_fd",          ct.c_int)]       # file descriptor

class OpenSysCallRecord(ct.Structure):
    _fields_ = [
        ("m_startTs",     ct.c_ulonglong),
        ("m_endTs",       ct.c_ulonglong),
        ("m_tgid",        ct.c_uint),
        ("m_pid",         ct.c_uint),
        ("m_fd",          ct.c_int),               # file descriptor
        ("m_fname",       ct.c_char * FILE_NAME_LENGTH)]   # file name

class MmapSysCallRecord(ct.Structure):
    _fields_ = [
        ("m_startTs",     ct.c_ulonglong),
        ("m_start",       ct.c_ulonglong),
        ("m_len",         ct.c_ulonglong),
        ("m_tgid",        ct.c_uint),
        ("m_pid",         ct.c_uint),
        ("m_fd",          ct.c_int)]    # file descriptor

#indicates the bunch of records submitted to perf buffer.
#used to typecast the data to get from perf buffer.
class SchedData(ct.Structure):
    _fields_ = [
        ("m_dataType",    ct.c_uint),
        ("m_evtData",     SchedRecord * g_nRecords)]

class CpuIdleData(ct.Structure):
    _fields_ = [
        ("m_dataType",    ct.c_uint),
        ("m_evtData",     CpuIdleRecord * g_nRecords)]

class CpuFreqData(ct.Structure):
    _fields_ = [
        ("m_dataType",    ct.c_uint),
        ("m_evtData",     CpuFreqRecord * g_nRecords)]

class BlockIoData(ct.Structure):
    _fields_ = [
        ("m_dataType",    ct.c_uint),
        ("m_evtData",     BlockIoRecord * g_nRecords)]

class SysCallData(ct.Structure):
    _fields_ = [
        ("m_dataType",    ct.c_uint),
        ("m_evtData",     SysCallRecord * g_nRecords)]

class FuncCountData(ct.Structure):
    _fields_ = [
        ("m_dataType",    ct.c_uint),
        ("m_evtData",     FuncCountRecord * g_nRecords)]

class PageFaultData(ct.Structure):
    _fields_ = [
        ("m_dataType",    ct.c_uint),
        ("m_evtData",     PageFaultRecord * g_nRecords)]

class LibTraceData(ct.Structure):
    _fields_ = [
        ("m_dataType",    ct.c_uint),
        ("m_evtData",     LibTraceRecord * g_nRecords)]

class MemTraceData(ct.Structure):
    _fields_ = [
        ("m_dataType",    ct.c_uint),
        ("m_evtData",     MemTraceRecord * g_nRecords)]

class PthreadData(ct.Structure):
    _fields_ = [
        ("m_dataType",    ct.c_uint),
        ("m_evtData",     PthreadRecord * g_nRecords)]

class IoTraceData(ct.Structure):
    _fields_ = [
        ("m_dataType",    ct.c_uint),
        ("m_evtData",     IoTraceRecord * g_nRecords)]

class OpenSysCallData(ct.Structure):
    _fields_ = [
        ("m_dataType",    ct.c_uint),
        ("m_evtData",     OpenSysCallRecord * g_nRecords)]

class MmapSysCallData(ct.Structure):
    _fields_ = [
        ("m_dataType",    ct.c_uint),
        ("m_evtData",     MmapSysCallRecord * g_nRecords)]

g_pthreadFunctions = {
    AMDTOsTraceFunctions.AMDT_PTHREAD_CREATE.value          : "pthread_create",
    AMDTOsTraceFunctions.AMDT_PTHREAD_EXIT.value            : "pthread_exit",
    AMDTOsTraceFunctions.AMDT_PTHREAD_MUTEX_LOCK.value      : "pthread_mutex_lock",
    AMDTOsTraceFunctions.AMDT_PTHREAD_MUTEX_TRYLOCK.value   : "pthread_mutex_trylock",
    AMDTOsTraceFunctions.AMDT_PTHREAD_MUTEX_TIMEDLOCK.value : "pthread_mutex_timedlock",
    AMDTOsTraceFunctions.AMDT_PTHREAD_MUTEX_UNLOCK.value    : "pthread_mutex_unlock",
    AMDTOsTraceFunctions.AMDT_PTHREAD_COND_WAIT.value       : "pthread_cond_wait",
    AMDTOsTraceFunctions.AMDT_PTHREAD_COND_TIMEDWAIT.value  : "pthread_cond_timedwait",
    AMDTOsTraceFunctions.AMDT_PTHREAD_COND_SIGNAL.value     : "pthread_cond_signal",
    AMDTOsTraceFunctions.AMDT_PTHREAD_COND_BROADCAST.value  : "pthread_cond_broadcast",
    AMDTOsTraceFunctions.AMDT_PTHREAD_JOIN.value            : "pthread_join",
}

g_memTraceFunctions = {
    AMDTOsTraceFunctions.AMDT_MALLOC.value      : "malloc",
    AMDTOsTraceFunctions.AMDT_CALLOC.value      : "calloc",
    AMDTOsTraceFunctions.AMDT_REALLOC.value     : "realloc",
    AMDTOsTraceFunctions.AMDT_FREE.value        : "free",
}

g_ioTraceFunctions = {
    AMDTOsTraceFunctions.AMDT_READ.value        : "read",
    AMDTOsTraceFunctions.AMDT_WRITE.value       : "write",
    AMDTOsTraceFunctions.AMDT_PREAD.value       : "pread",
    AMDTOsTraceFunctions.AMDT_PWRITE.value      : "pwrite",
    AMDTOsTraceFunctions.AMDT_AIO_READ.value    : "aio_read",
    AMDTOsTraceFunctions.AMDT_AIO_WRITE.value   : "aio_write",
    AMDTOsTraceFunctions.AMDT_IO_SUBMIT.value   : "io_submit",
}

#class for libTrace and FuncCount.
#used to generate the code from template
#Pattern format is library:function
class CodeFromTemplate(object):
    def __init__(self, evtType):
        self.m_code = ""          # code
        self.m_userFunctionsDict = {} # User lib functions Dict where key is function id and value is function name
        self.m_kernelFunctionsDict = {} # Kernel functions Dict where key is function id and value is function name
        self.m_userFunctionsAddressDict = {} # User lib functions Dict where key is the function id and value is the address
        self.m_excludeUserFuncs = set()
        self.m_excludeKernelFuncs = set()
        self.m_functionCount = 0  # No of functions
        self.m_funcToLibrary = {} # function to library map
        self.m_evtType = evtType  # type of the event.
        self.m_probeExistFuncs = {}   # List of functions which already have user probe
        self.m_configuredFids = []    # Configured functions by user.
        self.m_addresses, self.m_functions = (set(), set())  # set for functions and addresses.

    #Separate the library and functions from pattern.
    def GetLibPathAndFuncPattern(self, pattern):
        if pattern is None:
            raise Exception(" pattern is None")

        pattern = pattern.encode()
        parts = pattern.split(b'=')

        if parts is not None:
            (library, funcPattern) = parts
            patternLen = len(funcPattern)

            # if pattern ends with *, then replace * with .*
            if funcPattern.endswith(b'*'):
                funcPattern = funcPattern.replace(b'*', b'.*')

                # append .* at begining if len is more than 1
                if patternLen > 1:
                    funcPattern = b'.*' + funcPattern
            # pattern doesn't ends with *
            else:
                funcPattern = b'.*' + funcPattern + b'.*'

            funcPattern = funcPattern.replace(b'::', b'.*')
            libPath = library

            if library.lower() != g_kernel:
                try:
                    libPath = BPF.find_library(library)
                except:
                    raise Exception("Unable to find the library path %s" %library)

                #Then it may be executable.
                if libPath is None:
                    try:
                        libPath = BPF.find_exe(library)
                    except:
                        raise Exception("Unable to find the executable %s" %library)

                if libPath is None or len(libPath) == 0:
                    raise Exception("unable to find library %s" % library)

            return (libPath, funcPattern)

    #get the functions from library which suites the function pattern
    def GetUserFunctionsAndAddresses(self, library, pattern):
        if library is None:
            raise Exception("please provide the library")
        if pattern is None:
            raise Exception("please provide the pattern")

        try:
            return BPF.get_user_functions_and_addresses(library, pattern)
        except:
            raise Exception("Unable to find the functions and addresses in %s" %library)

    #get code for a function
    def AddFunction(self, funcName, template, isKernel, address = None):
        newFunc = ""
        text = ""

        if self.m_evtType == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_LIBTRACE.value:
            newFunc = "library_trace_%d" % (self.m_functionCount + AMDT_LIBTRACE_FUNCTION_START)
            text = template.replace("AMDT_PROBE_FUNCTION", newFunc)
            text = text.replace("AMDT_FID", "%d" % (self.m_functionCount + AMDT_LIBTRACE_FUNCTION_START))
        elif self.m_evtType == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_FUNCCOUNT.value:
            funcCountHandler = "trace_funccount_%d" % (self.m_functionCount + AMDTOsTraceFunctions.AMDT_FUNCCOUNT_FUNCTION_START.value)
            retFuncCountHandler = "trace_funccount_%d_ret" % (self.m_functionCount + AMDTOsTraceFunctions.AMDT_FUNCCOUNT_FUNCTION_START.value)
            text = template.replace("AMDT_PROBE_FUNCTION_RET", retFuncCountHandler)
            text = text.replace("AMDT_PROBE_FUNCTION", funcCountHandler)
            text = text.replace("AMDT_FID", "%d" % (self.m_functionCount + AMDTOsTraceFunctions.AMDT_FUNCCOUNT_FUNCTION_START.value))

        self.m_configuredFids.append(self.m_functionCount + AMDTOsTraceFunctions.AMDT_FUNCCOUNT_FUNCTION_START.value)

        if isKernel is True:
            self.m_kernelFunctionsDict[self.m_functionCount] = funcName
        else:
            self.m_userFunctionsDict[self.m_functionCount] = funcName

            if address is not None:
                self.m_userFunctionsAddressDict[self.m_functionCount] = address

        self.m_functionCount += 1

        return text

    #generate the code from template.
    def GenerateCodeFromTemplate(self, pattern):
        template = ""

        if self.m_evtType == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_LIBTRACE.value:
            template = g_bpfLibTraceCode
        elif self.m_evtType == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_FUNCCOUNT.value:
            template = g_bpfFuncCountCode

        # pattern will be like lib=funcPattern
        # separate the library and funcPattern
        (libPath, funcPattern) = self.GetLibPathAndFuncPattern(pattern)

        if libPath.lower() != g_kernel:
            functionsAndAddresses = self.GetUserFunctionsAndAddresses(libPath, funcPattern)
            funcCount = len(self.m_probeExistFuncs)

            # get the functions and addresses, add this to respective set.
            # so that duplicate probes will be removed.
            for funcId, funcName in self.m_probeExistFuncs.items():
                funcName = funcName.encode()
                funcName = b'^' + funcName + b'$'
                funcs = BPF.get_user_functions(libPath, funcName)
                addrs = BPF.get_user_addresses(libPath, funcName)

                for func in funcs:
                    self.m_functions.add(func)
                for addr in addrs:
                    self.m_addresses.add(addr)

            for function, address in functionsAndAddresses:
                for funcId, funcName in self.m_probeExistFuncs.items():
                    if funcName == function:
                        self.m_configuredFids.append(funcId)

                if address in self.m_addresses or function in self.m_functions or function in self.m_excludeUserFuncs:
                    continue

                self.m_addresses.add(address)
                self.m_functions.add(function)
                funcCount += 1

                if funcCount > AMDT_PROBE_LIMIT:
                    print("WARNING : Max number of uprobes supported is 1000")
                    break

                self.m_code += self.AddFunction(function, template, False, address)  # append to the code
                self.m_funcToLibrary[function] = libPath   #update function to library dict.
        else:
            kernelFunctions = BPF.get_kprobe_functions(funcPattern)
            funcCount = 0

            for funcName in kernelFunctions:
                if funcName in self.m_excludeKernelFuncs:
                    continue

                funcCount += 1

                if funcCount > AMDT_PROBE_LIMIT:
                    print("WARNING : Max number of kprobes supported is 1000")
                    break

                self.m_code += self.AddFunction(funcName, template, True)  # append to the code
                self.m_funcToLibrary[funcName] = libPath   #update function to library dict.

    def UpdateExcludeFuncs(self, pattern):
        # pattern will be like lib=funcPattern
        # separate the library and funcPattern
        (libPath, funcPattern) = self.GetLibPathAndFuncPattern(pattern)

        if libPath.lower() != g_kernel:
            userFunctions = BPF.get_user_functions(libPath, funcPattern)

            for funcName in userFunctions:
                self.m_excludeUserFuncs.add(funcName)
        else:
            kernelFunctions = BPF.get_kprobe_functions(funcPattern)

            for funcName in kernelFunctions:
                self.m_excludeKernelFuncs.add(funcName)

    def GetUserFunctions(self):
        return self.m_userFunctionsDict

    def GetUserFunctionAddress(self):
        return self.m_userFunctionsAddressDict

    def GetKernelFunctions(self):
        return self.m_kernelFunctionsDict

    def GetFuncToLibrary(self):
        return self.m_funcToLibrary

    def GetCode(self):
        return self.m_code

    def GetFunctionCount(self):
        return self.m_functionCount

    def SetProbeExistFuncs(self, probeExistFuncs):
        self.m_probeExistFuncs = probeExistFuncs

    def GetFunctionIds(self):
        return self.m_configuredFids

class BpfCode(object):
    def __init__(self):
        #bpf header dict
        self.m_headerDict = {
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_SCHEDULE.value: g_bpfSchedHeader,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_CPUIDLE.value: g_bpfCpuIdleHeader,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_CPUFREQ.value: g_bpfCpuFreqHeader,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_DISKIO.value: g_bpfBlockIoHeader,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_SYSCALL.value: g_bpfSysCallHeader,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_PAGEFAULT.value: g_bpfPageFaultHeader,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_MEMTRACE.value: g_bpfMemTraceHeader,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_LIBTRACE.value: g_bpfLibTraceHeader,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_FUNCCOUNT.value: g_bpfFuncCountHeader,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_PTHREAD.value: g_bpfPthreadHeader,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_IOTRACE.value: g_bpfIoTraceHeader,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_OPEN_SYSCALL.value: g_bpfOpenSysCallHeader,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_MMAP_SYSCALL.value: g_bpfMmapSysCallHeader,
        }
        #bpf source dict
        self.m_codeDict = {
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_SCHEDULE.value: g_bpfSchedCode,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_CPUIDLE.value: g_bpfCpuIdleCode,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_CPUFREQ.value: g_bpfCpuFreqCode,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_DISKIO.value: g_bpfBlockIoCode,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_SYSCALL.value: g_bpfSysCallCode,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_PAGEFAULT.value: g_bpfPageFaultCode,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_MEMTRACE.value: g_bpfMemTraceCode,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_LIBTRACE.value: g_bpfLibTraceCode,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_FUNCCOUNT.value: g_bpfFuncCountCode,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_PTHREAD.value: g_bpfPthreadCode,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_IOTRACE.value: g_bpfIoTraceCode,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_OPEN_SYSCALL.value: g_bpfOpenSysCallCode,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_MMAP_SYSCALL.value: g_bpfMmapSysCallCode,
        }

    def updateCode(self, evtType, code):
        self.m_codeDict[evtType] = code

    def updateHeader(self, evtType, hdr):
        self.m_headerDict[evtType] = hdr

    def getKernelCode(self, events):

        self.m_bpfSource = g_bpfCommonHeader

        if events is not None and len(events) != 0:
            for event in events:
                self.m_bpfSource += self.m_headerDict[event]

        self.m_bpfSource += g_bpfCommonCode

        if events is not None:
            for event in events:
                self.m_bpfSource += self.m_codeDict[event]

        return self.m_bpfSource

class BpfTrace(object):
    def __init__(self):
        parser = argparse.ArgumentParser()
        parser.add_argument('-e', '--events', type=int, nargs ='+', help='trace event groups')
        parser.add_argument('-p', '--pids', type=int, nargs ='+', help='trace pids')
        parser.add_argument('-c', '--cpus', type=int, nargs ='+', help='trace cores')
        parser.add_argument('-i', '--idle', action='store_true', help='trace idle process for sched_switch event')
        parser.add_argument('-l', '--libtrace', type=str, nargs = '+', help='get the user space call stack for functions in library/Executable')
        parser.add_argument('-f', '--funccount', type=str, nargs = '+', help='count the function calls for functions in library/Executable')
        parser.add_argument('-m',  '--maxthreads', type=int, help='Max Threads supported')
        parser.add_argument('-xf', '--excludefunc', type=str, nargs = '+', help='exclude these functions from founc count')
        parser.add_argument('-IT', '--iotracethreshold', type=int, help='IO trace threshold(bytes), Trace I/O calls which are taking more than or equal to the time provided')
        parser.add_argument('-CT', '--cpuidlethreshold', type=int, help='cpu idle threshold(usec), Trace Cpu idle when core is idle for more than or equal to provided nsec')
        parser.add_argument('-MT', '--memsizethreshold', type=int, help='Memory allocation threshold(bytes), trace memory allocations more than or equal to the provided size')
        parser.add_argument('-ST', '--syscallthreshold', type=int, help='syscall threshold(usec). Trace syscalls which are taking more than or equal to the time provided')
        parser.add_argument('-FT', '--funccountthreshold', type=int, help='function count threshold(usec). Trace functions which are taking more than or equal to the time provided')
        parser.add_argument('-PT', '--pthreadthreshold', type=int, help='pthread threshold(usec). Trace locks which are taking more than or equal to the time provided')
        parser.add_argument('-IC', '--iotracecallstack', action='store_true', help='IO Trace Call Stack collection')
        parser.add_argument('-MC', '--memtracecallstack', action='store_true', help='Mem Trace Call Stack collection')
        parser.add_argument('-PC', '--pthreadcallstack', action='store_true', help='Pthread Trace Call Stack collection')
        parser.add_argument('-LC', '--libtracecallstack', action='store_true', help='Lib Trace Call Stack Collection')
        parser.add_argument('-N', '--noofcpus', type=int, help='no of cpus on the system')
        parser.add_argument('-B', '--buffersize', type=int, help='per core perf buffer size in pages')
        parser.add_argument('-G', '--groupsize', type=int, help='group of events sent to user space')
        parser.add_argument('-C', '--callstacksize', type = int, help='No of call stack entries')
        parser.add_argument('-O', '--outputdir', type=str, help='Directory to store the output files')
        parser.add_argument('-RF', '--readfifo', type=str, help='Read FIFO Path')
        parser.add_argument('-WF', '--writefifo', type=str, help='Write FIFO Path')
        parser.add_argument('-S', '--sysCallPath', type=str, help='Syscalls to be traced as json file')
        self.m_args = parser.parse_args()
        global g_wrFifoPath
        global g_rdFifoPath

        if self.m_args.noofcpus is None:
            raise Exception("Please provide the no of cpus with -N option")

        if self.m_args.outputdir is None:
            raise Exception("Please provide the output directory to store the output files with -O option")

        if self.m_args.events is None:
            self.m_args.events = []

        if self.m_args.libtrace is not None:
            self.m_args.events.append(AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_LIBTRACE.value)

        if self.m_args.funccount is not None and self.m_args.events.count(AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_FUNCCOUNT.value) == 0:
            self.m_args.events.append(AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_FUNCCOUNT.value)

        if len(self.m_args.events) == 0:
            raise Exception("No events are configured")

        self.m_stopTracing = False
        self.m_startTracing = False
        self.m_csvFile = {}
        self.m_csvWriter = {}
        self.m_lostCount = 0
        self.m_coreList = []
        self.m_swp = False
        g_wrFifoPath = self.m_args.writefifo
        g_rdFifoPath = self.m_args.readfifo
        self.m_probeExistFuncs = {}
        self.m_libTraceCode = None
        self.m_funcCountCode = None
        self.m_funcCountFids = []
        self.m_funcIdToRVA = {}

        self.m_fileNames = {
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_SCHEDULE.value: "schedule/trace",
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_CPUIDLE.value: "cpuidle/trace",
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_CPUFREQ.value: "cpufreq/trace",
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_DISKIO.value: "diskio/trace",
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_SYSCALL.value: "syscall/trace",
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_PAGEFAULT.value: "pagefault/trace",
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_LIBTRACE.value: "libtrace/trace",
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_MEMTRACE.value: "memtrace/trace",
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_FUNCCOUNT.value: "funccount/trace",
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_PTHREAD.value: "pthread/trace",
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_IOTRACE.value: "iotrace/trace",
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_OPEN_SYSCALL.value: "opensyscall/trace",
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_MMAP_SYSCALL.value: "mmapsyscall/trace",
        }

        self.m_fileHeader = {
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_SCHEDULE.value: ["Core", "StartTs", "EndTs", "Pid", "Tid", "State", "Pre-empted"],
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_CPUIDLE.value: ["Core", "StartTs", "EndTs", "C-State"],
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_CPUFREQ.value: None,
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_DISKIO.value: ["InsertTs", "IssueTs", "CompleteTs", "Pid", "Tid", "Size", "Major", "Minor", "Operation"],
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_SYSCALL.value: ["StartTs", "EndTs", "Pid", "Tid", "Sid"],
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_PAGEFAULT.value: ["StartTs", "Pid", "Tid", "Data Address", "Ip", "ErrCode", "IsKernel"],
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_LIBTRACE.value: ["StartTs", "Pid", "Tid", "stackId", "Fid"],
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_MEMTRACE.value: ["StartTs", "EndTs", "Pid", "Tid", "stackId", "Fid", "address", "size"],
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_FUNCCOUNT.value: ["StartTs", "EndTs", "Pid", "Tid", "Fid"],
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_PTHREAD.value: ["StartTs", "EndTs", "Pid", "Tid", "PthreadId", "stackId", "Fid", "address", "status", "lockType"],
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_IOTRACE.value: ["StartTs", "EndTs", "Pid", "Tid", "stackId", "Fid", "size", "rw", "fd"],
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_OPEN_SYSCALL.value: ["StartTs", "EndTs", "Pid", "Tid", "Fd", "FileName"],
            AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_MMAP_SYSCALL.value: ["StartTs", "Pid", "Tid", "Fd", "Start", "Length"],
        }

        for event in self.m_args.events:
            if event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_MEMTRACE.value:
                self.m_probeExistFuncs.update(g_memTraceFunctions)
            elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_IOTRACE.value:
                self.m_probeExistFuncs.update(g_ioTraceFunctions)
            elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_PTHREAD.value:
                self.m_probeExistFuncs.update(g_pthreadFunctions)

    def constructKernelCode(self):
        global g_bpfCommonHeader
        global g_nRecords
        global g_nCallStacks
        global g_bufferSize
        self.m_code = BpfCode()

        if self.m_code is None:
            raise Exception("BpfCode is None")

        if self.m_args.pids is None:
            self.m_swp = True

        if self.m_args.libtrace is not None:
            self.m_libTraceCode = CodeFromTemplate(AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_LIBTRACE.value)
            for pattern in self.m_args.libtrace:
                self.m_libTraceCode.GenerateCodeFromTemplate(pattern)
            self.m_code.updateCode(AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_LIBTRACE.value, self.m_libTraceCode.GetCode())

        if self.m_args.funccount is not None:
            global g_bpfFuncCountHeader
            self.m_funcCountCode = CodeFromTemplate(AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_FUNCCOUNT.value)
            self.m_funcCountCode.SetProbeExistFuncs(self.m_probeExistFuncs)

            if self.m_args.excludefunc is not None:
                for pattern in self.m_args.excludefunc:
                    self.m_funcCountCode.UpdateExcludeFuncs(pattern)

            for pattern in self.m_args.funccount:
                self.m_funcCountCode.GenerateCodeFromTemplate(pattern)

            self.m_code.updateCode(AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_FUNCCOUNT.value, self.m_funcCountCode.GetCode())
            g_bpfFuncCountHeader = g_bpfFuncCountHeader.replace("AMDT_NUM_FUNCTIONS", "%d" % (self.m_funcCountCode.GetFunctionCount() + AMDTOsTraceFunctions.AMDT_FUNCCOUNT_FUNCTION_START.value))
            self.m_code.updateHeader(AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_FUNCCOUNT.value, g_bpfFuncCountHeader)
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_FUNCTION_COUNT", "#define AMDT_FUNCTION_COUNT 1")
            self.m_funcCountFids = self.m_funcCountCode.GetFunctionIds()
        else:
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_FUNCTION_COUNT", "")

        if self.m_args.pids is not None:
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_PROCESS_FILTER", "#define AMDT_PROCESS_FILTER 1")
        else:
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_PROCESS_FILTER", "")

        if self.m_args.cpus is not None:
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_CORE_FILTER", "#define AMDT_CORE_FILTER 1")
        else:
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_CORE_FILTER", "")

        #if self.m_args.idle is not None and self.m_args.idle is False:
        #    g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_IDLE_PROCESS_FILTER", "#define AMDT_IDLE_PROCESS_FILTER 1")
        #else:
        #    g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_IDLE_PROCESS_FILTER", "")

        if self.m_args.maxthreads is not None:
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_MAX_THREADS", "#define AMDT_MAX_THREADS %d" %self.m_args.maxthreads)
        else:
            if self.m_args.pids is not None:
                g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_MAX_THREADS", "#define AMDT_MAX_THREADS %d" %AMDT_MAX_THREADS_APP)
            else:
                g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_MAX_THREADS", "#define AMDT_MAX_THREADS %d" %AMDT_MAX_THREADS_SWP)

        if self.m_args.memsizethreshold is not None:
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_MEMSIZE_THRESHOLD", "#define AMDT_MEMSIZE_THRESHOLD %d" %self.m_args.memsizethreshold)
        else:
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_MEMSIZE_THRESHOLD", "#define AMDT_MEMSIZE_THRESHOLD %d" %AMDT_MEMSIZE_DEFAULT_THRESHOLD)

        if self.m_args.syscallthreshold is not None:
            #convert usec to nsec and pass it to the BPF.
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_SYSCALL_THRESHOLD", "#define AMDT_SYSCALL_THRESHOLD %d" %(self.m_args.syscallthreshold * 1000))
        else:
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_SYSCALL_THRESHOLD", "#define AMDT_SYSCALL_THRESHOLD %d" %AMDT_SYSCALL_DEFAULT_THRESHOLD)

        if self.m_args.funccountthreshold is not None:
            #convert usec to nsec and pass it to the BPF.
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_FUNCCOUNT_THRESHOLD", "#define AMDT_FUNCCOUNT_THRESHOLD %d" %(self.m_args.funccountthreshold * 1000))
        else:
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_FUNCCOUNT_THRESHOLD", "#define AMDT_FUNCCOUNT_THRESHOLD %d" %AMDT_FUNCCOUNT_DEFAULT_THRESHOLD)

        if self.m_args.pthreadthreshold is not None:
            #convert usec to nsec and pass it to the BPF.
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_PTHREAD_THRESHOLD", "#define AMDT_PTHREAD_THRESHOLD %d" %(self.m_args.pthreadthreshold * 1000))
        else:
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_PTHREAD_THRESHOLD", "#define AMDT_PTHREAD_THRESHOLD %d" %AMDT_PTHREAD_DEFAULT_THRESHOLD)

        if self.m_args.cpuidlethreshold is not None:
            #convert usec to nsec and pass it to the BPF.
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_CPUIDLE_THRESHOLD", "#define AMDT_CPUIDLE_THRESHOLD %d" %(self.m_args.cpuidlethreshold * 1000))
        else:
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_CPUIDLE_THRESHOLD", "#define AMDT_CPUIDLE_THRESHOLD %d" %AMDT_CPUIDLE_DEFAULT_THRESHOLD)

        if self.m_args.iotracethreshold is not None:
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_IOTRACE_THRESHOLD", "#define AMDT_IOTRACE_THRESHOLD %d" %self.m_args.iotracethreshold)
        else:
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_IOTRACE_THRESHOLD", "#define AMDT_IOTRACE_THRESHOLD %d" %AMDT_IOTRACE_DEFAULT_THRESHOLD)

        if self.m_args.libtracecallstack is not None and self.m_args.libtracecallstack is True:
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_LIBTRACE_CALLSTACK_COLLECT", "#define AMDT_LIBTRACE_CALLSTACK_COLLECT 1")
        else:
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_LIBTRACE_CALLSTACK_COLLECT", "")

        if self.m_args.memtracecallstack is not None and self.m_args.memtracecallstack is True:
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_MEMTRACE_CALLSTACK_COLLECT", "#define AMDT_MEMTRACE_CALLSTACK_COLLECT 1")
        else:
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_MEMTRACE_CALLSTACK_COLLECT", "")

        if self.m_args.iotracecallstack is not None and self.m_args.iotracecallstack is True:
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_IOTRACE_CALLSTACK_COLLECT", "#define AMDT_IOTRACE_CALLSTACK_COLLECT 1")
        else:
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_IOTRACE_CALLSTACK_COLLECT", "")

        if self.m_args.pthreadcallstack is not None and self.m_args.pthreadcallstack is True:
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_PTHREAD_CALLSTACK_COLLECT", "#define AMDT_PTHREAD_CALLSTACK_COLLECT 1")
        else:
            g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_PTHREAD_CALLSTACK_COLLECT", "")

        if self.m_args.buffersize is not None:
            g_bufferSize = self.m_args.buffersize

        if self.m_args.groupsize is not None:
            g_nRecords = self.m_args.groupsize

        if self.m_args.callstacksize is not None:
            g_nCallStacks = self.m_args.callstacksize

        g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_DATA_GROUP_SIZE", "#define AMDT_DATA_GROUP_SIZE %d" %g_nRecords)
        g_bpfCommonHeader = g_bpfCommonHeader.replace("DEFINE_AMDT_CALLSTACK_SIZE", "#define AMDT_CALLSTACK_SIZE %d" %g_nCallStacks)

        self.m_bpfSource = self.m_code.getKernelCode(self.m_args.events)

    #create and open the output files
    def createOutputFiles(self):
        for event in self.m_args.events:
            filePath = self.m_args.outputdir + self.m_fileNames[event] + "_" + str(os.getpid()) + ".csv"
            csvFileObject = open(filePath, "a")
            csvWriterObject = csv.writer(csvFileObject, lineterminator='\n')
            self.m_csvFile[event] = csvFileObject
            self.m_csvWriter[event] = csvWriterObject
            if self.m_fileHeader[event] is not None:
                csvWriterObject.writerow(self.m_fileHeader[event])

    #close the opened output files
    def closeOutputFiles(self):
        for key, val in self.m_csvFile.items():
            val.close()

    #write mem leaks into file when profile stopped.
    def writeMemLeaks(self):
        filePath = self.m_args.outputdir + "memtrace/memleaks_" + str(os.getpid()) + ".csv"
        csvFileObject = open(filePath, "a")
        writer = csv.writer(csvFileObject, lineterminator='\n')
        writer.writerow(["Pid", "Tid", "Address"])
        memAllocs = self.m_bpfObj["g_memAllocs"]

        for k, v in memAllocs.items():
            writer.writerow([v.m_tgid, v.m_pid, v.m_address])

        csvFileObject.close()

    #write system calls count and elapsed time to file when profile stopped
    def writeSysCallStats(self):
        filePath = self.m_args.outputdir + "syscall/syscallstats_" + str(os.getpid()) + ".csv"
        csvFileObject = open(filePath, "a")
        writer = csv.writer(csvFileObject, lineterminator='\n')
        #writer.writerow(["Pid", "tid", "SysId", "Count", "TotalElapsedTime", "MinElapsedTime", "MaxElapsedTime"])
        writer.writerow(["SysId", "Count", "TotalElapsedTime", "MinElapsedTime", "MaxElapsedTime"])
        sysCallStats = self.m_bpfObj["g_sysCallStats"]

        for key, value in sysCallStats.items():
            writer.writerow([key.value, value.m_count, value.m_totalElapsedTime, value.m_minElapsedTime, value.m_maxElapsedTime])

        csvFileObject.close()

    #write function calls count and elapsed time to file when profile stopped
    def writeFuncCountStats(self):
        filePath = self.m_args.outputdir + "funccount/funccountstats_" + str(os.getpid()) + ".csv"
        csvFileObject = open(filePath, "a")
        writer = csv.writer(csvFileObject, lineterminator='\n')
        writer.writerow(["Fid", "Count", "TotalElapsedTime", "MinElapsedTime", "MaxElapsedTime"])
        funcCountStats = self.m_bpfObj["g_funcCountStats"]

        for key, value in funcCountStats.items():
            writer.writerow([key.value, value.m_count, value.m_totalElapsedTime, value.m_minElapsedTime, value.m_maxElapsedTime])

        csvFileObject.close()

    def writePageFaultStats(self):
        filePath = self.m_args.outputdir + "pagefault/pagefaultstats_" + str(os.getpid()) + ".csv"
        csvFileObject = open(filePath, "a")
        writer = csv.writer(csvFileObject, lineterminator='\n')
        writer.writerow(["PTID", "User PF Count", "Kernel PF Count"])
        pageFaultStats = self.m_bpfObj["g_pageFaultStats"]

        for k, v in pageFaultStats.items():
            writer.writerow([(k.value)>>32, (k.value)&0x00FFFFFFFF, v.m_userCount, v.m_kernelCount])

        csvFileObject.close()

    #write callstacks to file when profile stopped
    def writeCallStacks(self, stackTraces, stackTable, fileName):
        filePath = self.m_args.outputdir + fileName
        csvFileObject = open(filePath, "a")
        writer = csv.writer(csvFileObject, lineterminator='\n')
        writer.writerow(["Stack Id", "Pid", "Tid", "CallStack"])
        for stackId, tgid in stackTable.items():
            row = [stackId.value, (tgid.value)>>32, (tgid.value)&0x00FFFFFFFF]
            for addr in reversed(list(stackTraces.walk(stackId.value))):
                row.append(addr)
            writer.writerow(row)

        csvFileObject.close()

    #write Function names and IDs to file when profile stopped
    def writeFuncNames(self, functions, start):
        isAppend = False
        filePath = self.m_args.outputdir + "metadata/functions_" + str(os.getpid()) + ".csv"

        if os.path.exists(filePath):
            csvFileObject = open(filePath, "a")
            isAppend = True
        else:
            csvFileObject = open(filePath, "w")

        writer = csv.writer(csvFileObject, lineterminator='\n')
        if isAppend is False:
            writer.writerow(["function Id", "function Name", "RVA"])

        for funcId, funcName in functions.items():
            fid = funcId + start
            rva = 0

            if fid in self.m_funcIdToRVA.keys():
                rva = self.m_funcIdToRVA[fid]

            if type(funcName) == str:
                writer.writerow([fid, funcName, rva])
            else:
                writer.writerow([fid, funcName.decode(), rva])

        csvFileObject.close()

    def writeMetaData(self):
        #write the skipped events count due to threshold
        skippedEvents = self.m_bpfObj["g_skippedEvents"]
        filePath = self.m_args.outputdir + "metadata/event_" + str(os.getpid()) + ".csv"
        csvFileObject = open(filePath, "a")
        writer = csv.writer(csvFileObject, lineterminator='\n')
        writer.writerow(["eventId", "threshold", "skipCount"])

        for event in self.m_args.events:
            if event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_CPUIDLE.value:
                writer.writerow([event, self.m_args.cpuidlethreshold, skippedEvents[event].value])
            elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_SYSCALL.value:
                writer.writerow([event, self.m_args.syscallthreshold, skippedEvents[event].value])
            elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_MEMTRACE.value:
                writer.writerow([event, self.m_args.memsizethreshold, skippedEvents[event].value])
            elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_IOTRACE.value:
                writer.writerow([event, self.m_args.iotracethreshold, skippedEvents[event].value])
            elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_PTHREAD.value:
                writer.writerow([event, self.m_args.pthreadthreshold, skippedEvents[event].value])
            elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_FUNCCOUNT.value:
                writer.writerow([event, self.m_args.funccountthreshold, skippedEvents[event].value])
            else:
                writer.writerow([event, 0, 0])

        csvFileObject.close()

        filePath = self.m_args.outputdir + "metadata/metadata_" + str(os.getpid()) + ".csv"
        csvFileObject = open(filePath, "a")
        writer = csv.writer(csvFileObject, lineterminator='\n')
        writer.writerow(["key", "value"])
        #write Lost event count due to buffer overflow.
        writer.writerow(["LOSTCOUNT", str(self.m_lostCount)])
        #write perf buffer size in pages for each core
        writer.writerow(["BUFFERSIZE", str(g_bufferSize)])
        #write no of records transferred to user space from kernel at a time through perf buffer
        writer.writerow(["GROUPSIZE", str(g_nRecords)])
        #write no of unique call stack entries configured
        writer.writerow(["CALLSTACKSIZE", str(g_nCallStacks)])

        csvFileObject.close()

    def writeProcInfo(self):
        procInfo = self.m_bpfObj["g_procInfo"]
        filePath = self.m_args.outputdir + "metadata/procinfo_" + str(os.getpid()) + ".csv"
        csvFileObject = open(filePath, "a")
        writer = csv.writer(csvFileObject, lineterminator='\n')

        for k,v in procInfo.items():
            writer.writerow([k.value, v.m_ppid, v.m_tgid, v.m_comm.decode('UTF-8')])

        csvFileObject.close()

    # get records which are not submitted to perf buffer
    def writeRemainingRecords(self):
        if self.m_args.events is not None:
            for event in self.m_args.events:
                writer = self.m_csvWriter[event]
                if event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_SCHEDULE.value:
                    for core in self.m_coreList:
                        data = self.m_bpfObj["g_schedData"][0][core]
                        index = self.m_bpfObj["g_schedIndex"][0][core]
                        if index != 0:
                            for i in range(index):
                                rec = data.m_evtData[i]
                                writer.writerow([core, rec.m_startTs, rec.m_endTs, rec.m_tgid, rec.m_pid, rec.m_state, int(rec.m_voluntarySw)])

                    #get records which doesn't have completed next sched switch
                    schedTable = self.m_bpfObj["g_prevSchedSwitch"]
                    for k,v in schedTable.items():
                        writer.writerow([v.m_core, v.m_startTs, AMDT_UNKNOWN_TIMESTAMP, AMDT_UNKNOWN_TGID, k.value, v.m_state, AMDT_FALSE])

                    #schedTable = self.m_bpfObj["g_prevIdleSchedSwitch"]
                    #for k,v in schedTable.items():
                    #    writer.writerow([v.m_core, v.m_startTs, AMDT_UNKNOWN_TIMESTAMP, AMDT_UNKNOWN_TGID, AMDT_IDLE_THREAD, v.m_state, AMDT_FALSE])

                elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_CPUIDLE.value:
                    for core in self.m_coreList:
                        data = self.m_bpfObj["g_cpuIdleData"][0][core]
                        index = self.m_bpfObj["g_cpuIdleIndex"][0][core]
                        if index != 0:
                            for i in range(index):
                                rec = data.m_evtData[i]
                                writer.writerow([rec.m_cpuId, rec.m_startTs, rec.m_endTs, rec.m_state])

                    #get records which doesn't have ended idle time by that time profile stopped
                    cpuIdleTable = self.m_bpfObj["g_prevCpuIdle"]
                    for k,v in cpuIdleTable.items():
                        writer.writerow([k.value, v.m_startTs, AMDT_UNKNOWN_TIMESTAMP, v.m_state])

                elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_CPUFREQ.value:
                    for core in self.m_coreList:
                        data = self.m_bpfObj["g_cpuFreqData"][0][core]
                        index = self.m_bpfObj["g_cpuFreqIndex"][0][core]
                        if index != 0:
                            for i in range(index):
                                rec = data.m_evtData[i]
                                writer.writerow([rec.m_cpuId, rec.m_startTs, rec.m_endTs, rec.m_tgid, rec.m_pid, rec.m_state])

                    #get records which doesn't have ended idle time by that time profile stopped
                    cpuFreqTable = self.m_bpfObj["g_prevCpuFreq"]
                    for k,v in cpuFreqTable.items():
                        writer.writerow([k.value, v.m_startTs, AMDT_UNKNOWN_TIMESTAMP, v.m_tgid, v.m_pid, v.m_state])

                elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_PAGEFAULT.value:
                    self.writePageFaultStats()
                #    if self.m_swp is False:
                #        for core in self.m_coreList:
                #            data = self.m_bpfObj["g_pageFaultData"][0][core]
                #            index = self.m_bpfObj["g_pageFaultIndex"][0][core]
                #            if index != 0:
                #                for i in range(index):
                #                    rec = data.m_evtData[i]
                #                    writer.writerow([rec.m_startTs, rec.m_tgid, rec.m_pid, rec.m_address, rec.m_ip, rec.m_errCode, rec.m_isKernel])

                elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_DISKIO.value:
                    for core in self.m_coreList:
                        data = self.m_bpfObj["g_blockIoData"][0][core]
                        index = self.m_bpfObj["g_blockIoIndex"][0][core]
                        if index != 0:
                            for i in range(index):
                                rec = data.m_evtData[i]
                                writer.writerow([rec.m_insertTs, rec.m_issueTs, rec.m_completeTs, rec.m_tgid, rec.m_pid, rec.m_size, rec.m_major, rec.m_minor, rec.m_operation])

                    blockTable = self.m_bpfObj["g_blockIoStart"]
                    for k,v in blockTable.items():
                         writer.writerow([v.m_insertTs, v.m_issueTs, v.m_completeTs, v.m_tgid, v.m_pid, v.m_size, v.m_major, v.m_minor, v.m_operation])

                elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_SYSCALL.value:
                    if self.m_swp is False:
                        for core in self.m_coreList:
                            data = self.m_bpfObj["g_sysCallData"][0][core]
                            index = self.m_bpfObj["g_sysCallIndex"][0][core]
                            if index != 0:
                                for i in range(index):
                                    rec = data.m_evtData[i]
                                    writer.writerow([rec.m_startTs, rec.m_endTs, rec.m_tgid, rec.m_pid, rec.m_sid])

                        # Don't process with start or end Timestamp as unknown for syscall entry
                        #sysCallTable = self.m_bpfObj["g_sysCallEntry"]
                        #for k,v in sysCallTable.items():
                        #    writer.writerow([v.m_startTs, v.m_endTs, v.m_tgid, v.m_pid, v.m_sid])

                    self.writeSysCallStats()

                elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_FUNCCOUNT.value:
                    if self.m_swp is False:
                        for core in self.m_coreList:
                            data = self.m_bpfObj["g_funcCountData"][0][core]
                            index = self.m_bpfObj["g_funcCountIndex"][0][core]
                            if index != 0:
                                for i in range(index):
                                    rec = data.m_evtData[i]
                                    writer.writerow([rec.m_startTs, rec.m_endTs, rec.m_tgid, rec.m_pid, rec.m_fid])

                    self.writeFuncCountStats()

                    self.writeFuncNames(self.m_funcCountCode.GetUserFunctions(), AMDTOsTraceFunctions.AMDT_FUNCCOUNT_FUNCTION_START.value)
                    self.writeFuncNames(self.m_funcCountCode.GetKernelFunctions(), AMDTOsTraceFunctions.AMDT_FUNCCOUNT_FUNCTION_START.value)

                elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_PTHREAD.value:
                    for core in self.m_coreList:
                        data = self.m_bpfObj["g_pthreadData"][0][core]
                        index = self.m_bpfObj["g_pthreadIndex"][0][core]
                        if index != 0:
                            for i in range(index):
                                rec = data.m_evtData[i]
                                writer.writerow([rec.m_startTs, rec.m_endTs, rec.m_tgid, rec.m_pid, rec.m_pthreadId, rec.m_stackId, rec.m_fid, rec.m_address, rec.m_status, rec.m_lockType])

                    #stackTable = self.m_bpfObj["g_pthreadStackIdToPid"]
                    #self.writeCallStacks(self.m_pthread, stackTable, ("pthread/callstack_" + str(os.getpid()) + ".csv"))
                    self.writeFuncNames(g_pthreadFunctions, 0)

                elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_IOTRACE.value:
                    for core in self.m_coreList:
                        data = self.m_bpfObj["g_ioTraceData"][0][core]
                        index = self.m_bpfObj["g_ioTraceIndex"][0][core]
                        if index != 0:
                            for i in range(index):
                                rec = data.m_evtData[i]
                                writer.writerow([rec.m_startTs, rec.m_endTs, rec.m_tgid, rec.m_pid, rec.m_stackId, rec.m_fid, rec.m_size, rec.m_ioType, rec.m_fd])

                    #stackTable = self.m_bpfObj["g_ioTraceStackIdToPid"]
                    #self.writeCallStacks(self.m_ioTrace, stackTable, ("iotrace/callstack_" + str(os.getpid()) + ".csv"))
                    self.writeFuncNames(g_ioTraceFunctions, 0)

                elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_LIBTRACE.value:
                    for core in self.m_coreList:
                        data = self.m_bpfObj["g_libTraceData"][0][core]
                        index = self.m_bpfObj["g_libTraceIndex"][0][core]
                        if index != 0:
                            for i in range(index):
                                rec = data.m_evtData[i]
                                fid = AMDT_LIBTRACE_FUNCTION_START + rec.m_fid
                                writer.writerow([rec.m_startTs, rec.m_tgid, rec.m_pid, rec.m_stackId, fid])

                    #stackTable = self.m_bpfObj["g_libTraceStackIdToPid"]
                    #self.writeCallStacks(self.m_libTrace, stackTable, ("libtrace/callstack_" + str(os.getpid()) + ".csv"))
                    self.writeFuncNames(self.m_libTraceCode.GetUserFunctions(), AMDT_LIBTRACE_FUNCTION_START)

                elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_MEMTRACE.value:
                    for core in self.m_coreList:
                        data = self.m_bpfObj["g_memTraceData"][0][core]
                        index = self.m_bpfObj["g_memTraceIndex"][0][core]
                        if index != 0:
                            for i in range(index):
                                rec = data.m_evtData[i]
                                writer.writerow([rec.m_startTs, rec.m_endTs, rec.m_tgid, rec.m_pid, rec.m_stackId, rec.m_fid, rec.m_address, rec.m_size])

                    self.writeMemLeaks()

                    #stackTable = self.m_bpfObj["g_memTraceStackIdToPid"]
                    #self.writeCallStacks(self.m_memTrace, stackTable, ("memtrace/callstack_" + str(os.getpid()) + ".csv"))
                    self.writeFuncNames(g_memTraceFunctions, 0)

                elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_OPEN_SYSCALL.value:
                    for core in self.m_coreList:
                        data = self.m_bpfObj["g_openSysCallData"][0][core]
                        index = self.m_bpfObj["g_openSysCallIndex"][0][core]
                        if index != 0:
                            for i in range(index):
                                rec = data.m_evtData[i]
                                writer.writerow([rec.m_startTs, rec.m_endTs, rec.m_tgid, rec.m_pid, rec.m_fd, rec.m_fname])

                elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_MMAP_SYSCALL.value:
                    for core in self.m_coreList:
                        data = self.m_bpfObj["g_mmapSysCallData"][0][core]
                        index = self.m_bpfObj["g_mmapSysCallIndex"][0][core]
                        if index != 0:
                            for i in range(index):
                                rec = data.m_evtData[i]
                                writer.writerow([rec.m_startTs, rec.m_tgid, rec.m_pid, rec.m_fd, rec.m_start, rec.m_len])

                #elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_FUNCCOUNT.value:
                #    counts = self.m_bpfObj["g_funcCount"]
                #    for key, count in counts.items():
                #        if self.m_swp is True:
                #            writer.writerow([AMDT_UNKNOWN_TGID, AMDT_UNKNOWN_PID, key.value, count.value])
                #        else:
                #            if key.m_fid in self.m_funcCountFids:
                #                writer.writerow([(key.m_tgid)>>32, (key.m_tgid)&0x00FFFFFFFF, key.m_fid, count.value])
#
#                    self.writeFuncNames(self.m_funcCountCode.GetUserFunctions(), AMDTOsTraceFunctions.AMDT_FUNCCOUNT_FUNCTION_START.value)
#                    self.writeFuncNames(self.m_funcCountCode.GetKernelFunctions(), AMDTOsTraceFunctions.AMDT_FUNCCOUNT_FUNCTION_START.value)

    #callback function to read data from perf buffer
    def writeTraceData(self, cpu, data, size):
        dataType = (ct.cast(data, ct.POINTER(ct.c_int)).contents).value
        writer = self.m_csvWriter[dataType]
        if dataType == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_SCHEDULE.value:
            schedData = ct.cast(data, ct.POINTER(SchedData)).contents
            for i in range(g_nRecords):
                rec = schedData.m_evtData[i]
                writer.writerow([cpu, rec.m_startTs, rec.m_endTs, rec.m_tgid, rec.m_pid, rec.m_state, int(rec.m_voluntarySw)])

        elif dataType == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_CPUIDLE.value:
            cpuIdleData = ct.cast(data, ct.POINTER(CpuIdleData)).contents
            for i in range(g_nRecords):
                rec = cpuIdleData.m_evtData[i]
                writer.writerow([rec.m_cpuId, rec.m_startTs, rec.m_endTs, rec.m_state])

        elif dataType == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_CPUFREQ.value:
            cpuFreqData = ct.cast(data, ct.POINTER(CpuFreqData)).contents
            for i in range(g_nRecords):
                rec = cpuFreqData.m_evtData[i]
                writer.writerow([rec.m_cpuId, rec.m_startTs, rec.m_endTs, rec.m_tgid, rec.m_pid, rec.m_state])

        elif dataType == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_PAGEFAULT.value:
            pageFaultData = ct.cast(data, ct.POINTER(PageFaultData)).contents
            for i in range(g_nRecords):
                rec = pageFaultData.m_evtData[i]
                writer.writerow([rec.m_startTs, rec.m_tgid, rec.m_pid, rec.m_address, rec.m_ip, rec.m_errCode, rec.m_isKernel])

        elif dataType == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_DISKIO.value:
            blockIoData = ct.cast(data, ct.POINTER(BlockIoData)).contents
            for i in range(g_nRecords):
                rec = blockIoData.m_evtData[i]
                writer.writerow([rec.m_insertTs, rec.m_issueTs, rec.m_completeTs, rec.m_tgid, rec.m_pid, rec.m_size, rec.m_major, rec.m_minor, rec.m_operation])

        elif dataType == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_SYSCALL.value:
            sysCallData = ct.cast(data, ct.POINTER(SysCallData)).contents
            for i in range(g_nRecords):
                rec = sysCallData.m_evtData[i]
                writer.writerow([rec.m_startTs, rec.m_endTs, rec.m_tgid, rec.m_pid, rec.m_sid])

        elif dataType == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_FUNCCOUNT.value:
            funcCountData = ct.cast(data, ct.POINTER(FuncCountData)).contents
            for i in range(g_nRecords):
                rec = funcCountData.m_evtData[i]
                writer.writerow([rec.m_startTs, rec.m_endTs, rec.m_tgid, rec.m_pid, rec.m_fid])

        elif dataType == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_LIBTRACE.value:
            libTraceData = ct.cast(data, ct.POINTER(LibTraceData)).contents
            for i in range(g_nRecords):
                rec = libTraceData.m_evtData[i]
                fid = AMDT_LIBTRACE_FUNCTION_START + rec.m_fid
                writer.writerow([rec.m_startTs, rec.m_tgid, rec.m_pid, rec.m_stackId, fid])

        elif dataType == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_MEMTRACE.value:
            memTraceData = ct.cast(data, ct.POINTER(MemTraceData)).contents
            for i in range(g_nRecords):
                rec = memTraceData.m_evtData[i]
                writer.writerow([rec.m_startTs, rec.m_endTs, rec.m_tgid, rec.m_pid, rec.m_stackId, rec.m_fid, rec.m_address, rec.m_size])

        elif dataType == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_PTHREAD.value:
            pthreadData = ct.cast(data, ct.POINTER(PthreadData)).contents
            for i in range(g_nRecords):
                rec = pthreadData.m_evtData[i]
                writer.writerow([rec.m_startTs, rec.m_endTs, rec.m_tgid, rec.m_pid, rec.m_pthreadId, rec.m_stackId, rec.m_fid, rec.m_address, rec.m_status, rec.m_lockType])

        elif dataType == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_IOTRACE.value:
            ioTraceData = ct.cast(data, ct.POINTER(IoTraceData)).contents
            for i in range(g_nRecords):
                rec = ioTraceData.m_evtData[i]
                writer.writerow([rec.m_startTs, rec.m_endTs, rec.m_tgid, rec.m_pid, rec.m_stackId, rec.m_fid, rec.m_size, rec.m_ioType, rec.m_fd])

        elif dataType == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_OPEN_SYSCALL.value:
            openSysCallData = ct.cast(data, ct.POINTER(OpenSysCallData)).contents
            for i in range(g_nOpenRecords):
                rec = openSysCallData.m_evtData[i]
                writer.writerow([rec.m_startTs, rec.m_endTs, rec.m_tgid, rec.m_pid, rec.m_fd, rec.m_fname])

        elif dataType == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_MMAP_SYSCALL.value:
            mmapSysCallData = ct.cast(data, ct.POINTER(MmapSysCallData)).contents
            for i in range(g_nRecords):
                rec = mmapSysCallData.m_evtData[i]
                writer.writerow([rec.m_startTs, rec.m_tgid, rec.m_pid, rec.m_fd, rec.m_start, rec.m_len])

    # callback function to indicate lost records
    def lostTraceData(self, lostRecCnt):
        self.m_lostCount += lostRecCnt  #update the lost record count

    # signal handler for SIGTERM
    def cleanup(self):
        ret = False
        if self.m_startTracing is True and self.m_bpfObj is not None:
            profileStatus = self.m_bpfObj["g_profileStatus"]
            profileStatus[ct.c_int(0)] = ct.c_int(0)    #set the status to profile stopped

            if self.m_args.pids is not None:
                tracePids = self.m_bpfObj["g_tracePids"]
                pidList = []
                for k,v in tracePids.items():
                    pidList.append(k.value)

                for pid in pidList:
                    tracePids[ct.c_int(pid)] = ct.c_int(0)
            
            ret = True

        self.m_stopTracing = True    #profile stopped
        return ret

    #attach k-Probes for DISKIO
    def attachDiskIoProbes(self):
        try:
            if BPF.get_kprobe_functions(b'__blk_account_io_start'):
                self.m_bpfObj.attach_kprobe(event="__blk_account_io_start", fn_name="trace_block_rq_insert")
            elif BPF.get_kprobe_functions(b'blk_account_io_start'):
                self.m_bpfObj.attach_kprobe(event="blk_account_io_start", fn_name="trace_block_rq_insert")
            else:
                print("WARNING: Failed to attach block_rq_insert kprobe for diskio")

            if BPF.get_kprobe_functions(b'blk_mq_start_request'):
                self.m_bpfObj.attach_kprobe(event="blk_mq_start_request", fn_name="trace_block_rq_issue")
            elif BPF.get_kprobe_functions(b'blk_start_request'):
                self.m_bpfObj.attach_kprobe(event="blk_start_request", fn_name="trace_block_rq_issue")
            else:
                print("WARNING: Failed to attach block_rq_issue kprobe for diskio")

            if BPF.get_kprobe_functions(b'__blk_account_io_done'):
                self.m_bpfObj.attach_kprobe(event="__blk_account_io_done", fn_name="trace_block_rq_complete")
            elif BPF.get_kprobe_functions(b'blk_account_io_done'):
                self.m_bpfObj.attach_kprobe(event="blk_account_io_done", fn_name="trace_block_rq_complete")
            else:
                print("WARNING: Failed to attach block_rq_complete kprobe for diskio")

        except Exception:
            raise Exception("Failed to attach kprobes for DISKIO")

    #attach uprobes
    def attachProbes(self, lib, funcName, funcId, canFail=False, fnPrefix=None):
        ret = True

        if fnPrefix is None:
            fnPrefix = funcName

        libPath = BPF.find_library(lib)
        #Then it may be executable.
        if libPath is None:
            libPath = BPF.find_exe(str(lib))

        if libPath is not None and len(libPath) != 0:
            function = funcName.encode()
            function = b'^' + function + b'$'
            addresses = BPF.get_user_addresses(libPath, function)

            if funcId is not None and addresses is not None and len(addresses) != 0:
                self.m_funcIdToRVA[funcId] = addresses.pop()

            try:
                self.m_bpfObj.attach_uprobe(name=lib, sym=funcName, fn_name=fnPrefix + "_enter")
                self.m_bpfObj.attach_uretprobe(name=lib, sym=funcName, fn_name=fnPrefix + "_exit")
            except Exception:
                if canFail:
                    ret = False
                else:
                    raise Exception("Failed to attach %s : lib %s" %(funcName, lib))
        else:
            print("WARNING : %s library is not found" %lib)
            ret = False

        return ret

    def loadKernelCode(self):
        pidList = "" # pids separated by :

        #load bpf code into kernel
        try:
            self.m_bpfObj = BPF(text=self.m_bpfSource)
        except:
            raise Exception("Failed to load bpf code into kernel")

        #attach uprobe for functions to get the cal stack for library functions
        if self.m_libTraceCode is not None:
            libTraceFunctions = self.m_libTraceCode.GetUserFunctions()
            libTraceFuncToLibrary = self.m_libTraceCode.GetFuncToLibrary()
            libTraceAddresses = self.m_libTraceCode.GetUserFunctionAddress()

            for funcId, funcName in libTraceFunctions.items():
                fid = funcId + AMDT_LIBTRACE_FUNCTION_START
                library = libTraceFuncToLibrary[funcName]

                if fid is not None:
                    self.m_funcIdToRVA[fid] = libTraceAddresses[funcId]

                try:
                    self.m_bpfObj.attach_uprobe(name=library, sym=funcName, fn_name="library_trace_%d" % fid)
                except:
                    raise Exception("Failed to attach uprobe for %s:%s" %(library, funcName))

        #attach uprobe for functions to trace memory allocations, pthread trace and IoTrace
        if self.m_args.events is not None:
            for event in self.m_args.events:
                if event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_MEMTRACE.value:
                    for key, func in g_memTraceFunctions.items():
                        self.attachProbes("c", func, key)
                elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_IOTRACE.value:
                    for key, func in g_ioTraceFunctions.items():
                        if func.startswith('aio'):
                            self.attachProbes("rt", func, key)
                        elif func.startswith('io_'):
                            self.attachProbes('aio', func, key)
                        else:
                            self.attachProbes("c", func, key)
                elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_PTHREAD.value:
                    for key, func in g_pthreadFunctions.items():
                        ret = self.attachProbes("pthread", func, key, True)

                        if ret is False:
                            ret = self.attachProbes("c", func, key, True)

                            if ret is False:
                                print("WARNING : function %s is not found in libc" %func)

                elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_DISKIO.value:
                    self.attachDiskIoProbes()
                elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_SYSCALL.value:
                    traceSysCalls = self.m_bpfObj["g_traceSysCalls"]
                    if self.m_args.sysCallPath is not None:
                        with open(self.m_args.sysCallPath) as f:
                            data = json.load(f)
                            for sysCall in data['syscalls']:
                                if sysCall['trace'] == True:
                                    traceSysCalls[ct.c_int(int(sysCall['id']))] = ct.c_int(1)

        #attach uprobe for functions to get count of each function
        if self.m_funcCountCode is not None:
            userFunctions = self.m_funcCountCode.GetUserFunctions()
            funcCountFuncToLibrary = self.m_funcCountCode.GetFuncToLibrary()
            funcCountAddresses = self.m_funcCountCode.GetUserFunctionAddress()

            for funcId, funcName in userFunctions.items():
                fid = funcId + AMDTOsTraceFunctions.AMDT_FUNCCOUNT_FUNCTION_START.value
                library = funcCountFuncToLibrary[funcName]

                if funcName in self.m_probeExistFuncs:
                    continue

                if fid is not None:
                    self.m_funcIdToRVA[fid] = funcCountAddresses[funcId]

                try:
                    self.m_bpfObj.attach_uprobe(name=library, sym=funcName, fn_name="trace_funccount_%d" % (fid))
                    self.m_bpfObj.attach_uretprobe(name=library, sym=funcName, fn_name="trace_funccount_%d_ret" % (fid))
                except:
                    print("WARNING : Failed to attach uprobe for %s:%s" %(library, funcName))

            kernelFunctions = self.m_funcCountCode.GetKernelFunctions()

            for funcId, funcName in kernelFunctions.items():
                try:
                    self.m_bpfObj.attach_kprobe(event=funcName, fn_name="trace_funccount_%d" % (funcId + AMDTOsTraceFunctions.AMDT_FUNCCOUNT_FUNCTION_START.value))
                    self.m_bpfObj.attach_kretprobe(event=funcName, fn_name="trace_funccount_%d_ret" % (funcId + AMDTOsTraceFunctions.AMDT_FUNCCOUNT_FUNCTION_START.value))
                except:
                    print("WARNING : Failed to attach kprobe for %s" %(funcName))

            if not userFunctions and not kernelFunctions:
                print("WARNING : Given function pattern through --func doesn't resolve to any functions")

        #open perf buffer with size as g_bufferSize in pages, perf buffer is per core
        self.m_bpfObj["g_perfBuffer"].open_perf_buffer(self.writeTraceData, g_bufferSize, self.lostTraceData)

        if self.m_args.cpus is not None:
            traceCores = self.m_bpfObj["g_traceCores"]
            for core in self.m_args.cpus:
                self.m_coreList.append(core)
                traceCores[ct.c_int(core)] = ct.c_int(1) #update the trace cores
        else:
            for core in range(self.m_args.noofcpus):
                self.m_coreList.append(core)

        # call stack option is not supported
        # get the respective tables from bpf for callstack
        # if self.m_args.libtrace is not None:
        #    self.m_libTrace = self.m_bpfObj["g_libTrace"]

        #if self.m_args.events is not None:
        #    for event in self.m_args.events:
        #        if event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_MEMTRACE.value:
        #            self.m_memTrace = self.m_bpfObj["g_memTrace"]
        #        elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_IOTRACE.value:
        #            self.m_ioTrace = self.m_bpfObj["g_ioTrace"]
        #        elif event == AMDTOsTraceDataTypes.AMDT_OS_TRACE_DATA_TYPE_PTHREAD.value:
        #            self.m_pthread = self.m_bpfObj["g_pthread"]

        # write to fifo, so that uProf can continue in Configure
        if g_wrFifo is not None:
            selfPid = str(os.getpid())
            os.write(g_wrFifo, selfPid.encode())

        # wait for list of PIDs from uProf
        g_rdFifo = os.open(g_rdFifoPath, os.O_RDONLY)

        if g_rdFifo is not None:
            pidList = os.read(g_rdFifo, AMDT_PID_STR_SIZE)

            if len(pidList) == 0:
                sys.exit(0)

        #get the profile type table from bpf and set the profile type
        profileType = self.m_bpfObj["g_profileType"]

        if len(pidList) != 0:
            pids = pidList.decode()

            if pids == "-1":
                profileType[ct.c_int(0)] = ct.c_int(1) #set the profile type to SWP
            else:
                profileType[ct.c_int(0)] = ct.c_int(0); #set the profile type to APP
                tracePids = self.m_bpfObj["g_tracePids"]
                for pid in pids.split(':'):
                    tracePids[ct.c_int(int(pid))] = ct.c_int(1) #update the traced pids

        self.m_startTracing = True

        #get the profile status table from bpf and start the profiling
        profileStatus = self.m_bpfObj["g_profileStatus"]
        profileStatus[ct.c_int(0)] = ct.c_int(1);  #set the profile status to running

        #close the read fifo so that uProf can continue in startProfiling
        if g_rdFifo is not None:
            os.close(g_rdFifo)

        #collect the data from perf buffer until profile stops
        while self.m_stopTracing == False:
            try:
                self.m_bpfObj.perf_buffer_poll()
            except KeyboardInterrupt:
                break

        #collect, if perf buffer contains data
        self.m_bpfObj.perf_buffer_poll(100)
        self.m_startTracing = False

        #collect the Data which is not sent to the perf Buffer
        self.writeRemainingRecords()

        self.writeMetaData()
        self.writeProcInfo()

        #close the opened output files
        self.closeOutputFiles()

        #indicate the uprof that bpf script is going to exit.
        if g_wrFifo is not None:
            os.close(g_wrFifo)

        sys.exit(0)

# signal handler for SIGTERM
def signalHandler(sig, fname):
    isCleaned = False

    if g_trace is not None:
        isCleaned = g_trace.cleanup()

    if isCleaned is False:
        sys.exit(1)

if __name__ == "__main__":
    #signal handler for SIGTERM signal for graceful termination
    signal.signal(signal.SIGINT, signalHandler)
    signal.signal(signal.SIGTERM, signalHandler)

    #close open fds other than 0, 1, 2
    pid = os.getpid()
    dirName = "/proc/" + str(pid) + "/fd"
    for name in os.listdir(dirName):
        fd = int(name)
        if fd > 2:
            try:
                os.close(fd)
            except:
                continue

    # create object for BpfTrace
    g_trace = BpfTrace()
    if g_trace is None:
        raise Exception("BpfTrace Object is None")

    g_wrFifo = os.open(g_wrFifoPath, os.O_WRONLY)

    # construct the BPF code by replacing few Macros
    g_trace.constructKernelCode()

    # create and open Output files in write mode
    g_trace.createOutputFiles()

    # load BPF code into kernel and wait for SIGTERM signal
    # continuously poll and read the perf buffer
    g_trace.loadKernelCode()

