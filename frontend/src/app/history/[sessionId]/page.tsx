'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Layout from '../../../components/Layout';
import AppWrapper from '../../../components/AppWrapper';
import { useAuth } from '../../../contexts/SupabaseAuthContext';

interface VerificationRecord {
  sessionId: string;
  userId: string;
  formData: {
    firstName: string;
    lastName: string;
    middleName?: string;
    suffix?: string;
    ssn: string;
    dateOfBirth: string;
    activeDutyDate: string;
  };
  result: {
    success: boolean;
    method: string;
    eligibility?: {
      activeDutyCovered: boolean;
      scraEligibilityType: string;
      matchReasonCode: string;
      covered: boolean;
    };
  };
  status: 'completed' | 'failed' | 'in_progress';
  timestamp: string;
  createdAt: string;
}

interface Screenshot {
  name: string;
  url: string;
}

interface ImageWithFallbackProps {
  src: string;
  alt: string;
  className?: string;
  filename: string;
}

function ImageWithFallback({ src, alt, className, filename }: ImageWithFallbackProps) {
  const [hasError, setHasError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  if (!src) {
    return (
      <div className={`flex items-center justify-center h-64 bg-gray-100 ${className || ''}`}>
        <p className="text-gray-500 text-sm">No image URL provided</p>
      </div>
    );
  }

  if (hasError) {
    return (
      <div className={`flex flex-col items-center justify-center h-64 bg-gray-50 border-2 border-dashed border-gray-300 ${className || ''}`}>
        <svg className="w-12 h-12 text-gray-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        <p className="text-gray-500 text-sm text-center">Unable to load screenshot</p>
        <p className="text-gray-400 text-xs text-center mt-1">{filename}</p>
      </div>
    );
  }

  return (
    <div className={`relative ${className || ''}`}>
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100">
          <div className="flex flex-col items-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mb-2"></div>
            <p className="text-gray-500 text-sm">Loading image...</p>
          </div>
        </div>
      )}
      <img
        src={src}
        alt={alt}
        className="w-full h-full object-contain"
        onLoad={() => {
          setIsLoading(false);
          setHasError(false);
        }}
        onError={() => {
          setIsLoading(false);
          setHasError(true);
        }}
        style={{ display: isLoading ? 'none' : 'block' }}
      />
    </div>
  );
}


