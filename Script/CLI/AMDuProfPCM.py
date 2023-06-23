from colors import bcolors
import pages
from datetime import datetime

class uProfPCM():
    def __init__(self):
        print(pages.AMDuProcPCM)
        options = input(">")

        while True:
            if options in ['e','exit',"Exit",'E']:    
                exit(0)
            options = options.split(',')
            for option in options:
                if int(option) not in [i for i in range(1,11,1)]:
                    print("Invalid Input. Try Again.\n>")
                    input(options)
            break
        options.sort()
        self.metricsToLog = [int(option) for option in options]

        print(pages.AMDuProcPCMCores)
        options = input(">")

        if options[0] == '0':
            self.loggingDevice = 'core'
        elif options[0] == '1':
            self.loggingDevice = 'CCX'
        elif options[0] == '2':
            self.loggingDevice = 'CCD'
        elif options[0] == '3':
            self.loggingDevice = 'Packages'
        elif options[0] == '4':
            self.loggingDevice = 'All'
        else:
            print("Invalid Input. Defaulting to Logging All Cores")
            self.loggingDevice = 'All'
    
        options = options.split(',')
        value = options[0].split(' ')
        options[0] = value[1]
        self.loggingIndices = [int(option) for option in options]

        print(pages.AMDuProcPCMDuration)
        options = input(">")
        options = options.split()
        self.duration = int(options[0])
        self.LoggingInterval = int(options[1])

    def PcmRunCommand(self,addr):
        command = f'sudo {addr}/AMDuProfPcm '
        metrics = '-m '
        metric_indices = ['ipc','fp','l1','l2','l3','dc','memory','pcie','xgmi','dma']

        for metric in self.metricsToLog:
            metrics += metric_indices[metric-1]+ ","
        metrics = metrics[:-1]
        metrics += " "

        if(self.loggingDevice == 'All'):
            log_command = '-a '
        else:
            log_command = '-c '
            log_command += self.loggingDevice.strip().lower() +"="
            for indice in self.loggingIndices:
                log_command += str(indice)+","
            log_command = log_command[:-1]
            log_command += " "
        
        duration = f"-d {self.duration} "
        pmcinterval = f"-t {self.LoggingInterval} "

        # output_name = f"-o /home/usr/pratham/{datetime.today().strftime('%Y-%m-%d')}.csv"
        output_name = f"-o /tmp/{datetime.today().strftime('%Y%m%d')}.csv"
        final_command = command + metrics + log_command + duration + pmcinterval + output_name
        return final_command,output_name

        # (trap 'kill 0' SIGINT; sleep 4 & sleep 2 & wait)
