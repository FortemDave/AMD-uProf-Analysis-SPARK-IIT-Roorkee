#==================================================================================
# Copyright (c) 2021 , Advanced Micro Devices, Inc.  All rights reserved.
#
# author AMD Developer Tools Team
# file AMDTBpfKernel.py
# brief Contains the BPF code to be loaded into kernel
#==================================================================================

#Common header for all types of events
g_bpfCommonHeader = """
//Kernel header files
#include <uapi/linux/ptrace.h>
#include <uapi/linux/limits.h>
#include <uapi/linux/mman.h>
#include <linux/sched.h>
#include <linux/kdev_t.h>
#include <uapi/linux/aio_abi.h>
#include <linux/blkdev.h>
#include <linux/blk-mq.h>

//This enum will indicate the type of data submitting to the Perf Buffer
enum AMDTOsTraceDataTypes
{
    AMDT_OS_TRACE_DATA_TYPE_SCHEDULE = 1,
    AMDT_OS_TRACE_DATA_TYPE_CPUIDLE,
    AMDT_OS_TRACE_DATA_TYPE_CPUFREQ,
    AMDT_OS_TRACE_DATA_TYPE_DISKIO,
    AMDT_OS_TRACE_DATA_TYPE_PAGEFAULT,
    AMDT_OS_TRACE_DATA_TYPE_SYSCALL,
    AMDT_OS_TRACE_DATA_TYPE_PTHREAD,
    AMDT_OS_TRACE_DATA_TYPE_MEMTRACE,
    AMDT_OS_TRACE_DATA_TYPE_IOTRACE,
    AMDT_OS_TRACE_DATA_TYPE_LIBTRACE,
    AMDT_OS_TRACE_DATA_TYPE_FUNCCOUNT,
    AMDT_OS_TRACE_DATA_TYPE_OPEN_SYSCALL,
    AMDT_OS_TRACE_DATA_TYPE_MMAP_SYSCALL,
    AMDT_OS_TRACE_DATA_TYPE_END = AMDT_OS_TRACE_DATA_TYPE_MMAP_SYSCALL,
};

//Profile Status
enum AMDTOsTraceProfileStatus
{
    AMDT_OS_TRACE_PROFILE_STOPPED,
    AMDT_OS_TRACE_PROFILE_RUNNING
};

//type of profiling
enum AMDTOsTraceProfileType
{
    AMDT_OS_TRACE_PROFILE_APP,
    AMDT_OS_TRACE_PROFILE_SWP
};

//Tracing user space functions
//Modification of this requires the modification for "class AMDTOsTraceFunctions" in AMDTBpfTrace.py
enum AMDTOsTraceFunctions
{
    AMDT_PTHREAD_CREATE            = 0x01,
    AMDT_PTHREAD_EXIT,
    AMDT_PTHREAD_MUTEX_LOCK,
    AMDT_PTHREAD_MUTEX_TRYLOCK,
    AMDT_PTHREAD_MUTEX_TIMEDLOCK,
    AMDT_PTHREAD_MUTEX_UNLOCK,
    AMDT_PTHREAD_COND_WAIT,
    AMDT_PTHREAD_COND_TIMEDWAIT,
    AMDT_PTHREAD_COND_SIGNAL,
    AMDT_PTHREAD_COND_BROADCAST,
    AMDT_PTHREAD_JOIN,
    AMDT_MALLOC,
    AMDT_CALLOC,
    AMDT_REALLOC,
    AMDT_FREE,
    AMDT_READ,
    AMDT_WRITE,
    AMDT_PREAD,
    AMDT_PWRITE,
    AMDT_AIO_READ,
    AMDT_AIO_WRITE,
    AMDT_IO_SUBMIT,
    AMDT_FUNCCOUNT_FUNCTION_START
};

//define process filter only for APP based profiling
DEFINE_AMDT_PROCESS_FILTER

//define Core filter only, if cores are specified through command line
DEFINE_AMDT_CORE_FILTER

//define callstack collection macro to collect the call stack
DEFINE_AMDT_PTHREAD_CALLSTACK_COLLECT
DEFINE_AMDT_IOTRACE_CALLSTACK_COLLECT
DEFINE_AMDT_MEMTRACE_CALLSTACK_COLLECT
DEFINE_AMDT_LIBTRACE_CALLSTACK_COLLECT

//thresholds for different events
DEFINE_AMDT_MEMSIZE_THRESHOLD
DEFINE_AMDT_CPUIDLE_THRESHOLD
DEFINE_AMDT_SYSCALL_THRESHOLD
DEFINE_AMDT_FUNCCOUNT_THRESHOLD
DEFINE_AMDT_IOTRACE_THRESHOLD
DEFINE_AMDT_PTHREAD_THRESHOLD

//Define Max Processes
DEFINE_AMDT_MAX_THREADS

//Define function count
DEFINE_AMDT_FUNCTION_COUNT

DEFINE_AMDT_DATA_GROUP_SIZE      // bunch of events submitted to perf buffer
DEFINE_AMDT_CALLSTACK_SIZE       // no of unique callstacks in stack map

#define AMDT_IDLE_PROCESS  0
#define AMDT_STATUS_OK     0
#define AMDT_STATUS_ERROR -1

//Upper 32 bits indicates the PID in user space
//Lower 32 bits indicates the TID in user space
#define AMDT_GET_TGID(id) (id >> 32)
#define AMDT_GET_PID(id) ((u32)id)

#define AMDT_MAX_SYSCALLS        1024
#define AMDT_UNKNOWN_TIMESTAMP   ULLONG_MAX
#define AMDT_UNKNOWN_CSTATE      0xFFFFFFFF
#define AMDT_UNKNOWN_TGID        0xFFFFFFFF
#define AMDT_UNKNOWN_PID         0xFFFFFFFF
#define AMDT_UNKNOWN_CORE_ID     0xFFFFFFFF
#define AMDT_UNKNOWN_STACK_ID    -1
#define AMDT_UNKNOWN_ADDRESS     0
#define AMDT_MAX_CORES           1024
#define AMDT_UNKNOWN_SECTOR_ID   ULLONG_MAX
#define AMDT_THREAD_NAME_UPDATE_COUNT    16

#define AMDT_PROCESS_NAME_LENGTH 128

//No of events skipped due to threshold in each trace event
BPF_ARRAY(g_skippedEvents, u64, AMDT_OS_TRACE_DATA_TYPE_END);

BPF_ARRAY(g_profileType, u32, 1);   //array for profile type
BPF_ARRAY(g_profileStatus, u32, 1); //array for profile status

#if defined(AMDT_PROCESS_FILTER)
BPF_HASH(g_tracePids, u32, bool); //Hashmap to store the pids which needs to be traced in APP based profiling
#endif

#if defined(AMDT_CORE_FILTER)
BPF_ARRAY(g_traceCores, bool, AMDT_MAX_CORES); //Hashmap to store the cores which needs to be traced.
#endif

BPF_PERF_OUTPUT(g_perfBuffer);  // Perf buffer

//New Process or thread info created while tracing
struct ForkRecord
{
    u32    m_ppid;
    u32    m_tgid;
    u32    m_threadNameUpdateCnt;
    char   m_comm[AMDT_PROCESS_NAME_LENGTH];
};

BPF_HASH(g_procInfo, u32, struct ForkRecord); // key is PID or TID

//prev context switch for a process.
struct PrevSchedSwitch
{
    u64    m_startTs;
    u64    m_state;
    u32    m_core;
};

//to store previous Context switch
BPF_HASH(g_prevSchedSwitch, u32, struct PrevSchedSwitch, AMDT_MAX_THREADS);
"""

#Common code for different types of events
g_bpfCommonCode = """
//get the profile status(stopped or running)
static inline bool getProfileStatus()
{
    u32 zero = 0;
    u32 *pStatus = g_profileStatus.lookup(&zero);

    if (pStatus && ((*pStatus) == AMDT_OS_TRACE_PROFILE_RUNNING))
    {
        return true;
    }

    return false;
}

//get the profile type(SWP or APP)
static inline u32 getProfileType()
{
    u32 zero = 0;
    u32 *pType = g_profileType.lookup(&zero);
    return pType? (*pType): AMDT_STATUS_ERROR;
}

#if defined(AMDT_PROCESS_FILTER)
//Add the pisd to process filtering
static inline void setPid(u32 pid)
{
    bool enable = true;
    g_tracePids.update(&pid, &enable);
}

//Check whether Pid is traced or not.
static inline bool isPidTraced(u32 pid)
{
    bool *pIsTraced = g_tracePids.lookup(&pid);
    return pIsTraced? (*pIsTraced): false;
}
#endif

#if defined(AMDT_CORE_FILTER)
//check whether core is traced or not
static inline bool isCoreTraced(u32 core)
{
    bool *pIsTraced = g_traceCores.lookup(&core);
    return pIsTraced? (*pIsTraced): false;
}
#endif

//check whether given pid is idle process or not
static inline bool isIdleProcess(u32 pid)
{
    return (pid == AMDT_IDLE_PROCESS)? true: false;
}

//Validate the required filters before processing the event.
static inline bool getFilterResult(u32 pid, u32 core)
{
#if !defined(AMDT_PROCESS_FILTER)
    if (!getProfileStatus())
    {
        return false;
    }
#endif

#if defined(AMDT_PROCESS_FILTER)
    if ((pid != AMDT_UNKNOWN_PID) && (isPidTraced(pid) == false))
    {
        return false;
    }
#endif

#if defined(AMDT_CORE_FILTER)
    if ((core != AMDT_UNKNOWN_CORE_ID) && (isCoreTraced(core) == false))
    {
        return false;
    }
#endif

    return true;
}

#if defined(AMDT_PROCESS_FILTER)
// Increment the function count
static inline int incrementFuncCount(u32 fid, u64 duration)
{
#ifdef AMDT_FUNCTION_COUNT
    //update the funccount stats.
    struct FuncCountStats *pStats = g_funcCountStats.lookup(&fid);

    if (NULL != pStats)
    {
        ++(pStats->m_count);
        pStats->m_totalElapsedTime += duration;

        // update the min elapsed time if duration is less than previous min for this function
        if (duration < (pStats->m_minElapsedTime))
        {
            pStats->m_minElapsedTime = duration;
        }

        // update the max elapsed time if duration is greater than previous max for this function
        if (duration > (pStats->m_maxElapsedTime))
        {
            pStats->m_maxElapsedTime = duration;
        }
    }
    else
    {
        struct FuncCountStats stats = {};

        stats.m_count = 1;
        stats.m_totalElapsedTime = duration;
        stats.m_minElapsedTime = duration;
        stats.m_maxElapsedTime = duration;

        g_funcCountStats.update(&fid, &stats);
    }
#endif

    return 0;
}
#endif

// update the map with given process/thread name.
static inline void updateThreadName(u32 pid, char* pName)
{
    struct ForkRecord *rec = g_procInfo.lookup(&pid);

    if ((rec != NULL) && (pName != NULL))
    {
        if ((rec->m_tgid == AMDT_UNKNOWN_TGID) && (rec->m_threadNameUpdateCnt > 0))
        {
            rec->m_comm[0] = '\\0';

            if (bpf_probe_read_str(rec->m_comm, AMDT_PROCESS_NAME_LENGTH, pName) < 0)
            {
                rec->m_comm[0] = '\\0';
            }

            --(rec->m_threadNameUpdateCnt);
        }
    }
}

// get the current process/thread name and update the map.
static inline void saveThreadName(u32 pid)
{
    struct ForkRecord *rec = g_procInfo.lookup(&pid);

    if (rec != NULL)
    {
        if ((rec->m_tgid == AMDT_UNKNOWN_TGID) && (rec->m_threadNameUpdateCnt > 0))
        {
            rec->m_comm[0] = '\\0';

            if (bpf_get_current_comm(rec->m_comm, TASK_COMM_LEN) != 0)
            {
                rec->m_comm[0] = '\\0';
            }

            --(rec->m_threadNameUpdateCnt);
        }
    }
}

//update the prev Context switch record.
static inline void updateSchedTable(u32 key, u64 state, u64 ts, u32 core)
{
    struct PrevSchedSwitch value = {};

    value.m_state = state;
    value.m_startTs = ts;
    value.m_core = core;

    g_prevSchedSwitch.update(&key, &value);
}

//This event is used to trace the child processes created by the traced application.
//Parent is traced application and child needs to be added to the traced Pids
TRACEPOINT_PROBE(sched, sched_process_fork)
{
    if (getProfileStatus())
    {
        u32  child = args->child_pid;
        u64  ts  = bpf_ktime_get_ns();
        struct ForkRecord rec;

        rec.m_ppid = args->parent_pid;
        rec.m_tgid = AMDT_UNKNOWN_TGID;
        rec.m_threadNameUpdateCnt = AMDT_THREAD_NAME_UPDATE_COUNT;
        rec.m_comm[0] = '\\0';

        if (bpf_probe_read_str(rec.m_comm, AMDT_PROCESS_NAME_LENGTH, args->child_comm) < 0)
        {
            rec.m_comm[0] = '\\0';
        }

#if defined(AMDT_PROCESS_FILTER)
        if (isPidTraced(args->parent_pid) == true)
        {
            setPid(args->child_pid);
            g_procInfo.update(&child, &rec);
            updateSchedTable(child, TASK_INTERRUPTIBLE, ts, bpf_get_smp_processor_id());
        }
#else
        g_procInfo.update(&child, &rec);
        updateSchedTable(child, TASK_INTERRUPTIBLE, ts, bpf_get_smp_processor_id());
#endif
    }

    return 0;
}

TRACEPOINT_PROBE(syscalls, sys_enter_execve)
{
    if (getProfileStatus())
    {
        u64  id = bpf_get_current_pid_tgid();
        u32  pid = AMDT_GET_PID(id);

        struct ForkRecord *rec = g_procInfo.lookup(&pid);

        if (rec != NULL)
        {
            rec->m_tgid = AMDT_GET_TGID(id);
            rec->m_comm[0] = '\\0';

            if (bpf_probe_read_str(rec->m_comm, AMDT_PROCESS_NAME_LENGTH, args->filename) < 0)
            {
                rec->m_comm[0] = '\\0';
            }
        }
        else
        {
            struct ForkRecord rec = {};

            rec.m_ppid = AMDT_UNKNOWN_PID;
            rec.m_tgid = AMDT_GET_TGID(id);
            rec.m_comm[0] = '\\0';
            rec.m_threadNameUpdateCnt = AMDT_THREAD_NAME_UPDATE_COUNT;

            if (bpf_probe_read_str(rec.m_comm, AMDT_PROCESS_NAME_LENGTH, args->filename) < 0)
            {
                rec.m_comm[0] = '\\0';
            }

#if defined(AMDT_PROCESS_FILTER)
            if (isPidTraced(pid) == true)
            {
                g_procInfo.update(&pid, &rec);
            }
#else
            g_procInfo.update(&pid, &rec);
#endif
        }
    }

    return 0;
}
"""

