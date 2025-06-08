from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QTableWidget,
    QTableWidgetItem, QPushButton, QHBoxLayout, 
    QHeaderView, QWidget, QLabel, QComboBox,
    QLineEdit, QHBoxLayout, QProgressBar, QMessageBox
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
import csv
import os
import pandas as pd


class CourseDataLoader(QThread):
    """Background thread to load course data"""
    data_ready = pyqtSignal(list, list)
    
    def __init__(self, raw_df, after_sheets, sales_sheets):
        super().__init__()
        self.raw_df = raw_df
        self.after_sheets = after_sheets
        self.sales_sheets = sales_sheets
    
    def run(self):
        # Extract unique courses from raw data
        raw_courses = self.raw_df['عنوان دوره'].dropna().unique().tolist()
        
        # Extract unique courses from after data
        after_courses = set()
        for sheet_name, df in self.after_sheets.items():
            if 'نام دوره آموزشی' in df.columns:
                after_courses.update(df['نام دوره آموزشی'].dropna().astype(str).unique())
        
        # Extract unique courses from sales data
        sales_courses = set()
        for sheet_name, df in self.sales_sheets.items():
            if 'نام دوره آموزشی' in df.columns:
                sales_courses.update(df['نام دوره آموزشی'].dropna().astype(str).unique())
        
        # Combine all standardized courses
        all_standard_courses = sorted(after_courses.union(sales_courses))
        
        # Emit the data
        self.data_ready.emit(raw_courses, all_standard_courses)


