'use client';

import { useState, useEffect, useCallback } from 'react';
import Image from 'next/image';
import { formValidationSchema } from '../lib/validation';
import { formatDateToISO, formatDateToMMDDYYYY } from '../lib/date-utils';
import Layout from '../components/Layout';
import SettingsModal from '../components/SettingsModal';
import BackendHealthCheck from '../components/BackendHealthCheck';
import { FormData } from '../lib/types';
import { useAuth } from '../contexts/SupabaseAuthContext';
import { z } from 'zod';
import { backendAPI, VerificationRequest, VerificationResponse } from '../lib/backend-api';
import { uploadScreenshotsToSupabase, uploadPdfToSupabase, VerificationScreenshot } from '../lib/supabase';
import { useRealTimeVerification } from '../hooks/useRealTimeVerification';
import RealTimeScreenshots from '../components/RealTimeScreenshots';

// State keys for localStorage
const STORAGE_KEYS = {
  FORM_DATA: 'scra_verification_form',
  RESULT: 'scra_verification_result',
  SESSION_ID: 'scra_verification_session_id',
  SCREENSHOTS: 'scra_verification_screenshots',
  SELECTED_SCREENSHOT: 'scra_selected_screenshot',
  VERIFICATION_COMPLETE: 'scra_verification_complete',
  VERIFICATION_STATE: 'scra_verification_state'
} as const;


// Helper functions for localStorage
const saveToStorage = (key: string, data: unknown) => {
  try {
    localStorage.setItem(key, JSON.stringify(data));
  } catch {
    // Silently fail on localStorage errors
  }
};

const loadFromStorage = (key: string, defaultValue: unknown = null) => {
  try {
    const stored = localStorage.getItem(key);
    return stored ? JSON.parse(stored) : defaultValue;
  } catch {
    return defaultValue;
  }
};

const clearStorage = (key: string) => {
  try {
    localStorage.removeItem(key);
  } catch {
    // Silently fail on localStorage errors
  }
};