#sched event header
g_bpfSchedHeader = """
struct SchedRecord
{
    u64    m_startTs;
    u64    m_endTs;
    u32    m_tgid;
    u32    m_pid;
    u64    m_state;
    bool   m_voluntarySw;
};

struct SchedData
{
    u32    m_dataType;
    struct SchedRecord m_evtData[AMDT_DATA_GROUP_SIZE];
};

//Per cpu array which contains the bunch of records.
BPF_PERCPU_ARRAY(g_schedData, struct SchedData, 1);
//Index array to indicate the no of records.
BPF_PERCPU_ARRAY(g_schedIndex, u32, 1);
"""

g_bpfSchedCode = """
//Process is freed from the system, update that process is no more exist
//remove entry from g_prevSchedSwitch as it is not required any more.
TRACEPOINT_PROBE(sched, sched_process_free)
{
    u32 key     = args->pid;
    u32 core    = bpf_get_smp_processor_id();

    if (!isIdleProcess(args->pid) && getFilterResult(args->pid, core))
    {
        u32 zero  = 0;
        u64  id = bpf_get_current_pid_tgid();

        struct PrevSchedSwitch *pPrevSw = g_prevSchedSwitch.lookup(&key);

        struct SchedData *pData = g_schedData.lookup(&zero);
        u32 *pIndex = g_schedIndex.lookup(&zero);

        if (pData && pIndex)
        {
            u32 i = *pIndex;
            pData->m_dataType = AMDT_OS_TRACE_DATA_TYPE_SCHEDULE;

            if ((i >= 0) && (i < AMDT_DATA_GROUP_SIZE))
            {
                pData->m_evtData[i].m_tgid = AMDT_GET_TGID(id);
                pData->m_evtData[i].m_pid = args->pid;
                pData->m_evtData[i].m_endTs = bpf_ktime_get_ns();

                if (pPrevSw)
                {
                    pData->m_evtData[i].m_startTs = pPrevSw->m_startTs;
                    pData->m_evtData[i].m_state = pPrevSw->m_state;
                }
                else
                {
                    pData->m_evtData[i].m_startTs = AMDT_UNKNOWN_TIMESTAMP;
                    pData->m_evtData[i].m_state = EXIT_DEAD;
                }
            }

            if (*pIndex == AMDT_DATA_GROUP_SIZE)
            {
                (*pIndex) = 0;
                g_perfBuffer.perf_submit(args, pData, sizeof(struct SchedData));
            }
        }
    }

    g_prevSchedSwitch.delete(&key);

    return 0;
};

TRACEPOINT_PROBE(sched, sched_switch)
{
    u32   zero  = 0;
    u64   ts    = bpf_ktime_get_ns();
    u32   core  = bpf_get_smp_processor_id();
    u64   id    = bpf_get_current_pid_tgid();

    if ((args->prev_pid != AMDT_IDLE_PROCESS) && getFilterResult(args->prev_pid, core))
    {
        //sched-out process
        u32 key = args->prev_pid;
        u64 state = args->prev_state;
        struct PrevSchedSwitch *pPrevSw = g_prevSchedSwitch.lookup(&key);

        struct SchedData *pData = g_schedData.lookup(&zero);
        u32 *pIndex = g_schedIndex.lookup(&zero);

        if (pData && pIndex)
        {
            u32 i = *pIndex;
            pData->m_dataType = AMDT_OS_TRACE_DATA_TYPE_SCHEDULE;

            if ((i >= 0) && (i < AMDT_DATA_GROUP_SIZE))
            {
                pData->m_evtData[i].m_tgid = (args->prev_pid == AMDT_GET_PID(id)) ? AMDT_GET_TGID(id) : AMDT_UNKNOWN_TGID;
                pData->m_evtData[i].m_pid = args->prev_pid;

                if (pPrevSw)
                {
                    pData->m_evtData[i].m_state = pPrevSw->m_state;
                    pData->m_evtData[i].m_startTs = pPrevSw->m_startTs;
                }
                else
                {
                    pData->m_evtData[i].m_state = TASK_RUNNING;
                    pData->m_evtData[i].m_startTs = AMDT_UNKNOWN_TIMESTAMP;
                }

                pData->m_evtData[i].m_endTs = ts;
                //if process was in running state at sched-out, then make voluntarySw to False.
                pData->m_evtData[i].m_voluntarySw = (state == TASK_RUNNING) ? false : true;

                (*pIndex)++;
            }

            if (*pIndex == AMDT_DATA_GROUP_SIZE)
            {
                (*pIndex) = 0;
                g_perfBuffer.perf_submit(args, pData, sizeof(struct SchedData));
            }
        }

        // if process is running and sched-out, then make the next state as sleep state
        if (state == TASK_RUNNING)
        {
            state = TASK_INTERRUPTIBLE;
        }

        if (pPrevSw)
        {
            pPrevSw->m_state = state;
            pPrevSw->m_startTs = ts;
            pPrevSw->m_core = core;
        }
        else
        {
            updateSchedTable(key, state, ts, core);
        }
    }

    if ((args->next_pid != AMDT_IDLE_PROCESS) && getFilterResult(args->next_pid, core))
    {
        //sched-in process.
        u32 key = args->next_pid;
        u64 state = TASK_RUNNING;
        struct PrevSchedSwitch *pPrevSw = g_prevSchedSwitch.lookup(&key);

        struct SchedData *pData = g_schedData.lookup(&zero);
        u32 *pIndex = g_schedIndex.lookup(&zero);

        if (pData && pIndex)
        {
            u32 i = *pIndex;
            pData->m_dataType = AMDT_OS_TRACE_DATA_TYPE_SCHEDULE;

            if ((i >= 0) && (i < AMDT_DATA_GROUP_SIZE))
            {
                pData->m_evtData[i].m_tgid = (args->next_pid == AMDT_GET_PID(id)) ? AMDT_GET_TGID(id) : AMDT_UNKNOWN_TGID;
                pData->m_evtData[i].m_pid = args->next_pid;

                if (pPrevSw)
                {
                    pData->m_evtData[i].m_state = pPrevSw->m_state;
                    pData->m_evtData[i].m_startTs = pPrevSw->m_startTs;
                }
                else
                {
                    pData->m_evtData[i].m_state = TASK_INTERRUPTIBLE;
                    pData->m_evtData[i].m_startTs = AMDT_UNKNOWN_TIMESTAMP;
                }

                pData->m_evtData[i].m_endTs = ts;
                pData->m_evtData[i].m_voluntarySw = false;
                (*pIndex)++;
            }

            if (*pIndex == AMDT_DATA_GROUP_SIZE)
            {
                (*pIndex) = 0;
                g_perfBuffer.perf_submit(args, pData, sizeof(struct SchedData));
            }
        }

        if (pPrevSw)
        {
            pPrevSw->m_state = state;
            pPrevSw->m_startTs = ts;
            pPrevSw->m_core = core;
        }
        else
        {
            updateSchedTable(key, state, ts, core);
        }

        updateThreadName(key, args->next_comm);
    }

    return 0;
};
"""

g_bpfCpuIdleHeader = """
struct CpuIdleRecord
{
    u64  m_startTs;
    u64  m_endTs;
    u32  m_cpuId;
    u32  m_state;
};

//prev cpu idle record (entry into idle state)
struct PrevCpuIdle
{
    u32  m_state;
    u64  m_startTs;
};

//to store previous Cpu idle events
BPF_HASH(g_prevCpuIdle, u32, struct PrevCpuIdle, AMDT_MAX_CORES);

struct CpuIdleData
{
    u32  m_dataType;
    struct CpuIdleRecord m_evtData[AMDT_DATA_GROUP_SIZE];
};

BPF_PERCPU_ARRAY(g_cpuIdleData, struct CpuIdleData, 1);
BPF_PERCPU_ARRAY(g_cpuIdleIndex, u32, 1);
"""

