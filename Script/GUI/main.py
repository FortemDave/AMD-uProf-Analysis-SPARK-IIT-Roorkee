import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QStackedWidget, QLineEdit, QFileDialog
from PyQt5.QtGui import QFont
from TitleWindow import TitleWindow
from AMDuProfPCM import AMDuProfPCM
from AMDuProfPCM import TargetSelect


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Page Switching Example")
        self.setStyleSheet('background-color: #000000;')

        self.resize(850, 500)

        # self.setGeometry(100, 100, 300, 150)

        self.stacked_widget = QStackedWidget(self)
        self.setCentralWidget(self.stacked_widget)

        self.TitleWindow = TitleWindow()
        self.AMDuProfPCM = AMDuProfPCM()
        self.TimeAndDuration = TargetSelect()


        self.stacked_widget.addWidget(self.TitleWindow)
        self.stacked_widget.addWidget(self.AMDuProfPCM)

        self.stacked_widget.setCurrentIndex(0)

        self.TitleWindow.next_button.clicked.connect(self.navigate_to_PCM)
        self.AMDuProfPCM.next_button.clicked.connect(self.navigate_to_PCM_Page_2)
        self.TimeAndDuration.next_button.clicked.connect(self.navigate_to_PCM_Page_3)

    def navigate_to_PCM(self):
        if not(self.TitleWindow.AMDUPROFPCM or self.TitleWindow.AMDUPROFCLI or self.TitleWindow.AMDUPROFSYS):
            self.TitleWindow.add_warning()
        else:
            if self.TitleWindow.AMDUPROFPCM:
                self.setCentralWidget(self.AMDuProfPCM)
                self.TitleWindow.hide()
                self.AMDuProfPCM.show()
            if self.TitleWindow.AMDUPROFCLI:
                pass
            if self.TitleWindow.AMDUPROFSYS:
                pass

    def navigate_to_PCM_Page_2(self):
        if self.AMDuProfPCM.save_status():
            # go to next page
            self.setCentralWidget(self.TimeAndDuration)
            self.AMDuProfPCM.hide()
            self.TimeAndDuration.show()
        else:
            self.AMDuProfPCM.add_warning()


    def navigate_to_PCM_Page_3(self):
        if self.TimeAndDuration.options_selected is None:
            # TODO: Warn to Select
            # pass
            1 == 1
        elif self.TimeAndDuration.options_selected == all:
            # TODO: Go to the Next Page
            1 == 1
        
        return

        

# if __name__ == "__main__":
app = QApplication(sys.argv)
window = MainWindow()
window.show()
sys.exit(app.exec_())