export default function Home() {
  const { user } = useAuth();
  
  // Check if we're in development mode
  const isDevMode = process.env.NEXT_PUBLIC_DEV_MODE === 'true';
  
  // SCRA Credentials state - auto-fill with dev credentials in development mode
  const [scraUsername, setScraUsername] = useState<string>(
    isDevMode ? (process.env.NEXT_PUBLIC_DEV_SCRA_USERNAME || '') : ''
  );
  const [scraPassword, setScraPassword] = useState<string>(
    isDevMode ? (process.env.NEXT_PUBLIC_DEV_SCRA_PASSWORD || '') : ''
  );
  const [credentialsLoading, setCredentialsLoading] = useState(false);
  
  // Initialize state from localStorage or defaults
  const [formData, setFormData] = useState<FormData>(() => {
    if (typeof window === 'undefined') {
      // SSR fallback
      return {
        firstName: '',
        lastName: '',
        middleName: '',
        suffix: '',
        ssn: '',
        dateOfBirth: new Date(),
        activeDutyDate: new Date(),
      };
    }
    
    const saved = loadFromStorage(STORAGE_KEYS.FORM_DATA);
    if (saved) {
      // Parse dates from stored strings back to Date objects
      return {
        ...saved,
        dateOfBirth: saved.dateOfBirth ? new Date(saved.dateOfBirth) : new Date(),
        activeDutyDate: saved.activeDutyDate ? new Date(saved.activeDutyDate) : new Date(),
      };
    }
    
    return {
      firstName: '',
      lastName: '',
      middleName: '',
      suffix: '',
      ssn: '',
      dateOfBirth: new Date(),
      activeDutyDate: new Date(),
    };
  });
  
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<VerificationResponse | null>(() => 
    typeof window !== 'undefined' ? loadFromStorage(STORAGE_KEYS.RESULT) : null
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [currentJobId, setCurrentJobId] = useState<string | null>(() => 
    typeof window !== 'undefined' ? loadFromStorage(STORAGE_KEYS.SESSION_ID) : null
  );
  const [showSettings, setShowSettings] = useState(false);
  const [credentialsRequiredError, setCredentialsRequiredError] = useState(false);
  const [selectedScreenshot, setSelectedScreenshot] = useState<VerificationScreenshot | null>(null); // eslint-disable-line @typescript-eslint/no-unused-vars

  // Real-time verification tracking
  const { 
    session: realtimeSession, 
    screenshots: realtimeScreenshots,
    startTracking,
    stopTracking
  } = useRealTimeVerification();

  // Update screenshots when real-time data comes in
  useEffect(() => {
    if (realtimeScreenshots && realtimeScreenshots.length > 0) {
      // Save screenshots to localStorage for persistence
      saveToStorage('scra_verification_screenshots', realtimeScreenshots);
    }
  }, [realtimeScreenshots]);

  // Save complete verification state when result changes
  useEffect(() => {
    if (result && result.sessionId) {
      const verificationState = {
        result,
        realtimeScreenshots,
        timestamp: new Date().toISOString(),
        isComplete: result.success !== undefined
      };
      saveToStorage(STORAGE_KEYS.VERIFICATION_STATE, verificationState);
    }
  }, [result, realtimeScreenshots]);

  // Restore complete verification state on page load
  useEffect(() => {
    if (!result) {
      const savedState = loadFromStorage(STORAGE_KEYS.VERIFICATION_STATE, null);
      
      if (savedState && savedState.result) {
        setResult(savedState.result);
        
        if (savedState.result.sessionId && savedState.isComplete) {
          startTracking(savedState.result.sessionId);
        }
      }
    }
  }, [result, startTracking]);

  // Handle session completion
  useEffect(() => {
    if (realtimeSession) {
      if (realtimeSession.status === 'completed') {
        setResult({
          success: true,
          sessionId: realtimeSession.session_id,
          result: realtimeSession
        });
        setIsSubmitting(false);
        
        // Trigger history refresh
        triggerHistoryRefresh();
      } else if (realtimeSession.status === 'failed') {
        setResult({
          success: false,
          sessionId: realtimeSession.session_id,
          error: realtimeSession.error_message || 'Verification failed'
        });
        setIsSubmitting(false);
      }
    }
  }, [realtimeSession]);

  // Trigger history refresh when verification completes
  const triggerHistoryRefresh = () => {
    // Dispatch a custom event to notify history page to refresh
    window.dispatchEvent(new CustomEvent('verificationCompleted'));
  };

  const clearForm = () => {
    setFormData({
      firstName: '',
      lastName: '',
      middleName: '',
      suffix: '',
      ssn: '',
      dateOfBirth: new Date(),
      activeDutyDate: new Date(),
    });
    setResult(null);
    setErrors({});
    setSelectedScreenshot(null);
    setCurrentJobId(null);
    
    // Clear all localStorage for verification state
    Object.values(STORAGE_KEYS).forEach(key => {
      localStorage.removeItem(key);
    });
    
    // Stop real-time tracking
    stopTracking();
  };

  // Save verification record to Supabase
  const saveVerificationToSupabase = async (session: {sessionId: string; status: string; result: VerificationResponse}) => {
    if (!user) {
      return;
    }
    
    try {
      const { saveVerificationToSupabase: saveVerification } = await import('../lib/supabase');
      
      const verificationData = {
        sessionId: session.sessionId,
        userId: user.id,
        formData: {
          ...formData,
          dateOfBirth: formData.dateOfBirth instanceof Date ? formData.dateOfBirth.toISOString().split('T')[0] : formData.dateOfBirth,
          activeDutyDate: formData.activeDutyDate instanceof Date ? formData.activeDutyDate.toISOString().split('T')[0] : formData.activeDutyDate
        },
        result: session.result,
        status: session.status as 'completed' | 'failed' | 'in_progress',
        timestamp: new Date().toISOString(),
        createdAt: new Date().toISOString()
      };
      
      await saveVerification(verificationData);
    } catch {
      // Log error silently - don't expose to console in production
    }
  };

  // Load SCRA credentials from Supabase
  const loadCredentials = useCallback(async () => {
    if (!user) {
      setScraUsername('');
      setScraPassword('');
      return;
    }

    setCredentialsLoading(true);
    try {
      const { getUserSettings } = await import('../lib/supabase');
      const settings = await getUserSettings(user.id);
      
      if (settings) {
        setScraUsername(settings.scraUsername || '');
        setScraPassword(settings.scraPassword || '');
      } else {
        setScraUsername('');
        setScraPassword('');
      }
    } catch {
      setScraUsername('');
      setScraPassword('');
    } finally {
      setCredentialsLoading(false);
    }
  }, [user]);

  // Load credentials when user changes
  useEffect(() => {
    loadCredentials();
  }, [loadCredentials]);

  // Save form data to localStorage whenever it changes
  useEffect(() => {
    saveToStorage(STORAGE_KEYS.FORM_DATA, formData);
  }, [formData]);

  useEffect(() => {
    if (result) {
      saveToStorage(STORAGE_KEYS.RESULT, result);
    } else {
      clearStorage(STORAGE_KEYS.RESULT);
    }
  }, [result]);


  useEffect(() => {
    if (currentJobId) {
      saveToStorage(STORAGE_KEYS.SESSION_ID, currentJobId);
    } else {
      clearStorage(STORAGE_KEYS.SESSION_ID);
    }
  }, [currentJobId]);



  const handleInputChange = (field: keyof FormData, value: string | Date) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
    
    // Clear error for this field when user starts typing
    if (errors[field]) {
      setErrors(prev => ({
        ...prev,
        [field]: ''
      }));
    }
  };

  const formatSSN = (value: string) => {
    const digits = value.replace(/\D/g, '');
    const limited = digits.slice(0, 9);
    
    if (limited.length >= 6) {
      return `${limited.slice(0, 3)}-${limited.slice(3, 5)}-${limited.slice(5)}`;
    } else if (limited.length >= 4) {
      return `${limited.slice(0, 3)}-${limited.slice(3)}`;
    } else {
      return limited;
    }
  };

  const handleSSNChange = (value: string) => {
    const formatted = formatSSN(value);
    handleInputChange('ssn', formatted);
  };

  const validateForm = (): boolean => {
    try {
      const ssnDigits = formData.ssn.replace(/\D/g, '');
      
      const validationData = {
        ...formData,
        ssn: ssnDigits,
        middleName: formData.middleName || undefined,
        suffix: formData.suffix || undefined,
      };
      
      formValidationSchema.parse(validationData);
      setErrors({});
      return true;
    } catch (error) {
      if (error instanceof z.ZodError) {
        const newErrors: Record<string, string> = {};
        error.issues.forEach(issue => {
          const field = issue.path[0] as string;
          newErrors[field] = issue.message;
        });
        setErrors(newErrors);
      }
      return false;
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    // Check if we have both username and password in local state
    // In development mode, credentials are auto-filled, so skip dialog
    if (!scraUsername || !scraPassword) {
      if (!isDevMode) {
        setCredentialsRequiredError(true);
        setShowSettings(true);
        return;
      } else {
        // Development mode: log warning but continue (credentials should be auto-filled)
        console.warn('🚨 Dev mode: SCRA credentials missing, but continuing anyway');
      }
    }

    setIsSubmitting(true);
    setResult(null);
    setSelectedScreenshot(null);
    setCurrentJobId(null);

    try {
      const verificationData: VerificationRequest = {
        firstName: formData.firstName.trim(),
        lastName: formData.lastName.trim(),
        middleName: formData.middleName?.trim() || '',
        suffix: formData.suffix?.trim() || '',
        ssn: formData.ssn.replace(/\D/g, ''),
        dateOfBirth: formatDateToMMDDYYYY(formData.dateOfBirth),
        activeDutyDate: formatDateToMMDDYYYY(formData.activeDutyDate),
      };

      // Call Railway Backend API with user ID for real-time tracking
      const result = await backendAPI.verifyActiveDuty(verificationData, user?.id);
      
      if (result.success && result.sessionId) {
        setCurrentJobId(result.sessionId);
        
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
            
            // Save verification record to Supabase
            await saveVerificationToSupabase({
              sessionId: result.sessionId,
              status: 'completed',
              result: result
            });
            
            // Trigger history refresh
            triggerHistoryRefresh();
            
            // Also broadcast to other tabs
            localStorage.setItem('scra_verification_completed', Date.now().toString());
            
            // Notify backend that files were successfully uploaded
            try {
              let backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
              // Remove any unwanted port numbers from production URLs
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
        } else {
          // Save even if no files
          await saveVerificationToSupabase({
            sessionId: result.sessionId,
            status: 'completed', 
            result: result
          });
          
          // Trigger history refresh
          triggerHistoryRefresh();
        }
        
        // Set the result immediately since we have it
        setResult(result);
        setIsSubmitting(false);
        
        // Still set currentJobId for any additional session monitoring
        // but we already have the complete result
      } else {
        setResult(result);
        setIsSubmitting(false);
      }

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Verification function call failed';
      setResult({
        success: false,
        error: errorMessage
      });
      setIsSubmitting(false);
      setCurrentJobId(null);
    }
  };


  const handleSettingsClose = async () => {
    setShowSettings(false);
    setCredentialsRequiredError(false);
    // Small delay to ensure Firestore propagation, then reload credentials
    await new Promise(resolve => setTimeout(resolve, 100));
    await loadCredentials();
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
                  <strong>Development Mode:</strong> Authentication bypassed. SCRA credentials auto-filled. Sign in/out buttons functional for testing.
                </p>
              </div>
            </div>
          </div>
        )}
        
        <SettingsModal 
          open={showSettings} 
          onClose={handleSettingsClose}
          required={credentialsRequiredError}
          onCredentialsSaved={() => loadCredentials()}
        />
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            New SCRA Verification
          </h1>
          <p className="text-gray-600">
            Enter service member information to verify active duty status
          </p>
        </div>


        {!credentialsLoading && (!scraUsername || !scraPassword) && !isDevMode && (
          <div className="mb-8 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex items-center">
              <svg className="w-5 h-5 text-blue-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div className="flex-1">
                <h3 className="text-blue-800 font-medium">Setup Required</h3>
                <p className="text-blue-700 text-sm mt-1">
                  SCRA credentials are required for verification. Click &ldquo;Start SCRA Verification&rdquo; below to configure them, or 
                  <button 
                    onClick={() => setShowSettings(true)}
                    className="text-blue-800 underline hover:text-blue-900 ml-1"
                  >
                    set them up now.
                  </button>
                </p>
              </div>
            </div>
          </div>
        )}


        <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
          {/* Form Section */}
          <div className="bg-white rounded-xl shadow-sm border border-gray-200">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-lg font-semibold text-gray-900">Service Member Information</h2>
              <p className="text-sm text-gray-600 mt-1">Enter the details for SCRA verification</p>
            </div>
            
            <form onSubmit={handleSubmit} className="p-6 space-y-6">
              {/* Name Fields */}
              <div className="space-y-4">
                <h3 className="text-sm font-medium text-gray-900 flex items-center">
                  <svg className="w-4 h-4 mr-2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
                  </svg>
                  Personal Information
                </h3>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      First Name <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.firstName}
                      onChange={(e) => handleInputChange('firstName', e.target.value)}
                      className={`w-full px-4 py-3 border rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors ${
                        errors.firstName ? 'border-red-300 bg-red-50' : 'border-gray-300 hover:border-gray-400'
                      }`}
                      placeholder="Enter first name"
                      required
                      disabled={isSubmitting}
                    />
                    {errors.firstName && (
                      <p className="mt-1 text-sm text-red-600">{errors.firstName}</p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Last Name <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.lastName}
                      onChange={(e) => handleInputChange('lastName', e.target.value)}
                      className={`w-full px-4 py-3 border rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors ${
                        errors.lastName ? 'border-red-300 bg-red-50' : 'border-gray-300 hover:border-gray-400'
                      }`}
                      placeholder="Enter last name"
                      required
                      disabled={isSubmitting}
                    />
                    {errors.lastName && (
                      <p className="mt-1 text-sm text-red-600">{errors.lastName}</p>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Middle Name
                    </label>
                    <input
                      type="text"
                      value={formData.middleName}
                      onChange={(e) => handleInputChange('middleName', e.target.value)}
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 hover:border-gray-400 transition-colors"
                      placeholder="Enter middle name (optional)"
                      disabled={isSubmitting}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Suffix
                    </label>
                    <select
                      value={formData.suffix}
                      onChange={(e) => handleInputChange('suffix', e.target.value)}
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 hover:border-gray-400 transition-colors"
                      disabled={isSubmitting}
                    >
                      <option value="">Select suffix (optional)</option>
                      <option value="Jr">Jr</option>
                      <option value="Sr">Sr</option>
                      <option value="II">II</option>
                      <option value="III">III</option>
                      <option value="IV">IV</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Identification */}
              <div className="space-y-4">
                <h3 className="text-sm font-medium text-gray-900 flex items-center">
                  <svg className="w-4 h-4 mr-2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H5a2 2 0 00-2 2v9a2 2 0 002 2h14a2 2 0 002-2V8a2 2 0 00-2-2h-5m-4 0V4a2 2 0 114 0v2m-4 0a2 2 0 104 0m-5 8a2 2 0 100-4 2 2 0 000 4zm0 0c1.306 0 2.417.835 2.83 2M9 14a3.001 3.001 0 00-2.83 2M15 11h3m-3 4h2" />
                  </svg>
                  Identification
                </h3>
                
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Social Security Number <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.ssn}
                    onChange={(e) => handleSSNChange(e.target.value)}
                    className={`w-full px-4 py-3 border rounded-lg text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors ${
                      errors.ssn ? 'border-red-300 bg-red-50' : 'border-gray-300 hover:border-gray-400'
                    }`}
                    placeholder="XXX-XX-XXXX"
                    maxLength={11}
                    required
                    disabled={isSubmitting}
                  />
                  {errors.ssn && (
                    <p className="mt-1 text-sm text-red-600">{errors.ssn}</p>
                  )}
                  <p className="mt-1 text-xs text-gray-500">
                    Your SSN is encrypted and used only for verification purposes
                  </p>
                </div>
              </div>

              {/* Dates */}
              <div className="space-y-4">
                <h3 className="text-sm font-medium text-gray-900 flex items-center">
                  <svg className="w-4 h-4 mr-2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  Important Dates
                </h3>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Date of Birth <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="date"
                      value={formatDateToISO(formData.dateOfBirth)}
                      onChange={(e) => handleInputChange('dateOfBirth', new Date(e.target.value))}
                      className={`w-full px-4 py-3 border rounded-lg text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors ${
                        errors.dateOfBirth ? 'border-red-300 bg-red-50' : 'border-gray-300 hover:border-gray-400'
                      }`}
                      required
                      disabled={isSubmitting}
                    />
                    {errors.dateOfBirth && (
                      <p className="mt-1 text-sm text-red-600">{errors.dateOfBirth}</p>
                    )}
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Active Duty Date <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="date"
                      value={formatDateToISO(formData.activeDutyDate)}
                      onChange={(e) => handleInputChange('activeDutyDate', new Date(e.target.value))}
                      className={`w-full px-4 py-3 border rounded-lg text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-colors ${
                        errors.activeDutyDate ? 'border-red-300 bg-red-50' : 'border-gray-300 hover:border-gray-400'
                      }`}
                      required
                      disabled={isSubmitting}
                    />
                    {errors.activeDutyDate && (
                      <p className="mt-1 text-sm text-red-600">{errors.activeDutyDate}</p>
                    )}
                    <p className="mt-1 text-xs text-gray-500">
                      Date of interest for SCRA coverage verification
                    </p>
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="pt-6 border-t border-gray-200">
                <div className="flex flex-col space-y-3">
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="w-full flex justify-center items-center py-3 px-6 border border-transparent rounded-lg shadow-sm text-base font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    title={(!scraUsername || !scraPassword) && !isDevMode ? "SCRA credentials required" : "Start verification"}
                  >
                    {isSubmitting ? (
                      <>
                        <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                        </svg>
                        Verifying Active Duty Status...
                      </>
                    ) : (
                      <>
                        <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        Start SCRA Verification
                      </>
                    )}
                  </button>

                  {(result || realtimeSession) && (
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
                <h3 className="text-lg font-semibold mb-3 text-gray-900">Verification Results</h3>
                
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
                          <p className="font-semibold text-green-800">Verification Successful</p>
                          <p className="text-sm text-green-600">SCRA status has been verified</p>
                        </div>
                      </div>
                      
                      <div className="flex flex-wrap gap-3">
                        {/* PDF Download from Direct Response */}
                        {result.data?.automationResult?.pdf && (
                          <button
                            onClick={() => {
                              const pdfData = result.data!.automationResult!.pdf!;
                              const blob = new Blob([Uint8Array.from(atob(pdfData.data), c => c.charCodeAt(0))], {type: 'application/pdf'});
                              const url = URL.createObjectURL(blob);
                              const link = document.createElement('a');
                              link.href = url;
                              link.download = pdfData.filename || 'scra_verification_result.pdf';
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
                            Download PDF ({Math.round((result.data.automationResult.pdf.size || 0) / 1024)}KB)
                          </button>
                        )}
                        
                        {/* Legacy PDF Download */}
                        {!result.data?.automationResult?.pdf && (result?.result?.pdfDownloaded || result?.result?.pdfUrl) && (
                          <a
                            href={result?.result?.pdfUrl}
                            download="scra_verification_result.pdf"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-lg text-white bg-green-600 hover:bg-green-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-green-500 transition-colors"
                          >
                            <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                            </svg>
                            Download Verification PDF
                          </a>
                        )}
                      </div>
                    </div>

                    {/* Screenshots from Direct Response */}
                    {result.data?.automationResult?.screenshots && result.data.automationResult.screenshots.length > 0 && (
                      <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl">
                        <h4 className="font-medium text-blue-800 mb-3 flex items-center">
                          <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                          </svg>
                          Verification Screenshots ({result.data.automationResult.screenshots.length})
                        </h4>
                        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                          {result.data.automationResult.screenshots.map((screenshot, index) => (
                            <div key={index} className="group relative">
                              <div className="aspect-w-3 aspect-h-2 bg-gray-100 rounded-lg overflow-hidden border">
                                <Image
                                  src={`data:image/png;base64,${screenshot.data}`}
                                  alt={screenshot.description || `Step ${screenshot.step}`}
                                  width={300}
                                  height={200}
                                  className="w-full h-32 object-cover cursor-pointer hover:opacity-90 transition-opacity"
                                  onClick={() => {
                                    // Open in new window for full view
                                    const newWindow = window.open();
                                    if (newWindow) {
                                      newWindow.document.write(`
                                        <html>
                                          <head><title>${screenshot.filename}</title></head>
                                          <body style="margin:0;background:black;display:flex;justify-content:center;align-items:center;min-height:100vh;">
                                            <img src="data:image/png;base64,${screenshot.data}" style="max-width:100%;max-height:100%;object-fit:contain;" alt="${screenshot.description}" />
                                          </body>
                                        </html>
                                      `);
                                    }
                                  }}
                                />
                                <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-20 transition-all duration-200 flex items-center justify-center">
                                  <svg className="w-8 h-8 text-white opacity-0 group-hover:opacity-100 transition-opacity" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
                                  </svg>
                                </div>
                              </div>
                              <div className="mt-2 text-xs text-gray-600 truncate">
                                <div className="font-medium">{screenshot.filename}</div>
                                <div className="text-gray-500">{screenshot.description}</div>
                              </div>
                            </div>
                          ))}
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
                        <p className="font-semibold text-red-800">Verification Failed</p>
                        <p className="text-sm text-red-600 mt-1">{result.error}</p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Live Debug Display */}
          <div className="space-y-6">
            {/* Current Step */}
            <div className="bg-white rounded-xl shadow-sm border border-gray-200">
              <div className="p-6">
                <h3 className="text-lg font-semibold mb-4 text-gray-900">Live Automation Progress</h3>
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
                      <p className="text-sm text-gray-600 mt-1">Please wait while we process your verification...</p>
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