g_bpfCpuIdleCode = """
TRACEPOINT_PROBE(power, cpu_idle)
{
    u32 key         = args->cpu_id;
    u64 ts          = bpf_ktime_get_ns();
    u32 zero        = 0;
    u64 duration    = AMDT_CPUIDLE_THRESHOLD;
    u64 startTs     = AMDT_UNKNOWN_TIMESTAMP;
    u32 state       = AMDT_UNKNOWN_CSTATE;
    struct PrevCpuIdle *pIdleEntry = NULL;

    bool res = getFilterResult(AMDT_UNKNOWN_PID, args->cpu_id);

    if ((res == true) && ((args->state == AMDT_UNKNOWN_CSTATE) || (args->state == -1)))
    {
        pIdleEntry = g_prevCpuIdle.lookup(&key);

        if (NULL != pIdleEntry)
        {
            duration  = (ts - pIdleEntry->m_startTs);
            startTs   = pIdleEntry->m_startTs;
            state     = pIdleEntry->m_state;
        }

        if (duration >= AMDT_CPUIDLE_THRESHOLD)
        {
            struct CpuIdleData *pData = g_cpuIdleData.lookup(&zero);
            u32 *pIndex = g_cpuIdleIndex.lookup(&zero);

            if ((pData == NULL) || (pIndex == NULL))
            {
                return 0;
            }

            pData->m_dataType = AMDT_OS_TRACE_DATA_TYPE_CPUIDLE;

            if ((*pIndex >= 0) && (*pIndex < AMDT_DATA_GROUP_SIZE))
            {
                u32 i = *pIndex;
                pData->m_evtData[i].m_cpuId = args->cpu_id;
                pData->m_evtData[i].m_endTs = ts;
                pData->m_evtData[i].m_startTs = startTs;
                pData->m_evtData[i].m_state = state;
                (*pIndex)++;
            }

            if (*pIndex == AMDT_DATA_GROUP_SIZE)
            {
                (*pIndex) = 0;
                g_perfBuffer.perf_submit(args, pData, sizeof(struct CpuIdleData));
            }
        }
        else
        {
            //increment the skip count of cpu idle events
            u32 index = AMDT_OS_TRACE_DATA_TYPE_CPUIDLE;
            u64 *pCount = g_skippedEvents.lookup(&index);

            if (pCount)
            {
                (*pCount)++;
            }
        }

        g_prevCpuIdle.delete(&key);
    }
    else if((res == true) && (args->state != AMDT_UNKNOWN_CSTATE) && (args->state != -1))
    {
        //core entered into cpu idle state
        struct PrevCpuIdle idle = {};
        idle.m_startTs = ts;
        idle.m_state = args->state;
        g_prevCpuIdle.update(&key, &idle);
    }

    return 0;
};
"""

g_bpfCpuFreqHeader = """
struct CpuFreqRecord
{
    u64   m_startTs;
    u64   m_endTs;
    u32   m_tgid;
    u32   m_pid;
    u32   m_cpuId;
    u32   m_state;
};

//to store previous Cpu idle events
BPF_HASH(g_prevCpuFreq, u32, struct CpuFreqRecord, AMDT_MAX_CORES);

struct CpuFreqData
{
    u32 m_dataType;
    struct CpuFreqRecord m_evtData[AMDT_DATA_GROUP_SIZE];
};

BPF_PERCPU_ARRAY(g_cpuFreqData, struct CpuFreqData, 1);
BPF_PERCPU_ARRAY(g_cpuFreqIndex, u32, 1);
"""

g_bpfCpuFreqCode = """
TRACEPOINT_PROBE(power, cpu_frequency)
{
    u32 zero = 0;
    u64 id = bpf_get_current_pid_tgid();
    u64 ts = bpf_ktime_get_ns();

    if (getFilterResult(AMDT_UNKNOWN_PID, args->cpu_id) == true)
    {
        u32 key = args->cpu_id;
        struct CpuFreqRecord *pPrev = g_prevCpuFreq.lookup(&key);

        if (NULL != pPrev)
        {
            struct CpuFreqData *pData = g_cpuFreqData.lookup(&zero);
            u32 *pIndex = g_cpuFreqIndex.lookup(&zero);

            if ((pData == NULL) || (pIndex == NULL))
            {
                return 0;
            }

            pData->m_dataType = AMDT_OS_TRACE_DATA_TYPE_CPUFREQ;

            if ((*pIndex >= 0) && (*pIndex < AMDT_DATA_GROUP_SIZE))
            {
                u32 i = *pIndex;
                pData->m_evtData[i].m_startTs = pPrev->m_startTs;
                pData->m_evtData[i].m_endTs = ts;
                pData->m_evtData[i].m_state = pPrev->m_state;
                pData->m_evtData[i].m_cpuId = pPrev->m_cpuId;
                pData->m_evtData[i].m_tgid = AMDT_GET_TGID(id);
                pData->m_evtData[i].m_pid = AMDT_GET_PID(id);
                (*pIndex)++;
            }

            if (*pIndex == AMDT_DATA_GROUP_SIZE)
            {
                (*pIndex) = 0;
                g_perfBuffer.perf_submit(args, pData, sizeof(struct CpuFreqData));
            }

            pPrev->m_startTs = ts;
            pPrev->m_state = args->state;
            pPrev->m_cpuId = args->cpu_id;
        }
        else
        {
            struct CpuFreqRecord rec = {};

            rec.m_startTs = ts;
            rec.m_state = args->state;
            rec.m_cpuId = args->cpu_id;
            g_prevCpuFreq.update(&key, &rec);
        }
    }

    return 0;
};
"""
g_bpfBlockIoHeader = """
enum BlockIoOperationType
{
    AMDT_BLOCKIO_NONE = 0,
    AMDT_BLOCKIO_READ = 1 << 0,
    AMDT_BLOCKIO_WRITE = 1 << 1,
    AMDT_BLOCKIO_METADATA = 1 << 2,
    AMDT_BLOCKIO_SYNCHRONOUS = 1 << 3,
    AMDT_BLOCKIO_READAHEAD = 1 << 4,
    AMDT_BLOCKIO_FLUSH = 1 << 5,
    AMDT_BLOCKIO_DISCARD = 1 << 6,
    AMDT_BLOCKIO_ERASE = 1 << 7,
    AMDT_BLOCKIO_OTHER = 1 << 8
};

struct BlockIoRecord
{
    u64   m_insertTs;
    u64   m_issueTs;
    u64   m_completeTs;
    u32   m_tgid;
    u32   m_pid;
    u64   m_size;
    u32   m_operation;
    u32   m_major;
    u32   m_minor;
};

// store the start of the block IO Operation
BPF_HASH(g_blockIoStart, struct request *, struct BlockIoRecord);

struct BlockIoData
{
    u32  m_dataType;
    struct BlockIoRecord m_evtData[AMDT_DATA_GROUP_SIZE];
};

BPF_PERCPU_ARRAY(g_blockIoData, struct BlockIoData, 1);
BPF_PERCPU_ARRAY(g_blockIoIndex, u32, 1);
"""

g_bpfBlockIoCode = """
static inline u32 getOperationType(unsigned int cmdFlags)
{
    u32 operationType = AMDT_BLOCKIO_NONE;
#ifdef REQ_WRITE
    if (cmdFlags & REQ_READ)
    {
        operationType |= AMDT_BLOCKIO_READ;
    }

    if (cmdFlags & REQ_WRITE)
    {
        operationType |= AMDT_BLOCKIO_WRITE;
    }
    
    if (cmdFlags & REQ_FLUSH)
    {
        operationType |= AMDT_BLOCKIO_FLUSH;
    }
#elif defined(REQ_OP_SHIFT)
    if ((cmdFlags >> REQ_OP_SHIFT) == REQ_OP_READ)
    {
        operationType |= AMDT_BLOCKIO_READ;
    }

    if ((cmdFlags >> REQ_OP_SHIFT) == REQ_OP_WRITE)
    {
        operationType |= AMDT_BLOCKIO_WRITE;
    }
    
    if ((cmdFlags >> REQ_OP_SHIFT) == REQ_OP_FLUSH)
    {
        operationType |= AMDT_BLOCKIO_FLUSH;
    }
#else
    if ((cmdFlags & REQ_OP_MASK) == REQ_OP_READ)
    {
        operationType |= AMDT_BLOCKIO_READ;
    }

    if ((cmdFlags & REQ_OP_MASK) == REQ_OP_WRITE)
    {
        operationType |= AMDT_BLOCKIO_WRITE;
    }
    if ((cmdFlags & REQ_OP_MASK) == REQ_OP_FLUSH)
    {
        operationType |= AMDT_BLOCKIO_FLUSH;
    }
#endif

    return operationType;
}

// block_rq_insert equivalent
int trace_block_rq_insert(struct pt_regs *ctx, struct request *req)
{
    struct BlockIoRecord start = {};
    u64 id = bpf_get_current_pid_tgid();

    if (req && req->rq_disk && getProfileStatus())
    {
        u64 ts = bpf_ktime_get_ns();
        start.m_tgid        = AMDT_GET_TGID(id);
        start.m_pid         = AMDT_GET_PID(id);
        start.m_insertTs    = ts;
        start.m_issueTs     = ts;
        start.m_completeTs  = ts;
        start.m_size        = req->__data_len;
        start.m_major       = req->rq_disk->major;
        start.m_minor       = req->rq_disk->first_minor;
        start.m_operation   = getOperationType(req->cmd_flags);

        g_blockIoStart.update(&req, &start);
        saveThreadName(AMDT_GET_PID(id));
    }

    return 0;
}

int trace_block_rq_issue(struct pt_regs *ctx, struct request *req)
{
    if (req && req->rq_disk)
    {
        struct BlockIoRecord *pStart = g_blockIoStart.lookup(&req);

        if (pStart)
        {
            pStart->m_issueTs = bpf_ktime_get_ns();
        }
        else
        {
            if (getProfileStatus())
            {
                u64 id = bpf_get_current_pid_tgid();
                struct BlockIoRecord start = {};

                start.m_tgid        = AMDT_GET_TGID(id);
                start.m_pid         = AMDT_GET_PID(id);
                start.m_insertTs    = AMDT_UNKNOWN_TIMESTAMP;
                start.m_issueTs     = bpf_ktime_get_ns();
                start.m_completeTs  = AMDT_UNKNOWN_TIMESTAMP;
                start.m_size        = req->__data_len;
                start.m_major       = req->rq_disk->major;
                start.m_minor       = req->rq_disk->first_minor;
                start.m_operation   = getOperationType(req->cmd_flags);

                g_blockIoStart.update(&req, &start);
            }
        }
    }

    return 0;
}

int trace_block_rq_complete(struct pt_regs *ctx, struct request *req)
{
    if (req && !(req->rq_flags & RQF_FLUSH_SEQ))
    {
        struct BlockIoRecord *pStart = g_blockIoStart.lookup(&req);

        if (pStart)
        {
            //end of block Operation
            u32 zero = 0;
            struct BlockIoData *pData = g_blockIoData.lookup(&zero);
            u32 *pIndex = g_blockIoIndex.lookup(&zero);

            if (pData && pIndex)
            {
                u32 i = *pIndex;
                pData->m_dataType = AMDT_OS_TRACE_DATA_TYPE_DISKIO;

                if ((i >= 0) && (i < AMDT_DATA_GROUP_SIZE))
                {
                    pData->m_evtData[i].m_insertTs      = pStart->m_insertTs;
                    pData->m_evtData[i].m_issueTs       = pStart->m_issueTs;
                    pData->m_evtData[i].m_completeTs    = bpf_ktime_get_ns();
                    pData->m_evtData[i].m_tgid          = pStart->m_tgid;
                    pData->m_evtData[i].m_pid           = pStart->m_pid;
                    pData->m_evtData[i].m_size          = pStart->m_size;
                    pData->m_evtData[i].m_major         = pStart->m_major;
                    pData->m_evtData[i].m_minor         = pStart->m_minor;
                    pData->m_evtData[i].m_operation     = pStart->m_operation;

                    (*pIndex)++;
                }

                if (*pIndex == AMDT_DATA_GROUP_SIZE)
                {
                    (*pIndex) = 0;
                    g_perfBuffer.perf_submit(ctx, pData, sizeof(struct BlockIoData));
                }
            }

            //delete the previous record.
            g_blockIoStart.delete(&req);
        }
    }

    return 0;
}
"""

