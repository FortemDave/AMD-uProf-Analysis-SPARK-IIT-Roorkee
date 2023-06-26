import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QStackedWidget, QLineEdit, QFileDialog, QMessageBox
from PyQt5.QtGui import QFont



class AMDuProfPCM(QWidget):
    def __init__(self):
        super().__init__()
        self.options_selected = None
        self.setWindowTitle("AMDuProf PCM Customizer")
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #000000;
            }

            QLabel#heading_label {
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
        self.directory = None
        # Add the heading label
        self.heading_label = QLabel("µProfCLI Option Customization", self)
        self.heading_label.setObjectName("heading_label")
        self.layout.addWidget(self.heading_label)

        self.custom_font = QFont("Cascadia Mono", 13)

        # Take input for the Address of AMDuProf/bin/ file
        input_layout = QHBoxLayout()
        self.label = QLabel(f"<font color='white'>Enter the Absolute Address of <b>uProf/bin</b> Folder.</font>")
        self.label.setFont(self.custom_font)
        # self.label.setStyleSheet("background-color: grey;")
        input_layout.addWidget(self.label)  


        self.input_box = QLineEdit(self)
        self.input_box.setFont(self.custom_font)
        self.input_box.setStyleSheet("background-color: grey;")
        self.input_box.setGeometry(50, 50, 300, 30)  # user_input = self.input_box.text()
        input_layout.addWidget(self.input_box)

        self.button = QPushButton("Select Directory")
        self.button.setGeometry(50, 50, 300, 30)
        self.button.clicked.connect(self.select_directory)
        # input_layout.addLayout
        input_layout.addWidget(self.button)

        self.layout.addLayout(input_layout)
        
        options = [
            "Instructions Per Clock[IPC] (Also contains Effective Frequency, CPI)",
            "G-Flops",
            "L1 Cache Metrics (DC Access, IC Fetch/Miss Ratio)",
            "L2 Cache Metrics (L2D & L2I Cache Related Access/Hit/Miss)",
            "L3 Cache Metrics (L3 Access,Miss,Average Miss Latency)",
            "Data Cache (Advanced metrics - Only on Zen3 & Zen4)",
            "Memory",
            "PCIe",
            "xGMI",
            "DMA bandwidth (in GB/s) [Only on Zen4 Processors]"
        ]
        options_cli = ['ipc','dma','fp','l1','l2','l3','dc','memory','pcie','xgmi']
        self.line_buttons = []

        for i in range(10):
            line_layout = QHBoxLayout()

            label = QLabel(f"<font color='orange'><b>{options[i]}.</font></b></")
            label.setFont(self.custom_font)
            line_layout.addWidget(label)

            button = QPushButton(f"{options_cli[i]}")
            button.setFixedSize(100,35)
            button.setCheckable(True)
            button.setChecked(False)
            button.clicked.connect(self.toggle_variable)
            line_layout.addWidget(button)

            self.line_buttons.append((label, button))
            self.layout.addLayout(line_layout)


        self.next_button = QPushButton("Next")
        self.next_button.setGeometry(350, 50, 30, 30)

        self.layout.addWidget(self.next_button)
        self.setLayout(self.layout)
    
    def select_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            self.directory = directory
        elif self.input_box.text() not in [None,'']:
            self.directory = self.input_box.text()
        else:
            self.directory = None

    def toggle_variable(self):
        button = self.sender()
        index = next((i for i, (_, b) in enumerate(self.line_buttons) if b is button), None)
        if button.isChecked():
            button.setStyleSheet("background-color: gold; color:black;")
        else:
            button.setStyleSheet("")
        
    def save_status(self):  
        options = ['ipc','dma','fp','l1','l2','l3','dc','memory','pcie','xgmi']
        final_options = []
        for index, (label, button) in enumerate(self.line_buttons):
            if button.isChecked():
                final_options.append(options[index]) 
        
        self.options_selected = final_options
        if len(final_options) != 0 and (self.directory or self.input_box.text() not in [None,'']):
            return True
        return False
    
    def add_warning(self):
        self.warning_label = QLabel(self)
        custom_font = QFont("Cascadia Mono", 13)
        self.warning_label.setFont(custom_font)
        self.warning_label.setText(
            "<ul>"
            "<li><font color='orange'><b>Enter the Address & Select at least one!</font></b></li>"
            "</ul>"
        )
        self.warning_label.setWordWrap(True)
        self.layout.addWidget(self.warning_label)

    def check_before_next_page(self):
        if self.directory is None:
            self.add_warning()
            return
        # Write code to go to the next page


