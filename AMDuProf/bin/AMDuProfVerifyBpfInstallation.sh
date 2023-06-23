#==================================================================================
# Copyright (c) 2021 , Advanced Micro Devices, Inc.  All rights reserved.
#
# author AMD Developer Tools Team
# file AMDuProfVerifyBpfInstallation.sh
# Check BPF support and BCC Installed or not
#==================================================================================

#! /bin/bash

# This Script is used to Verify whether BPF is supported or not in this system
# Verify whether BCC Library is installed or not.
# Create BPF specific files under user AMDuProf directory.
usage()  {
    echo "Usage:"
    echo "Verify BPF Support and BCC Installation:    sudo ./AMDuProfVerifyBpfInstallation.sh"
}

check_exe_permission()
{
    # script can be executed only with root permission.
    if [ "$(id -u)" != "0" ];
    then
        echo "Please execute this script with root permission."
        exit 0
    fi
}

create_bpf_files()
{
    UPROF_BIN=`pwd`
    cd $UPROF_BIN

    if [ -c /dev/null ];
    then
        ./AMDuProfCLI setup --os-trace > /dev/null 2>&1
    else
        ./AMDuProfCLI setup --os-trace
    fi

    ./AMDuProfCLI info --bpf
}

# check for root permission
check_exe_permission

if  [ "$#" -eq 0 ] ;
then
    # call BPF setup command
    create_bpf_files
else
    # Usage
    usage
fi
