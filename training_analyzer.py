# training_analyzer.py
from collections import defaultdict
import pandas as pd


class TrainingAnalyzer:
    """
    Handles all business logic related to analyzing personnel training status.
    This ensures consistency across UI display, exports, and other features.
    """
    def __init__(self, data_manager):
        self.dm = data_manager


    def _get_requirements(self, mapped_company, mapped_position, mapped_categories, dealer_name=None, raw_company=None):
        """
        Gathers all training requirements (sales and after-sales) for a given role.
        """
        grouped_reqs = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

        # 1. Get After-Sales Requirements
        print(f"\n=== DEBUG: Processing After-Sales Requirements ===")
        print(f"Dealer: {dealer_name}, Mapped Company: {mapped_company}, Mapped Position: {mapped_position}, Categories: {mapped_categories}")

        # For SMC dealers, use the mapped company name to look up sheets
        if raw_company == 'smc':
            after_sheet_df = self.dm.after_sheets.get(mapped_company)
            print(f"🔍 SMC dealer detected - using mapped company '{mapped_company}' for after-sales lookup")
        else:
            # Use original logic for non-SMC dealers
            after_sheet_df = self.dm.after_sheets.get(mapped_company)
            print(f"🔍 Non-SMC dealer - using mapped company '{mapped_company}' for after-sales lookup")

        if after_sheet_df is None:
            lookup_key = mapped_company
            print(f"❌ No after-sales sheet found for key '{lookup_key}'")
        else:
            lookup_key = mapped_company
            print(f"✅ Loaded after-sales sheet for key '{lookup_key}' with {len(after_sheet_df)} rows")

            search_cars = mapped_categories + ["عمومی"]
            print(f"🔍 Looking for rows where position == '{mapped_position}' and car in {search_cars}")

            matched_rows = 0
            for _, row in after_sheet_df.iterrows():
                row_pos = str(row.get("پست کاری", "")).strip()
                row_car = str(row.get("نام خودرو", "")).strip() or "عمومی"

                if row_pos == mapped_position and row_car in search_cars:
                    criteria = str(row.get("نام سرفصل", "")).strip()
                    course = str(row.get("نام دوره آموزشی", "")).strip()
                    if criteria and course and criteria.lower() != "nan" and course.lower() != "nan":
                        grouped_reqs["after"][row_car][criteria].append(course)
                        matched_rows += 1

            if matched_rows == 0:
                print(f"⚠️ No matching rows found for mapped position '{mapped_position}' in after-sales sheet.")

        # 2. Get Sales Requirements
        # For SMC dealers, use the mapped company name to look up sheets
        if raw_company == 'smc':
            sales_sheet_df = self.dm.sales_sheets.get(mapped_company)
            print(f"🔍 SMC dealer - using mapped company '{mapped_company}' for sales lookup")
        else:
            # Use original logic for non-SMC dealers
            sales_sheet_df = self.dm.sales_sheets.get(mapped_company)
            print(f"🔍 Non-SMC dealer - using mapped company '{mapped_company}' for sales lookup")
        
        if sales_sheet_df is not None:
            lookup_key = mapped_company
            print(f"✅ Processing sales requirements from sheet for key '{lookup_key}'")
            
            for _, row in sales_sheet_df.iterrows():
                row_pos = str(row.get("پست کاری", "")).strip()
                if row_pos == mapped_position:
                    criteria = str(row.get("نام سرفصل", "")).strip()
                    course = str(row.get("نام دوره آموزشی", "")).strip()
                    if criteria and course and criteria != "nan" and course != "nan":
                        grouped_reqs["sales"]["فروش"][criteria].append(course)
        else:
            lookup_key = mapped_company
            print(f"❌ No sales sheet found for key '{lookup_key}'")
        
        return grouped_reqs


    def _calculate_pass_status(self, grouped_reqs, passed_courses_set):
        """
        Calculates the pass/fail status for each criterion based on the rules.
        - Rule 1: Pass if any required course is in passed_courses_set.
        - Rule 2: Pass if criteria name contains 'گازسوز' (exempt).
        - Rule 3: 'ابزار مخصوص' passes only if all other criteria in the same car group are passed.
        """
        pass_status = defaultdict(lambda: defaultdict(dict))

        # First pass: Handle standard passes and 'گازسوز' exemptions.
        for file, cars in grouped_reqs.items():
            for car, criteria_dict in cars.items():
                for crit, courses in criteria_dict.items():
                    passed = any(c in passed_courses_set for c in courses) or "گازسوز" in crit
                    pass_status[file][car][crit] = passed

        # Second pass: Handle conditional 'ابزار مخصوص' logic.
        for file, cars in grouped_reqs.items():
            for car, criteria_dict in cars.items():
                for crit in criteria_dict.keys():
                    if "ابزار مخصوص" in crit:
                        other_crits = [c for c in criteria_dict.keys() if c != crit]
                        all_others_passed = all(pass_status[file][car].get(c, False) for c in other_crits)
                        pass_status[file][car][crit] = all_others_passed
        
        return pass_status


    def analyze_personnel_training(self, pcode, dealer_name, position):
        """
        Performs a full training analysis for a single person in a specific role.
        """
        personnel_data = self.dm.raw[
            (self.dm.raw['کد پرسنلی'] == pcode) &
            (self.dm.raw['عنوان نمایندگی'] == dealer_name)
        ]
        if personnel_data.empty:
            return None

        # Apply mappings
        raw_company = personnel_data.iloc[0].get('company', '')
        mapped_company = self.dm.company_mapping.get(raw_company, raw_company)
        mapped_position = self.dm.position_mapping.get(position, position)
        

        # CRITICAL FIX: For SMC dealers, use hardcoded categories
        if raw_company == 'smc':
            # For SMC dealers, use hardcoded categories
            mapped_categories = ['j6', 'tigerv', 'عمومی']
            print(f"SMC dealer detected - using hardcoded categories: {mapped_categories}")
        else:
            lookup_dealer_name = self.dm.get_training_data_dealer_name(dealer_name)
            print(f"Non-SMC dealer - using training data dealer name: {lookup_dealer_name}")
            dealer_cats = self.dm.get_dealer_categories(lookup_dealer_name)
            mapped_categories = [self.dm.car_mapping.get(cat, cat) for cat in dealer_cats]


        # Get passed courses
        passed_courses = personnel_data['عنوان دوره'].dropna().unique().tolist()
        mapped_passed_courses = {self.dm.course_mapping.get(c, c) for c in passed_courses}
        
        # Get all requirements - pass dealer_name for SMC handling
        requirements = self._get_requirements(mapped_company, mapped_position, mapped_categories, dealer_name)
        
        pass_statuses = self._calculate_pass_status(requirements, mapped_passed_courses)

        # Structure the final result
        analysis_result = {
            "pcode": pcode,
            "name": personnel_data.iloc[0]['نام و نام خانوادگی'],
            "position": position,
            "dealer_name": dealer_name,
            "passed_courses_set": mapped_passed_courses,
            "requirements": requirements,
            "pass_statuses": pass_statuses,
        }
        return analysis_result


    def generate_dealer_personnel_summary(self, dealer_name):
        """
        Generates a summary of training progress for each person-position
        at a specific dealer. (FIXED VERSION)
        """
        summary_list = []
        dealer_personnel = self.dm.get_personnel_for_dealer(dealer_name)
        seen_combinations = set()

        for _, row in dealer_personnel.iterrows():
            name = row['نام و نام خانوادگی']
            pcode = row.get('کد پرسنلی', '')
            
            # Get all positions for this person
            positions = []
            if pd.notna(row.get('عنوان شغل')) and row.get('عنوان شغل').strip():
                positions.append(row.get('عنوان شغل').strip())
            if pd.notna(row.get('شغل موازی (ارتقا)')) and row.get('شغل موازی (ارتقا)').strip():
                positions.extend([p.strip() for p in row.get('شغل موازی (ارتقا)').split('&&&') if p.strip()])
            
            for pos in positions:
                # Skip if we've already processed this combination OR if position is not mappable
                if (pcode, pos) in seen_combinations or pos not in self.dm.position_mapping:
                    continue
                seen_combinations.add((pcode, pos))

                # Analyze training for this specific person-position combination
                analysis = self.analyze_personnel_training(pcode, dealer_name, pos)
                if not analysis:
                    continue

                # Calculate progress percentages
                after_progress = self._calculate_progress_percentage(analysis, 'after')
                sales_progress = self._calculate_progress_percentage(analysis, 'sales')

                summary_list.append({
                    'name': name,
                    'position': pos,
                    'after_progress': after_progress,
                    'sales_progress': sales_progress,
                })
        
        # Sort by name and position for consistent display
        summary_list.sort(key=lambda x: (x['name'], x['position']))
        return summary_list

    def _calculate_progress_percentage(self, analysis, section_type):
        """
        Calculate the percentage of completed requirements for a given section.
        
        Args:
            analysis: The analysis result from analyze_personnel_training()
            section_type: Either 'sales' or 'after'
        
        Returns:
            String: Percentage as "XX%" or "-" if no requirements
        """
        if not analysis or 'requirements' not in analysis:
            return "-"
        
        requirements = analysis['requirements']
        pass_statuses = analysis.get('pass_statuses', {})
        
        # Check if this section exists in requirements
        if section_type not in requirements:
            return "-"
        
        section_requirements = requirements[section_type]
        if not section_requirements:
            return "-"
        
        # Count total requirements and passed requirements
        total_requirements = 0
        passed_requirements = 0
        
        for car, criteria_dict in section_requirements.items():
            for criteria, courses in criteria_dict.items():
                total_requirements += 1
                # Check if this specific requirement is passed
                if (section_type in pass_statuses and 
                    car in pass_statuses[section_type] and 
                    criteria in pass_statuses[section_type][car] and 
                    pass_statuses[section_type][car][criteria]):
                    passed_requirements += 1
        
        if total_requirements == 0:
            return "-"
        
        percentage = (passed_requirements / total_requirements) * 100
        return f"{percentage:.1f}%"

    def generate_dealer_export_df(self, dealer_name):
        """
        Generates a detailed DataFrame for a single dealer, suitable for export.
        This replaces the old `get_dealer_criteria_data` method.
        """
        dealer_personnel = self.dm.get_personnel_for_dealer(dealer_name)
        
        export_rows = []
        seen_combinations = set()

        for _, row in dealer_personnel.iterrows():
            name = row['نام و نام خانوادگی']
            pcode = row.get('کد پرسنلی', '')
            
            positions = []
            if pd.notna(row.get('عنوان شغل')) and row.get('عنوان شغل').strip():
                positions.append(row.get('عنوان شغل').strip())
            if pd.notna(row.get('شغل موازی (ارتقا)')) and row.get('شغل موازی (ارتقا)').strip():
                positions.extend([p.strip() for p in row.get('شغل موازی (ارتقا)').split('&&&') if p.strip()])
            
            for pos in positions:
                # Use a more comprehensive key to avoid duplicates
                combination_key = (name, pos, pcode)
                if combination_key in seen_combinations:
                    continue
                seen_combinations.add(combination_key)

                # Only process positions that can be mapped
                if pos not in self.dm.position_mapping:
                    continue

                analysis = self.analyze_personnel_training(pcode, dealer_name, pos)
                if not analysis:
                    continue
                
                # Convert analysis results to flat rows for DataFrame export
                for file, cars in analysis['requirements'].items():
                    for car, criteria_dict in cars.items():
                        for crit, courses in criteria_dict.items():
                            is_passed = analysis['pass_statuses'].get(file, {}).get(car, {}).get(crit, False)
                            
                            # Determine the reason/status text
                            reason = "گذرانده نشده"
                            if is_passed:
                                if "گازسوز" in crit:
                                    reason = "گازسوز (معاف)"
                                elif "ابزار مخصوص" in crit:
                                    reason = "ابزار مخصوص (شرطی)"
                                else:
                                    # Find which course was passed
                                    passed_course = next((c for c in courses if c in analysis['passed_courses_set']), "تکمیل شده")
                                    reason = passed_course
                            elif "ابزار مخصوص" in crit:
                                reason = "ابزار مخصوص (سایر معیارها تکمیل نشده)"

                            export_rows.append({
                                'نمایندگی': dealer_name,
                                'نام پرسنل': name,
                                'سمت': pos,
                                'معیار': crit,
                                'دسته': "خدمات پس از فروش" if file == "after" else "فروش",
                                'خودرو': car,
                                'گذرانده شده': 'بله' if is_passed else 'خیر',
                                'دلیل': reason
                            })

        return pd.DataFrame(export_rows)