#g_bpfBlockIoHeader = """
#struct BlockIoRecord
#{
#    u64   m_startTs;
#    u64   m_endTs;
#    u32   m_tgid;
#    u32   m_pid;
#    u64   m_size;
#    u32   m_major;
#    u32   m_minor;
#    char  m_rwbs[8];
#};
#
#struct BlockIoKey
#{
#    u64     sector;
#    u32     device;
#};

#// store the start of the block IO Operation
#BPF_HASH(g_blockIoStart, struct BlockIoKey, struct BlockIoRecord);

#struct BlockIoData
#{
#    u32  m_dataType;
#    struct BlockIoRecord m_evtData[AMDT_DATA_GROUP_SIZE];
#};
#
#BPF_PERCPU_ARRAY(g_blockIoData, struct BlockIoData, 1);
#BPF_PERCPU_ARRAY(g_blockIoIndex, u32, 1);
#"""
#
#g_bpfBlockIoCode = """
#TRACEPOINT_PROBE(block, block_rq_insert)
#{
#    struct BlockIoRecord data = {};
#    u64 id = bpf_get_current_pid_tgid();
#    struct BlockIoKey key = {};
#
#    key.sector = (args->sector == 0) ? AMDT_UNKNOWN_SECTOR_ID : args->sector;
#    key.device = args->dev;
#
#    if (getFilterResult(AMDT_UNKNOWN_PID, bpf_get_smp_processor_id()) == true)
#    {
#        data.m_tgid     = AMDT_GET_TGID(id);
#        data.m_pid      = AMDT_GET_PID(id);
#        data.m_startTs  = bpf_ktime_get_ns();
#        data.m_size     = args->nr_sector;
#        data.m_endTs    = AMDT_UNKNOWN_TIMESTAMP;
#        data.m_major    = MAJOR(args->dev);
#        data.m_minor    = MINOR(args->dev);
#
#        if (bpf_probe_read_str(data.m_rwbs, 8, args->rwbs) < 0)
#        {
#            data.m_rwbs[0] = '\\0';
#        }
#
#        g_blockIoStart.update(&key, &data);
#    }
#
#    return 0;
#};
#
#TRACEPOINT_PROBE(block, block_rq_issue)
#{
#    struct BlockIoRecord *pStart = NULL;
#    u64 id = bpf_get_current_pid_tgid();
#    struct BlockIoKey key = {};
#
#    key.sector = (args->sector == 0) ? AMDT_UNKNOWN_SECTOR_ID : args->sector;
#    key.device = args->dev;
#
#    if (getFilterResult(AMDT_UNKNOWN_PID, bpf_get_smp_processor_id()) == true)
#    {
#        pStart = g_blockIoStart.lookup(&key);
#
#        if (pStart == NULL)
#        {
#            //block_rq_insert is not found, then consider the block_rq_issue as start of block operation
#            struct BlockIoRecord data = {};
#
#            data.m_tgid = AMDT_GET_TGID(id);
#            data.m_pid = AMDT_GET_PID(id);
#            data.m_startTs = bpf_ktime_get_ns();
#            data.m_size = (args->nr_sector);
#            data.m_endTs = AMDT_UNKNOWN_TIMESTAMP;
#            data.m_major = MAJOR(args->dev);
#            data.m_minor = MINOR(args->dev);
#
#            if (bpf_probe_read_str(data.m_rwbs, 8, args->rwbs) < 0)
#            {
#                data.m_rwbs[0] = '\\0';
#            }
#
#            g_blockIoStart.update(&key, &data);
#        }
#    }
#
#    return 0;
#};
#
#TRACEPOINT_PROBE(block, block_rq_complete)
#{
#    struct BlockIoRecord *pStart = NULL;
#    struct BlockIoKey key = {};
#
#    key.sector = (args->sector == 0) ? AMDT_UNKNOWN_SECTOR_ID : args->sector;
#    key.device = args->dev;
#
#    if (getFilterResult(AMDT_UNKNOWN_PID, AMDT_UNKNOWN_CORE_ID) == true)
#    {
#        pStart = g_blockIoStart.lookup(&key);
#
#        if (pStart)
#        {
#            //end of block Operation
#            u32 zero = 0;
#            struct BlockIoData *pData = g_blockIoData.lookup(&zero);
#            u32 *pIndex = g_blockIoIndex.lookup(&zero);
#
#            if ((pData == NULL) || (pIndex == NULL))
#            {
#                return 0;
#            }
#
#            pData->m_dataType = AMDT_OS_TRACE_DATA_TYPE_DISKIO;
#
#            if ((*pIndex >= 0) && (*pIndex < AMDT_DATA_GROUP_SIZE))
#            {
#                u32 i = *pIndex;
#                pData->m_evtData[i].m_startTs = pStart->m_startTs;
#                pData->m_evtData[i].m_endTs = bpf_ktime_get_ns();
#                pData->m_evtData[i].m_tgid = pStart->m_tgid;
#                pData->m_evtData[i].m_pid = pStart->m_pid;
#                pData->m_evtData[i].m_size = pStart->m_size;
#                pData->m_evtData[i].m_major = pStart->m_major;
#                pData->m_evtData[i].m_minor = pStart->m_minor;
#
#                if (bpf_probe_read_str(pData->m_evtData[i].m_rwbs, 8, pStart->m_rwbs) < 0)
#                {
#                    pData->m_evtData[i].m_rwbs[0] = '\\0';
#                }
#
#                (*pIndex)++;
#            }
#
#            if (*pIndex == AMDT_DATA_GROUP_SIZE)
#            {
#                (*pIndex) = 0;
#                g_perfBuffer.perf_submit(args, pData, sizeof(struct BlockIoData));
#            }
#
#            //delete the previous record.
#            g_blockIoStart.delete(&key);
#        }
#    }
#
#    return 0;
#};
#"""

g_bpfSysCallHeader = """
//store the sys call entry
BPF_HASH(g_sysCallEntry, u64, u64);
BPF_ARRAY(g_traceSysCalls, char, AMDT_MAX_SYSCALLS);

struct SysCallStats
{
    u64   m_count;
    u64   m_totalElapsedTime;
    u64   m_minElapsedTime;
    u64   m_maxElapsedTime;
};

//Store Sys calls stats
BPF_HASH(g_sysCallStats, u32, struct SysCallStats, AMDT_MAX_SYSCALLS);

#if defined(AMDT_PROCESS_FILTER)
struct SysCallRecord
{
    u64    m_startTs;
    u64    m_endTs;
    u64    m_sid;
    u32    m_tgid;
    u32    m_pid;
};

struct SysCallData
{
    u32 m_dataType;
    struct SysCallRecord m_evtData[AMDT_DATA_GROUP_SIZE];
};

BPF_PERCPU_ARRAY(g_sysCallData, struct SysCallData, 1);
BPF_PERCPU_ARRAY(g_sysCallIndex, u32, 1);
#endif //AMDT_PROCESS_FILTER
"""

g_bpfSysCallCode = """
//system call entry
TRACEPOINT_PROBE(raw_syscalls, sys_enter)
{
    if ((args->id >= 0) && (args->id < AMDT_MAX_SYSCALLS))
    {
        u64 id = bpf_get_current_pid_tgid();
        u32 sysId = (u32)args->id;
        char *pSysIdFound = g_traceSysCalls.lookup(&sysId);

        if (pSysIdFound && (*pSysIdFound == 1) && getFilterResult(AMDT_GET_PID(id), bpf_get_smp_processor_id()))
        {
            u64 key = (id << 32) | sysId;
            u64 ts = bpf_ktime_get_ns();

            g_sysCallEntry.update(&key, &ts);
            saveThreadName(AMDT_GET_PID(id));
        }
    }

    return 0;
};

//system call exit
TRACEPOINT_PROBE(raw_syscalls, sys_exit)
{
    if ((args->id >= 0) && (args->id < AMDT_MAX_SYSCALLS))
    {
        u64 id = bpf_get_current_pid_tgid();
        u32 sysId = (u32)args->id;
        u64 key = (id << 32) | sysId;

        u64 *pStartTs = g_sysCallEntry.lookup(&key);

        if (pStartTs)
        {
            u64 ts = bpf_ktime_get_ns();
            u64 duration = ts - (*pStartTs);

#if defined(AMDT_PROCESS_FILTER)
            if (duration >= AMDT_SYSCALL_THRESHOLD)
            {
                u32 zero = 0;
                struct SysCallData *pData = g_sysCallData.lookup(&zero);
                u32 *pIndex = g_sysCallIndex.lookup(&zero);

                if (pData && pIndex)
                {
                    u32 i = *pIndex;
                    pData->m_dataType = AMDT_OS_TRACE_DATA_TYPE_SYSCALL;

                    if ((i >= 0) && (i < AMDT_DATA_GROUP_SIZE))
                    {
                        pData->m_evtData[i].m_startTs = *pStartTs;
                        pData->m_evtData[i].m_endTs = ts;
                        pData->m_evtData[i].m_tgid = AMDT_GET_TGID(id);
                        pData->m_evtData[i].m_pid = AMDT_GET_PID(id);
                        pData->m_evtData[i].m_sid = args->id;
                        (*pIndex)++;
                    }

                    if (*pIndex == AMDT_DATA_GROUP_SIZE)
                    {
                        (*pIndex) = 0;
                        g_perfBuffer.perf_submit(args, pData, sizeof(struct SysCallData));
                    }
                }
            }
#if 0
            else
            {
                // increment the Skipped event count for system calls
                u32 index = AMDT_OS_TRACE_DATA_TYPE_SYSCALL;
                u64 *pCount = g_skippedEvents.lookup(&index);

                if (pCount)
                {
                    (*pCount)++;
                }
            }
#endif
#endif //AMDT_PROCESS_FILTER

            //update the syscall stats.
            struct SysCallStats *pStats = g_sysCallStats.lookup(&sysId);

            if (NULL != pStats)
            {
                ++(pStats->m_count);
                pStats->m_totalElapsedTime += duration;

                // update the min elapsed time if duration is less than previous min for this sys call
                if (duration < (pStats->m_minElapsedTime))
                {
                    pStats->m_minElapsedTime = duration;
                }

                // update the max elapsed time if duration is greater than previous max for this syscall
                if (duration > (pStats->m_maxElapsedTime))
                {
                    pStats->m_maxElapsedTime = duration;
                }
            }
            else
            {
                struct SysCallStats stats = {};

                stats.m_count = 1;
                stats.m_totalElapsedTime = duration;
                stats.m_minElapsedTime = duration;
                stats.m_maxElapsedTime = duration;

                g_sysCallStats.update(&sysId, &stats);
            }

            g_sysCallEntry.delete(&key);
        }
    }

    return 0;
};
"""

g_bpfPageFaultHeader = """
#if 0
struct PageFaultRecord
{
    u64   m_startTs;
    u32   m_tgid;
    u32   m_pid;
    u64   m_address;
    u64   m_ip;
    u64   m_errCode;
    bool  m_isKernel;
};

struct PageFaultData
{
    u32  m_dataType;
    struct PageFaultRecord m_evtData[AMDT_DATA_GROUP_SIZE];
};

BPF_PERCPU_ARRAY(g_pageFaultData, struct PageFaultData, 1);
BPF_PERCPU_ARRAY(g_pageFaultIndex, u32, 1);
#endif

struct PageFaultStats
{
    u64  m_userCount;
    u64  m_kernelCount;
};

BPF_HASH(g_pageFaultStats, u64, struct PageFaultStats, AMDT_MAX_THREADS);
"""

