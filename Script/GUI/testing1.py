import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QLineEdit, QPushButton, QMessageBox
from PyQt5.QtGui import QFont, QColor, QPalette
from PyQt5.QtCore import Qt

class ProfilingWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Enter Profiling Duration & Frequency")
        self.setGeometry(100, 100, 800, 550)

        self.setStyleSheet("background-color: lightgray;")

        self.duration_label = QLabel("Duration:", self)
        self.duration_label.setGeometry(20, 70, 120, 30)
        self.duration_label.setStyleSheet("color: gold;")
        self.duration_label.setFont(QFont("Arial", 12))

        self.duration_input = QLineEdit(self)
        self.duration_input.setGeometry(150, 70, 120, 30)
        self.duration_input.setStyleSheet("color: white;")
        self.duration_input.setFont(QFont("Arial", 12))

        self.interval_label = QLabel("Frequency Interval:", self)
        self.interval_label.setGeometry(20, 120, 150, 30)
        self.interval_label.setStyleSheet("color: gold;")
        self.interval_label.setFont(QFont("Arial", 12))

        self.interval_input = QLineEdit(self)
        self.interval_input.setGeometry(220, 120, 120, 30)
        self.interval_input.setStyleSheet("color: white;")
        self.interval_input.setFont(QFont("Arial", 12))

        self.bullet_label_1 = QLabel("\u2022 Number of Entries = Duration/PMC Interval", self)
        self.bullet_label_1.setGeometry(20, 200, 400, 30)
        self.bullet_label_1.setStyleSheet("color: gold;")
        self.bullet_label_1.setFont(QFont("Arial", 12))

        self.bullet_label_2 = QLabel("\u2022 Frequency = 1/PMC Interval", self)
        self.bullet_label_2.setGeometry(20, 230, 400, 30)
        self.bullet_label_2.setStyleSheet("color: gold;")
        self.bullet_label_2.setFont(QFont("Arial", 12))

        self.next_button = QPushButton("Next", self)
        self.next_button.setGeometry(700, 500, 80, 30)
        self.next_button.clicked.connect(self.next_button_clicked)

    def next_button_clicked(self):
        duration = int(self.duration_input.text())
        interval = int(self.interval_input.text())

        if interval > duration:
            QMessageBox.warning(self, "Invalid Input", "Frequency Interval cannot be greater than Duration.")
        else:
            num_entries = duration // interval
            frequency = 1 / interval

            print("Number of Entries:", num_entries)
            print("Frequency:", frequency)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ProfilingWindow()
    window.show()
    sys.exit(app.exec_())
