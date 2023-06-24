#!/bin/bash

# Function to display the loading bar
loading_bar() {
    local duration=$1
    local total_ticks=30
    local interval=$(bc -l <<< "$duration / $total_ticks")
    local progress=0
    local bar=""

    # Hide the cursor
    tput civis

    # Set the color to blue
    local blue=$(tput setaf 4)

    for ((tick=0; tick<=total_ticks; tick++)); do
        bar+="█"
        printf "\r${blue}[%-${total_ticks}s]" "${bar:0:$total_ticks}"
        sleep $interval
    done

    # Reset the color and move to the next line
    tput sgr0
    echo

    # Show the cursor
    tput cnorm
}

# Enter the duration in seconds
echo "Enter the duration in seconds: "
read duration

# Execute the two commands in parallel
(command1 & command2) &

# Start the loading bar
loading_bar $duration

# Wait for the commands to finish
wait

echo "Commands executed successfully!"