g_bpfPageFaultCode = """
TRACEPOINT_PROBE(exceptions, page_fault_user)
{
    u64 id = bpf_get_current_pid_tgid();

    if (getFilterResult(AMDT_GET_PID(id), bpf_get_smp_processor_id()) == true)
    {
#if 0
        u32 zero = 0;
        struct PageFaultData *pData = g_pageFaultData.lookup(&zero);
        u32 *pIndex = g_pageFaultIndex.lookup(&zero);

        if ((pData == NULL) || (pIndex == NULL))
        {
            return 0;
        }

        pData->m_dataType = AMDT_OS_TRACE_DATA_TYPE_PAGEFAULT;

        if ((*pIndex >= 0) && (*pIndex < AMDT_DATA_GROUP_SIZE))
        {
            u32 i = *pIndex;
            pData->m_evtData[i].m_startTs = bpf_ktime_get_ns();
            pData->m_evtData[i].m_address = args->address;
            pData->m_evtData[i].m_ip = args->ip;
            pData->m_evtData[i].m_errCode = args->error_code;
            pData->m_evtData[i].m_tgid = AMDT_GET_TGID(id);
            pData->m_evtData[i].m_pid = AMDT_GET_PID(id);
            pData->m_evtData[i].m_isKernel = false;
            (*pIndex)++;
        }

        if (*pIndex == AMDT_DATA_GROUP_SIZE)
        {
            (*pIndex) = 0;
            g_perfBuffer.perf_submit(args, pData, sizeof(struct PageFaultData));
        }
#endif

        struct PageFaultStats *pStats = g_pageFaultStats.lookup(&id);

        if (pStats)
        {
            ++(pStats->m_userCount);
        }
        else
        {
            struct PageFaultStats stats = {};

            stats.m_userCount = 1;
            stats.m_kernelCount = 0;
            g_pageFaultStats.update(&id, &stats);
        }

        saveThreadName(AMDT_GET_PID(id));
    }

    return 0;
};

TRACEPOINT_PROBE(exceptions, page_fault_kernel)
{
    u64 id = bpf_get_current_pid_tgid();

    if (getFilterResult(AMDT_GET_PID(id), bpf_get_smp_processor_id()) == true)
    {
#if 0
        u32 zero = 0;
        struct PageFaultData *pData = g_pageFaultData.lookup(&zero);
        u32 *pIndex = g_pageFaultIndex.lookup(&zero);

        if ((pData == NULL) || (pIndex == NULL))
        {
            return 0;
        }

        pData->m_dataType = AMDT_OS_TRACE_DATA_TYPE_PAGEFAULT;

        if ((*pIndex >= 0) && (*pIndex < AMDT_DATA_GROUP_SIZE))
        {
            u32 i = *pIndex;
            pData->m_evtData[i].m_startTs = bpf_ktime_get_ns();
            pData->m_evtData[i].m_address = args->address;
            pData->m_evtData[i].m_ip = args->ip;
            pData->m_evtData[i].m_errCode = args->error_code;
            pData->m_evtData[i].m_tgid = AMDT_GET_TGID(id);
            pData->m_evtData[i].m_pid = AMDT_GET_PID(id);
            pData->m_evtData[i].m_isKernel = true;
            (*pIndex)++;
        }

        if (*pIndex == AMDT_DATA_GROUP_SIZE)
        {
            (*pIndex) = 0;
            g_perfBuffer.perf_submit(args, pData, sizeof(struct PageFaultData));
        }
#endif

        struct PageFaultStats *pStats = g_pageFaultStats.lookup(&id);

        if (pStats)
        {
            ++(pStats->m_kernelCount);
        }
        else
        {
            struct PageFaultStats stats = {};

            stats.m_userCount = 0;
            stats.m_kernelCount = 1;
            g_pageFaultStats.update(&id, &stats);
        }

        saveThreadName(AMDT_GET_PID(id));
    }

    return 0;
};
"""

g_bpfFuncCountHeader = """
struct FuncCountRecord
{
    u64     m_startTs;
    u64     m_endTs;
    u32     m_fid;
    u32     m_tgid;
    u32     m_pid;
};

struct FuncCountData
{
    u32 m_dataType;
    struct FuncCountRecord m_evtData[AMDT_DATA_GROUP_SIZE];
};

BPF_PERCPU_ARRAY(g_funcCountData, struct FuncCountData, 1);
BPF_PERCPU_ARRAY(g_funcCountIndex, u32, 1);

struct FuncCountStats
{
    u64   m_count;
    u64   m_totalElapsedTime;
    u64   m_minElapsedTime;
    u64   m_maxElapsedTime;
};

BPF_HASH(g_funcCountEntry, u64, u64);
BPF_HASH(g_funcCountStats, u32, struct FuncCountStats, AMDT_NUM_FUNCTIONS);
"""

g_bpfFuncCountCode = """
//AMDT_PROBE_FUNCTION is replaced with specific function with function id.
int AMDT_PROBE_FUNCTION(void *ctx)
{
    u64 id = bpf_get_current_pid_tgid();

    if (getFilterResult(AMDT_GET_PID(id), bpf_get_smp_processor_id()))
    {
        u64 key = (id << 32) | AMDT_FID;
        u64 ts = bpf_ktime_get_ns();

        g_funcCountEntry.update(&key, &ts);
    }

    return 0;
}

//AMDT_PROBE_FUNCTION_RET is replaced with specific function with function id.
int AMDT_PROBE_FUNCTION_RET(void *ctx)
{
    u64 id = bpf_get_current_pid_tgid();
    u64 key = (id << 32) | AMDT_FID;
    u64 *pStartTs = g_funcCountEntry.lookup(&key);

    if (pStartTs)
    {
        u64 ts = bpf_ktime_get_ns();
        u64 duration = ts - (*pStartTs);

        if (duration >= AMDT_FUNCCOUNT_THRESHOLD)
        {
            u32 zero = 0;

            struct FuncCountData *pData = g_funcCountData.lookup(&zero);
            u32 *pIndex = g_funcCountIndex.lookup(&zero);

            if (pData && pIndex)
            {
                u32 i = *pIndex;
                pData->m_dataType = AMDT_OS_TRACE_DATA_TYPE_FUNCCOUNT;

                if ((i >= 0) && (i < AMDT_DATA_GROUP_SIZE))
                {
                    pData->m_evtData[i].m_startTs = *pStartTs;
                    pData->m_evtData[i].m_endTs = ts;
                    pData->m_evtData[i].m_tgid = AMDT_GET_TGID(id);
                    pData->m_evtData[i].m_pid = AMDT_GET_PID(id);
                    pData->m_evtData[i].m_fid = AMDT_FID;
                    (*pIndex)++;
                }

                if (*pIndex == AMDT_DATA_GROUP_SIZE)
                {
                    (*pIndex) = 0;
                    g_perfBuffer.perf_submit(ctx, pData, sizeof(struct FuncCountData));
                }
            }
        }

        u32 fid = AMDT_FID;
        //update the funccount stats.
        struct FuncCountStats *pStats = g_funcCountStats.lookup(&fid);

        if (NULL != pStats)
        {
            ++(pStats->m_count);
            pStats->m_totalElapsedTime += duration;

            // update the min elapsed time if duration is less than previous min for this function
            if (duration < (pStats->m_minElapsedTime))
            {
                pStats->m_minElapsedTime = duration;
            }

            // update the max elapsed time if duration is greater than previous max for this function
            if (duration > (pStats->m_maxElapsedTime))
            {
                pStats->m_maxElapsedTime = duration;
            }
        }
        else
        {
            struct FuncCountStats stats = {};

            stats.m_count = 1;
            stats.m_totalElapsedTime = duration;
            stats.m_minElapsedTime = duration;
            stats.m_maxElapsedTime = duration;

            g_funcCountStats.update(&fid, &stats);
        }

        g_funcCountEntry.delete(&key);
    }

    return 0;
}
"""

g_bpfPthreadHeader = """
struct PthreadRecord
{
    u64    m_startTs;
    u64    m_endTs;
    u32    m_tgid;
    u32    m_pid;
    u64    m_pthreadId;
    int    m_stackId;
    u32    m_fid;
    u64    m_address;
    u16    m_status;
    u16    m_lockType;
};

#ifdef AMDT_PTHREAD_CALLSTACK_COLLECT
    //map with key is stack id and value is Pid
    BPF_HASH(g_pthreadStackIdToPid, int, u64, AMDT_CALLSTACK_SIZE);
    //Stack trace map for Pthread API.
    BPF_STACK_TRACE(g_pthread, AMDT_CALLSTACK_SIZE);
#endif
//Hash is used to identify who has taken the lock and release the lock
BPF_HASH(g_pthreadLocks, u64, struct PthreadRecord);

struct PthreadData
{
    u32 m_dataType;
    struct PthreadRecord m_evtData[AMDT_DATA_GROUP_SIZE];
};

BPF_PERCPU_ARRAY(g_pthreadData, struct PthreadData, 1);
BPF_PERCPU_ARRAY(g_pthreadIndex, u32, 1);

//lock status
enum PthreadStatus
{
    AMDT_LOCK_STATUS_NONE,
    AMDT_LOCK_ACQUIRE_SUCCESS,
    AMDT_LOCK_RELEASE_SUCCESS,
    AMDT_LOCK_ACQUIRE_FAILED,
    AMDT_LOCK_RELEASE_FAILED,
};

//Type of lock
enum PthreadLockType
{
    AMDT_LOCK_TYPE_NONE,
    AMDT_LOCK_TYPE_MUTEX,
    AMDT_LOCK_TYPE_CV
};
"""

