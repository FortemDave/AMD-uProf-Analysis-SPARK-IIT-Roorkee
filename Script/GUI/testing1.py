import sys
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout

class ButtonGlowWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Button Glow Example")
        
        self.buttons = []
        self.button_states = []
        
        layout = QVBoxLayout()
        
        for i in range(3):
            button = QPushButton(f"Button {i+1}")
            button.clicked.connect(lambda checked, idx=i: self.button_clicked(idx))
            self.buttons.append(button)
            self.button_states.append(False)
            layout.addWidget(button)
        
        self.setLayout(layout)
    
    def button_clicked(self, idx):
        # Turn off glow for previously clicked buttons
        for i, button in enumerate(self.buttons):
            if i != idx and self.button_states[i]:
                self.button_states[i] = False
                button.setStyleSheet("")
        
        # Toggle glow for the clicked button
        self.button_states[idx] = not self.button_states[idx]
        
        if self.button_states[idx]:
            self.buttons[idx].setStyleSheet("background-color: yellow")
        else:
            self.buttons[idx].setStyleSheet("")
        

if __name__ == "__main__":
    app = QApplication(sys.argv)
    widget = ButtonGlowWidget()
    widget.show()
    sys.exit(app.exec_())
