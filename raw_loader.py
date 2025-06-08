import pandas as pd
import re
import os

def sanitize_dataframe(df):
    """
    Sanitize all values in a DataFrame using Persian normalization rules.
    Remove spaces only in columns 'نام دوره آموزشی' and 'عنوان دوره'.
    """
    persian_map = {
        'ي': 'ی',
        'ك': 'ک',
        '\u200c': ' ',  # ZWNJ to space
    }

    def sanitize(text, remove_spaces=False):
        if pd.isna(text):
            return ""
        text = str(text)
        text = text.replace('pds , ','pds و ')
        text = text.replace('ISO 10002 , ISO 10004','ISO 10002 و ISO 10004')

        text = text.replace(', ', '&&&')
        if remove_spaces:
            text = text.replace(' ', '')  # Remove spaces only for specified columns
        for arabic_char, persian_char in persian_map.items():
            text = text.replace(arabic_char, persian_char)
        text = text.replace('&&&', 'ampersand')
        text = text.replace('،', '')
        text = re.sub(r'[^a-zA-Z0-9\u0600-\u06FF\s]', '', text)
        text = text.lower()  # Convert all English letters to lowercase here
        text = text.replace('ampersand', '&&&')
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    # Apply sanitize to each cell, checking if the column needs space removal
    for col in df.columns:
        remove_spaces = col in ['نام دوره آموزشی', 'عنوان دوره']
        df[col] = df[col].apply(lambda x: sanitize(x, remove_spaces=remove_spaces))

    return df


def load_sanitized_data(file_path):
    """
    Load and sanitize a single-sheet Excel file.
    Applies special rules for 'after.xlsx' and 'sales.xlsx'.
    Also applies dealer mappings if available.
    """
    try:
        df = pd.read_excel(file_path)
        df = sanitize_dataframe(df)

        filename = os.path.basename(file_path).lower()

        if 'after' in filename:
            if 'نام خودرو' in df.columns:
                df['نام خودرو'] = df['نام خودرو'].apply(lambda x: x if x else 'عمومی')
        elif 'sales' in filename:
            if 'نام خودرو' not in df.columns:
                df['نام خودرو'] = 'عمومی'
        
        # Apply dealer mappings for raw data files
        if 'raw' in filename or 'dealers' not in filename:  # Apply to raw data, not dealers data
            dealer_mappings = load_dealer_mappings()
            df = apply_dealer_mappings(df, dealer_mappings)

        return df

    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return pd.DataFrame()

# Updated data loading functions with dealer mapping integration

def load_dealer_mappings():
    """Load dealer mappings from file"""
    path = 'mappings/dealer_mapping.csv'
    mappings = {}
    
    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                
                for row in reader:
                    if len(row) >= 2:
                        mappings[row[0]] = row[1]
        except Exception as e:
            print(f"Error loading dealer mappings: {e}")
    
    return mappings


def apply_dealer_mappings(df, dealer_mappings):
    """Apply dealer name mappings to a DataFrame"""
    if 'عنوان نمایندگی' in df.columns and dealer_mappings:
        df = df.copy()  # Don't modify original
        df['عنوان نمایندگی'] = df['عنوان نمایندگی'].map(dealer_mappings).fillna(df['عنوان نمایندگی'])
    return df


def load_all_sanitized_sheets(file_path):
    """
    Load and sanitize all worksheets in an Excel file.
    Returns a dictionary {sheet_name: sanitized DataFrame}.
    Applies same special handling as load_sanitized_data.
    Also applies dealer mappings if available.
    """
    try:
        excel_file = pd.ExcelFile(file_path)
        sanitized_sheets = {}
        filename = os.path.basename(file_path).lower()

        # Load dealer mappings once
        dealer_mappings = load_dealer_mappings()

        for sheet_name in excel_file.sheet_names:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            df = sanitize_dataframe(df)

            if 'after' in filename:
                if 'نام خودرو' in df.columns:
                    df['نام خودرو'] = df['نام خودرو'].apply(lambda x: x if x else 'عمومی')
            elif 'sales' in filename:
                if 'نام خودرو' not in df.columns:
                    df['نام خودرو'] = 'عمومی'
            
            # Apply dealer mappings for raw data files
            if 'raw' in filename or 'dealers' not in filename:  # Apply to raw data, not dealers data
                df = apply_dealer_mappings(df, dealer_mappings)

            sanitized_sheets[sheet_name] = df

        return sanitized_sheets
    except Exception as e:
        print(f"Error loading sheets from {file_path}: {e}")
        return {}