#!/usr/bin/env python2
#=====================================================================
# Copyright 2020 (c), Advanced Micro Devices, Inc. All rights reserved.
#
# AMDDummySleep.py - Dummy application for more than one type of profile
#                    together. This script will run till the first type
#                    of profiling exits.
#
# Developed by AMDuProf Profiler team.
#=====================================================================
import sys
import os
import platform
from time import sleep
import os
import AMDUtils as utils

# Write the initial value as 0
envHld = open(utils.getTempFilePath(fileName="env.txt"),'w')
envHld.write('0')
envHld.close()

# wait for first profile type to complete and se the value to 1
while 1:
    envHld = open(utils.getTempFilePath(fileName="env.txt"),'r')
    value = envHld.read()

    if (value == '1'):
        break
    envHld.close()

    sleep(0.5)

