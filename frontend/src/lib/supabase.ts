'use client';

import { createClient } from '@supabase/supabase-js';
import type { User } from '@supabase/supabase-js';

// Supabase configuration
const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://placeholder.supabase.co';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'placeholder_key';

// Only throw error at runtime, not during build
if (typeof window !== 'undefined' && (!process.env.NEXT_PUBLIC_SUPABASE_URL || !process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY)) {
  console.warn('⚠️ Supabase environment variables not configured properly');
}

// Create Supabase client with caching configuration
export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  db: {
    schema: 'public',
  },
  auth: {
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: true
  },
  global: {
    headers: { 
      'x-application-name': 'active-duty-verification',
      'cache-control': 'max-age=300' // 5 minutes cache
    }
  },
  realtime: {
    params: {
      eventsPerSecond: 2
    }
  }
});

// Auth functions
export async function signInWithGoogle(): Promise<User> {
  // Use environment variable for redirect URL, fallback to current origin
  const redirectUrl = process.env.NEXT_PUBLIC_SITE_URL || `${window.location.origin}/`;
    
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: 'google',
    options: {
      redirectTo: redirectUrl,
    }
  });
  
  if (error) throw error;
  
  // Return user from session after OAuth redirect
  const { data: { session } } = await supabase.auth.getSession();
  if (!session?.user) throw new Error('No user session found');
  
  return session.user;
}

export async function signOut(): Promise<void> {
  const { error } = await supabase.auth.signOut();
  if (error) throw error;
}

export function onAuthStateChange(callback: (user: User | null) => void) {
  return supabase.auth.onAuthStateChange((event, session) => {
    callback(session?.user || null);
  });
}

export async function getCurrentUser(): Promise<User | null> {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.user || null;
}

export async function getCurrentUserToken(): Promise<string | null> {
  const { data: { session } } = await supabase.auth.getSession();
  return session?.access_token || null;
}

// User Settings
export interface UserSettings {
  scraUsername: string;
  scraPassword: string;
  updatedAt: string;
}

export async function saveUserSettings(userId: string, settings: {scraUsername: string, scraPassword: string}): Promise<void> {
  const { error } = await supabase
    .from('user_settings')
    .upsert({
      user_id: userId,
      scra_username: settings.scraUsername,
      scra_password: settings.scraPassword,
      updated_at: new Date().toISOString()
    }, {
      onConflict: 'user_id'
    });

  if (error) throw error;
}

export async function getUserSettings(userId: string): Promise<UserSettings | null> {
  const { data, error } = await supabase
    .from('user_settings')
    .select('*')
    .eq('user_id', userId)
    .single();

  if (error) {
    if (error.code === 'PGRST116') return null; // No rows found
    throw error;
  }

  return {
    scraUsername: data.scra_username || '',
    scraPassword: data.scra_password || '',
    updatedAt: data.updated_at || ''
  };
}

// Verification History
export interface VerificationRecord {
  id?: string;
  sessionId: string;
  userId: string;
  formData: {
    // Single record fields
    firstName?: string;
    lastName?: string;
    middleName?: string;
    suffix?: string;
    ssn?: string;
    dateOfBirth?: string;
    activeDutyDate?: string;
    // Multi-record fields
    type?: string;
    record_count?: number;
    fixed_width_preview?: string;
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
    pdfDownloaded?: boolean;
    pdfUrl?: string;
    error?: string;
    timestamp: string;
    data?: any;
  };
  status: 'completed' | 'failed' | 'in_progress';
  timestamp: string;
  createdAt: string;
}

export async function saveVerificationToSupabase(verification: VerificationRecord): Promise<void> {
  const user = await getCurrentUser();
  if (!user) throw new Error('No authenticated user');

  const { error } = await supabase
    .from('verifications')
    .insert({
      session_id: verification.sessionId,
      user_id: user.id,
      form_data: verification.formData,
      result: verification.result,
      status: verification.status,
      timestamp: verification.timestamp,
      created_at: new Date().toISOString()
    });

  if (error) throw error;
}

