# data_manager.py
import pandas as pd
import os
import csv

from raw_loader import load_sanitized_data, load_all_sanitized_sheets

class DataManager:
    """Handles loading and managing all application data and mappings."""

    def __init__(self, resource_path="res/", mapping_path="mappings/"):
        self.resource_path = resource_path
        self.mapping_path = mapping_path

        self.raw = pd.DataFrame()
        self.dealers = pd.DataFrame()
        self.after_sheets = {}
        self.sales_sheets = {}

        self.position_mapping = {}
        self.car_mapping = {}
        self.company_mapping = {}
        self.course_mapping = {}

    def load_all_data(self):
        """Loads all data files and mappings from disk."""
        # Load data files
        self.raw = load_sanitized_data(os.path.join(self.resource_path, "raw.xlsx"))
        self.dealers = load_sanitized_data(os.path.join(self.resource_path, "dealers.xlsx"))
        self.after_sheets = load_all_sanitized_sheets(os.path.join(self.resource_path, "after.xlsx"))
        self.sales_sheets = load_all_sanitized_sheets(os.path.join(self.resource_path, "sales.xlsx"))

        # Load all mappings
        self._load_mapping_file('position_mapping.csv', self.position_mapping)
        self._load_mapping_file('car_mapping.csv', self.car_mapping)
        self._load_mapping_file('company_mapping.csv', self.company_mapping)
        self._load_mapping_file('course_mapping.csv', self.course_mapping)

    def _load_mapping_file(self, filename, mapping_dict):
        """Helper to load a single CSV mapping file."""
        path = os.path.join(self.mapping_path, filename)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                for row in reader:
                    if len(row) >= 2:
                        mapping_dict[row[0]] = row[1]

    def get_all_dealer_names(self):
        """Returns a sorted list of unique dealer names."""
        return sorted(self.raw['عنوان نمایندگی'].unique())

    def get_dealer_categories(self, dealer_name):
        """Extracts authorized service categories for a specific dealer."""
        categories = []
        dealer_code = dealer_name[:4]
        dealer_row = self.dealers[self.dealers.iloc[:, 0] == dealer_code]

        if not dealer_row.empty:
            row = dealer_row.iloc[0]
            # Columns D to AV (index 3 to 47) contain category flags
            for col_idx in range(3, min(48, len(self.dealers.columns))):
                category_name = self.dealers.columns[col_idx]
                cell_value = row.iloc[col_idx]
                if pd.notna(cell_value) and str(cell_value).strip().lower() == 'p':
                    categories.append(category_name)
        return categories

    def get_personnel_for_dealer(self, dealer_name):
        """Retrieves all personnel records for a given dealer."""
        return self.raw[self.raw['عنوان نمایندگی'] == dealer_name]