class TargetSelect(QWidget):
    def __init__(self):
        super().__init__()
        self.options_selected = None
        self.setWindowTitle("AMDuProf PCM Customizer")
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #000000;
            }

            QLabel#heading_label {
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
        self.custom_font = QFont("Cascadia Mono", 13)

        self.buttons = []
        self.button_states = []

        # Add the subheading label
        self.subheading_label = QLabel("<font color='gold'><center><h2>Enter Profiling Target.</font></h2></center>", self)
        self.subheading_label.setObjectName("subheading_label")
        self.layout.addWidget(self.subheading_label)

         # Add bullet points for additional information
        self.bullet_points_label = QLabel(self)
        self.bullet_points_label.setFont(self.custom_font)
        self.bullet_points_label.setText(
            "<ul>"
            "<font color='gold'><b>\tCCX:</font></b>"
            "<li><font color='light grey'>The core events will be collected from all the cores of this ccx.</font></li>"
            "<li><font color='light grey'>The l3 and df events will be collected from the first core of this ccx.</font></li>"
            "<font color='gold'><b>CCD:</font></b>"
            "<li><font color='light grey'>The core events will be collected from all the cores of this die.</font></li>"
            "<li><font color='light grey'>The l3 events will be collected from the first core of all the ccx's of this die.</font></li>"
            "<li><font color='light grey'>The df events will be collected from the first core of this die.</font></li>"
            "<font color='gold'><b>PACKAGE:</font></b>"
            "<li><font color='light grey'>The core events will be collected from all the cores of this package.</font></li>"
            "<li><font color='light grey'>The l3 events will be collected from the first core of all the ccx's of this package.</font></li>"
            "<li><font color='light grey'>The df events will be collected from the first core of all the die of this package</font></li>"
            "<font color='gold'><b>ALL:</font></b>"
            "<li><font color='light grey'>Log Metrics From All Cores</font></li>"
            "</ul>"
        )
        self.bullet_points_label.setWordWrap(True)


        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)


        self.layout.addWidget(self.bullet_points_label)
        self.options = ["Core","CCX","CCD","Package","ALL"]
        for i in range(len(self.options)):
            button = QPushButton(f"{self.options[i]}")
            button.clicked.connect(lambda checked, idx=i: self.button_clicked(idx))
            self.buttons.append(button)
            self.button_states.append(False)
            button_layout.addWidget(button)
        self.layout.addWidget(button_container)

        # Take input for the Address of AMDuProf/bin/ file
        input_layout = QHBoxLayout()
        self.label = QLabel(f"<font color='white'>Enter Hyphen-Seperated Target Range.</font>")
        self.label.setFont(self.custom_font)
        input_layout.addWidget(self.label)

        self.input_box = QLineEdit(self)
        self.input_box.setFont(self.custom_font)
        self.input_box.setStyleSheet("background-color: grey;")
        self.input_box.setGeometry(50, 50, 300, 30)  # user_input = self.input_box.text()
        input_layout.addWidget(self.input_box)

        self.layout.addLayout(input_layout)

        self.next_button = QPushButton("Next")
        self.next_button.setGeometry(350, 50, 30, 30)
        self.layout.addWidget(self.next_button)

        self.setLayout(self.layout)

    def add_warning(self):
            self.warning_label = QLabel(self)
            custom_font = QFont("Cascadia Mono", 13)
            self.warning_label.setFont(custom_font)
            self.warning_label.setText(
                "<ul>"
                "<li><font color='orange'><b>Enter the Address & Select at least one!</font></b></li>"
                "</ul>"
            )
            self.warning_label.setWordWrap(True)
            self.layout.addWidget(self.warning_label)

    def button_clicked(self, idx):
        print(idx,self.options[idx],self.options[idx].lower())
        self.options_selected = self.options[idx].lower()
        # Turn off glow for previously clicked buttons
        for i, button in enumerate(self.buttons):
            if i != idx and self.button_states[i]:
                self.button_states[i] = False
                button.setStyleSheet("")

        # Toggle glow for the clicked button
        self.button_states[idx] = not self.button_states[idx]

        if self.button_states[idx]:
            self.buttons[idx].setStyleSheet("background-color: gold; color: black")
        else:
            self.buttons[idx].setStyleSheet("")


