"""
CSV processing utilities for SCRA multi-record verification
"""

import csv
import io
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime
import re


class SCRARecord:
    """Represents a single SCRA verification record"""
    
    def __init__(self, data: Dict[str, Any]):
        self.ssn = self._clean_ssn(data.get('ssn', ''))
        self.date_of_birth = self._format_date(data.get('date_of_birth', ''))
        self.last_name = self._clean_name(data.get('last_name', ''))
        self.first_name = self._clean_name(data.get('first_name', ''))
        self.middle_name = self._clean_name(data.get('middle_name', ''))
        self.customer_record_id = self._clean_customer_id(data.get('customer_record_id', ''))
        self.active_duty_status_date = self._format_date(data.get('active_duty_status_date', ''))
        
        # Store original row for error reporting
        self.original_data = data
        self.row_number = data.get('_row_number', 0)
        
    def _clean_ssn(self, ssn: str) -> str:
        """Clean and validate SSN - must be 9 digits"""
        if not ssn:
            return ''
        # Remove all non-digits
        digits = re.sub(r'\D', '', str(ssn))
        return digits[:9] if len(digits) >= 9 else digits
    
    def _format_date(self, date_str: str) -> str:
        """Format date to YYYYMMDD or return empty string"""
        if not date_str:
            return ''
        
        date_str = str(date_str).strip()
        
        # Remove any non-digit characters for length check
        digits = re.sub(r'\D', '', date_str)
        
        # If already 8 digits, assume YYYYMMDD
        if len(digits) == 8:
            return digits
        
        # Try to parse various formats including MM/DD/YY
        date_formats = [
            '%m/%d/%y',    # NEW: 10/29/86 (2-digit year)
            '%m-%d-%y',    # NEW: 10-29-86
            '%m/%d/%Y',    # 10/29/1986
            '%m-%d-%Y',    # 10-29-1986
            '%Y-%m-%d',    # 1986-10-29
            '%Y/%m/%d',    # 1986/10/29
            '%d/%m/%Y',    # 29/10/1986 (European)
            '%d-%m-%Y',    # 29-10-1986
            '%d/%m/%y',    # 29/10/86 (European)
        ]
        
        for fmt in date_formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y%m%d')
            except ValueError:
                continue
        
        # If we can't parse it, try to validate as YYYYMMDD before returning
        if len(digits) >= 6:
            candidate = digits[:8].ljust(8, '0')
            # Validate that this is actually a valid date
            try:
                datetime.strptime(candidate, '%Y%m%d')
                return candidate
            except ValueError:
                # Invalid date, return empty string
                return ''
        
        return ''
    
    def _clean_name(self, name: str) -> str:
        """Clean and validate name field"""
        if not name:
            return ''
        return str(name).strip().upper()[:20]  # Max 20 chars for SCRA format
    
    def _clean_customer_id(self, customer_id: str) -> str:
        """Clean customer ID field"""
        if not customer_id:
            return ''
        return str(customer_id).strip()[:20]  # Max 20 chars for SCRA format
    
    def validate(self) -> List[str]:
        """Validate the record and return list of errors"""
        errors = []
        
        # SSN validation - can be empty (will be converted to spaces)
        if self.ssn and len(self.ssn) != 9:
            errors.append(f"SSN must be 9 digits or empty, got {len(self.ssn)}")
        elif self.ssn and not self.ssn.isdigit():
            errors.append("SSN must contain only digits or be empty")
        
        if not self.last_name:
            errors.append("Last name is required")
        
        if not self.first_name:
            errors.append("First name is required")
        
        if not self.active_duty_status_date:
            errors.append("Active duty status date is required")
        elif len(self.active_duty_status_date) != 8:
            errors.append("Active duty status date must be in YYYYMMDD format")
        else:
            # Validate that it's a real date
            try:
                datetime.strptime(self.active_duty_status_date, '%Y%m%d')
            except ValueError:
                errors.append(f"Active duty status date '{self.active_duty_status_date}' is not a valid date")
        
        # Optional date validation
        if self.date_of_birth and len(self.date_of_birth) != 8:
            errors.append("Date of birth must be in YYYYMMDD format or empty")
        elif self.date_of_birth:
            # Validate that it's a real date
            try:
                datetime.strptime(self.date_of_birth, '%Y%m%d')
            except ValueError:
                errors.append(f"Date of birth '{self.date_of_birth}' is not a valid date")
        
        return errors
    
    def to_fixed_width(self) -> str:
        """Convert record to 119-character fixed-width format (correct SCRA format)"""
        # CORRECT SCRA fixed-width format (119 characters total):
        # SSN: positions 0-8 (9 chars, spaces if empty)
        # DOB: positions 9-16 (8 chars, YYYYMMDD or 8 spaces if empty)
        # Last Name: starts at position 17, variable length
        # First Name: starts at position 43, variable length
        # Names section total: positions 17-90 (74 chars)
        # Active Duty Status Date: positions 91-98 (8 chars, YYYYMMDD)
        # Middle Name: positions 99-118 (20 chars, optional, space-padded)
        
        line = ""
        
        # SSN: 9 characters (spaces if empty)
        ssn = self.ssn.strip() if self.ssn else ''
        if ssn and len(ssn) == 9 and ssn.isdigit():
            line += ssn  # Positions 0-8
        else:
            line += ' ' * 9  # 9 spaces if empty or invalid
        
        # DOB: exactly 8 characters (YYYYMMDD or 8 spaces)
        dob = self.date_of_birth.strip() if self.date_of_birth else ''
        if dob and len(dob) == 8 and dob.isdigit():
            line += dob  # Positions 9-16
        else:
            line += ' ' * 8  # 8 spaces if empty or invalid
        
        # Names section: 74 characters total (positions 17-90)
        # Last name starts at position 17, first name at position 43
        # Names should be title case (first letter uppercase, rest lowercase)
        last_name = self.last_name.strip().title()
        first_name = self.first_name.strip().title()
        
        # Last name: position 17-42 (26 characters available)
        last_padded = last_name.ljust(26)[:26]
        
        # First name: position 43-90 (48 characters available)
        first_padded = first_name.ljust(48)[:48]
        
        line += last_padded + first_padded  # Positions 17-90 (74 chars total)
        
        # Active Duty Status Date: 8 characters, YYYYMMDD
        line += self.active_duty_status_date[:8].ljust(8)  # Positions 91-98
        
        # Middle Name: 20 characters, optional, space-padded, title case
        middle = (self.middle_name.strip().title() if self.middle_name else '')
        line += middle.ljust(20)[:20]  # Positions 99-118
        
        # Ensure the line is exactly 119 characters
        line = line.ljust(119)[:119]
        
        return line
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary for API calls"""
        return {
            'ssn': self.ssn,
            'firstName': self.first_name,
            'lastName': self.last_name,
            'middleName': self.middle_name,
            'dateOfBirth': self.date_of_birth,
            'activeDutyDate': self.active_duty_status_date,
            'customerRecordId': self.customer_record_id
        }


class CSVProcessor:
    """Processes CSV files for SCRA multi-record verification"""
    
    def __init__(self):
        # Core required columns for new format
        self.required_columns = ['ssn', 'last_name', 'first_name', 'active_duty_status_date']
        # Optional columns (now includes date_of_birth, middle_name, customer_record_id)
        self.optional_columns = ['date_of_birth', 'middle_name', 'customer_record_id']
        self.all_columns = self.required_columns + self.optional_columns
    
    def parse_csv_content(self, csv_content: str) -> Tuple[List[SCRARecord], List[str]]:
        """
        Parse CSV content and return records and errors
        
        Returns:
            Tuple of (records, errors)
        """
        records = []
        errors = []
        
        try:
            # Use StringIO to read CSV content
            csv_file = io.StringIO(csv_content)
            
            # Detect delimiter
            sample = csv_content[:1024]
            sniffer = csv.Sniffer()
            try:
                delimiter = sniffer.sniff(sample).delimiter
            except csv.Error:
                delimiter = ','
            
            # Read CSV
            csv_file.seek(0)
            reader = csv.DictReader(csv_file, delimiter=delimiter)
            
            # Normalize column names (lowercase, replace spaces/dashes with underscores)
            if reader.fieldnames:
                normalized_fieldnames = []
                for field in reader.fieldnames:
                    normalized = field.lower().strip()
                    normalized = re.sub(r'[^\w]', '_', normalized)
                    normalized = re.sub(r'_+', '_', normalized)
                    normalized = normalized.strip('_')
                    normalized_fieldnames.append(normalized)
                
                # Create mapping from normalized to original
                field_mapping = dict(zip(normalized_fieldnames, reader.fieldnames))
                
                # Check for required columns
                missing_columns = []
                for required in self.required_columns:
                    if required not in normalized_fieldnames:
                        # Try common variations
                        variations = self._get_column_variations(required)
                        found = False
                        for variation in variations:
                            if variation in normalized_fieldnames:
                                # Update the mapping
                                idx = normalized_fieldnames.index(variation)
                                normalized_fieldnames[idx] = required
                                found = True
                                break
                        if not found:
                            missing_columns.append(required)
                
                if missing_columns:
                    errors.append(f"Missing required columns: {', '.join(missing_columns)}")
                    return records, errors
            
            # Process each row
            row_number = 1
            for row in reader:
                row_number += 1
                
                # Normalize row keys
                normalized_row = {}
                for norm_field, orig_field in field_mapping.items():
                    if norm_field in self.all_columns:
                        normalized_row[norm_field] = row.get(orig_field, '').strip()
                
                # Add row number for error reporting
                normalized_row['_row_number'] = row_number
                
                # Create record
                try:
                    record = SCRARecord(normalized_row)
                    
                    # Validate record
                    record_errors = record.validate()
                    if record_errors:
                        for error in record_errors:
                            errors.append(f"Row {row_number}: {error}")
                    else:
                        records.append(record)
                        
                except Exception as e:
                    errors.append(f"Row {row_number}: Error processing record - {str(e)}")
            
            if not records and not errors:
                errors.append("No valid records found in CSV file")
                
        except Exception as e:
            errors.append(f"Error parsing CSV file: {str(e)}")
        
        return records, errors
    
    def _get_column_variations(self, column: str) -> List[str]:
        """Get common variations of column names"""
        variations = {
            'ssn': ['social_security_number', 'social_security', 'ss_number', 'ssn_number'],
            'last_name': ['lastname', 'surname', 'family_name', 'last'],
            'first_name': ['firstname', 'given_name', 'first'],
            'middle_name': ['middlename', 'middle_initial', 'middle', 'mi'],
            'date_of_birth': ['dob', 'birth_date', 'birthdate', 'date_birth'],
            'active_duty_status_date': ['active_duty_date', 'duty_date', 'status_date', 'service_date'],
            'customer_record_id': ['customer_id', 'record_id', 'id', 'customer_number']
        }
        return variations.get(column, [])
    
    def generate_fixed_width_file(self, records: List[SCRARecord]) -> str:
        """Generate fixed-width text file content from records"""
        lines = []
        for record in records:
            lines.append(record.to_fixed_width())
        return '\n'.join(lines)
    
    def validate_csv_file(self, csv_content: str) -> Dict[str, Any]:
        """
        Validate CSV file and return summary
        
        Returns:
            Dictionary with validation results
        """
        records, errors = self.parse_csv_content(csv_content)
        
        return {
            'valid': len(errors) == 0,
            'record_count': len(records),
            'error_count': len(errors),
            'errors': errors,
            'records': [record.to_dict() for record in records[:5]],  # First 5 for preview
            'total_records': len(records)
        }


def process_csv_for_scra(csv_content: str) -> Tuple[str, List[SCRARecord], List[str]]:
    """
    Main function to process CSV content for SCRA multi-record verification
    
    Args:
        csv_content: Raw CSV file content as string
        
    Returns:
        Tuple of (fixed_width_content, records, errors)
    """
    processor = CSVProcessor()
    records, errors = processor.parse_csv_content(csv_content)
    
    if errors:
        return '', records, errors
    
    fixed_width_content = processor.generate_fixed_width_file(records)
    return fixed_width_content, records, errors


# Example usage and testing
if __name__ == "__main__":
    # Test CSV content (new format with MM/DD/YY dates)
    test_csv = """ssn,first_name,last_name,date_of_birth,active_duty_status_date