// Cache for user verifications
const verificationCache = new Map<string, { data: VerificationRecord[], timestamp: number }>();
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes in milliseconds

export async function getUserVerifications(userId: string, useCache: boolean = true, limit: number = 25): Promise<VerificationRecord[]> {
  const cacheKey = `verifications_${userId}_${limit}`;
  const now = Date.now();

  // Check cache first
  if (useCache && verificationCache.has(cacheKey)) {
    const cached = verificationCache.get(cacheKey)!;
    if (now - cached.timestamp < CACHE_DURATION) {
      return cached.data;
    }
  }

  // Retry logic for transient database issues
  let lastError: any = null;
  const maxRetries = 2;
  
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const { data, error } = await supabase
        .from('verifications')
        .select(`
          id,
          session_id,
          user_id,
          form_data,
          result->>success,
          result->>method,
          result->>error,
          result->>timestamp,
          result->eligibility,
          status,
          timestamp,
          created_at
        `)
        .eq('user_id', userId)
        .order('created_at', { ascending: false })
        .limit(limit)
        .abortSignal(AbortSignal.timeout(15000)); // 15 second timeout

      if (error) {
        // Check if it's a timeout error
        if (error.message?.includes('timeout') || error.code === '57014') {
          lastError = error;
          if (attempt < maxRetries) {
            // Wait before retry (exponential backoff)
            await new Promise(resolve => setTimeout(resolve, 1000 * (attempt + 1)));
            continue;
          }
        }
        throw error;
      }

      const mappedData: VerificationRecord[] = (data || []).map((record: any) => ({
        id: record.id,
        sessionId: record.session_id,
        userId: record.user_id,
        formData: record.form_data,
        result: {
          success: record.success === 'true' || record.success === true,
          method: record.method || '',
          error: record.error || undefined,
          timestamp: record.timestamp || '',
          eligibility: record.eligibility as any, // Cast to any since we're getting JSON from Supabase
          pdfDownloaded: false,
          pdfUrl: undefined,
        },
        status: record.status,
        timestamp: record.timestamp,
        createdAt: record.created_at
      }));

      // Cache the results
      if (useCache) {
        verificationCache.set(cacheKey, { data: mappedData, timestamp: now });
      }

      return mappedData;
    } catch (err) {
      lastError = err;
      if (attempt < maxRetries) {
        // Wait before retry
        await new Promise(resolve => setTimeout(resolve, 1000 * (attempt + 1)));
        continue;
      }
      throw err;
    }
  }
  
  // If we get here, all retries failed
  throw lastError || new Error('Failed to fetch verifications after retries');
}

export async function getVerificationDetails(userId: string, sessionId: string): Promise<VerificationRecord | null> {
  const { data, error } = await supabase
    .from('verifications')
    .select('*')
    .eq('user_id', userId)
    .eq('session_id', sessionId)
    .single();

  if (error) {
    if (error.code === 'PGRST116') return null; // No rows found
    throw error;
  }

  return {
    id: data.id,
    sessionId: data.session_id,
    userId: data.user_id,
    formData: data.form_data,
    result: data.result, // Full result data including files
    status: data.status,
    timestamp: data.timestamp,
    createdAt: data.created_at
  };
}

export async function deleteVerification(sessionId: string, userId: string): Promise<void> {
  const { error } = await supabase
    .from('verifications')
    .delete()
    .eq('session_id', sessionId)
    .eq('user_id', userId);

  if (error) throw error;

  // Clear relevant caches
  clearVerificationCache(userId);
}

// Cache for screenshots and PDFs (longer duration to reduce repeated signed URL generation)
const screenshotCache = new Map<string, { data: Array<{name: string, url: string}>, timestamp: number }>();
const pdfCache = new Map<string, { data: string | null, timestamp: number }>();
const SIGNED_URL_CACHE_DURATION = 30 * 60 * 1000; // 30 minutes (signed URLs expire after 1 hour)

