from colors import bcolors
from datetime import datetime
import AMDuProfPCM
import pages
import os

print(pages.STARTSCREEN)

options = input(">")

while True:
    if options in ['e','exit',"Exit",'E']:    
        exit(0)
    options = options.split(',')
    for option in options:
        if option not in ['1','2','3']:
            print("Invalid Input. Try Again.\n>")
            input(options)
    break

options.sort()
options = [int(option) for option in options]

uProfPCM = False
uProfTimeChart = False
if 1 in options:
    uProfPCM = True
if 2 in options:
    uProfTimeChart = True

#print(pages.ADDRESS)
#addr = input(">")
addr = "/home/pratham/uProf/uProfLatest/bin"
# Start with AMDuProf PCM
if uProfPCM:
    PCM = AMDuProfPCM.uProfPCM()
    PCM_Command,fileAddress = PCM.PcmRunCommand(addr)
    print(f"The command that was generated is- f{PCM_Command}")
    os.system(PCM_Command)
    os.system(f"sed '1,47d' {fileAddress} >> {datetime.today().strftime('%Y%m%d')}_stripped.csv")
    os.system(f"rm {fileAddress}")
    os.system(f"mv -i {datetime.today().strftime('%Y%m%d')}_stripped.csv $USER/Script/Output")