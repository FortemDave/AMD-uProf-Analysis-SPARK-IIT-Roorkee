from TitleWindow import TitleWindow
from datetime import datetime
import os
class UserInfo():
    def __init__(self):
        self.uProf_bin_address = None
        self.options = None #Metrics Being Logged
        self.log_target = None #Values to Log
        self.log_metrics = None #Core/CCX/CCD/Package Indices
        self.duration = None
        self.interval = None
    

    def generatePCMcommand(self):

        option_list = ''
        for option in self.options:
            option_list += option
            option_list += ","
        option_list = option_list[:-1]

        homeDir = os.popen('echo $HOME').read()
        current_datetime = datetime.now()
        command = f"sudo {self.uProf_bin_address}/AMDuProfPCM -m {option_list} {self.log_target}{self.log_metrics} -d {self.duration} -t {self.interval} -o {homeDir.strip()}/uProf/Output/{current_datetime.strftime('%d%m_%H%M%S')}.csv"
        print(command)

    def ExportToFile(self):



        f"""
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
        (command1 & command2) &

        # Start the loading bar
        loading_bar $duration

        # Wait for the commands to finish
        wait

        echo "Commands executed successfully!"

        """

        pass