// Cache management functions
export function clearVerificationCache(userId?: string): void {
  if (userId) {
    // Clear all cache entries for this user (regardless of limit)
    const keysToDelete: string[] = [];
    verificationCache.forEach((_, key) => {
      if (key.startsWith(`verifications_${userId}`)) {
        keysToDelete.push(key);
      }
    });
    keysToDelete.forEach(key => verificationCache.delete(key));
  } else {
    verificationCache.clear();
    screenshotCache.clear();
    pdfCache.clear();
  }
}

// File Storage
export async function uploadScreenshotsToSupabase(
  userId: string,
  sessionId: string,
  screenshots: Array<{
    step: string;
    filename: string;
    description: string;
    data: string; // base64
    timestamp: string;
    size: number;
  }>
): Promise<void> {
  for (const screenshot of screenshots) {
    try {

      // Convert base64 to array buffer
      const binaryString = atob(screenshot.data);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      // Upload to Supabase Storage
      const filePath = `users/${userId}/verifications/${sessionId}/screenshots/${screenshot.filename}`;
      const { error } = await supabase.storage
        .from('verification-files')
        .upload(filePath, bytes, {
          contentType: 'image/png',
          upsert: true
        });

      if (error) throw error;
    } catch (error) {
      console.error(`Failed to upload screenshot ${screenshot.filename}:`, error);
      throw error;
    }
  }
}

export async function uploadPdfToSupabase(
  userId: string,
  sessionId: string,
  pdfData: {
    filename: string;
    data: string; // base64
    size: number;
    timestamp: string;
  }
): Promise<void> {
  try {

    // Convert base64 to array buffer
    const binaryString = atob(pdfData.data);
    const bytes = new Uint8Array(binaryString.length);
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }

    // Upload to Supabase Storage
    const filePath = `users/${userId}/verifications/${sessionId}/pdfs/${pdfData.filename}`;
    const { error } = await supabase.storage
      .from('verification-files')
      .upload(filePath, bytes, {
        contentType: 'application/pdf',
        upsert: true
      });

    if (error) throw error;
  } catch (error) {
    console.error(`Failed to upload PDF:`, error);
    throw error;
  }
}

export async function getFileUrl(filePath: string): Promise<string> {
  // Use createSignedUrl for private buckets (expires in 1 hour)
  const { data, error } = await supabase.storage
    .from('verification-files')
    .createSignedUrl(filePath, 3600);
  
  if (error) {
    console.error(`Error creating signed URL for ${filePath}:`, error);
    throw error;
  }
  
  return data.signedUrl;
}

export async function downloadPdf(userId: string, sessionId: string, filename: string): Promise<void> {
  try {
    const filePath = `users/${userId}/verifications/${sessionId}/pdfs/${filename}`;
    
    // Use createSignedUrl for private buckets
    const { data, error } = await supabase.storage
      .from('verification-files')
      .createSignedUrl(filePath, 3600); // 1 hour expiration
    
    if (error) {
      console.error(`Error creating signed URL for PDF:`, error);
      throw error;
    }
    
    // Open in new tab for download
    window.open(data.signedUrl, '_blank');
  } catch (error) {
    console.error('Error downloading PDF:', error);
    throw error;
  }
}