g_bpfPthreadCode = """
//Pthread API enter.
//mutex_addr : lock adress
//status : lock status
//lockType : mutex or condition Variable
//fid : function Id.
static inline int tracePthreadEnter(struct pt_regs *ctx, void *mutex_addr, u16 lockType, u32 fid)
{
    u64 id = bpf_get_current_pid_tgid();

    if (isPidTraced(AMDT_GET_PID(id)))
    {
        u64 key = (id << 32) | fid;

#ifdef AMDT_PTHREAD_CALLSTACK_COLLECT
        //store stack traces into map and return the stackID.
        int stackId = g_pthread.get_stackid(ctx, BPF_F_USER_STACK);

        if (stackId >= 0)
        {
            g_pthreadStackIdToPid.update(&stackId, &id);
        }
#else
        int stackId = AMDT_UNKNOWN_STACK_ID;
#endif
        struct PthreadRecord rec = {};

        rec.m_stackId = stackId;
        rec.m_address = (u64)mutex_addr;
        rec.m_startTs = bpf_ktime_get_ns();

        g_pthreadLocks.update(&key, &rec);
        saveThreadName(AMDT_GET_PID(id));
        return 0;
    }

    return -1;
}

//Pthread API Exit.
//retValue : return value by API
//status : lock status
//lockType : mutex or condition Variable
//fid : function Id.
static inline int tracePthreadExit(struct pt_regs *ctx, int retValue, u16 lockType, u32 fid)
{
    u64 id = bpf_get_current_pid_tgid();
    u64 key = (id << 32) | fid;
    struct PthreadRecord *pEntry = g_pthreadLocks.lookup(&key);

    if (pEntry)
    {
        u32 zero = 0;

        struct PthreadData *pData = g_pthreadData.lookup(&zero);
        u32 *pIndex = g_pthreadIndex.lookup(&zero);
        u64 ts = bpf_ktime_get_ns();

#ifdef AMDT_FUNCTION_COUNT
        incrementFuncCount(fid, (ts - pEntry->m_startTs));
#endif

        if (pData && pIndex)
        {
            u32 i = *pIndex;
            pData->m_dataType = AMDT_OS_TRACE_DATA_TYPE_PTHREAD;

            if ((i >= 0) && (i < AMDT_DATA_GROUP_SIZE))
            {
                pData->m_evtData[i].m_startTs = pEntry->m_startTs;
                pData->m_evtData[i].m_endTs = ts;
                pData->m_evtData[i].m_stackId = pEntry->m_stackId;
                pData->m_evtData[i].m_tgid = AMDT_GET_TGID(id);
                pData->m_evtData[i].m_pid = AMDT_GET_PID(id);
                pData->m_evtData[i].m_lockType = lockType;
                pData->m_evtData[i].m_fid = fid;

                switch(fid)
                {
                    case AMDT_PTHREAD_MUTEX_LOCK:
                    case AMDT_PTHREAD_MUTEX_TRYLOCK:
                    case AMDT_PTHREAD_MUTEX_TIMEDLOCK:
                    case AMDT_PTHREAD_COND_WAIT:
                    case AMDT_PTHREAD_COND_TIMEDWAIT:
                        // condition wait will release the lock first
                        if (((fid == AMDT_PTHREAD_COND_WAIT) || (fid == AMDT_PTHREAD_COND_TIMEDWAIT)) &&
                            (lockType == AMDT_LOCK_TYPE_MUTEX))
                        {
                            pData->m_evtData[i].m_status = (retValue == 0) ? AMDT_LOCK_RELEASE_SUCCESS : AMDT_LOCK_RELEASE_FAILED;
                        }
                        else
                        {
                            pData->m_evtData[i].m_status = (retValue == 0)? AMDT_LOCK_ACQUIRE_SUCCESS: AMDT_LOCK_ACQUIRE_FAILED;
                        }

                        pData->m_evtData[i].m_address = pEntry->m_address;
                        pData->m_evtData[i].m_pthreadId = 0;
                        break;
                    case AMDT_PTHREAD_MUTEX_UNLOCK:
                    case AMDT_PTHREAD_COND_SIGNAL:
                    case AMDT_PTHREAD_COND_BROADCAST:
                        pData->m_evtData[i].m_status = (retValue == 0)? AMDT_LOCK_RELEASE_SUCCESS: AMDT_LOCK_RELEASE_FAILED;
                        pData->m_evtData[i].m_address = pEntry->m_address;
                        pData->m_evtData[i].m_pthreadId = 0;
                        break;
                    case AMDT_PTHREAD_CREATE:
                    case AMDT_PTHREAD_JOIN:
                        if (retValue == 0)
                        {
                            bpf_probe_read(&pData->m_evtData[i].m_pthreadId, sizeof(u64), (u64 *)pEntry->m_address);
                        }
                        else
                        {
                            pData->m_evtData[i].m_pthreadId = 0;
                        }

                        pData->m_evtData[i].m_address = AMDT_UNKNOWN_ADDRESS;
                        pData->m_evtData[i].m_status = AMDT_LOCK_STATUS_NONE;
                        break;
                    default:
                        pData->m_evtData[i].m_pthreadId = 0;
                        pData->m_evtData[i].m_address = pEntry->m_address;
                        pData->m_evtData[i].m_status = AMDT_LOCK_STATUS_NONE;
                }

                (*pIndex)++;
            }

            if (*pIndex == AMDT_DATA_GROUP_SIZE)
            {
                (*pIndex) = 0;
                g_perfBuffer.perf_submit(ctx, pData, sizeof(struct PthreadData));
            }
        }

        g_pthreadLocks.delete(&key);
    }

    return 0;
}

//TODO : Need to think of creating a simple template for below functions
int pthread_create_enter(struct pt_regs *ctx, void *thread)
{
    return tracePthreadEnter(ctx, thread, AMDT_LOCK_TYPE_NONE, AMDT_PTHREAD_CREATE);
}

int pthread_create_exit(struct pt_regs *ctx)
{
    return tracePthreadExit(ctx, PT_REGS_RC(ctx), AMDT_LOCK_TYPE_NONE, AMDT_PTHREAD_CREATE);
}

int pthread_join_enter(struct pt_regs *ctx, void *thread)
{
    return tracePthreadEnter(ctx, thread, AMDT_LOCK_TYPE_NONE, AMDT_PTHREAD_JOIN);
}

int pthread_join_exit(struct pt_regs *ctx)
{
    return tracePthreadExit(ctx, PT_REGS_RC(ctx), AMDT_LOCK_TYPE_NONE, AMDT_PTHREAD_JOIN);
}

int pthread_exit_enter(struct pt_regs *ctx, void *retVal)
{
    return tracePthreadEnter(ctx, AMDT_UNKNOWN_ADDRESS, AMDT_LOCK_TYPE_NONE, AMDT_PTHREAD_EXIT);
}

int pthread_exit_exit(struct pt_regs *ctx)
{
    return tracePthreadExit(ctx, PT_REGS_RC(ctx), AMDT_LOCK_TYPE_NONE, AMDT_PTHREAD_EXIT);
}

int pthread_mutex_lock_enter(struct pt_regs *ctx, void *mutex_addr)
{
    return tracePthreadEnter(ctx, mutex_addr, AMDT_LOCK_TYPE_MUTEX, AMDT_PTHREAD_MUTEX_LOCK);
}

int pthread_mutex_lock_exit(struct pt_regs *ctx)
{
    return tracePthreadExit(ctx, PT_REGS_RC(ctx), AMDT_LOCK_TYPE_MUTEX, AMDT_PTHREAD_MUTEX_LOCK);
}

int pthread_mutex_trylock_enter(struct pt_regs *ctx, void *mutex_addr)
{
    return tracePthreadEnter(ctx, mutex_addr, AMDT_LOCK_TYPE_MUTEX, AMDT_PTHREAD_MUTEX_TRYLOCK);
}

int pthread_mutex_trylock_exit(struct pt_regs *ctx)
{
    return tracePthreadExit(ctx, PT_REGS_RC(ctx), AMDT_LOCK_TYPE_MUTEX, AMDT_PTHREAD_MUTEX_TRYLOCK);
}

int pthread_mutex_timedlock_enter(struct pt_regs *ctx, void *mutex_addr)
{
    return tracePthreadEnter(ctx, mutex_addr, AMDT_LOCK_TYPE_MUTEX, AMDT_PTHREAD_MUTEX_TIMEDLOCK);
}

int pthread_mutex_timedlock_exit(struct pt_regs *ctx)
{
    return tracePthreadExit(ctx, PT_REGS_RC(ctx), AMDT_LOCK_TYPE_MUTEX, AMDT_PTHREAD_MUTEX_TIMEDLOCK);
}

int pthread_mutex_unlock_enter(struct pt_regs *ctx, void *mutex_addr)
{
    return tracePthreadEnter(ctx, mutex_addr, AMDT_LOCK_TYPE_MUTEX, AMDT_PTHREAD_MUTEX_UNLOCK);
}

int pthread_mutex_unlock_exit(struct pt_regs *ctx)
{
    return tracePthreadExit(ctx, PT_REGS_RC(ctx), AMDT_LOCK_TYPE_MUTEX, AMDT_PTHREAD_MUTEX_UNLOCK);
}

int pthread_cond_wait_enter(struct pt_regs *ctx, void *cond_addr, void *mutex_addr)
{
    tracePthreadEnter(ctx, mutex_addr, AMDT_LOCK_TYPE_MUTEX, AMDT_PTHREAD_COND_WAIT);
    tracePthreadExit(ctx, 0, AMDT_LOCK_TYPE_MUTEX, AMDT_PTHREAD_COND_WAIT);

    return tracePthreadEnter(ctx, cond_addr, AMDT_LOCK_TYPE_CV, AMDT_PTHREAD_COND_WAIT);
}

int pthread_cond_wait_exit(struct pt_regs *ctx)
{
    return tracePthreadExit(ctx, PT_REGS_RC(ctx), AMDT_LOCK_TYPE_CV, AMDT_PTHREAD_COND_WAIT);
}

int pthread_cond_timedwait_enter(struct pt_regs *ctx, void *cond_addr, void *mutex_addr)
{
    tracePthreadEnter(ctx, mutex_addr, AMDT_LOCK_TYPE_MUTEX, AMDT_PTHREAD_COND_TIMEDWAIT);
    tracePthreadExit(ctx, 0, AMDT_LOCK_TYPE_MUTEX, AMDT_PTHREAD_COND_TIMEDWAIT);

    return tracePthreadEnter(ctx, cond_addr, AMDT_LOCK_TYPE_CV, AMDT_PTHREAD_COND_TIMEDWAIT);
}

int pthread_cond_timedwait_exit(struct pt_regs *ctx)
{
    return tracePthreadExit(ctx, PT_REGS_RC(ctx), AMDT_LOCK_TYPE_CV, AMDT_PTHREAD_COND_TIMEDWAIT);
}

int pthread_cond_signal_enter(struct pt_regs *ctx, void *cond_addr)
{
    return tracePthreadEnter(ctx, cond_addr, AMDT_LOCK_TYPE_CV, AMDT_PTHREAD_COND_SIGNAL);
}

int pthread_cond_signal_exit(struct pt_regs *ctx, void *cond_addr)
{
    return tracePthreadExit(ctx, PT_REGS_RC(ctx), AMDT_LOCK_TYPE_CV, AMDT_PTHREAD_COND_SIGNAL);
}

int pthread_cond_broadcast_enter(struct pt_regs *ctx, void *cond_addr)
{
    return tracePthreadEnter(ctx, cond_addr, AMDT_LOCK_TYPE_CV, AMDT_PTHREAD_COND_BROADCAST);
}

int pthread_cond_broadcast_exit(struct pt_regs *ctx, void *cond_addr)
{
    return tracePthreadExit(ctx, PT_REGS_RC(ctx), AMDT_LOCK_TYPE_CV, AMDT_PTHREAD_COND_BROADCAST);
}
"""

g_bpfLibTraceHeader = """
struct LibTraceRecord
{
    u64    m_startTs;
    u32    m_tgid;
    u32    m_pid;
    int    m_stackId;
    u32    m_fid;  //function id
};

#ifdef AMDT_LIBTRACE_CALLSTACK_COLLECT
    //stackId to Pid map
    BPF_HASH(g_libTraceStackIdToPid, int, u64, AMDT_CALLSTACK_SIZE);
    //Stack traces for function in library of executable.
    BPF_STACK_TRACE(g_libTrace, AMDT_CALLSTACK_SIZE);
#endif

struct LibTraceData
{
    u32 m_dataType;
    struct LibTraceRecord m_evtData[AMDT_DATA_GROUP_SIZE];
};

BPF_PERCPU_ARRAY(g_libTraceData, struct LibTraceData, 1);
BPF_PERCPU_ARRAY(g_libTraceIndex, u32, 1);
"""

