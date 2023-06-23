from colors import bcolors

STARTSCREEN = f"""
================================================================
{bcolors.BCyan} AMDuProf Output Logger  [uProfPCM, uProfCLI, uProfSys] {bcolors.ENDC}
----------------------------------------------------------------
{bcolors.BIWhite}Note:{bcolors.ENDC}
• NMI watchdog must be disabled 
{bcolors.BYellow}  sudo echo 0 > /proc/sys/kernel/nmi_watchdog{bcolors.ENDC}
• Set Performance_Event_Paranoid to -1 (Default is 4) 
{bcolors.BYellow}  /proc/sys/kernel/perf_event_paranoid to -1{bcolors.ENDC}
• Use the following command to load the msr driver:
{bcolors.BYellow}  modprobe msr{bcolors.ENDC}
----------------------------------------------------------------
{bcolors.BIWhite}Options:{bcolors.ENDC}
• Select the Commands you would like to execute \n[Enter as Comma Seperated Indices]:

{bcolors.BIGreen}1. AMD uProf PCM {bcolors.ENDC}
Summary: Provides IPC, L1, L2, L3 Cache, Memory, PCIe metrics from cores.
{bcolors.BIGreen}2. AMD uProf CLI TimeChart{bcolors.ENDC}
Summary: Provides Power, Thermal, Frequency, P-State metrics
{bcolors.BIGreen}3. AMD uProf CLI Collect-Report{bcolors.ENDC}
Summary: Provides Hotzones and Other information provided as a CSV.
         (Yet to be implemented.)

Enter e at any moment to exit.
e.g. Enter 1,2 for uProc PCM & uProf CLI to log in parallel.
================================================================
"""

ADDRESS = f"""
================================================================
Enter Absolute Address to the AmduProf Bin Folder
Note: Enter command {bcolors.BIWhite}pwd{bcolors.ENDC} at bin 
      directory to get the complete address
================================================================
"""
AMDuProcPCM = f"""
{bcolors.BIWhite}Enter 'help' to get detailed information.{bcolors.ENDC}

Enter Comma Seperated Values of the metrics you wish to log.
{bcolors.BIGreen}1. Instructions Per Clock[IPC]{bcolors.ENDC}
(Also contains Effective Frequency, CPI)
{bcolors.BIGreen}2. G-Flops{bcolors.ENDC}
{bcolors.BIGreen}3. L1 Cache Metrics (DC Access, IC Fetch/Miss Ratio){bcolors.ENDC}
{bcolors.BIGreen}4. L2 Cache Metrics (L2D & L2I Cache Related Access/Hit/Miss){bcolors.ENDC}
{bcolors.BIGreen}5. L3 Cache Metrics (L3 Access,Miss,Average Miss Latency){bcolors.ENDC}
{bcolors.BIGreen}6. Data Cache (Advanced metrics - Only on Zen3 & Zen4){bcolors.ENDC}
{bcolors.BIGreen}7. Memory{bcolors.ENDC}
{bcolors.BIGreen}8. PCIe{bcolors.ENDC}
{bcolors.BIGreen}9. xGMI{bcolors.ENDC}
{bcolors.BIGreen}10.DMA bandwidth (in GB/s) [Only on Zen4 Processors]{bcolors.ENDC}
"""
AMDuProcPCMCores = f"""
Enter specific {bcolors.BIGreen}cores(0) | ccx(1) | ccd(2) | packages(3)| all(4){bcolors.ENDC} to log.
{bcolors.BIWhite}CCX:{bcolors.ENDC}
• The core events will be collected from all the cores of this ccx.
• The l3 and df events will be collected from the first core of this ccx.
{bcolors.BIWhite}CCD:{bcolors.ENDC}
• The core events will be collected from all the cores of this die.
• The l3 events will be collected from the first core of all the ccx's of this die.
• The df events will be collected from the first core of this die.
{bcolors.BIWhite}PACKAGE:{bcolors.ENDC}
• The core events will be collected from all the cores of this package.
• The l3 events will be collected from the first core of all the ccx's of this package.
• The df events will be collected from the first core of all the die of this package
{bcolors.BICyan}ALL:{bcolors.ENDC}
• Log Metrics From All Cores

E.g. 0 1,2,3  - Log Metrics from Core Indexed 1, 2 and 3.
E.g. 2 2 - Log Metrics from CCD Indexed 2
"""

AMDuProcPCMDuration = f"""
Enter Space Seperated Values for
{bcolors.BIWhite} 
             Duration(Seconds) 
                    and 
Profile Monitoring Count Interval(Milliseconds)
{bcolors.ENDC}
to be logged at.

Note: Number of Entries = Duration/PMC Interval 
Note: Frequency = 1/PMC Interval
"""