export async function getScreenshotUrls(userId: string, sessionId: string, useCache: boolean = true): Promise<Array<{name: string, url: string}>> {
  const cacheKey = `screenshots_${userId}_${sessionId}`;
  const now = Date.now();

  // Check cache first (use longer cache for signed URLs)
  if (useCache && screenshotCache.has(cacheKey)) {
    const cached = screenshotCache.get(cacheKey)!;
    if (now - cached.timestamp < SIGNED_URL_CACHE_DURATION) {
      return cached.data;
    }
  }

  // Try multiple possible paths based on actual Supabase structure
  const pathsToTry = [
    `sessions/${sessionId}/screenshots`,
    `users/${userId}/verifications/${sessionId}/screenshots`,
  ];
  
  let data: any[] = [];
  let error: any = null;
  let foundPath: string | null = null;
  
  try {
    for (const path of pathsToTry) {
      const response = await supabase.storage
        .from('verification-files')
        .list(path);
      
      if (response.data && response.data.length > 0) {
        data = response.data;
        error = response.error;
        foundPath = path;
        break;
      }
    }
  } catch (e) {
    console.error('Error fetching screenshots:', e);
    throw e;
  }

  if (error) throw error;

  // Generate SIGNED URLs for each screenshot (bucket is private)
  const screenshots = [];
  for (const file of data || []) {
    if (!foundPath) continue;
    
    const filePath = `${foundPath}/${file.name}`;
    
    const { data: urlData, error: urlError } = await supabase.storage
      .from('verification-files')
      .createSignedUrl(filePath, 3600);
    
    if (urlError) {
      console.error(`Error creating signed URL for ${filePath}:`, urlError);
      continue;
    }
    
    screenshots.push({
      name: file.name,
      url: urlData.signedUrl
    });
  }

  // Cache the results
  if (useCache && screenshots.length > 0) {
    screenshotCache.set(cacheKey, { data: screenshots, timestamp: now });
  }
  
  return screenshots;
}

export async function getPdfUrl(userId: string, sessionId: string, filename: string, useCache: boolean = true): Promise<string | null> {
  const cacheKey = `pdf_${userId}_${sessionId}_${filename}`;
  const now = Date.now();

  // Check cache first (use longer cache for signed URLs)
  if (useCache && pdfCache.has(cacheKey)) {
    const cached = pdfCache.get(cacheKey)!;
    if (now - cached.timestamp < SIGNED_URL_CACHE_DURATION) {
      return cached.data;
    }
  }

  try {
    const pdfDir = `users/${userId}/verifications/${sessionId}/pdfs`;
    const filePath = `${pdfDir}/${filename}`;
    
    const { data, error } = await supabase.storage
      .from('verification-files')
      .createSignedUrl(filePath, 3600);
    
    if (error) {
      console.error(`Error creating signed URL for PDF ${filePath}:`, error);
      return null;
    }
    
    const result = data.signedUrl;

    // Cache the result
    if (useCache) {
      pdfCache.set(cacheKey, { data: result, timestamp: now });
    }

    return result;
  } catch (error) {
    console.error('Error getting PDF URL:', error);
    return null;
  }
}

export async function viewScreenshots(userId: string, sessionId: string): Promise<void> {
  try {
    const screenshots = await getScreenshotUrls(userId, sessionId);
    
    // Open each screenshot in new tab
    for (const screenshot of screenshots) {
      window.open(screenshot.url, '_blank');
    }
  } catch (error) {
    console.error('Error viewing screenshots:', error);
    throw error;
  }
}

// Real-time Session Tracking
export interface VerificationSession {
  id: string;
  session_id: string;
  user_id: string;
  status: 'in_progress' | 'completed' | 'failed';
  current_step?: string;
  progress: number;
  form_data: {
    firstName: string;
    lastName: string;
    middleName?: string;
    ssn: string;
    dateOfBirth: string;
    activeDutyDate: string;
  };
  error_message?: string;
  created_at: string;
  updated_at: string;
}

export interface VerificationScreenshot {
  id: string;
  session_id: string;
  step: string;
  filename: string;
  description?: string;
  storage_path?: string;
  file_size?: number;
  uploaded_at: string;
  url?: string; // Signed URL for frontend access
}

// Real-time subscriptions
export function subscribeToSession(
  sessionId: string,
  onSessionUpdate: (session: VerificationSession) => void,
  onError?: (error: Error) => void
) {
  const subscription = supabase
    .channel(`session:${sessionId}`)
    .on(
      'postgres_changes',
      {
        event: '*',
        schema: 'public',
        table: 'verification_sessions',
        filter: `session_id=eq.${sessionId}`
      },
      (payload) => {
        if (payload.new) {
          onSessionUpdate(payload.new as VerificationSession);
        }
      }
    )
    .subscribe((status) => {
      if (status === 'SUBSCRIBED') {
      }
    });

  return subscription;
}

