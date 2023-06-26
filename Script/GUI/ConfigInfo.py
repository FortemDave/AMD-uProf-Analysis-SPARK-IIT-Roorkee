from TitleWindow import TitleWindow
from datetime import datetime
import os
import subprocess

class UserInfo():
    def __init__(self):
        self.current_datetime = datetime.now()
        self.uProf_bin_address = None
        self.options = None #Metrics Being Logged
        self.log_target = None #Values to Log
        self.log_metrics = None #Core/CCX/CCD/Package Indices
        self.duration = None
        self.interval = None #Note: This is multiplexing interval. Divide by 4 to convert to sampling interval


    def generatePCMcommand(self):

        option_list = ''
        for option in self.options:
            option_list += option
            option_list += ","
        option_list = option_list[:-1]

        homeDir = os.popen('echo $HOME').read().strip()
        # subprocess.run([])
        os.system(f"mkdir -p {homeDir}/uProf/Output")
        command = f"sudo {self.uProf_bin_address}/AMDuProfPcm -m {option_list} {self.log_target}{self.log_metrics} -d {self.duration} -t {self.interval/4} -o {homeDir.strip()}/uProf/Output/"
        # command = f"sudo {self.uProf_bin_address}/AMDuProfPcm -m {option_list} {self.log_target}{self.log_metrics} -d {self.duration} -t {self.interval/4} -o {homeDir.strip()}/uProf/Output/{self.current_datetime.strftime('%d%m_%H%M%S')}.csv"

        print(command)
        # os.system(command)
        return command
        # subprocess.run([command]) 

    def generateTimechartCommand(self):
        homeDir = os.popen('echo $HOME').read().strip()

        return f"sudo {self.uProf_bin_address}/AMDuProfCLI timechart --event power --event temperature --event frequency -d {self.duration} -o {homeDir.strip()}/uProf/Output/"
        # return f"sudo {self.uProf_bin_address}/AMDuProfCLI timechart --event power --event temperature --event frequency -d {self.duration} -o {homeDir.strip()}/uProf/Output/{self.current_datetime.strftime('%d%m_%H%M%S')}.csv"
    

    def ExportToFile(self):

        homeDir = os.popen('echo $HOME').read().strip()
        

        my_file = f"""
        #!/bin/bash

        # Function to display the loading bar
        loading_bar() {{
            local duration={self.duration}
            local total_ticks=30
            local interval=$(bc -l <<< "$duration / $total_ticks")
            local progress=0
            local bar=""

            # Hide the cursor
            tput civis

            # Set the color to blue
            local blue=$(tput setaf 4)

            for ((tick=0; tick<=total_ticks; tick++)); do
                bar+="▒"
                printf "\r${{blue}}[%-${{total_ticks}}s]" "${{bar:0:$total_ticks}}"
                sleep $interval
            done

            # Reset the color and move to the next line
            tput sgr0
            echo

            # Show the cursor
            tput cnorm
        }}

        # Execute the two commands in parallel
        ({self.generatePCMcommand()}$(date +'%S%M_%d%m_PCM').csv & {self.generateTimechartCommand()}$(date +'%S%M_%d%m_CLI').csv) &

        # Start the loading bar
        loading_bar $duration

        # Wait for the commands to finish
        wait

        echo "Commands executed successfully!"

        """
        os.system(f'mkdir -p sudo bash {homeDir}/Script/exec')
        with open(f"{homeDir}/Script/exec/{self.current_datetime.strftime('%d%m_%H%M%S')}.sh",'w') as executable_file:
            executable_file.write(my_file)
        
        os.system(f"sudo bash {homeDir}/Script/exec/{self.current_datetime.strftime('%d%m_%H%M%S')}.sh")