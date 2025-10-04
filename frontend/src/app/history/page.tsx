'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Layout from '../../components/Layout';
import AppWrapper from '../../components/AppWrapper';
import { useAuth } from '../../contexts/SupabaseAuthContext';

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

interface HistoryStats {
  total: number;
  successful: number;
  failed: number;
  errors: number;
  success_rate: number;
}

interface HistoryResponse {
  success: boolean;
  data: {
    history: VerificationRecord[];
    stats: HistoryStats;
    pagination: {
      limit: number;
      offset: number;
      total: number;
    };
  };
  error?: string;
}

export default function HistoryPage() {
  const router = useRouter();
  const [history, setHistory] = useState<VerificationRecord[]>([]);
  const [stats, setStats] = useState<HistoryStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);
  const { user } = useAuth();

  const fetchHistory = async () => {
    if (!user) {
      setHistory([]);
      setStats(null);
      setLoading(false);
      return;
    }

    // Check if we're in development mode
    const isDevMode = process.env.NEXT_PUBLIC_DEV_MODE === 'true';
    
    if (isDevMode && user.id === 'dev-user-123') {
      // Development mode: Show empty state with helpful message
      setHistory([]);
      setStats({
        total: 0,
        successful: 0,
        failed: 0,
        errors: 0,
        success_rate: 0
      });
      setError(null);
      setLoading(false);
      return;
    }

    try {
      setLoading(true);
      const { getUserVerifications } = await import('../../lib/supabase');
      const records = await getUserVerifications(user.id, true); // Use cache
      
      // Sort records by createdAt in JavaScript (newest first)
      records.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
      
      setHistory(records);
      
      // Calculate stats
      const total = records.length;
      const successful = records.filter(r => r.status === 'completed' && r.result?.success).length;
      const failed = records.filter(r => r.status === 'failed' || (r.status === 'completed' && !r.result?.success)).length;
      const errors = 0; // Deprecated: errors are already included in failed count
      
      setStats({
        total,
        successful,
        failed,
        errors,
        success_rate: total > 0 ? Math.round((successful / total) * 100) : 0
      });
      
      setError(null);
    } catch (err) {
      setError(`Failed to load verification history: ${(err as any).message || err}`);
    } finally {
      setLoading(false);
    }
  };

  const deleteRecord = async (sessionId: string) => {
    if (!user) return;
    
    try {
      const { deleteVerification } = await import('../../lib/supabase');
      await deleteVerification(sessionId, user.id);
      
      // Refresh history after deletion
      await fetchHistory();
      setDeleteConfirm(null);
    } catch {
      setError('Failed to delete record');
    }
  };

  const viewScreenshots = async (sessionId: string) => {
    if (!user) return;
    
    try {
      // Get all screenshots for this session from Supabase Storage
      const { getScreenshotUrls } = await import('../../lib/supabase');
      const screenshotUrls = await getScreenshotUrls(user.id, sessionId);
      
      if (screenshotUrls.length === 0) {
        setError('No screenshots found for this session.');
        return;
      }
      
      // Open a simple gallery view - for now just open each in a new tab
      screenshotUrls.forEach(screenshot => {
        window.open(screenshot.url, '_blank');
      });
      
    } catch {
      setError('Failed to view screenshots. They may not be available.');
    }
  };

  const downloadPDF = async (sessionId: string) => {
    if (!user) return;
    
    try {
      // Try different possible PDF filenames in order of preference
      const possibleFilenames = [
        'scra_result.pdf',
        'scra_verification_report.pdf'
      ];
      
      let downloadURL: string | null = null;
      let foundFilename: string | null = null;
      
      // Check each possible filename
      for (const filename of possibleFilenames) {
        try {
          const { getPdfUrl } = await import('../../lib/supabase');
          const url = await getPdfUrl(user.id, sessionId, filename);
          
          if (url) {
            downloadURL = url;
            foundFilename = filename;
            break;
          }
        } catch {
          continue;
        }
      }
      
      if (downloadURL) {
        window.open(downloadURL, '_blank');
      } else {
        setError('PDF not found for this verification session.');
      }
    } catch {
      setError('Failed to download PDF. It may not be available.');
    }
  };

  const getStatusBadge = (record: VerificationRecord) => {
    const isSuccess = record.status === 'completed' && record.result?.success;
    
    // For successful verifications, assume files exist in storage (since file data is not loaded in history view)
    if (isSuccess) {
      return (
        <div className="flex flex-col space-y-1">
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
            ✅ Success
          </span>
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
            📄 📸 Files Available
          </span>
        </div>
      );
    } else if (record.status === 'failed') {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
          ❌ Failed
        </span>
      );
    } else {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
          ⚠️ Processing
        </span>
      );
    }
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  useEffect(() => {
    fetchHistory();
  }, [user]);

  // Listen for verification completion to refresh history
  useEffect(() => {
    const handleVerificationCompleted = () => {
      fetchHistory();
    };

    window.addEventListener('verificationCompleted', handleVerificationCompleted);
    
    return () => {
      window.removeEventListener('verificationCompleted', handleVerificationCompleted);
    };
  }, [user]); // Include user in dependency to re-setup listener when user changes

  return (
    <AppWrapper>
      <Layout>
      <div className="p-6">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Verification History</h1>
          <p className="text-gray-600">View and manage past military status verifications</p>
        </div>

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <div className="w-8 h-8 bg-blue-100 rounded-md flex items-center justify-center">
                    <svg className="w-5 h-5 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </div>
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">Total</p>
                  <p className="text-2xl font-semibold text-gray-900">{stats.total}</p>
                </div>
              </div>
            </div>
            
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <div className="w-8 h-8 bg-green-100 rounded-md flex items-center justify-center">
                    <svg className="w-5 h-5 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">Successful</p>
                  <p className="text-2xl font-semibold text-gray-900">{stats.successful}</p>
                </div>
              </div>
            </div>
            
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <div className="w-8 h-8 bg-red-100 rounded-md flex items-center justify-center">
                    <svg className="w-5 h-5 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </div>
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">Failed</p>
                  <p className="text-2xl font-semibold text-gray-900">{stats.failed}</p>
                </div>
              </div>
            </div>
            
            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center">
                <div className="flex-shrink-0">
                  <div className="w-8 h-8 bg-purple-100 rounded-md flex items-center justify-center">
                    <svg className="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                    </svg>
                  </div>
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-500">Success Rate</p>
                  <p className="text-2xl font-semibold text-gray-900">{stats.success_rate}%</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* History Table */}
        <div className="bg-white shadow rounded-lg">
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h2 className="text-lg font-medium text-gray-900">Recent Verifications</h2>
            <button
              onClick={async () => {
                // Clear cache and fetch fresh data
                const { clearVerificationCache } = await import('../../lib/supabase');
                clearVerificationCache(user?.id);
                fetchHistory();
              }}
              className="inline-flex items-center px-3 py-1.5 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
            >
              <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Refresh
            </button>
          </div>

          {loading ? (
            <div className="p-8 text-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
              <p className="mt-2 text-gray-500">Loading history...</p>
            </div>
          ) : error ? (
            <div className="p-8 text-center">
              <div className="text-red-500 mb-2">
                <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
              </div>
              <p className="text-gray-900 font-medium">Error loading history</p>
              <p className="text-gray-500">{error}</p>
              <button
                onClick={fetchHistory}
                className="mt-4 inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700"
              >
                Try Again
              </button>
            </div>
          ) : history.length === 0 ? (
            <div className="p-8 text-center">
              <div className="text-gray-400 mb-4">
                <svg className="w-12 h-12 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              {process.env.NEXT_PUBLIC_DEV_MODE === 'true' && user?.id === 'dev-user-123' ? (
                <>
                  <p className="text-gray-900 font-medium">🚀 Development Mode</p>
                  <p className="text-gray-500">History is disabled in development mode to avoid database conflicts.</p>
                  <p className="text-gray-500 mt-2">Start a new verification to test the system!</p>
                </>
              ) : (
                <>
                  <p className="text-gray-900 font-medium">No verification history</p>
                  <p className="text-gray-500">Start a new verification to see results here.</p>
                </>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Service Member
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      SSN
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Date
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {history.map((record) => (
                    <tr 
                      key={record.sessionId} 
                      className="hover:bg-gray-50 cursor-pointer transition-colors"
                      onClick={() => {
                        router.push(`/history/${record.sessionId}`);
                      }}
                    >
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div>
                            <div className="text-sm font-medium text-gray-900">
                              {record.formData.firstName} {record.formData.middleName && `${record.formData.middleName} `}{record.formData.lastName} {record.formData.suffix}
                            </div>
                            <div className="text-sm text-gray-500">
                              DOB: {record.formData.dateOfBirth} | Active: {record.formData.activeDutyDate}
                            </div>
                          </div>
                          <div className="ml-auto">
                            <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                            </svg>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {record.formData.ssn ? `***-**-${record.formData.ssn.slice(-4)}` : 'N/A'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {getStatusBadge(record)}
                        {record.result?.error && (
                          <div className="text-xs text-red-600 mt-1 max-w-xs truncate" title={record.result.error}>
                            {record.result.error}
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {formatDate(record.createdAt)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            router.push(`/history/${record.sessionId}`);
                          }}
                          className="text-indigo-600 hover:text-indigo-900 font-medium"
                          title="View Details"
                        >
                          View Details
                        </button>
                        {/* Show file action buttons for successful verifications */}
                        {record.status === 'completed' && record.result?.success && (
                          <>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                viewScreenshots(record.sessionId);
                              }}
                              className="text-green-600 hover:text-green-900 mr-2"
                              title="View Screenshots"
                            >
                              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                              </svg>
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                downloadPDF(record.sessionId);
                              }}
                              className="text-blue-600 hover:text-blue-900"
                              title="Download PDF"
                            >
                              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                              </svg>
                            </button>
                          </>
                        )}
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setDeleteConfirm(record.sessionId);
                          }}
                          className="text-red-600 hover:text-red-900"
                          title="Delete record"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Delete Confirmation Modal */}
        {deleteConfirm && (
          <div className="fixed inset-0 bg-gray-600 bg-opacity-50 flex items-center justify-center z-50">
            <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
              <div className="flex items-center mb-4">
                <div className="flex-shrink-0">
                  <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
                  </svg>
                </div>
                <div className="ml-3">
                  <h3 className="text-lg font-medium text-gray-900">Delete Verification Record</h3>
                </div>
              </div>
              <p className="text-gray-500 mb-6">
                Are you sure you want to delete this verification record? This will also remove any associated PDF files and debug images. This action cannot be undone.
              </p>
              <div className="flex justify-end space-x-3">
                <button
                  onClick={() => setDeleteConfirm(null)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-md hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={() => deleteRecord(deleteConfirm)}
                  className="px-4 py-2 text-sm font-medium text-white bg-red-600 border border-transparent rounded-md hover:bg-red-700"
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
      </Layout>
    </AppWrapper>
  );
}