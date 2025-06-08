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
        self.bdc_to_smc_map = {}


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
        self._load_mapping_file('dealer_mappings.csv', self.bdc_to_smc_map)

        self.load_bdc_to_smc_mapping()
        self.apply_dual_dealer_logic()




    def apply_dual_dealer_logic(self):
        if 'company' not in self.raw.columns or 'عنوان نمایندگی' not in self.raw.columns:
            return

        def _filter_positions(position_str, keyword):
            if not position_str:
                return ''
            parts = position_str.split('&&&')
            filtered = [p for p in parts if keyword in p]
            return '&&&'.join(filtered).strip()

        new_rows = []
        for idx, row in self.raw.iterrows():
            company = row['company']
            dealer_name = row['عنوان نمایندگی']
            dealer_code = str(dealer_name).split(" ")[0]

            if company != 'bdc' or dealer_code not in self.bdc_to_smc_map:
                new_rows.append(row)
                continue

            main_pos = str(row.get('عنوان شغل', '') or '')
            alt_pos = str(row.get('شغل موازی (ارتقا)', '') or '')
            full_pos = main_pos + '&&&' + alt_pos if alt_pos else main_pos

            diesel_present = 'دیزل' in full_pos
            siba_present = 'سیبا' in full_pos


            if diesel_present and not siba_present:
                new_rows.append(row)

            elif siba_present and not diesel_present:
                new_row = row.copy()
                new_row['company'] = 'smc'
                new_row['عنوان نمایندگی'] = self.bdc_to_smc_map[dealer_code]
                new_rows.append(new_row)

            elif diesel_present and siba_present:

                bdc_row = row.copy()
                bdc_row['company'] = 'bdc'
                bdc_row['عنوان نمایندگی'] = dealer_name
                bdc_row['عنوان شغل'] = _filter_positions(bdc_row.get('عنوان شغل', ''), 'دیزل')
                bdc_row['شغل موازی (ارتقا)'] = _filter_positions(bdc_row.get('شغل موازی (ارتقا)', ''), 'دیزل')

                smc_row = row.copy()
                smc_row['company'] = 'smc'
                smc_row['عنوان نمایندگی'] = self.bdc_to_smc_map[dealer_code]
                smc_row['عنوان شغل'] = _filter_positions(smc_row.get('عنوان شغل', ''), 'سیبا')
                smc_row['شغل موازی (ارتقا)'] = _filter_positions(smc_row.get('شغل موازی (ارتقا)', ''), 'سیبا')

                new_rows.extend([bdc_row, smc_row])

            else:
                # Keep original BDC row
                bdc_row = row.copy()
                bdc_row['company'] = 'bdc'
                bdc_row['عنوان نمایندگی'] = dealer_name
                new_rows.append(bdc_row)
                
                # Create corresponding SMC row
                smc_row = row.copy()
                smc_row['company'] = 'smc'
                smc_row['عنوان نمایندگی'] = self.bdc_to_smc_map[dealer_code]

                # Apply 'سیبا' to job titles for the new SMC row if not already present
                if pd.notna(smc_row.get('عنوان شغل')) and 'سیبا' not in smc_row['عنوان شغل']:
                    smc_row['عنوان شغل'] = smc_row['عنوان شغل'].strip() + ' سیبا'
                if pd.notna(smc_row.get('شغل موازی (ارتقا)')):
                    # Split and append ' سیبا' to each part if not present
                    alt_pos_parts = [p.strip() + ' سیبا' if 'سیبا' not in p else p.strip() for p in smc_row['شغل موازی (ارتقا)'].split('&&&')]
                    smc_row['شغل موازی (ارتقا)'] = '&&&'.join(alt_pos_parts)

                new_rows.append(smc_row)




        self.raw = pd.DataFrame(new_rows)

    def get_original_dealer_name(self, current_dealer_name):
        """
        Returns the original BDC dealer name if the current name is a mapped SMC dealer.
        This is needed for training analysis to work correctly with mapped dealers.
        """
        # Check if this is a mapped SMC dealer name
        for bdc_code, smc_name in self.bdc_to_smc_map.items():
            if smc_name == current_dealer_name:
                # Find the original BDC dealer name with this code
                original_dealers = self.raw[
                    (self.raw['company'] == 'bdc') & 
                    (self.raw['عنوان نمایندگی'].str.startswith(bdc_code))
                ]['عنوان نمایندگی'].unique()
                
                if len(original_dealers) > 0:
                    return original_dealers[0]
        
        # If not a mapped dealer, return the original name
        return current_dealer_name

    def get_training_data_dealer_name(self, dealer_name):
        """
        Returns the dealer name that should be used for training data lookups.
        For mapped SMC dealers, this returns the original BDC dealer name.
        """
        return self.get_original_dealer_name(dealer_name)



    def load_bdc_to_smc_mapping(self):
        """Loads BDC to SMC dealer name mapping from a CSV like: bdc_code,smc_dealer_name"""
        self.bdc_to_smc_map = {}
        path = os.path.join(self.mapping_path, 'bdc_to_smc.csv')
        if not os.path.exists(path):
            print("⚠ Mapping file not found:", path)
            return
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            for row in reader:
                if len(row) >= 2:
                    bdc_code = row[0].strip()
                    smc_dealer = row[1].strip()
                    self.bdc_to_smc_map[bdc_code] = smc_dealer



    def _load_mapping_file(self, filename, mapping_dict):
        """Helper to load a single CSV mapping file."""
        assert 'csv' in globals(), "csv is not in globals"

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

        categories = []
        dealer_code = dealer_name[:4]

        dealer_row = self.dealers[self.dealers.iloc[:, 0] == dealer_code]

        if not dealer_row.empty:
            row = dealer_row.iloc[0]
            for col_idx in range(3, min(48, len(self.dealers.columns))):
                category_name = self.dealers.columns[col_idx]
                cell_value = row.iloc[col_idx]
                if pd.notna(cell_value) and str(cell_value).strip().lower() == 'p':
                    categories.append(category_name)
        else:
            print(f"    ❌ No dealer found with code '{dealer_code}' in dealers.xlsx")
        return categories



    def get_personnel_for_dealer(self, dealer_name):
        """Retrieves all personnel records for a given dealer."""
        return self.raw[self.raw['عنوان نمایندگی'] == dealer_name]