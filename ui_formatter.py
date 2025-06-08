class UIFormatter:
    """Formats analysis data into rich text (HTML) for display in Qt widgets."""

    @staticmethod
    def _get_status_indicator(is_passed):
        """Returns a colored symbol for pass/fail status."""
        return '<span style="color: green;">✔</span>' if is_passed else '<span style="color: red;">✖</span>'

    @staticmethod
    def _calculate_average(progress_list):
        """Calculate average from a list of progress percentages."""
        if not progress_list:
            return 0
        # Extract numeric values from strings like "75%"
        numeric_values = []
        for progress in progress_list:
            if progress and progress != "-" and progress.strip():
                try:
                    # Remove % sign and convert to float
                    progress_str = str(progress).strip()
                    if progress_str.endswith('%'):
                        numeric_value = float(progress_str[:-1])
                    else:
                        numeric_value = float(progress_str)
                    numeric_values.append(numeric_value)
                except (ValueError, AttributeError):
                    continue
        
        return sum(numeric_values) / len(numeric_values) if numeric_values else 0

    @staticmethod
    def _create_personnel_table(personnel_data, table_title, progress_column):
        """Create HTML table for personnel with specific progress column."""
        if not personnel_data:
            return f"<p>هیچ پرسنل {table_title} یافت نشد.</p>"
        
        # Calculate average
        progress_values = [record[progress_column] for record in personnel_data]
        average = UIFormatter._calculate_average(progress_values)
        
        html = f"<h4>{table_title} (میانگین: {average:.1f}%)</h4>"
        html += "<table border='1' style='width:100%; border-collapse: collapse;' cellpadding='5'>"
        html += """
            <tr style='background-color:#f0f0f0;'>
                <th>نام پرسنل</th>
                <th>سمت</th>
                <th>پیشرفت</th>
            </tr>
        """
        
        for record in personnel_data:
            progress_value = record[progress_column]
            # Color code the progress cell based on completion
            progress_style = ""
            if progress_value and progress_value != "-" and str(progress_value).strip():
                try:
                    progress_str = str(progress_value).strip()
                    if progress_str.endswith('%'):
                        numeric_progress = float(progress_str[:-1])
                    else:
                        numeric_progress = float(progress_str)
                    
                    if numeric_progress >= 80:
                        progress_style = "background-color: #90EE90;"  # Light green
                    elif numeric_progress >= 50:
                        progress_style = "background-color: #FFE4B5;"  # Light yellow
                    else:
                        progress_style = "background-color: #FFB6C1;"  # Light red
                except (ValueError, AttributeError):
                    pass
            
            html += f"""
                <tr>
                    <td>{record['name']}</td>
                    <td>{record['position']}</td>
                    <td style='text-align:center; {progress_style}'>{progress_value}</td>
                </tr>
            """
        html += "</table><br>"
        return html



    @staticmethod
    def format_dealer_details_html(dealer_name, categories, summary_data):
        """Creates HTML for the dealer information panel with separate sales and after-sales tables."""
        html = f"<h3>{dealer_name}</h3>"
        html += "<b>خودروهای مجاز:</b> " + (", ".join(categories) if categories else "هیچکدام")
        html += "<hr>"

        if not summary_data:
            html += "<p>اطلاعاتی برای نمایش وجود ندارد.</p>"
            return html

        # Separate personnel by their progress data (fixed logic)
        sales_personnel = []
        after_sales_personnel = []
        
        for record in summary_data:
            # Check if person has meaningful sales progress
            sales_progress = record.get('sales_progress', '')
            if (sales_progress and 
                sales_progress != "-" and 
                str(sales_progress).strip() and 
                str(sales_progress).strip() != "0%" and
                str(sales_progress).strip() != "0"):
                sales_personnel.append(record)
            
            # Check if person has meaningful after-sales progress  
            after_progress = record.get('after_progress', '')
            if (after_progress and 
                after_progress != "-" and 
                str(after_progress).strip() and 
                str(after_progress).strip() != "0%" and
                str(after_progress).strip() != "0"):
                after_sales_personnel.append(record)

        # Create separate tables
        html += UIFormatter._create_personnel_table(
            sales_personnel, 
            "پرسنل فروش", 
            "sales_progress"
        )
        
        html += UIFormatter._create_personnel_table(
            after_sales_personnel, 
            "پرسنل خدمات پس از فروش", 
            "after_progress"
        )
        
        return html

    @staticmethod
    def format_personnel_details_html(analysis_result):
        """Creates a detailed HTML report for a single person's training status."""
        if not analysis_result:
            return "اطلاعاتی برای نمایش وجود ندارد."

        name = analysis_result['name']
        position = analysis_result['position']
        passed_set = analysis_result['passed_courses_set']
        requirements = analysis_result['requirements']
        pass_statuses = analysis_result['pass_statuses']

        html = f"<h3>{name}</h3><b>سمت:</b> {position}<hr>"

        # Display Requirements Analysis
        html += "<h4>تحلیل وضعیت آموزشی</h4>"
        if not requirements:
            html += "<p>هیچ دوره الزامی برای این سمت تعریف نشده است.</p>"
            return html

        for file, cars in requirements.items():
            file_title = "خدمات پس از فروش" if file == "after" else "فروش"
            html += f"<b>بخش: {file_title}</b>"
            html += "<table border='1' style='width:100%; border-collapse: collapse;' cellpadding='5'>"
            html += "<tr style='background-color:#f0f0f0;'><th>خودرو/دسته</th><th>معیار</th><th>وضعیت</th><th>دوره‌های الزامی</th></tr>"

            for car, criteria_dict in sorted(cars.items()):
                for crit, courses in sorted(criteria_dict.items()):
                    is_passed = pass_statuses.get(file, {}).get(car, {}).get(crit, False)
                    status_icon = UIFormatter._get_status_indicator(is_passed)
                    
                    # Color courses based on whether they were passed
                    course_parts = []
                    for c in courses:
                        if c in passed_set:
                            course_parts.append(f'<span style="background-color:#a2c1d5;">{c}</span>')
                        else:
                            course_parts.append(f'<span style="background-color:#d3d3d3;">{c}</span>')
                    
                    courses_str = " & ".join(course_parts)

                    html += f"<tr><td>{car}</td><td>{crit}</td><td style='text-align:center;'>{status_icon}</td><td>{courses_str}</td></tr>"
            
            html += "</table><br>"
        
        # Display Passed Courses
        if passed_set:
            html += "<b>دوره‌های گذرانده شده:</b> "
            courses_html = [f'<span style="background-color:#a2c1d5; padding: 2px 5px; border-radius: 3px;">{c}</span>' for c in sorted(list(passed_set))]
            html += " ".join(courses_html)
            html += "<hr>"

        return html
