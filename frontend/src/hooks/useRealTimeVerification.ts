'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { 
  VerificationSession, 
  VerificationScreenshot,
  subscribeToSession,
  subscribeToScreenshots,
  getVerificationSession,
  getSessionScreenshots
} from '../lib/supabase';

interface UseRealTimeVerificationReturn {
  session: VerificationSession | null;
  screenshots: VerificationScreenshot[];
  loading: boolean;
  error: string | null;
  startTracking: (sessionId: string) => void;
  stopTracking: () => void;
}

export function useRealTimeVerification(): UseRealTimeVerificationReturn {
  const [session, setSession] = useState<VerificationSession | null>(null);
  const [screenshots, setScreenshots] = useState<VerificationScreenshot[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const subscriptionsRef = useRef<any[]>([]);

  const startTracking = useCallback(async (sessionId: string) => {
    setLoading(true);
    setError(null);
    setSession(null);
    setScreenshots([]);

    try {
      // Get initial session data
      const initialSession = await getVerificationSession(sessionId);
      if (initialSession) {
        setSession(initialSession);
      }

      // Get initial screenshots
      const initialScreenshots = await getSessionScreenshots(sessionId);
      if (initialScreenshots.length > 0) {
        setScreenshots(initialScreenshots);
      }

      // Subscribe to session updates
      const sessionSub = subscribeToSession(
        sessionId,
        (updatedSession) => {
          setSession(updatedSession);
        },
        (error) => {
          console.error('❌ Session subscription error:', error);
          setError('Real-time updates failed');
        }
      );

      // Subscribe to screenshot updates
      const screenshotsSub = subscribeToScreenshots(
        sessionId,
        (newScreenshot) => {
          setScreenshots(prev => {
            // Avoid duplicates
            const exists = prev.some(s => s.id === newScreenshot.id);
            if (exists) return prev;
            
            // Add new screenshot in chronological order
            const updated = [...prev, newScreenshot].sort(
              (a, b) => new Date(a.uploaded_at).getTime() - new Date(b.uploaded_at).getTime()
            );
            return updated;
          });
        },
        (error) => {
          console.error('❌ Screenshots subscription error:', error);
        }
      );

      subscriptionsRef.current = [sessionSub, screenshotsSub];

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start tracking');
    } finally {
      setLoading(false);
    }
  }, []);

  const stopTracking = useCallback(() => {
    
    // Unsubscribe from all channels
    subscriptionsRef.current.forEach(sub => {
      if (sub && typeof sub.unsubscribe === 'function') {
        sub.unsubscribe();
      }
    });
    
    subscriptionsRef.current = [];
    setSession(null);
    setScreenshots([]);
    setError(null);
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      // Cleanup subscriptions on unmount
      subscriptionsRef.current.forEach(sub => {
        if (sub && typeof sub.unsubscribe === 'function') {
          sub.unsubscribe();
        }
      });
      subscriptionsRef.current = [];
    };
  }, []);

  return {
    session,
    screenshots,
    loading,
    error,
    startTracking,
    stopTracking
  };
}