export function subscribeToScreenshots(
  sessionId: string,
  onScreenshotUpdate: (screenshot: VerificationScreenshot) => void,
  onError?: (error: Error) => void
) {
  const subscription = supabase
    .channel(`screenshots:${sessionId}`)
    .on(
      'postgres_changes',
      {
        event: 'INSERT',
        schema: 'public',
        table: 'verification_screenshots',
        filter: `session_id=eq.${sessionId}`
      },
      async (payload) => {
        if (payload.new) {
          const screenshot = payload.new as VerificationScreenshot;
          // Get signed URL for the screenshot (bucket is private)
          if (screenshot.storage_path) {
            const { data, error } = await supabase.storage
              .from('verification-files')
              .createSignedUrl(screenshot.storage_path, 3600);
            
            if (!error && data) {
              onScreenshotUpdate({
                ...screenshot,
                url: data.signedUrl
              } as any);
            }
          }
        }
      }
    )
    .subscribe((status) => {
      if (status === 'SUBSCRIBED') {
      }
    });

  return subscription;
}

// Get session data
export async function getVerificationSession(sessionId: string): Promise<VerificationSession | null> {
  const { data, error } = await supabase
    .from('verification_sessions')
    .select('*')
    .eq('session_id', sessionId)
    .single();

  if (error) {
    if (error.code === 'PGRST116') return null; // No rows found
    throw error;
  }

  return data;
}

// Get screenshots for session using backend API
export async function getSessionScreenshots(sessionId: string): Promise<VerificationScreenshot[]> {
  try {
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL;
    if (!backendUrl) {
      throw new Error('Backend URL not configured');
    }

    // Get user session for authorization
    const { data: { session } } = await supabase.auth.getSession();
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    
    if (session?.access_token) {
      headers['Authorization'] = `Bearer ${session.access_token}`;
    }

    const response = await fetch(`${backendUrl}/screenshots/${sessionId}`, {
      method: 'GET',
      headers,
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch screenshots: ${response.status}`);
    }

    const result = await response.json();
    
    if (!result.success) {
      throw new Error(result.error || 'Failed to get screenshots');
    }

    return result.screenshots || [];
  } catch (error) {
    console.error('Error fetching session screenshots:', error);
    
    // Fallback to direct Supabase query if backend API fails
    console.log('Falling back to direct Supabase query...');
    const { data, error: supabaseError } = await supabase
      .from('verification_screenshots')
      .select('*')
      .eq('session_id', sessionId)
      .order('uploaded_at', { ascending: true });

    if (supabaseError) throw supabaseError;

    // Add signed URLs to screenshots (bucket is private)
    const screenshotsWithUrls = [];
    for (const screenshot of data || []) {
      const { data: urlData, error: urlError } = await supabase.storage
        .from('verification-files')
        .createSignedUrl(screenshot.storage_path, 3600);
      
      if (!urlError && urlData) {
        screenshotsWithUrls.push({
          ...screenshot,
          url: urlData.signedUrl
        } as VerificationScreenshot);
      }
    }
    return screenshotsWithUrls;
  }
}

// Get latest screenshots for a user
export async function getUserLatestScreenshots(userId: string, limit: number = 10): Promise<VerificationScreenshot[]> {
  try {
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL;
    if (!backendUrl) {
      throw new Error('Backend URL not configured');
    }

    // Get user session for authorization
    const { data: { session } } = await supabase.auth.getSession();
    if (!session?.access_token) {
      throw new Error('Authentication required');
    }

    const response = await fetch(`${backendUrl}/screenshots/user/${userId}/latest?limit=${limit}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${session.access_token}`,
      },
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch user screenshots: ${response.status}`);
    }

    const result = await response.json();
    
    if (!result.success) {
      throw new Error(result.error || 'Failed to get user screenshots');
    }

    return result.screenshots || [];
  } catch (error) {
    console.error('Error fetching user screenshots:', error);
    return [];
  }
}