class TimeAndDuration(QWidget):
    def __init__(self):
        super().__init__()
        self.options_selected = None
        self.resize(850, 500)
        self.setWindowTitle("<font color='white'>AMDuProf Logger Customizer</font>")
        self.setStyleSheet("background-color: lightgray;")
        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #0A10F0;
            }

            QLabel#heading_label {
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
        self.layout = QVBoxLayout()
        self.custom_font = QFont("Cascadia Mono", 13)

        # Add the subheading label
        self.subheading_label = QLabel("<font color='gold'><center><h1>Enter Profiling Duration & Frequency.</font></h2></center>", self)
        self.subheading_label.setObjectName("subheading_label")
        self.layout.addWidget(self.subheading_label)        

         # Add bullet points for additional information
        self.bullet_points_label = QLabel(self)
        self.bullet_points_label.setFont(self.custom_font)
        self.bullet_points_label.setText(
            "<ul>"
            "<li><font color='gold'>Number of Entries = Duration/PMC Interval.</font></li>"
            "<li><font color='gold'>Frequency = 1/PMC Interval.</font></li>"
            "</ul>"
        )
        self.bullet_points_label.setWordWrap(True)
        self.layout.addWidget(self.bullet_points_label)
        self.custom_font = QFont("Cascadia Mono", 13)

        # Take input for the Address of AMDuProf/bin/ file
        input_layout = QHBoxLayout()
        self.label = QLabel(f"<font color='white'>Duration [in seconds]</font>")
        self.label.setFont(self.custom_font)
        input_layout.addWidget(self.label)

        self.input_box = QLineEdit(self)
        self.input_box.setFont(self.custom_font)
        self.input_box.setStyleSheet("background-color: grey;")
        self.input_box.setGeometry(100, 100, 100, 50)  # user_input = self.input_box.text()
        input_layout.addWidget(self.input_box)

        self.layout.addLayout(input_layout)

        # Take input for the Address of AMDuProf/bin/ file
        input_layout2 = QHBoxLayout()
        self.label2 = QLabel(f"<font color='white'>Logging Interval[PMC] [in Milliseconds]</font>")
        self.label2.setFont(self.custom_font)
        input_layout2.addWidget(self.label2)

        self.input_box2 = QLineEdit(self)
        self.input_box2.setFont(self.custom_font)
        self.input_box2.setStyleSheet("background-color: grey;")

        self.input_box2.setGeometry(100, 100, 100, 50)  # user_input = self.input_box2.text()
        input_layout2.addWidget(self.input_box2)

        self.layout.addLayout(input_layout2)

        self.next_button = QPushButton("Next")
        self.next_button.setGeometry(350, 50, 30, 30)
        self.layout.addWidget(self.next_button)

        self.setLayout(self.layout)        

    def VerifyInputs(self):
        try:
            print(self.input_box.text())
            print(self.input_box2.text())

            self.duration = int(self.input_box.text())
            self.interval = int(self.input_box2.text())
        except:
            QMessageBox.warning(self, f"<font color='white'>Invalid Input</font>", "<font color='white'>Enter Integer/Float input!</font>")
            return False
        if self.interval/1000 > self.duration:
            QMessageBox.warning(self, "<font color='white'>Invalid Input</font>", "<font color='white'>Frequency Interval cannot be greater than Duration.</font>")
            return False
        return True
