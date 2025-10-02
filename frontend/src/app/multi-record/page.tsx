'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Layout from '../../components/Layout';
import SettingsModal from '../../components/SettingsModal';
import BackendHealthCheck from '../../components/BackendHealthCheck';
import { useAuth } from '../../contexts/SupabaseAuthContext';
import { backendAPI, VerificationResponse, CSVValidationResult } from '../../lib/backend-api';
import { uploadScreenshotsToSupabase, uploadPdfToSupabase } from '../../lib/supabase';
import { useRealTimeVerification } from '../../hooks/useRealTimeVerification';
import RealTimeScreenshots from '../../components/RealTimeScreenshots';

export default function MultiRecordPage() {
  const { user } = useAuth();
  const router = useRouter();
  
  // Check if we're in development mode
  const isDevMode = process.env.NEXT_PUBLIC_DEV_MODE === 'true';
  
  // State
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [csvContent, setCsvContent] = useState<string>('');
  const [fixedWidthContent, setFixedWidthContent] = useState<string>('');
  const [validation, setValidation] = useState<CSVValidationResult | null>(null);
  const [isValidating, setIsValidating] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<VerificationResponse | null>(null);
  const [showSettings, setShowSettings] = useState(false);
  const [credentialsRequiredError, setCredentialsRequiredError] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  // Real-time verification tracking
  const { 
    session: realtimeSession, 
    screenshots: realtimeScreenshots,
    startTracking,
    stopTracking
  } = useRealTimeVerification();

  // Handle file selection
  const handleFileSelect = useCallback(async (file: File) => {
    if (!file) return;
    
    // Validate file type
    if (!file.name.toLowerCase().endsWith('.csv')) {
      alert('Please select a CSV file');
      return;
    }
    
    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      alert('File size must be less than 5MB');
      return;
    }
    
    setCsvFile(file);
    
    // Read file content for preview
    const reader = new FileReader();
    reader.onload = async (e) => {
      const content = e.target?.result as string;
      setCsvContent(content);
    };
    reader.readAsText(file);
    
    // Convert CSV to fixed-width format
    await convertAndValidateCSV(file);
  }, []);

  // Convert CSV to fixed-width format and validate
  const convertAndValidateCSV = async (file: File) => {
    setIsValidating(true);
    try {
      const response = await backendAPI.convertCSVToFixedWidth(file);
      
      if (response.success && response.fixed_width_content) {
        // Success - show fixed-width preview
        const recordCount = response.fixed_width_content.split('\n').filter(line => line.trim()).length;
        setValidation({
          valid: true,
          record_count: recordCount,
          error_count: 0,
          errors: [],
          records: [],
          total_records: recordCount
        });
        
        // Store the fixed-width content for verification
        setFixedWidthContent(response.fixed_width_content);
        
      } else {
        // Validation errors
        setValidation({
          valid: false,
          record_count: 0,
          error_count: response.error_count || 1,
          errors: response.validation_errors || ['Conversion failed'],
          records: [],
          total_records: 0
        });
        setFixedWidthContent('');
      }
    } catch (error) {
      console.error('CSV conversion error:', error);
      setValidation({
        valid: false,
        record_count: 0,
        error_count: 1,
        errors: [error instanceof Error ? error.message : 'Conversion failed'],
        records: [],
        total_records: 0
      });
      setFixedWidthContent('');
    } finally {
      setIsValidating(false);
    }
  };

  // Handle drag and drop
  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  }, [handleFileSelect]);

  // Handle file input change
  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelect(e.target.files[0]);
    }
  };

  // Handle form submission
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validation || !validation.valid) {
      alert('Please upload and validate a CSV file first');
      return;
    }

    if (!fixedWidthContent) {
      alert('No fixed-width content to process. Please upload and validate a CSV file first.');
      return;
    }

    setIsSubmitting(true);
    setResult(null);

    try {
      // Call multi-record verification API with fixed-width content
      const result = await backendAPI.verifyMultipleRecords(
        { fixed_width_content: fixedWidthContent },
        user?.id
      );
      
      if (result.success && result.sessionId) {
        // Start real-time tracking for this session
        startTracking(result.sessionId);
        
        // Process screenshots and PDF from the direct response
        if (result.data?.automationResult?.screenshots || result.data?.automationResult?.pdf) {
          try {
            // Upload screenshots if available
            if (user && result.data?.automationResult?.screenshots) {
              await uploadScreenshotsToSupabase(
                user.id, 
                result.sessionId!, 
                result.data.automationResult.screenshots
              );
            }
            
            // Upload PDF if available
            if (user && result.data?.automationResult?.pdf) {
              await uploadPdfToSupabase(
                user.id, 
                result.sessionId!, 
                {
                  ...result.data.automationResult.pdf,
                  timestamp: new Date().toISOString()
                }
              );
            }
            
            // Notify backend that files were successfully uploaded
            try {
              let backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
              if (backendUrl.includes('scraverify-production.up.railway.app') && backendUrl.includes(':8000')) {
                backendUrl = backendUrl.replace(':8000', '');
              }
              await fetch(`${backendUrl}/verification/${result.sessionId}/uploaded`, {
                method: 'POST'
              });
            } catch {
              // Silently handle upload notification errors
            }
          } catch {
            // Silently handle file upload errors
          }
        }
        
        // Set the result immediately since we have it
        setResult(result);
        setIsSubmitting(false);
        
      } else {
        setResult(result);
        setIsSubmitting(false);
      }

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Multi-record verification failed';
      setResult({
        success: false,
        error: errorMessage
      });
      setIsSubmitting(false);
    }
  };

  // Clear form
  const clearForm = () => {
    setCsvFile(null);
    setCsvContent('');
    setFixedWidthContent('');
    setValidation(null);
    setResult(null);
    stopTracking();
  };

  // Generate sample CSV
  const generateSampleCSV = () => {
    const sampleCSV = `ssn,first_name,last_name,date_of_birth,active_duty_status_date,middle_name,customer_record_id
123456789,John,Doe,19900101,20200101,M,CUST001
987654321,Jane,Smith,,20210615,A,CUST002
555666777,Bob,Johnson,19851215,20190301,,CUST003`;
    
    const blob = new Blob([sampleCSV], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'scra_sample.csv';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <Layout>
      <div className="p-6 max-w-6xl mx-auto">
        {/* Development Mode Indicator */}
        {isDevMode && (
          <div className="mb-6 p-4 bg-yellow-50 border-l-4 border-yellow-400 rounded-lg">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <svg className="h-5 w-5 text-yellow-400" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
              </div>
              <div className="ml-3">
                <p className="text-sm text-yellow-800">
                  <strong>Development Mode:</strong> Authentication bypassed. SCRA credentials auto-filled.
                </p>
              </div>
            </div>
          </div>
        )}
        
        <SettingsModal 
          open={showSettings} 
          onClose={() => setShowSettings(false)}
          required={credentialsRequiredError}
          onCredentialsSaved={() => {}}
        />

        {/* Header */}
        <div className="mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 mb-2">
                Multi-Record SCRA Verification
              </h1>
              <p className="text-gray-600">
                Upload a CSV file to verify multiple service members at once
              </p>
            </div>
            <button
              onClick={() => router.push('/')}
              className="inline-flex items-center px-4 py-2 border border-gray-300 rounded-lg shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
            >
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
              Single Record
            </button>
          </div>
        </div>

        <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
          {/* Upload Section */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">CSV File Upload</h2>
              <p className="text-sm text-gray-600 mt-1">Upload a CSV file with service member records</p>
            </div>
            
            <form onSubmit={handleSubmit} className="p-6 space-y-6">
              {/* File Upload Area */}
              <div
                className={`relative border-2 border-dashed rounded-lg p-6 text-center ${
                  dragActive 
                    ? 'border-blue-400 bg-blue-50' 
                    : validation?.valid 
                      ? 'border-green-400 bg-green-50'
                      : validation && !validation.valid
                        ? 'border-red-400 bg-red-50'
                        : 'border-gray-300 hover:border-gray-400'
                }`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
              >
                <input
                  type="file"
                  accept=".csv"
                  onChange={handleFileInputChange}
                  className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                  disabled={isSubmitting}
                />
                
                <div className="space-y-4">
                  <div className="mx-auto w-12 h-12 text-gray-400">
                    <svg fill="none" stroke="currentColor" viewBox="0 0 24 24" className="w-full h-full">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                  </div>
                  
                  <div>
                    <p className="text-lg font-medium text-gray-900">
                      {csvFile ? csvFile.name : 'Drop your CSV file here'}
                    </p>
                    <p className="text-sm text-gray-500 mt-1">
                      or click to browse files
                    </p>
                  </div>
                  
                  {csvFile && (
                    <div className="text-sm text-gray-600">
                      Size: {Math.round(csvFile.size / 1024)}KB
                    </div>
                  )}
                </div>
              </div>

              {/* CSV Requirements */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <h3 className="text-sm font-medium text-blue-800 mb-2">CSV Format Requirements</h3>
                <ul className="text-sm text-blue-700 space-y-1">
                  <li>• <strong>Required columns:</strong> ssn, first_name, last_name, active_duty_status_date</li>
                  <li>• <strong>Optional columns:</strong> date_of_birth, middle_name, customer_record_id</li>
                  <li>• <strong>SSN:</strong> 9 digits (with or without dashes)</li>
                  <li>• <strong>Dates:</strong> YYYYMMDD format or MM/DD/YYYY</li>
                  <li>• <strong>File size:</strong> Maximum 5MB</li>
                </ul>
                <button
                  type="button"
                  onClick={generateSampleCSV}
                  className="mt-3 text-sm text-blue-600 hover:text-blue-800 underline"
                >
                  Download sample CSV template
                </button>
              </div>

              {/* Validation Results */}
              {isValidating && (
                <div className="flex items-center justify-center py-4">
                  <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
                  <span className="ml-2 text-sm text-gray-600">Validating CSV...</span>
                </div>
              )}

              {validation && (
                <div className={`p-4 rounded-lg border ${
                  validation.valid 
                    ? 'bg-green-50 border-green-200' 
                    : 'bg-red-50 border-red-200'
                }`}>
                  <div className="flex items-center mb-2">
                    <div className={`w-5 h-5 rounded-full flex items-center justify-center mr-2 ${
                      validation.valid ? 'bg-green-100' : 'bg-red-100'
                    }`}>
                      {validation.valid ? (
                        <svg className="w-3 h-3 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      ) : (
                        <svg className="w-3 h-3 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      )}
                    </div>
                    <h3 className={`text-sm font-medium ${
                      validation.valid ? 'text-green-800' : 'text-red-800'
                    }`}>
                      {validation.valid ? 'CSV Valid' : 'CSV Invalid'}
                    </h3>
                  </div>
                  
                  <div className={`text-sm ${
                    validation.valid ? 'text-green-700' : 'text-red-700'
                  }`}>
                    {validation.valid ? (
                      <p>Found {validation.record_count} valid records ready for processing</p>
                    ) : (
                      <div>
                        <p>{validation.error_count} errors found:</p>
                        <ul className="mt-1 ml-4 list-disc">
                          {validation.errors.map((error, index) => (
                            <li key={index}>{error}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>

                  {/* Preview fixed-width format */}
                  {validation.valid && fixedWidthContent && (
                    <div className="mt-3 pt-3 border-t border-green-200">
                      <p className="text-sm font-medium text-green-800 mb-2">SCRA Fixed-Width Format Preview:</p>
                      <div className="bg-gray-50 p-3 rounded border text-xs font-mono text-gray-700 max-h-32 overflow-y-auto">
                        {fixedWidthContent.split('\n').slice(0, 5).map((line, index) => (
                          <div key={index} className="whitespace-pre">
                            {line}
                          </div>
                        ))}
                        {fixedWidthContent.split('\n').length > 5 && (
                          <div className="text-gray-500 italic">
                            ... and {fixedWidthContent.split('\n').length - 5} more records
                          </div>
                        )}
                      </div>
                      <p className="text-xs text-green-600 mt-1">
                        Each record is exactly 119 characters in SCRA format
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* Submit Button */}
              <div className="pt-6 border-t border-gray-200">
                <div className="flex flex-col space-y-3">
                  <button
                    type="submit"
                    disabled={isSubmitting || !validation?.valid}
                    className="w-full flex justify-center items-center py-3 px-6 border border-transparent rounded-lg shadow-sm text-base font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {isSubmitting ? (
                      <>
                        <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Processing {validation?.record_count || 0} Records...
                      </>
                    ) : (
                      <>
                        <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        Process {validation?.record_count || 0} Records
                      </>
                    )}
                  </button>

                  {result && (
                    <button
                      type="button"
                      onClick={clearForm}
                      className="w-full py-2.5 px-4 border border-gray-300 rounded-lg shadow-sm text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 transition-colors"
                      disabled={isSubmitting}
                    >
                      <svg className="w-4 h-4 mr-2 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                      </svg>
                      Start New Verification
                    </button>
                  )}
                </div>
              </div>
            </form>

            {/* Results Summary */}
            {result && (
              <div className="border-t border-gray-200 p-6">
                <h3 className="text-lg font-semibold mb-3 text-gray-900">Multi-Record Results</h3>
                
                {result.success ? (
                  <div className="space-y-4">
                    <div className="p-4 bg-green-50 border border-green-200 rounded-xl">
                      <div className="flex items-center mb-3">
                        <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center mr-3">
                          <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        </div>
                        <div>
                          <p className="font-semibold text-green-800">Processing Complete</p>
                          <p className="text-sm text-green-600">
                            {result.data?.processingResult?.recordsProcessed || result.data?.multiRecordRequest?.recordCount || 0} records processed
                          </p>
                        </div>
                      </div>
                      
                      <div className="flex flex-wrap gap-3">
                        {/* PDF Download */}
                        {result.data?.automationResult?.pdf && (
                          <button
                            onClick={() => {
                              const pdfData = result.data!.automationResult!.pdf!;
                              const blob = new Blob([Uint8Array.from(atob(pdfData.data), c => c.charCodeAt(0))], {type: 'application/pdf'});
                              const url = URL.createObjectURL(blob);
                              const link = document.createElement('a');
                              link.href = url;
                              link.download = pdfData.filename || 'scra_multi_record_results.pdf';
                              document.body.appendChild(link);
                              link.click();
                              document.body.removeChild(link);
                              URL.revokeObjectURL(url);
                            }}
                            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-lg text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 transition-colors"
                          >
                            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            Download Results PDF ({Math.round((result.data.automationResult.pdf.size || 0) / 1024)}KB)
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Processing Summary */}
                    {result.data?.processingResult && (
                      <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl">
                        <h4 className="font-medium text-blue-800 mb-2">Processing Summary</h4>
                        <div className="text-sm text-blue-700 space-y-1">
                          <div>Records Processed: {result.data.processingResult.recordsProcessed}</div>
                          <div>Certificate Generated: {result.data.processingResult.certificateGenerated ? 'Yes' : 'No'}</div>
                          <div>Status: {result.data.processingResult.processingComplete ? 'Complete' : 'In Progress'}</div>
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="p-4 bg-red-50 border border-red-200 rounded-xl">
                    <div className="flex items-center mb-2">
                      <div className="w-8 h-8 bg-red-100 rounded-full flex items-center justify-center mr-3">
                        <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </div>
                      <div>
                        <p className="font-semibold text-red-800">Processing Failed</p>
                        <p className="text-sm text-red-600 mt-1">{result.error}</p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Live Progress Display */}
          <div className="space-y-6">
            {/* Current Step */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200">
              <div className="p-6">
                <h3 className="text-lg font-semibold mb-4 text-gray-900">Live Processing Progress</h3>
                <div className="flex items-center p-4 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg">
                  <div className={`w-3 h-3 rounded-full mr-4 ${
                    isSubmitting || realtimeSession?.status === 'in_progress'
                      ? 'bg-blue-500 animate-pulse' 
                      : result?.success || realtimeSession?.status === 'completed'
                        ? 'bg-green-500' 
                        : result?.error || realtimeSession?.status === 'failed'
                          ? 'bg-red-500' 
                          : 'bg-gray-400'
                  }`}></div>
                  <div className="flex-1">
                    <p className="font-medium text-gray-900">
                      {realtimeSession ? (realtimeSession.current_step || realtimeSession.status) : (result ? 'Ready to start new verification' : 'Ready to start')}
                    </p>
                    {(isSubmitting || realtimeSession?.status === 'in_progress') && (
                      <p className="text-sm text-gray-600 mt-1">Processing multiple records...</p>
                    )}
                    
                    {/* Real-time progress bar */}
                    {realtimeSession && realtimeSession.status === 'in_progress' && (
                      <div className="space-y-2 mt-3">
                        <div className="flex justify-between text-sm text-gray-600">
                          <span>Progress</span>
                          <span>{Math.round(realtimeSession.progress || 0)}%</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div 
                            className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                            style={{ width: `${realtimeSession.progress || 0}%` }}
                          ></div>
                        </div>
                      </div>
                    )}
                  </div>
                  {(isSubmitting || realtimeSession?.status === 'in_progress') && (
                    <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
                  )}
                </div>
              </div>
            </div>

            {/* Real-time Screenshots */}
            <RealTimeScreenshots 
              screenshots={realtimeScreenshots || []}
              loading={realtimeSession?.status === 'in_progress' || false}
              className="bg-white rounded-xl shadow-sm border border-gray-200 p-6"
            />
          </div>
        </div>
      </div>
      
      {/* Backend Health Check */}
      {process.env.NODE_ENV === 'development' && (
        <BackendHealthCheck />
      )}
    </Layout>
  );
}
