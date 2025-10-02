"""
PDF splitting utilities for multi-record SCRA verification
"""

import io
import zipfile
import base64
from typing import List, Dict, Any, Tuple
from datetime import datetime
import re

try:
    from PyPDF2 import PdfReader, PdfWriter
except ImportError:
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        # Fallback for older versions
        from PyPDF2 import PdfFileReader as PdfReader, PdfFileWriter as PdfWriter


class PDFSplitter:
    """Utility class for splitting multi-record SCRA PDFs into individual certificates"""
    
    def __init__(self):
        self.pages_per_person = 2  # Each SCRA certificate is 2 pages
    
    def split_multi_record_pdf(self, pdf_data: bytes, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Split a multi-record PDF into individual certificates
        
        Args:
            pdf_data: Raw PDF bytes
            records: List of record data for naming individual PDFs
            
        Returns:
            Dictionary containing individual PDFs and ZIP archive
        """
        try:
            # Read the original PDF
            pdf_reader = PdfReader(io.BytesIO(pdf_data))
            total_pages = len(pdf_reader.pages)
            
            print(f"📄 Processing PDF with {total_pages} pages for {len(records)} records")
            
            # Validate page count
            expected_pages = len(records) * self.pages_per_person
            if total_pages < expected_pages:
                print(f"⚠️ Warning: PDF has {total_pages} pages but expected {expected_pages} for {len(records)} records")
            
            individual_pdfs = []
            
            # Split PDF for each record
            for i, record in enumerate(records):
                start_page = i * self.pages_per_person
                end_page = start_page + self.pages_per_person
                
                # Skip if not enough pages
                if start_page >= total_pages:
                    print(f"⚠️ Skipping record {i+1}: not enough pages in PDF")
                    continue
                
                # Create individual PDF
                pdf_writer = PdfWriter()
                
                # Add pages for this person (handle case where PDF has fewer pages than expected)
                actual_end_page = min(end_page, total_pages)
                for page_num in range(start_page, actual_end_page):
                    pdf_writer.add_page(pdf_reader.pages[page_num])
                
                # Generate filename for this person
                filename = self._generate_filename(record, i + 1)
                
                # Write PDF to bytes
                pdf_buffer = io.BytesIO()
                pdf_writer.write(pdf_buffer)
                pdf_bytes = pdf_buffer.getvalue()
                pdf_buffer.close()
                
                individual_pdfs.append({
                    'filename': filename,
                    'data': pdf_bytes,
                    'size': len(pdf_bytes),
                    'pages': f"{start_page + 1}-{actual_end_page}",
                    'record_index': i
                })
                
                print(f"✅ Created {filename} ({len(pdf_bytes)} bytes, pages {start_page + 1}-{actual_end_page})")
            
            # Create ZIP archive containing all individual PDFs
            zip_data = self._create_zip_archive(individual_pdfs)
            
            return {
                'success': True,
                'individual_pdfs': individual_pdfs,
                'zip_archive': {
                    'filename': f'scra_certificates_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip',
                    'data': zip_data,
                    'size': len(zip_data),
                    'count': len(individual_pdfs)
                },
                'total_records': len(records),
                'total_pdfs_created': len(individual_pdfs)
            }
            
        except Exception as e:
            print(f"❌ Error splitting PDF: {e}")
            return {
                'success': False,
                'error': str(e),
                'individual_pdfs': [],
                'zip_archive': None
            }
    
    def _generate_filename(self, record: Dict[str, Any], record_number: int) -> str:
        """Generate a filename for an individual certificate PDF"""
        
        # Try to use person's name
        first_name = record.get('firstName', '').strip()
        last_name = record.get('lastName', '').strip()
        
        if first_name and last_name:
            # Clean names for filename
            first_clean = re.sub(r'[^\w\s-]', '', first_name).strip()
            last_clean = re.sub(r'[^\w\s-]', '', last_name).strip()
            filename = f"{first_clean}_{last_clean}_certificate.pdf"
        
        # Fallback to SSN if available
        elif record.get('ssn'):
            ssn = record.get('ssn', '').strip()
            if len(ssn) >= 4:  # Use last 4 digits for privacy
                filename = f"SSN_{ssn[-4:]}_certificate.pdf"
            else:
                filename = f"Record_{record_number}_certificate.pdf"
        
        # Final fallback to record number
        else:
            filename = f"Record_{record_number}_certificate.pdf"
        
        # Clean filename and ensure it's not too long
        filename = re.sub(r'[^\w\s.-]', '', filename)
        filename = re.sub(r'\s+', '_', filename)
        
        # Limit length
        if len(filename) > 50:
            base_name = filename[:46]
            filename = base_name + ".pdf"
        
        return filename
    
    def _create_zip_archive(self, individual_pdfs: List[Dict[str, Any]]) -> bytes:
        """Create a ZIP archive containing all individual PDFs"""
        
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for pdf_info in individual_pdfs:
                zip_file.writestr(pdf_info['filename'], pdf_info['data'])
        
        zip_data = zip_buffer.getvalue()
        zip_buffer.close()
        
        print(f"📦 Created ZIP archive with {len(individual_pdfs)} PDFs ({len(zip_data)} bytes)")
        
        return zip_data
    
    def convert_to_base64_response(self, split_result: Dict[str, Any]) -> Dict[str, Any]:
        """Convert PDF split result to base64 for API response"""
        
        if not split_result.get('success'):
            return split_result
        
        # Convert individual PDFs to base64
        individual_pdfs_b64 = []
        for pdf_info in split_result.get('individual_pdfs', []):
            individual_pdfs_b64.append({
                'filename': pdf_info['filename'],
                'data': base64.b64encode(pdf_info['data']).decode('utf-8'),
                'size': pdf_info['size'],
                'pages': pdf_info['pages'],
                'record_index': pdf_info['record_index']
            })
        
        # Convert ZIP archive to base64
        zip_info = split_result.get('zip_archive')
        zip_b64 = None
        if zip_info:
            zip_b64 = {
                'filename': zip_info['filename'],
                'data': base64.b64encode(zip_info['data']).decode('utf-8'),
                'size': zip_info['size'],
                'count': zip_info['count']
            }
        
        return {
            'success': True,
            'individual_pdfs': individual_pdfs_b64,
            'zip_archive': zip_b64,
            'total_records': split_result.get('total_records', 0),
            'total_pdfs_created': split_result.get('total_pdfs_created', 0)
        }


def split_scra_multi_record_pdf(pdf_data: bytes, records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Convenience function to split a multi-record SCRA PDF
    
    Args:
        pdf_data: Raw PDF bytes
        records: List of record data for naming
        
    Returns:
        Dictionary with split results ready for API response
    """
    splitter = PDFSplitter()
    split_result = splitter.split_multi_record_pdf(pdf_data, records)
    return splitter.convert_to_base64_response(split_result)
