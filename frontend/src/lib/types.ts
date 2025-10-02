// Request Types
export interface PersonRequest {
  pnId: string;              // SSN
  pnIdConfirmation: string;  // SSN confirmation
  firstName: string;
  lastName: string;
  middleName?: string;
  cadencyName?: string;      // Jr, Sr, III, etc.
  dateOfBirth: string;       // YYYYMMDD
  activeDutyDate: string;    // YYYYMMDD
  edi?: null;
  batchId?: string;
}

export interface CertificateRequest {
  personRequest: PersonRequest;
}

// Response Types
export interface Eligibility {
  dateOfInterest: string;
  transactionId: string;
  activeDutyCovered: boolean;
  activeDutyStartDate: string | null;
  activeDutyEndDate: string | null;
  activeDutyServiceComponentCode: string | null;
  activeDutyServiceComponentString: string | null;
  earlyIndicationCovered: boolean;
  earlyIndicationStartDate: string | null;
  earlyIndicationEndDate: string | null;
  earlyIndicationServiceComponentCode: string | null;
  earlyIndicationServiceComponentString: string | null;
  heraCovered: boolean;
  heraStartDate: string | null;
  heraEndDate: string | null;
  heraServiceComponentCode: string | null;
  heraServiceComponentString: string | null;
  activeDutyIndicatorCode: string | null;
  matchReasonCode: string;
  scraEligibilityType: string;
  covered: boolean;
}

export interface CertificateResponse {
  id: string;
  personRequest: PersonRequest;
  eligibility: Eligibility;
}

// PDF Split Types
export interface IndividualPDF {
  filename: string;
  data: string; // base64
  size: number;
  pages: string;
  record_index: number;
}

export interface ZipArchive {
  filename: string;
  data: string; // base64
  size: number;
  count: number;
}

export interface PDFSplitResult {
  success: boolean;
  individual_pdfs: IndividualPDF[];
  zip_archive: ZipArchive | null;
  total_records: number;
  total_pdfs_created: number;
  error?: string;
}

export interface LoginResponse {
  authenticationStatus: "AUTHENTICATED" | "FAILED";
  passwordLastChanged: number;
}

// Form Types
export interface FormData {
  firstName: string;
  lastName: string;
  middleName?: string;
  suffix?: string;           // Jr, Sr, III, etc.
  ssn: string;               // Required, will be pnId
  dateOfBirth: Date;         // Convert to YYYYMMDD
  activeDutyDate: Date;      // Convert to YYYYMMDD, default to today
}

// Verification Result UI Type
export interface VerificationResult {
  transactionId: string;
  covered: boolean;
  matchReasonCode: string;
  
  // Active Duty Status
  activeDutyCovered: boolean;
  activeDutyStartDate?: string;
  activeDutyEndDate?: string;
  activeDutyServiceComponent?: string;
  
  // Early Indication (Call-up notification)
  earlyIndicationCovered: boolean;
  earlyIndicationDates?: {
    start: string;
    end: string;
  };
  
  // HERA (Housing Emergency Relief Act)
  heraCovered: boolean;
  heraDates?: {
    start: string;
    end: string;
  };
}

// API Response Types
export interface VerifyRequest {
  firstName: string;
  lastName: string;
  middleName?: string;
  suffix?: string;
  ssn: string;
  dateOfBirth: string; // YYYY-MM-DD
  activeDutyDate: string; // YYYY-MM-DD
}

export interface VerifyResponse {
  success: boolean;
  data?: CertificateResponse;
  error?: string;
}