class NormalizerDialog(QDialog):
    def __init__(self, parent, raw_df, dealers_df, after_sheets, sales_sheets):
        super().__init__(parent)
        self.setWindowTitle("Data Normalization Tool")
        self.setGeometry(300, 300, 1000, 700)
        
        # Make dialog non-modal
        self.setModal(False)
        
        # Store references to data
        self.raw_df = raw_df
        self.dealers_df = dealers_df
        self.after_sheets = after_sheets
        self.sales_sheets = sales_sheets
        
        # Store all course mappings separately
        self.course_mappings = {}
        self.course_data_loaded = False
        
        layout = QVBoxLayout()
        self.tabs = QTabWidget()
        
        # Create tabs
        self.position_tab = self.create_position_tab()
        self.car_tab = self.create_car_tab()
        self.company_tab = self.create_company_tab()
        self.course_tab = self.create_course_tab_placeholder()
        self.dealer_tab = self.create_dealer_tab()  # New dealer tab
        
        self.tabs.addTab(self.position_tab, "Position Mappings")
        self.tabs.addTab(self.car_tab, "Car Category Mappings")
        self.tabs.addTab(self.company_tab, "Company Mappings")
        self.tabs.addTab(self.course_tab, "Course Mappings")
        self.tabs.addTab(self.dealer_tab, "Dealer Binding")  # Add dealer tab
        
        # Connect tab change
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("Save Mappings")
        self.cancel_btn = QPushButton("Cancel")
        
        self.save_btn.clicked.connect(self.save_mappings)
        self.cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addWidget(self.tabs)
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
        # Load existing mappings for other tabs
        self.load_mappings()
        
        # Start background course data loading
        self.course_loader = CourseDataLoader(raw_df, after_sheets, sales_sheets)
        self.course_loader.data_ready.connect(self.on_course_data_ready)
        self.course_loader.start()
    
    def create_dealer_tab(self):
        """Create dealer binding tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Add instruction label
        info_label = QLabel("Map dealer names from raw data to standardized names:")
        info_label.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(info_label)
        
        # Extract unique dealers from raw data
        if 'عنوان نمایندگی' in self.raw_df.columns:
            raw_dealers = self.raw_df['عنوان نمایندگی'].dropna().unique().tolist()
        else:
            raw_dealers = []
        
        # Create table
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Raw Dealer Name", "Mapped Dealer Name"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setRowCount(len(raw_dealers))
        
        for i, dealer in enumerate(raw_dealers):
            # Raw dealer name (read-only)
            raw_item = QTableWidgetItem(dealer)
            raw_item.setFlags(raw_item.flags() & ~Qt.ItemIsEditable)  # Make read-only
            table.setItem(i, 0, raw_item)
            
            # Mapped dealer name (editable)
            mapped_item = QTableWidgetItem(dealer)  # Default to same name
            table.setItem(i, 1, mapped_item)
        
        layout.addWidget(table)
        self.dealer_table = table
        
        # Add tip label
        tip_label = QLabel("Tip: Edit the 'Mapped Dealer Name' column to rename dealers. Leave blank to keep original name.")
        tip_label.setStyleSheet("color: gray; font-size: 10px; margin-top: 5px;")
        layout.addWidget(tip_label)
        
        widget.setLayout(layout)
        return widget
    
    def create_course_tab_placeholder(self):
        """Create a simple placeholder for course tab"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        self.course_loading_label = QLabel("Loading course data in background...")
        self.course_loading_label.setAlignment(Qt.AlignCenter)
        
        self.course_progress = QProgressBar()
        self.course_progress.setRange(0, 0)  # Indeterminate progress
        
        layout.addWidget(self.course_loading_label)
        layout.addWidget(self.course_progress)
        layout.addStretch()
        
        widget.setLayout(layout)
        return widget
    
    def on_course_data_ready(self, raw_courses, standard_courses):
        """Handle when course data is ready"""
        self.raw_course_list = raw_courses
        self.all_standard_courses = standard_courses
        self.course_data_loaded = True
        
        # Update the placeholder
        self.course_loading_label.setText("Course data loaded! Click to initialize course mappings.")
        self.course_progress.hide()
        
        # If user is currently on course tab, initialize it
        if self.tabs.currentIndex() == 3:
            self.initialize_course_tab()
    
    def on_tab_changed(self, index):
        """Handle tab changes"""
        if index == 3 and self.course_data_loaded and not hasattr(self, 'course_table'):
            self.initialize_course_tab()
    
    def initialize_course_tab(self):
        """Initialize the actual course tab"""
        if not self.course_data_loaded or hasattr(self, 'course_table'):
            return
        
        # Replace the placeholder with actual course tab
        self.course_tab = self.create_actual_course_tab()
        self.tabs.removeTab(3)
        self.tabs.insertTab(3, self.course_tab, "Course Mappings")
        self.tabs.setCurrentIndex(3)
        
        # Load course mappings
        self.load_course_mappings()
    
    def create_actual_course_tab(self):
        """Create the actual course tab with table"""
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create search bar
        search_layout = QHBoxLayout()
        search_label = QLabel("Search Courses:")
        self.course_search = QLineEdit()
        self.course_search.setPlaceholderText("Type to filter courses (showing first 20 by default)...")
        self.course_search.textChanged.connect(self.filter_course_table)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.course_search)
        layout.addLayout(search_layout)
        
        # Create table - start small
        table = QTableWidget()
        table.setColumnCount(2)  # Simplified: just Raw and Mapped
        table.setHorizontalHeaderLabels(["Raw Course", "Mapped Course"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        self.course_table = table
        
        # Show only first 20 courses initially
        self.populate_course_table_simple(limit=20)
        
        layout.addWidget(table)
        
        # Add instruction label
        info_label = QLabel("Tip: Use search to find specific courses. Total courses: " + str(len(self.raw_course_list)))
        info_label.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(info_label)
        
        widget.setLayout(layout)
        return widget
    
    def populate_course_table_simple(self, filter_text="", limit=None):
        """Populate course table with simplified approach"""
        if not hasattr(self, 'course_table'):
            return
            
        filter_text = filter_text.lower()
        
        # Save current mappings
        self.save_current_course_mappings()
        
        # Filter courses
        if filter_text:
            filtered_courses = [course for course in self.raw_course_list 
                               if filter_text in course.lower()]
        else:
            filtered_courses = self.raw_course_list
        
        # Apply limit
        if limit and not filter_text:
            filtered_courses = filtered_courses[:limit]
        
        # Clear and populate table
        self.course_table.setRowCount(len(filtered_courses))
        
        for i, course in enumerate(filtered_courses):
            self.course_table.setItem(i, 0, QTableWidgetItem(course))
            
            # Restore mapping from persistent storage
            mapped_value = self.course_mappings.get(course, "")
            self.course_table.setItem(i, 1, QTableWidgetItem(mapped_value))
    
    def filter_course_table(self):
        """Filter course table based on search text"""
        if not hasattr(self, 'course_table'):
            return
        search_text = self.course_search.text()
        self.populate_course_table_simple(search_text)
    
    def save_current_course_mappings(self):
        """Save current course mappings from visible table rows"""
        if not hasattr(self, 'course_table'):
            return
            
        for row in range(self.course_table.rowCount()):
            raw_item = self.course_table.item(row, 0)
            mapped_item = self.course_table.item(row, 1)
            
            if raw_item:
                raw_text = raw_item.text()
                mapped_text = mapped_item.text() if mapped_item else ""
                
                if mapped_text:
                    self.course_mappings[raw_text] = mapped_text
                elif raw_text in self.course_mappings:
                    del self.course_mappings[raw_text]
    
    def load_course_mappings(self):
        """Load course mappings from file"""
        path = 'mappings/course_mapping.csv'
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                
                for row in reader:
                    if len(row) >= 2:
                        self.course_mappings[row[0]] = row[1]
    
    def create_position_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Extract unique positions from raw data
        main_positions = self.raw_df['عنوان شغل'].dropna().unique().tolist()
        alt_positions = self.raw_df['شغل موازی (ارتقا)'].dropna().str.split('&&&').explode().str.strip().unique().tolist()
        all_positions = sorted(set(main_positions + alt_positions))
        
        # Extract positions from after and sales data
        after_positions = set()
        for sheet_name, df in self.after_sheets.items():
            if 'پست کاری' in df.columns:
                after_positions.update(df['پست کاری'].dropna().astype(str).unique())
        
        sales_positions = set()
        for sheet_name, df in self.sales_sheets.items():
            if 'پست کاری' in df.columns:
                sales_positions.update(df['پست کاری'].dropna().astype(str).unique())
        
        all_standard_positions = sorted(after_positions.union(sales_positions))
        
        # Create simplified table
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Raw Position", "Mapped Position"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setRowCount(len(all_positions))
        
        for i, position in enumerate(all_positions):
            table.setItem(i, 0, QTableWidgetItem(position))
            
            # Create combo box with standard positions
            combo = QComboBox()
            combo.addItem("")
            for std_pos in all_standard_positions:
                combo.addItem(std_pos)
            
            table.setCellWidget(i, 1, combo)
        
        layout.addWidget(table)
        self.position_table = table
        widget.setLayout(layout)
        return widget
    
    def create_car_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Extract car categories from dealers data
        car_categories = self.dealers_df.columns[3:48].tolist()
        
        # Extract car names from after and sales data
        after_cars = set()
        for sheet_name, df in self.after_sheets.items():
            if 'نام خودرو' in df.columns:
                after_cars.update(df['نام خودرو'].dropna().astype(str).unique())
        
        sales_cars = set()
        for sheet_name, df in self.sales_sheets.items():
            if 'نام خودرو' in df.columns:
                sales_cars.update(df['نام خودرو'].dropna().astype(str).unique())
        
        all_standard_cars = sorted(after_cars.union(sales_cars))
        
        # Create simplified table
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Raw Category", "Mapped Car"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setRowCount(len(car_categories))
        
        for i, category in enumerate(car_categories):
            table.setItem(i, 0, QTableWidgetItem(category))
            
            # Create combo box
            combo = QComboBox()
            combo.addItem("")
            for car in all_standard_cars:
                combo.addItem(car)
            
            table.setCellWidget(i, 1, combo)
        
        layout.addWidget(table)
        self.car_table = table
        widget.setLayout(layout)
        return widget
    
    def create_company_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Extract companies and sheet names
        companies = self.raw_df['company'].dropna().unique().tolist()
        after_sheets = sorted(self.after_sheets.keys())
        sales_sheets = sorted(self.sales_sheets.keys())
        all_sheets = sorted(set(after_sheets).union(set(sales_sheets)))
        
        # Create simplified table
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Raw Company", "Mapped Company"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setRowCount(len(companies))
        
        for i, company in enumerate(companies):
            table.setItem(i, 0, QTableWidgetItem(company))
            
            # Create combo box
            combo = QComboBox()
            combo.addItem("")
            for sheet in all_sheets:
                combo.addItem(sheet)
            
            table.setCellWidget(i, 1, combo)
        
        layout.addWidget(table)
        self.company_table = table
        widget.setLayout(layout)
        return widget
    
    def load_mappings(self):
        """Load existing mappings for position, car, company, and dealer tabs"""
        self.load_mapping_file('mappings/position_mapping.csv', self.position_table, 'position')
        self.load_mapping_file('mappings/car_mapping.csv', self.car_table, 'car')
        self.load_mapping_file('mappings/company_mapping.csv', self.company_table, 'company')
        self.load_dealer_mappings()
    
    def load_dealer_mappings(self):
        """Load dealer mappings from file"""
        path = 'mappings/dealer_mapping.csv'
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                
                mapping_dict = {}
                for row in reader:
                    if len(row) >= 2:
                        mapping_dict[row[0]] = row[1]
                
                # Apply mappings to dealer table
                for row in range(self.dealer_table.rowCount()):
                    raw_item = self.dealer_table.item(row, 0)
                    if raw_item and raw_item.text() in mapping_dict:
                        mapped_item = self.dealer_table.item(row, 1)
                        if mapped_item:
                            mapped_item.setText(mapping_dict[raw_item.text()])
    
    def load_mapping_file(self, path, table, tab_type):
        """Load mapping file for non-course tabs"""
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                
                mapping_dict = {}
                for row in reader:
                    if len(row) >= 2:
                        mapping_dict[row[0]] = row[1]
                
                # Apply mappings to table
                for row in range(table.rowCount()):
                    raw_item = table.item(row, 0)
                    if raw_item and raw_item.text() in mapping_dict:
                        combo = table.cellWidget(row, 1)
                        if combo:
                            index = combo.findText(mapping_dict[raw_item.text()])
                            if index >= 0:
                                combo.setCurrentIndex(index)
    
    def save_mappings(self):
        """Save all mappings"""
        os.makedirs("mappings", exist_ok=True)
        
        # Save non-course mappings
        self.save_mapping_type('position', self.position_table, 'position_mapping.csv')
        self.save_mapping_type('car', self.car_table, 'car_mapping.csv')
        self.save_mapping_type('company', self.company_table, 'company_mapping.csv')
        self.save_dealer_mappings()
        
        # Save course mappings if initialized
        if hasattr(self, 'course_table'):
            self.save_current_course_mappings()
            self.save_course_mappings()
        
        # Show success message
        QMessageBox.information(self, "Success", "All mappings saved successfully!")
        self.accept()
    
    def save_dealer_mappings(self):
        """Save dealer mappings"""
        path = os.path.join("mappings", "dealer_mapping.csv")
        
        with open(path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Raw", "Mapped"])
            
            for row in range(self.dealer_table.rowCount()):
                raw_item = self.dealer_table.item(row, 0)
                mapped_item = self.dealer_table.item(row, 1)
                
                raw = raw_item.text() if raw_item else ""
                mapped = mapped_item.text() if mapped_item else ""
                
                if raw and mapped and raw != mapped:  # Only save if different from original
                    writer.writerow([raw, mapped])
    
    def save_mapping_type(self, map_type, table, filename):
        """Save mappings for non-course tabs"""
        path = os.path.join("mappings", filename)
        
        with open(path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Raw", "Mapped"])
            
            for row in range(table.rowCount()):
                raw_item = table.item(row, 0)
                raw = raw_item.text() if raw_item else ""
                
                combo = table.cellWidget(row, 1)
                mapped = combo.currentText() if combo else ""
                
                if raw and mapped:
                    writer.writerow([raw, mapped])
    
    def save_course_mappings(self):
        """Save course mappings from persistent storage"""
        path = os.path.join("mappings", "course_mapping.csv")
        
        with open(path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Raw", "Mapped"])
            
            for raw, mapped in self.course_mappings.items():
                if raw and mapped:
                    writer.writerow([raw, mapped])


