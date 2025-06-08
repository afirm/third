import pandas as pd
# dealer_info_panel.py
from PyQt5.QtWidgets import QTextEdit, QWidget, QVBoxLayout

class DealerInfoPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
    
    def init_ui(self):
        layout = QVBoxLayout()
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)
        self.setLayout(layout)
    
    def display_info(self, dealer_name, df):
        dealer_data = df[df['dealer'] == dealer_name]
        info_text = f"<h2>Dealer: {dealer_name}</h2>"
        info_text += dealer_data.to_html(index=False)
        self.text_edit.setHtml(info_text)

        # Filter personnel for the selected dealer
        dealer_personnel = df[df['عنوان نمایندگی'] == dealer_name]
