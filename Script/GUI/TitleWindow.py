import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QStackedWidget, QLineEdit, QFileDialog
from PyQt5.QtGui import QFont


class TitleWindow(QWidget):
    

    def __init__(self):
        super().__init__()
        self.AMDUPROFPCM = False
        self.AMDUPROFCLI = False
        self.AMDUPROFSYS = False

        self.setWindowTitle("AMDuProf Output Logger")
        self.setStyleSheet(
            """
            QLabel#heading_label {
                background-color: #000000;
                color: #FFFFFF;
                font-family: "Arial";
                font-size: 24px;
                padding: 10px;
            }

            QPushButton {
                
                background-color: #4C4C4C;
                color: #FFFFFF;
                border: none;
                border-radius: 10px;
                padding: 10px;
                font-family: "Arial";
                font-size: 18px;
            }

            QPushButton:hover {
                background-color: #777777;
            }
            """
        )
        self.resize(850, 500)

        self.layout = QVBoxLayout()


        # Add the heading label
        self.heading_label = QLabel("AMDuProf Output Logger", self)
        self.heading_label.setObjectName("heading_label")
        self.layout.addWidget(self.heading_label)

        custom_font = QFont("Cascadia Mono", 13)

        # Add a Possible checklist for New-Users
        self.info_label = QLabel(self)
        self.info_label.setFont(custom_font)
        self.info_label.setText(
            "<ul>"
            "<li><font color='gold'><b>Note:</b><font color='grey'> Run the following commands once if they haven't \n been run yet.</font></li>"
            "<li><font color='gold'>NMI watchdog must be disabled</font></li>"
            "<font color='light grey'>sudo echo 0 > /proc/sys/kernel/nmi_watchdog</font>"
            "<li><font color='gold'>Set Performance_Event_Paranoid to -1 (Default is 4)</font></li>"
            "<font color='light grey'>/proc/sys/kernel/perf_event_paranoid to -1</font>"
            "<li><font color='gold'>Use the following command to load the msr driver:</font></li>"
            "<li><font color='light grey'>modprobe msr</font></li>"
            "</ul>"
        )
        self.layout.addWidget(self.info_label)

        # Add the subheading label
        self.subheading_label = QLabel("<font color='gold'><center><h2>Select Metrics you want to log.</font></h2></center>", self)
        self.subheading_label.setObjectName("subheading_label")
        self.layout.addWidget(self.subheading_label)

         # Add bullet points for additional information
        self.bullet_points_label = QLabel(self)
        self.bullet_points_label.setFont(custom_font)
        self.bullet_points_label.setText(
            "<ul>"
            "<li><font color='gold'><b>AMD uProf PCM:</font></b> <font color='light grey'>Provides IPC, L1, L2, L3 Cache, Memory, PCIe metrics from cores.</font></li>"
            "<li><font color='gold'><b>AMD uProf CLI:</font></b> <font color='light grey'>Provides Power, Thermal, Frequency, P-State metrics </font></li>"
            "<li><font color='gold'><b>AMD uProf CLI Collect-Report:</font></b> <font color='light grey'>Provides Hotzones and Other information provided as a CSV.</font></li>"
            "</ul>"
        )
        self.bullet_points_label.setWordWrap(True)
        self.layout.addWidget(self.bullet_points_label)

        # Create a horizontal layout for the button container
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)

        # Add the buttons to the horizontal layout
        self.button1 = QPushButton("uProfPCM", self)
        self.button2 = QPushButton("uProfCLI", self)
        self.button3 = QPushButton("uProfSys", self)
        button_layout.addWidget(self.button1)
        button_layout.addWidget(self.button2)
        button_layout.addWidget(self.button3)

        # Connect button signals to slots
        self.button1.clicked.connect(self.toggle_uProfPCM)
        self.button2.clicked.connect(self.toggle_uProfCLI)
        self.button3.clicked.connect(self.toggle_uProfSys)

        # Add the button container to the main layout
        self.layout.addWidget(button_container)

        # Add the "Next" button
        self.next_button = QPushButton("Next", self)
        self.next_button.setObjectName("next_button")
        # self.next_button.clicked.connect(self.navigate_to_PCM)
        self.layout.addWidget(self.next_button)

        self.setLayout(self.layout)
        
    def add_warning(self):
        self.warning_label = QLabel(self)
        custom_font = QFont("Cascadia Mono", 13)
        self.warning_label.setFont(custom_font)
        self.warning_label.setText(
            "<ul>"
            "<li><font color='orange'><b>Select at least one!</font></b></li>"
            "</ul>"
        )
        self.warning_label.setWordWrap(True)
        self.layout.addWidget(self.warning_label)

    def toggle_uProfPCM(self):
        #Refer to the global variables
        # /global AMDUPROFPCM
        self.AMDUPROFPCM = not self.AMDUPROFPCM
        self.update_button_style(self.button1, self.AMDUPROFPCM)

    def toggle_uProfCLI(self):
        #Refer to the global variables
        # global AMDUPROFCLI
        self.AMDUPROFCLI = not self.AMDUPROFCLI
        self.update_button_style(self.button2, self.AMDUPROFCLI)

    def toggle_uProfSys(self):
        #Refer to the global variables
        # global AMDUPROFSYS
        self.AMDUPROFSYS = not self.AMDUPROFSYS
        self.update_button_style(self.button3, self.AMDUPROFSYS)

    def update_button_style(self, button, toggled):
        if toggled:
            button.setStyleSheet("background-color: #FFD700; color: #36454F;")
        else:
            button.setStyleSheet("background-color: #4C4C4C; color: #FFFFFF;")

    