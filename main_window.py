# main_window.py
from PyQt5.QtWidgets import (
    QMainWindow, QSplitter, QListWidget, QVBoxLayout, QWidget,
    QLabel, QScrollArea, QListWidgetItem, QFileDialog, QDialog
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

from data_manager import DataManager
from training_analyzer import TrainingAnalyzer
from ui_formatter import UIFormatter
from exporter import Exporter
from NormalizerDialog import NormalizerDialog
import pandas as pd
# ui_formatter.py
from collections import defaultdict


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dealer-Personnel System")
        self.setGeometry(100, 100, 1200, 800)

        # Initialize helper classes
        self.data_manager = DataManager()
        self.analyzer = TrainingAnalyzer(self.data_manager)
        self.exporter = Exporter(self.analyzer)

        self.init_ui()
        self.load_initial_data()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Left Panel (Lists)
        left_panel = QSplitter(Qt.Vertical)
        self.dealer_list_widget = QListWidget()
        self.personnel_list_widget = QListWidget()
        left_panel.addWidget(self.dealer_list_widget)
        left_panel.addWidget(self.personnel_list_widget)

        # Right Panel (Details)
        right_panel = QSplitter(Qt.Vertical)
        self.dealer_details_label = QLabel(wordWrap=True, textFormat=Qt.RichText)
        self.personnel_details_label = QLabel(wordWrap=True, textFormat=Qt.RichText)
        self.personnel_details_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        dealer_scroll = QScrollArea(widgetResizable=True)
        dealer_scroll.setWidget(self.dealer_details_label)
        
        personnel_scroll = QScrollArea(widgetResizable=True)
        personnel_scroll.setWidget(self.personnel_details_label)

        right_panel.addWidget(dealer_scroll)
        right_panel.addWidget(personnel_scroll)
        
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 900])

        # Connections
        self.dealer_list_widget.currentItemChanged.connect(self._on_dealer_selected)
        self.personnel_list_widget.currentItemChanged.connect(self._on_personnel_selected)

        # Menubar
        menubar = self.menuBar()
        settings_menu = menubar.addMenu('Settings')
        export_menu = menubar.addMenu('Export')
        
        settings_menu.addAction('Data Normalization', self._open_normalizer)
        export_menu.addAction('Export Current Dealer', self._export_current_dealer)
        export_menu.addAction('Export All Dealers', self._export_all_dealers)

    def load_initial_data(self):
        """Loads all data and populates the main dealer list."""
        self.data_manager.load_all_data()
        self.dealer_list_widget.clear()
        dealer_names = self.data_manager.get_all_dealer_names()
        self.dealer_list_widget.addItems(dealer_names)


    def _on_dealer_selected(self, current, previous):
        """Slot for when a dealer is selected from the list."""
        if not current:
            return

        dealer_name = current.text()
        
        
        # Generate the new summary data
        summary_data = self.analyzer.generate_dealer_personnel_summary(dealer_name)
        
        self._update_dealer_details_panel(dealer_name, summary_data)
        self._populate_personnel_list(dealer_name)
        self.personnel_details_label.clear()



    def _on_personnel_selected(self, current, previous):
        """Slot for when a person is selected from the list."""
        if not current or not (current.flags() & Qt.ItemIsSelectable):
            self.personnel_details_label.clear()
            return

        item_data = current.data(Qt.UserRole)
        pcode = item_data['pcode']
        position = item_data['position']
        dealer_name = item_data['dealer_name']

        analysis_result = self.analyzer.analyze_personnel_training(pcode, dealer_name, position)
        html_content = UIFormatter.format_personnel_details_html(analysis_result)
        self.personnel_details_label.setText(html_content)

    def _update_dealer_details_panel(self, dealer_name, summary_data):
        """Updates the top-right panel with dealer info and summary table."""
        categories = self.data_manager.get_dealer_categories(dealer_name)
        # Pass the summary_data to the formatter
        html = UIFormatter.format_dealer_details_html(dealer_name, categories, summary_data)
        self.dealer_details_label.setText(html)



    def _populate_personnel_list(self, dealer_name):
        """Fills the personnel list based on the selected dealer."""
        self.personnel_list_widget.clear()
        personnel_df = self.data_manager.get_personnel_for_dealer(dealer_name)
        dealer_code = dealer_name[:4]

        # Use a set to avoid duplicate list entries for the same person/role
        unique_personnel = set()

        for _, row in personnel_df.iterrows():
            name = row['نام و نام خانوادگی']
            pcode = row['کد پرسنلی']
            
            positions = []
            main_pos = row.get('عنوان شغل', '')
            if pd.notna(main_pos) and main_pos.strip():
                positions.append(main_pos.strip())
            
            alt_pos = row.get('شغل موازی (ارتقا)', '')
            if pd.notna(alt_pos) and alt_pos.strip():
                positions.extend([p.strip() for p in alt_pos.split('&&&') if p.strip()])
            
            if not positions:
                positions.append('بدون سمت')

            for pos in positions:
                if (name, pos, pcode) not in unique_personnel:
                    unique_personnel.add((name, pos, pcode))
                    
                    # Create the list item
                    display_text = f"{dealer_code} | {name} | {pos} | {pcode}"
                    item = QListWidgetItem(display_text)
                    
                    # Store data within the item
                    item_data = {'pcode': pcode, 'position': pos, 'dealer_name': dealer_name}
                    item.setData(Qt.UserRole, item_data)
                    
                    # Disable item if its position is not in the mapping
                    if pos not in self.data_manager.position_mapping:
                        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                        item.setForeground(QColor('gray'))

                    self.personnel_list_widget.addItem(item)
    
    def _open_normalizer(self):
        """Opens the data normalization dialog."""
        # This requires passing the raw dataframes to the dialog
        dialog = NormalizerDialog(
            self,
            self.data_manager.raw,
            self.data_manager.dealers,
            self.data_manager.after_sheets,
            self.data_manager.sales_sheets
        )
        if dialog.exec_() == QDialog.Accepted:
            # Reload everything if changes were saved
            self.load_initial_data()
            self.dealer_details_label.clear()
            self.personnel_list_widget.clear()
            self.personnel_details_label.clear()

    def _export_current_dealer(self):
        """Exports the currently selected dealer's data."""
        current_item = self.dealer_list_widget.currentItem()
        if not current_item:
            return
        
        dealer_name = current_item.text()
        dealer_title = dealer_name[5:]
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save Current Dealer Data", f"{dealer_title}_training_status.xlsx", "Excel Files (*.xlsx)"
        )
        if filename:
            self.exporter.export_single_dealer(dealer_name, filename)

    def _export_all_dealers(self):
        """Exports all dealers' data to a single Excel file."""
        filename, _ = QFileDialog.getSaveFileName(
            self, "Save All Dealers Data", "all_dealers_training_status.xlsx", "Excel Files (*.xlsx)"
        )
        if filename:
            all_dealers = self.data_manager.get_all_dealer_names()
            self.exporter.export_all_dealers(all_dealers, filename)