g_bpfLibTraceCode = """
//AMDT_PROBE_FUNCTION is replaced by particular function with function ID.
int AMDT_PROBE_FUNCTION(void *ctx)
{
    //AMDT_FID indicates the function ID.
    u32 loc = AMDT_FID;
    u32 zero = 0;
    u64 id = bpf_get_current_pid_tgid();

    if (getFilterResult(AMDT_GET_PID(id), bpf_get_smp_processor_id()) == true)
    {
#ifdef AMDT_LIBTRACE_CALLSTACK_COLLECT
        int stackId = g_libTrace.get_stackid(ctx, BPF_F_USER_STACK);

        if (stackId >= 0)
        {
            g_libTraceStackIdToPid.update(&stackId, &id);
        }
#else
        int stackId = AMDT_UNKNOWN_STACK_ID;
#endif

        struct LibTraceData *pData = g_libTraceData.lookup(&zero);
        u32 *pIndex = g_libTraceIndex.lookup(&zero);

        if ((pData == NULL) || (pIndex == NULL))
        {
            return 0;
        }

        pData->m_dataType = AMDT_OS_TRACE_DATA_TYPE_LIBTRACE;

        if ((*pIndex >= 0) && (*pIndex < AMDT_DATA_GROUP_SIZE))
        {
            u32 i = *pIndex;
            pData->m_evtData[i].m_startTs = bpf_ktime_get_ns();
            pData->m_evtData[i].m_stackId = stackId;
            pData->m_evtData[i].m_tgid = AMDT_GET_TGID(id);
            pData->m_evtData[i].m_pid = AMDT_GET_PID(id);
            pData->m_evtData[i].m_fid = loc;
            (*pIndex)++;
        }

        if (*pIndex == AMDT_DATA_GROUP_SIZE)
        {
            (*pIndex) = 0;
            g_perfBuffer.perf_submit(ctx, pData, sizeof(struct LibTraceData));
        }
    }

    return 0;
}
"""

g_bpfIoTraceHeader = """
struct IoTraceRecord
{
    u64     m_startTs;
    u64     m_endTs;
    u32     m_tgid;
    u32     m_pid;
    int     m_stackId;
    u32     m_fid;
    u64     m_size;
    u16     m_ioType;
    int     m_fd;
};

//store the entry into IO system calls.
BPF_HASH(g_ioTraceEntry, u64, struct IoTraceRecord);

#ifdef AMDT_IOTRACE_CALLSTACK_COLLECT
    //stack ID to Pid map
    BPF_HASH(g_ioTraceStackIdToPid, int, u64, AMDT_CALLSTACK_SIZE);
    //Stack trace map for IO system calls
    BPF_STACK_TRACE(g_ioTrace, AMDT_CALLSTACK_SIZE);
#endif

struct IoTraceData
{
    u32 m_dataType;
    struct IoTraceRecord m_evtData[AMDT_DATA_GROUP_SIZE];
};

BPF_PERCPU_ARRAY(g_ioTraceData, struct IoTraceData, 1);
BPF_PERCPU_ARRAY(g_ioTraceIndex, u32, 1);

//IO operation type
enum IoOperationType
{
    AMDT_OPERATION_NONE=0,
    AMDT_OPERATION_READ,
    AMDT_OPERATION_WRITE,
    AMDT_OPERATION_FLUSH,
};
"""

g_bpfIoTraceCode = """
static inline int traceIoEnter(struct pt_regs *ctx, int fd, size_t count, u16 ioType, u32 fid)
{
    u64 id = bpf_get_current_pid_tgid();

    if (isPidTraced(AMDT_GET_PID(id)))
    {
        if (count >= AMDT_IOTRACE_THRESHOLD)
        {
            struct IoTraceRecord rec = {};
#ifdef AMDT_IOTRACE_CALLSTACK_COLLECT
            int stackId = g_ioTrace.get_stackid(ctx, BPF_F_USER_STACK);

            if (stackId >= 0)
            {
                g_ioTraceStackIdToPid.update(&stackId, &id);
            }
#else
            int stackId = AMDT_UNKNOWN_STACK_ID;
#endif

            rec.m_startTs = bpf_ktime_get_ns();
            rec.m_endTs = 0;
            rec.m_ioType = ioType;
            rec.m_tgid = AMDT_GET_TGID(id);
            rec.m_pid = AMDT_GET_PID(id);
            rec.m_fd = fd;
            rec.m_size = count;
            rec.m_stackId = stackId;
            rec.m_fid = fid;

            g_ioTraceEntry.update(&id, &rec);
        }
#if 0
        else
        {
            // increment the Skipped event count for I/O Trace
            u32 index = AMDT_OS_TRACE_DATA_TYPE_IOTRACE;
            u64 *pCount = g_skippedEvents.lookup(&index);

            if (pCount)
            {
                (*pCount)++;
            }
        }
#endif

        saveThreadName(AMDT_GET_PID(id));
        return 0;
    }

    return -1;
}

static inline int traceIoExit(struct pt_regs *ctx, ssize_t size)
{
    u64 id = bpf_get_current_pid_tgid();
    struct IoTraceRecord *pEntry = g_ioTraceEntry.lookup(&id);

    if (pEntry)
    {
        u32 zero = 0;
        u64 ts = bpf_ktime_get_ns();

#ifdef AMDT_FUNCTION_COUNT
        incrementFuncCount(pEntry->m_fid, (ts - pEntry->m_startTs));
#endif

        struct IoTraceData *pData = g_ioTraceData.lookup(&zero);
        u32 *pIndex = g_ioTraceIndex.lookup(&zero);

        if (pData && pIndex)
        {
            u32 i = *pIndex;
            pData->m_dataType = AMDT_OS_TRACE_DATA_TYPE_IOTRACE;

            if ((i >= 0) && (i < AMDT_DATA_GROUP_SIZE))
            {
                pData->m_evtData[i].m_startTs = pEntry->m_startTs;
                pData->m_evtData[i].m_endTs = ts;
                pData->m_evtData[i].m_stackId = pEntry->m_stackId;
                pData->m_evtData[i].m_tgid = pEntry->m_tgid;
                pData->m_evtData[i].m_pid = pEntry->m_pid;
                pData->m_evtData[i].m_size = size;
                pData->m_evtData[i].m_fd = pEntry->m_fd;
                pData->m_evtData[i].m_ioType = pEntry->m_ioType;
                pData->m_evtData[i].m_fid = pEntry->m_fid;
                (*pIndex)++;
            }

            if (*pIndex == AMDT_DATA_GROUP_SIZE)
            {
                (*pIndex) = 0;
                g_perfBuffer.perf_submit(ctx, pData, sizeof(struct IoTraceData));
            }
        }

        g_ioTraceEntry.delete(&id);
    }

    return 0;
}

//TODO: Need to think of creating a template for below code
int read_enter(struct pt_regs *ctx, int fd, void *buf, size_t count)
{
    return traceIoEnter(ctx, fd, count, AMDT_OPERATION_READ, AMDT_READ);
}

int read_exit(struct pt_regs *ctx)
{
    return traceIoExit(ctx, PT_REGS_RC(ctx));
}

int write_enter(struct pt_regs *ctx, int fd, void *buf, size_t count)
{
    return traceIoEnter(ctx, fd, count, AMDT_OPERATION_WRITE, AMDT_WRITE);
}

int write_exit(struct pt_regs *ctx)
{
    return traceIoExit(ctx, PT_REGS_RC(ctx));
}

int pread_enter(struct pt_regs *ctx, int fd, void *buf, size_t count)
{
    return traceIoEnter(ctx, fd, count, AMDT_OPERATION_READ, AMDT_PREAD);
}

int pread_exit(struct pt_regs *ctx)
{
    return traceIoExit(ctx, PT_REGS_RC(ctx));
}

int pwrite_enter(struct pt_regs *ctx, int fd, void *buf, size_t count)
{
    return traceIoEnter(ctx, fd, count, AMDT_OPERATION_WRITE, AMDT_PWRITE);
}

int pwrite_exit(struct pt_regs *ctx)
{
    return traceIoExit(ctx, PT_REGS_RC(ctx));
}

int aio_read_enter(struct pt_regs *ctx, struct iocb *aiocbp)
{
    return traceIoEnter(ctx, aiocbp->aio_fildes, aiocbp->aio_nbytes, AMDT_OPERATION_READ, AMDT_AIO_READ);
}

int aio_read_exit(struct pt_regs *ctx)
{
    return traceIoExit(ctx, PT_REGS_RC(ctx));
}

int aio_write_enter(struct pt_regs *ctx, struct iocb *aiocbp)
{
    return traceIoEnter(ctx, aiocbp->aio_fildes, aiocbp->aio_nbytes, AMDT_OPERATION_WRITE, AMDT_AIO_WRITE);
}

int aio_write_exit(struct pt_regs *ctx)
{
    return traceIoExit(ctx, PT_REGS_RC(ctx));
}

int io_submit_enter(struct pt_regs *ctx, aio_context_t io_ctx, long nr, struct iocb **ios)
{
    u16 type = AMDT_OPERATION_NONE;

    if (ios[0]->aio_lio_opcode == IOCB_CMD_PREAD)
    {
        type = AMDT_OPERATION_READ;
    }
    else if (ios[0]->aio_lio_opcode == IOCB_CMD_PWRITE)
    {
        type = AMDT_OPERATION_WRITE;
    }

#if 0
    for (long i = 0; i < nr; ++i)
    {
        traceIoEnter(ctx, ios[i]->aio_fildes, ios[i]->aio_nbytes, type, AMDT_IO_SUBMIT);
    }
#endif

    // TODO : Loops are not supported to traverse the each iocb. updating the file descriptor with no of requests.
    return traceIoEnter(ctx, (int)nr, ios[0]->aio_nbytes, type, AMDT_IO_SUBMIT);
}

int io_submit_exit(struct pt_regs *ctx)
{
    return traceIoExit(ctx, PT_REGS_RC(ctx));
}
"""

g_bpfMemTraceHeader = """
// Filled while return from alloc function
struct AllocRecord
{
    u64     m_startTs;
    u64     m_endTs;
    u32     m_tgid;
    u32     m_pid;
    int     m_stackId;
    u32     m_fid;
    u64     m_address;
    u64     m_size;
};

// Filled while entering into alloc function
struct MemEntryRecord
{
    u64     m_startTs;
    u64     m_size;
};

struct Key
{
    u64 id;
    u64 address;
};

//Store the entry of malloc like APIs
BPF_HASH(g_memEntry, u64, struct MemEntryRecord);

//Store the MemAllocs, if it is not empty by the end of profile, then
//this list indicates the leak memory.
BPF_HASH(g_memAllocs, struct Key, struct AllocRecord, 1000000);

#ifdef AMDT_MEMTRACE_CALLSTACK_COLLECT
    //Stack Id to Pid map
    BPF_HASH(g_memTraceStackIdToPid, int, u64, AMDT_CALLSTACK_SIZE);
    //Stack traces for memory allocs.
    BPF_STACK_TRACE(g_memTrace, AMDT_CALLSTACK_SIZE);
#endif

struct MemTraceData
{
    u32 m_dataType;
    struct AllocRecord m_evtData[AMDT_DATA_GROUP_SIZE];
};

BPF_PERCPU_ARRAY(g_memTraceData, struct MemTraceData, 1);
BPF_PERCPU_ARRAY(g_memTraceIndex, u32, 1);
"""

