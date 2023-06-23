#==================================================================================
# Copyright (c) 2021 , Advanced Micro Devices, Inc.  All rights reserved.
#
# author AMD Developer Tools Team
# file AMDTTestBccAvailability.py
# brief Validating whether bcc is installed or not
#==================================================================================

#!/usr/bin/python
from bcc import BPF
import sys

bpf_source = """
#include <uapi/linux/ptrace.h>
#include <linux/sched.h>

#define AMDT_BPF_STACK_SIZE 4096
#define AMDT_BPF_CALLSTACK_SIZE 128

struct data_t {
    int stack_id;
    int pid;
    long size;
    char comm[TASK_COMM_LEN];
};

struct addr {
    char stack[AMDT_BPF_STACK_SIZE];
};

BPF_PERCPU_ARRAY(stackArray, struct addr, 1);

BPF_PERF_OUTPUT(events);
BPF_STACK_TRACE(stack_traces, AMDT_BPF_CALLSTACK_SIZE);

TRACEPOINT_PROBE(sched, sched_switch)
{
    return 0;
}

int malloc_trace(struct pt_regs *ctx, size_t size)
{
    struct data_t data1 = {};
    data1.stack_id = stack_traces.get_stackid(ctx, BPF_F_USER_STACK);
    u32 zero = 0;
    struct addr *stack_addr = stackArray.lookup(&zero);

    if (stack_addr == NULL)
        return 0;

    data1.size = size;
    data1.pid = bpf_get_current_pid_tgid() >> 32;
    bpf_get_current_comm(&data1.comm, sizeof(data1.comm));
    events.perf_submit(ctx, &data1, sizeof(data1));
    return 0;
}
"""

b = BPF(text=bpf_source)
b.attach_uprobe(name="c", sym="malloc", fn_name="malloc_trace")

def print_event(cpu, data, size):
    pass

b["events"].open_perf_buffer(print_event, 256)
b.perf_buffer_poll(1)
print("AMD SUCCESS")
sys.exit(0)