export default function VerificationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { user } = useAuth();
  const sessionId = params?.sessionId as string;

  console.log('🔍 VerificationDetailPage mounted:', {
    params,
    sessionId,
    hasUser: !!user,
    userId: user?.id
  });

  const [record, setRecord] = useState<VerificationRecord | null>(null);
  const [screenshots, setScreenshots] = useState<Screenshot[]>([]);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedScreenshot, setSelectedScreenshot] = useState<Screenshot | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);

  useEffect(() => {
    console.log('🔄 useEffect triggered:', {
      hasUser: !!user,
      sessionId: sessionId,
      isInitialized: isInitialized
    });
    
    if (!user) {
      console.log('❌ No user authenticated');
      return;
    }
    
    if (!sessionId) {
      console.log('❌ No sessionId parameter');
      setError('No session ID provided');
      setLoading(false);
      return;
    }
    
    if (isInitialized) {
      console.log('⏭️ Already initialized, skipping fetch');
      return;
    }

    fetchVerificationDetails();
  }, [user, sessionId, isInitialized]);

  const fetchVerificationDetails = async () => {
    if (!user || isInitialized) return;

    try {
      setLoading(true);
      console.log(`📄 Fetching details for session: ${sessionId}`);
      console.log(`👤 User ID: ${user.id}`);

      // Skip sessionStorage caching to avoid quota issues
      // Rely on in-memory Supabase caching for better performance

      // Get verification record with full details
      console.log('🔍 Fetching verification details from database...');
      const { getVerificationDetails } = await import('../../../lib/supabase');
      let foundRecord = await getVerificationDetails(user.id, sessionId);
      
      console.log(`🎯 Looking for session ID: ${sessionId}`);

      if (!foundRecord) {
        console.error(`❌ Verification record not found for sessionId: ${sessionId}`);
        
        // Try URL decoding the sessionId in case it's encoded
        const decodedSessionId = decodeURIComponent(sessionId);
        if (decodedSessionId !== sessionId) {
          console.log(`🔄 Trying with decoded session ID: ${decodedSessionId}`);
          foundRecord = await getVerificationDetails(user.id, decodedSessionId);
        }
        
        if (!foundRecord) {
          setError(`Verification record not found. Session ID: ${sessionId}`);
          setIsInitialized(true);
          return;
        }
      }

      console.log('✅ Found verification record:', {
        sessionId: foundRecord.sessionId,
        status: foundRecord.status,
        createdAt: foundRecord.createdAt
      });

      setRecord(foundRecord);

      // Get screenshots from storage with detailed debugging
      let screenshotUrls: Screenshot[] = [];
      
      console.log('🔍 Attempting to load screenshots...');
      console.log('📍 Expected storage path: users/{userId}/verifications/{sessionId}/screenshots/');
      console.log('📍 Resolved path:', `users/${user.id}/verifications/${sessionId}/screenshots/`);
      
      try {
        const { getScreenshotUrls } = await import('../../../lib/supabase');
        console.log('📸 Calling getScreenshotUrls with:', {
          userId: user.id,
          sessionId: sessionId,
          useCache: true
        });
        
        screenshotUrls = await getScreenshotUrls(user.id, sessionId, true); // Use cache
        setScreenshots(screenshotUrls);
        
        console.log(`📸 Screenshot results:`, {
          count: screenshotUrls.length,
          screenshots: screenshotUrls.map(s => ({ name: s.name, url: s.url }))
        });
        
        if (screenshotUrls.length > 0) {
          setSelectedScreenshot(screenshotUrls[0]);
          console.log('✅ Selected first screenshot:', screenshotUrls[0].name);
        } else {
          console.log('⚠️ No screenshots found in storage');
        }
      } catch (err) {
        console.error('❌ Error loading screenshots from storage:', err);
        console.error('Storage error details:', {
          message: (err as any)?.message,
          stack: (err as any)?.stack
        });
        
        // Try alternative storage path (sessions/ instead of users/)
        console.log('🔄 Trying alternative storage path: sessions/{sessionId}/screenshots/');
        try {
          // Manually check the sessions path
          const { supabase } = await import('../../../lib/supabase');
          const alternativePath = `sessions/${sessionId}/screenshots`;
          console.log('📍 Alternative path:', alternativePath);
          
          const { data: files, error: listError } = await supabase.storage
            .from('verification-files')
            .list(alternativePath);
            
          if (listError) {
            console.error('❌ Alternative path failed:', listError);
          } else {
            console.log('📂 Files found in alternative path:', files?.length || 0);
            if (files && files.length > 0) {
              console.log('📋 Alternative path files:', files.map(f => f.name));
              
              // Convert to screenshot URLs using alternative path
              const alternativeUrls: Screenshot[] = [];
              for (const file of files) {
                const filePath = `sessions/${sessionId}/screenshots/${file.name}`;
                const { data: urlData } = supabase.storage
                  .from('verification-files')
                  .getPublicUrl(filePath);
                
                alternativeUrls.push({
                  name: file.name,
                  url: urlData.publicUrl
                });
              }
              
              screenshotUrls = alternativeUrls;
              setScreenshots(screenshotUrls);
              
              if (screenshotUrls.length > 0) {
                setSelectedScreenshot(screenshotUrls[0]);
              }
              console.log(`✅ Found ${screenshotUrls.length} screenshots from alternative path`);
            }
          }
        } catch (altErr) {
          console.error('❌ Alternative path also failed:', altErr);
        }
        
        // Last fallback: try to get screenshots from session database data
        if (screenshotUrls.length === 0) {
          console.log('🔄 Trying session database fallback...');
          try {
            const { getSessionScreenshots } = await import('../../../lib/supabase');
            const sessionScreenshots = await getSessionScreenshots(sessionId);
            screenshotUrls = sessionScreenshots.map(s => ({
              name: s.filename,
              url: s.url
            }));
            setScreenshots(screenshotUrls);
            
            if (screenshotUrls.length > 0) {
              setSelectedScreenshot(screenshotUrls[0]);
            }
            console.log(`📸 Found ${screenshotUrls.length} screenshots from session database`);
          } catch (sessionErr) {
            console.error('❌ Session database fallback failed:', sessionErr);
          }
        }
      }

      // Get PDF URL
      let foundPdfUrl: string | null = null;
      try {
        const { getPdfUrl } = await import('../../../lib/supabase');
        const possibleFilenames = ['scra_result.pdf', 'scra_verification_report.pdf'];
        
        for (const filename of possibleFilenames) {
          const url = await getPdfUrl(user.id, sessionId, filename, true); // Use cache
          if (url) {
            foundPdfUrl = url;
            setPdfUrl(url);
            console.log(`📄 Found PDF: ${filename}`);
            break;
          }
        }
      } catch (err) {
        console.error('Error loading PDF:', err);
      }

      // Skip sessionStorage caching - data is already cached in memory by Supabase functions

      setError(null);
      setIsInitialized(true);
    } catch (err) {
      console.error('❌ Error fetching verification details:', err);
      console.error('Error details:', {
        message: (err as any)?.message,
        stack: (err as any)?.stack,
        sessionId,
        userId: user?.id
      });
      
      let errorMessage = 'Failed to load verification details';
      if (err instanceof Error) {
        errorMessage = `Failed to load verification details: ${err.message}`;
      }
      
      setError(errorMessage);
      setIsInitialized(true);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getStatusBadge = (record: VerificationRecord) => {
    const isSuccess = record.status === 'completed' && record.result?.success;
    
    if (isSuccess) {
      return (
        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">
          ✅ Verification Successful
        </span>
      );
    } else if (record.status === 'failed') {
      return (
        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-800">
          ❌ Verification Failed
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800">
          ⚠️ Status Unknown
        </span>
      );
    }
  };

  const downloadPDF = () => {
    if (pdfUrl) {
      window.open(pdfUrl, '_blank');
    }
  };

  const refreshData = async () => {
    // Clear Supabase caches
    const { clearVerificationCache } = await import('../../../lib/supabase');
    clearVerificationCache(user?.id);
    
    // Reset component state
    setIsInitialized(false);
    setRecord(null);
    setScreenshots([]);
    setPdfUrl(null);
    setSelectedScreenshot(null);
    setError(null);
    setLoading(true);
  };

  if (loading) {
    return (
      <AppWrapper>
        <Layout>
          <div className="p-6 max-w-6xl mx-auto">
            <div className="animate-pulse">
              <div className="h-8 bg-gray-200 rounded mb-4 w-1/3"></div>
              <div className="h-4 bg-gray-200 rounded mb-8 w-1/2"></div>
              <div className="space-y-6">
                <div className="h-64 bg-gray-200 rounded"></div>
                <div className="h-48 bg-gray-200 rounded"></div>
              </div>
              {/* Debug info while loading */}
              <div className="mt-4 p-4 bg-gray-100 rounded text-xs">
                <p>🔍 Debug Info:</p>
                <p>Session ID: {sessionId || 'undefined'}</p>
                <p>Has User: {user ? 'Yes' : 'No'}</p>
                <p>User ID: {user?.id || 'undefined'}</p>
                <p>Params: {JSON.stringify(params)}</p>
              </div>
            </div>
          </div>
        </Layout>
      </AppWrapper>
    );
  }

  if (error || !record) {
    return (
      <AppWrapper>
        <Layout>
          <div className="p-6 max-w-6xl mx-auto">
            <div className="text-center py-12">
              <svg className="w-12 h-12 text-red-500 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <h2 className="text-xl font-semibold text-gray-900 mb-2">Error Loading Verification</h2>
              <p className="text-gray-600 mb-4">{error || 'Verification record not found'}</p>
              
              {/* Debug info for troubleshooting */}
              <div className="mb-4 p-4 bg-gray-100 rounded text-xs text-left">
                <p className="font-semibold mb-2">🔍 Debug Information:</p>
                <p>Session ID from URL: {sessionId || 'undefined'}</p>
                <p>Has User: {user ? 'Yes' : 'No'}</p>
                <p>User ID: {user?.id || 'undefined'}</p>
                <p>URL Params: {JSON.stringify(params)}</p>
                <p>Initialized: {isInitialized ? 'Yes' : 'No'}</p>
              </div>
              
              <div className="space-x-3">
                <button
                  onClick={refreshData}
                  className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
                >
                  <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  Try Again
                </button>
                <button
                  onClick={() => router.push('/history')}
                  className="inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
                >
                  ← Back to History
                </button>
              </div>
            </div>
          </div>
        </Layout>
      </AppWrapper>
    );
  }

  return (
    <AppWrapper>
      <Layout>
        <div className="p-6 max-w-6xl mx-auto">
          {/* Header */}
          <div className="mb-8">
            <div className="flex items-center justify-between mb-4">
              <div>
                <button
                  onClick={() => router.push('/history')}
                  className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-2"
                >
                  <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
                  </svg>
                  Back to History
                </button>
                <h1 className="text-2xl font-bold text-gray-900">
                  Verification Details
                </h1>
                <p className="text-gray-600">
                  {record.formData.firstName} {record.formData.middleName && `${record.formData.middleName} `}{record.formData.lastName} {record.formData.suffix}
                </p>
              </div>
              <div className="text-right">
                <div className="flex items-center space-x-3 mb-2">
                  <button
                    onClick={refreshData}
                    disabled={loading}
                    className="inline-flex items-center px-3 py-1.5 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                  >
                    <svg className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    {loading ? 'Loading...' : 'Refresh'}
                  </button>
                  {getStatusBadge(record)}
                </div>
                <p className="text-sm text-gray-500">
                  {formatDate(record.createdAt)}
                </p>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
            {/* Verification Details */}
            <div className="xl:col-span-1">
              <div className="bg-white rounded-xl shadow-sm border border-gray-200">
                <div className="p-6 border-b border-gray-200">
                  <h2 className="text-lg font-semibold text-gray-900">Service Member Information</h2>
                </div>
                <div className="p-6 space-y-4">
                  <div>
                    <label className="text-sm font-medium text-gray-500">Full Name</label>
                    <p className="mt-1 text-sm text-gray-900">
                      {record.formData.firstName} {record.formData.middleName && `${record.formData.middleName} `}{record.formData.lastName} {record.formData.suffix}
                    </p>
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium text-gray-500">SSN</label>
                    <p className="mt-1 text-sm text-gray-900">
                      ***-**-{record.formData.ssn.slice(-4)}
                    </p>
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium text-gray-500">Date of Birth</label>
                    <p className="mt-1 text-sm text-gray-900">{record.formData.dateOfBirth}</p>
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium text-gray-500">Active Duty Date</label>
                    <p className="mt-1 text-sm text-gray-900">{record.formData.activeDutyDate}</p>
                  </div>

                  <div>
                    <label className="text-sm font-medium text-gray-500">Session ID</label>
                    <p className="mt-1 text-xs font-mono text-gray-600 break-all">{record.sessionId}</p>
                  </div>
                </div>
              </div>

              {/* Verification Result */}
              <div className="mt-6 bg-white rounded-xl shadow-sm border border-gray-200">
                <div className="p-6 border-b border-gray-200">
                  <h2 className="text-lg font-semibold text-gray-900">Verification Result</h2>
                </div>
                <div className="p-6">
                  {record.result?.success ? (
                    <div className="space-y-4">
                      <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
                        <div className="flex items-center">
                          <svg className="w-5 h-5 text-green-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                          <span className="font-medium text-green-800">Active Duty Status Verified</span>
                        </div>
                      </div>
                      
                      {record.result.data && (
                        <div className="space-y-2">
                          <h4 className="font-medium text-gray-900">Details:</h4>
                          <pre className="text-xs bg-gray-50 p-3 rounded border overflow-x-auto">
                            {JSON.stringify(record.result.data, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="space-y-4">
                      <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
                        <div className="flex items-start">
                          <svg className="w-5 h-5 text-red-600 mr-2 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                          <div>
                            <span className="font-medium text-red-800">Verification Failed</span>
                            {record.result?.error && (
                              <p className="text-sm text-red-600 mt-1">{record.result.error}</p>
                            )}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* PDF Certificate */}
              {pdfUrl && (
                <div className="mt-6 bg-white rounded-xl shadow-sm border border-gray-200">
                  <div className="p-6 border-b border-gray-200">
                    <h2 className="text-lg font-semibold text-gray-900">Certificate</h2>
                  </div>
                  <div className="p-6">
                    <div className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                      <div className="flex items-center">
                        <svg className="w-8 h-8 text-red-600 mr-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                        </svg>
                        <div>
                          <p className="font-medium text-gray-900">SCRA Verification Certificate</p>
                          <p className="text-sm text-gray-500">PDF Document</p>
                        </div>
                      </div>
                      <button
                        onClick={downloadPDF}
                        className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
                      >
                        <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        Download PDF
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Screenshots */}
            <div className="xl:col-span-2">
              <div className="bg-white rounded-xl shadow-sm border border-gray-200">
                <div className="p-6 border-b border-gray-200">
                  <h2 className="text-lg font-semibold text-gray-900">
                    Verification Screenshots ({screenshots.length})
                  </h2>
                </div>
                <div className="p-6">
                  {screenshots.length > 0 ? (
                    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                      {/* Screenshot List */}
                      <div>
                        <h4 className="text-sm font-medium text-gray-700 mb-3">Step History</h4>
                        <div className="space-y-2 max-h-96 overflow-y-auto">
                          {screenshots.map((screenshot, index) => (
                            <div
                              key={index}
                              onClick={() => setSelectedScreenshot(screenshot)}
                              className={`flex items-center p-3 rounded-lg cursor-pointer transition-all ${
                                selectedScreenshot?.name === screenshot.name
                                  ? 'bg-blue-50 border-2 border-blue-200 shadow-sm'
                                  : 'bg-gray-50 hover:bg-gray-100 border-2 border-transparent'
                              }`}
                            >
                              <div className="w-2 h-2 bg-green-400 rounded-full mr-3 flex-shrink-0"></div>
                              <div className="flex-1 min-w-0">
                                <p className="text-sm font-medium text-gray-900 truncate">
                                  Step {index + 1}
                                </p>
                                <p className="text-xs text-gray-600 truncate">
                                  {screenshot.name}
                                </p>
                              </div>
                              {selectedScreenshot?.name === screenshot.name && (
                                <svg className="w-4 h-4 text-blue-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                                </svg>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Selected Screenshot */}
                      <div>
                        <h4 className="text-sm font-medium text-gray-700 mb-3">
                          {selectedScreenshot ? selectedScreenshot.name : 'Screenshot Preview'}
                        </h4>
                        
                        {selectedScreenshot ? (
                          <div 
                            className="relative bg-gray-100 rounded-lg overflow-hidden border cursor-pointer"
                            onClick={() => window.open(selectedScreenshot.url, '_blank')}
                          >
                            <ImageWithFallback
                              src={selectedScreenshot.url}
                              alt={selectedScreenshot.name}
                              className="w-full h-auto object-contain max-h-80 hover:opacity-90 transition-opacity"
                              filename={selectedScreenshot.name}
                            />
                            <div className="absolute bottom-2 right-2 bg-black bg-opacity-70 text-white px-2 py-1 rounded text-xs">
                              Click to enlarge
                            </div>
                          </div>
                        ) : (
                          <div className="flex flex-col items-center justify-center h-64 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
                            <svg className="w-12 h-12 text-gray-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                            </svg>
                            <p className="text-gray-500 text-sm text-center">
                              Select a screenshot to view
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-12">
                      <svg className="w-12 h-12 text-gray-400 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      <p className="text-gray-500 text-center mb-2">
                        No screenshots available for this verification
                      </p>
                      <p className="text-gray-400 text-sm text-center">
                        Screenshots may not have been captured during this verification process
                      </p>
                      <button
                        onClick={refreshData}
                        className="mt-4 inline-flex items-center px-3 py-2 border border-gray-300 shadow-sm text-sm leading-4 font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
                      >
                        <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        Refresh Data
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </Layout>
    </AppWrapper>
  );
}