g_bpfMemTraceCode = """
//enter into malloc like APIs
static inline int traceAllocEnter(struct pt_regs *ctx, size_t size)
{
    u64 id = bpf_get_current_pid_tgid();

    if (isPidTraced(AMDT_GET_PID(id)))
    {
        if (size >= AMDT_MEMSIZE_THRESHOLD)
        {
            struct MemEntryRecord rec = {};

#ifdef AMDT_MEMTRACE_CALLSTACK_COLLECT
            int stackId = g_memTrace.get_stackid(ctx, BPF_F_USER_STACK);

            if (stackId >= 0)
            {
                g_memTraceStackIdToPid.update(&stackId, &id);
            }
#endif

            rec.m_size = size;
            rec.m_startTs = bpf_ktime_get_ns();

            g_memEntry.update(&id, &rec);
        }
#if 0
        else
        {
            // increment the Skipped event count for Memory Trace
            u32 index = AMDT_OS_TRACE_DATA_TYPE_MEMTRACE;
            u64 *pCount = g_skippedEvents.lookup(&index);

            if (pCount)
            {
                (*pCount)++;
            }
        }
#endif
        return 0;
    }

    return -1;
}

//exit from alloc APIs
static inline int traceAllocReturn(struct pt_regs *ctx, u64 address, u32 fid)
{
    u64 id = bpf_get_current_pid_tgid();
    struct MemEntryRecord *pEntry = g_memEntry.lookup(&id);

    if (pEntry)
    {
        u32 tgid = AMDT_GET_TGID(id);

        if (address != 0)
        {
            struct Key key = {};
            struct AllocRecord rec = {};

            key.address = address;
            key.id = tgid;

            rec.m_address = address;
            rec.m_tgid    = tgid;
            rec.m_pid     = AMDT_GET_PID(id);

            g_memAllocs.update(&key, &rec);
        }

        u32 zero = 0;
        u64 ts = bpf_ktime_get_ns();

#ifdef AMDT_FUNCTION_COUNT
        incrementFuncCount(fid, (ts - pEntry->m_startTs));
#endif

        struct MemTraceData *pData = g_memTraceData.lookup(&zero);
        u32 *pIndex = g_memTraceIndex.lookup(&zero);

        if (pData && pIndex)
        {
            u32 i = *pIndex;
            pData->m_dataType = AMDT_OS_TRACE_DATA_TYPE_MEMTRACE;

            if ((i >= 0) && (i < AMDT_DATA_GROUP_SIZE))
            {
                pData->m_evtData[i].m_startTs   = pEntry->m_startTs;
                pData->m_evtData[i].m_endTs     = ts;
                pData->m_evtData[i].m_stackId   = AMDT_UNKNOWN_STACK_ID;
                pData->m_evtData[i].m_tgid      = tgid;
                pData->m_evtData[i].m_pid       = AMDT_GET_PID(id);
                pData->m_evtData[i].m_size      = pEntry->m_size;
                pData->m_evtData[i].m_address   = address;
                pData->m_evtData[i].m_fid       = fid;
                (*pIndex)++;
            }

            if (*pIndex == AMDT_DATA_GROUP_SIZE)
            {
                (*pIndex) = 0;
                g_perfBuffer.perf_submit(ctx, pData, sizeof(struct MemTraceData));
            }
        }

        g_memEntry.delete(&id);
    }

    return 0;
}

static inline int traceAllocExit(struct pt_regs *ctx, u32 fid)
{
    return traceAllocReturn(ctx, PT_REGS_RC(ctx), fid);
}

//enter into free.
static inline int traceFreeEnter(struct pt_regs *ctx, void *address, bool store)
{
    u64 id = bpf_get_current_pid_tgid();
    struct Key key = {};

    key.address = (u64)address;
    key.id = AMDT_GET_TGID(id);

    struct AllocRecord *pAlloc = g_memAllocs.lookup(&key);

    if (pAlloc)
    {
        g_memAllocs.delete(&key);
    }

    if (store && isPidTraced(AMDT_GET_PID(id)))
    {
        struct MemEntryRecord rec = {};

        rec.m_size = 0;
        rec.m_startTs = bpf_ktime_get_ns();

        g_memEntry.update(&id, &rec);
    }

    return 0;
}

static inline int traceFreeExit(struct pt_regs *ctx, u32 fid)
{
    u64 id = bpf_get_current_pid_tgid();
    struct MemEntryRecord *pEntry = g_memEntry.lookup(&id);

    if (pEntry)
    {
#ifdef AMDT_FUNCTION_COUNT
        incrementFuncCount(fid, (bpf_ktime_get_ns() - pEntry->m_startTs));
#endif
        g_memEntry.delete(&id);
    }

    return 0;
}

//TODO : Need to think of creating a template for below Code.
int malloc_enter(struct pt_regs *ctx, size_t size)
{
    return traceAllocEnter(ctx, size);
}

int malloc_exit(struct pt_regs *ctx)
{
    return traceAllocExit(ctx, AMDT_MALLOC);
}

int free_enter(struct pt_regs *ctx, void *address)
{
    return traceFreeEnter(ctx, address, true);
}

int free_exit(struct pt_regs *ctx)
{
    return traceFreeExit(ctx, AMDT_FREE);
}

int calloc_enter(struct pt_regs *ctx, size_t nmemb, size_t size)
{
    return traceAllocEnter(ctx, nmemb * size);
}

int calloc_exit(struct pt_regs *ctx)
{
    return traceAllocExit(ctx, AMDT_CALLOC);
}

int realloc_enter(struct pt_regs *ctx, void *ptr, size_t size)
{
    traceFreeEnter(ctx, ptr, false);
    return traceAllocEnter(ctx, size);
}

int realloc_exit(struct pt_regs *ctx)
{
    return traceAllocExit(ctx, AMDT_REALLOC);
}
"""
g_bpfOpenSysCallHeader = """
struct OpenSysCallRecord
{
    u64    m_startTs;
    u64    m_endTs;
    u32    m_tgid;
    u32    m_pid;
    int    m_fd;
    char   m_fname[NAME_MAX];
};

#define OPEN_AMDT_DATA_GROUP_SIZE 16

BPF_HASH(g_openEntry, u64, struct OpenSysCallRecord);

struct OpenSysCallData
{
    u32    m_dataType;
    struct OpenSysCallRecord m_evtData[OPEN_AMDT_DATA_GROUP_SIZE];
};

BPF_PERCPU_ARRAY(g_openSysCallData, struct OpenSysCallData, 1);
BPF_PERCPU_ARRAY(g_openSysCallIndex, u32, 1);
"""

g_bpfOpenSysCallCode = """
static inline int open_trace_entry(const char *filename)
{
    u64 id = bpf_get_current_pid_tgid();
    struct OpenSysCallRecord rec = {};

    if (getFilterResult(AMDT_GET_PID(id), AMDT_UNKNOWN_CORE_ID) == true)
    {
        rec.m_startTs = bpf_ktime_get_ns();

        if (bpf_probe_read_str(rec.m_fname, NAME_MAX, filename) < 0)
        {
            rec.m_fname[0] = '\\0';
        }

        g_openEntry.update(&id, &rec);
    }

    return 0;
}

static inline int open_trace_return(void *args, int fd)
{
    struct OpenSysCallRecord *pEntry = NULL;
    u64 id = bpf_get_current_pid_tgid();
    u32 zero = 0;

    pEntry = g_openEntry.lookup(&id);

    if (pEntry)
    {
        struct OpenSysCallData *pData = g_openSysCallData.lookup(&zero);
        u32 *pIndex = g_openSysCallIndex.lookup(&zero);

        if ((pData == NULL) || (pIndex == NULL))
        {
            return 0;
        }

        pData->m_dataType = AMDT_OS_TRACE_DATA_TYPE_OPEN_SYSCALL;

        if ((*pIndex >= 0) && (*pIndex < OPEN_AMDT_DATA_GROUP_SIZE))
        {
            u32 i = *pIndex;
            pData->m_evtData[i].m_startTs   = pEntry->m_startTs;
            pData->m_evtData[i].m_endTs     = bpf_ktime_get_ns();
            pData->m_evtData[i].m_tgid      = AMDT_GET_TGID(id);
            pData->m_evtData[i].m_pid       = AMDT_GET_PID(id);
            pData->m_evtData[i].m_fd        = fd;

            if (bpf_probe_read_str(pData->m_evtData[i].m_fname, NAME_MAX, pEntry->m_fname) < 0)
            {
                pData->m_evtData[i].m_fname[0] = '\\0';
            }

            (*pIndex)++;
        }

        if (*pIndex == OPEN_AMDT_DATA_GROUP_SIZE)
        {
            (*pIndex) = 0;
            g_perfBuffer.perf_submit(args, pData, sizeof(struct OpenSysCallData));
        }

        g_openEntry.delete(&id);
    }

    return 0;
}

TRACEPOINT_PROBE(syscalls, sys_enter_open)
{
    return open_trace_entry(args->filename);
};
TRACEPOINT_PROBE(syscalls, sys_exit_open)
{
    return open_trace_return(args, (int)args->ret);
};
"""

g_bpfMmapSysCallHeader = """
struct MmapSysCallRecord
{
    u64    m_startTs;
    u64    m_start;
    u64    m_len;
    u32    m_tgid;
    u32    m_pid;
    int    m_fd;
};

BPF_HASH(g_mmapEntry, u64, struct MmapSysCallRecord);

struct MmapSysCallData
{
    u32    m_dataType;
    struct MmapSysCallRecord m_evtData[AMDT_DATA_GROUP_SIZE];
};

BPF_PERCPU_ARRAY(g_mmapSysCallData, struct MmapSysCallData, 1);
BPF_PERCPU_ARRAY(g_mmapSysCallIndex, u32, 1);
"""

g_bpfMmapSysCallCode = """
TRACEPOINT_PROBE(syscalls, sys_enter_mmap)
{
    u64 id = bpf_get_current_pid_tgid();
    struct MmapSysCallRecord rec = {};

    if (args->prot & PROT_EXEC)
    {
        if (getFilterResult(AMDT_GET_PID(id), AMDT_UNKNOWN_CORE_ID) == true)
        {
            rec.m_startTs = bpf_ktime_get_ns();
            rec.m_tgid     = AMDT_GET_TGID(id);
            rec.m_pid     = AMDT_GET_PID(id);
            rec.m_start   = args->addr;
            rec.m_len     = args->len;
            rec.m_fd      = args->fd;

            g_mmapEntry.update(&id, &rec);
        }
    }

    return 0;
};

TRACEPOINT_PROBE(syscalls, sys_exit_mmap)
{
    struct MmapSysCallRecord *pEntry = NULL;
    u64 id = bpf_get_current_pid_tgid();
    u32 zero = 0;

    pEntry = g_mmapEntry.lookup(&id);

    if (pEntry)
    {
        if (args->ret > 0)
        {
            struct MmapSysCallData *pData = g_mmapSysCallData.lookup(&zero);
            u32 *pIndex = g_mmapSysCallIndex.lookup(&zero);

            if ((pData == NULL) || (pIndex == NULL))
            {
                return 0;
            }

            pData->m_dataType = AMDT_OS_TRACE_DATA_TYPE_MMAP_SYSCALL;

            if ((*pIndex >= 0) && (*pIndex < AMDT_DATA_GROUP_SIZE))
            {
                u32 i = *pIndex;
                pData->m_evtData[i].m_startTs = pEntry->m_startTs;
                pData->m_evtData[i].m_tgid = pEntry->m_tgid;
                pData->m_evtData[i].m_pid = pEntry->m_pid;
                pData->m_evtData[i].m_fd = pEntry->m_fd;
                pData->m_evtData[i].m_start = args->ret;
                pData->m_evtData[i].m_len = pEntry->m_len;
                (*pIndex)++;
            }

            if (*pIndex == AMDT_DATA_GROUP_SIZE)
            {
                (*pIndex) = 0;
                g_perfBuffer.perf_submit(args, pData, sizeof(struct MmapSysCallData));
            }
        }

        g_mmapEntry.delete(&id);
    }

    return 0;
};
"""