123456789,John,Doe,10/29/86,10/5/25
987654321,Jane,Smith,10/29/86,10/5/25
555666777,Bob,Johnson,10/29/86,10/5/25"""
    
    processor = CSVProcessor()
    records, errors = processor.parse_csv_content(test_csv)
    
    print(f"Processed {len(records)} records with {len(errors)} errors")
    
    if errors:
        print("Errors:")
        for error in errors:
            print(f"  - {error}")
    
    if records:
        print("\nFixed-width output:")
        fixed_width = processor.generate_fixed_width_file(records)
        print(fixed_width)
        
        print(f"\nFirst record: '{records[0].to_fixed_width()}' (length: {len(records[0].to_fixed_width())})")
        
        # Show parsed dates
        print("\nParsed dates:")
        for i, record in enumerate(records, 1):
            print(f"  Record {i}: DOB={record.date_of_birth}, Active Duty={record.active_duty_status_date}")


def process_csv_for_scra(csv_content: str) -> Tuple[str, List[SCRARecord], List[str]]:
    """
    Process CSV content and return fixed-width format, records, and any errors
    
    Returns:
        Tuple of (fixed_width_content, records_list, errors_list)
    """
    processor = CSVProcessor()
    
    try:
        # Parse CSV content directly to get SCRARecord objects
        records, errors = processor.parse_csv_content(csv_content)
        
        if errors:
            return "", [], errors
        
        if not records:
            return "", [], ["No valid records found in CSV file"]
        
        # Generate fixed-width content
        fixed_width_content = processor.generate_fixed_width_file(records)
        
        return fixed_width_content, records, []
        
    except Exception as e:
        return "", [], [f"Error processing CSV: {str(e)}"]
