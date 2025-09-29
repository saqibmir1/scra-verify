// Backend API service for Railway deployment

import { useState, useEffect } from "react";

export interface VerificationRequest {
  firstName: string;
  lastName: string;
  middleName?: string;
  suffix?: string;
  ssn: string;
  dateOfBirth: string;
  activeDutyDate: string;
}

export interface VerificationResponse {
  success: boolean;
  sessionId?: string;
  result?: {
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
  };
  data?: {
    automationResult?: {
      screenshots?: Array<{
        step: string;
        filename: string;
        description: string;
        data: string; // base64
        timestamp: string;
        size: number;
      }>;
      pdf?: {
        filename: string;
        data: string; // base64
        size: number;
      };
    };
    eligibility?: {
      activeDutyCovered: boolean;
      scraEligibilityType: string;
      matchReasonCode: string;
      covered: boolean;
    };
  };
  error?: string;
}

export interface SessionStatus {
  sessionId: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  progress: number;
  currentStep?: string;
  screenshots?: Array<{
    step: string;
    url: string;
    description: string;
    timestamp: string;
  }>;
  result?: VerificationResponse['result'];
  error?: string;
  startTime: string;
  endTime?: string;
}

class BackendAPI {
  private baseUrl: string;
  
  constructor() {
    let baseUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    // Remove any unwanted port numbers from production URLs
    if (baseUrl.includes('scraverify-production.up.railway.app') && baseUrl.includes(':8000')) {
      baseUrl = baseUrl.replace(':8000', '');
    }
    this.baseUrl = baseUrl;
  }

  async verifyActiveDuty(data: VerificationRequest, userId?: string): Promise<VerificationResponse> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    
    // Add user ID for real-time tracking if available
    if (userId) {
      headers['x-user-id'] = userId;
    }
    
    const response = await fetch(`${this.baseUrl}/verify`, {
      method: 'POST',
      headers,
      body: JSON.stringify(data)
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
  }

  async getSessionStatus(sessionId: string): Promise<SessionStatus> {
    const response = await fetch(`${this.baseUrl}/status/${sessionId}`);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
  }

  async getScreenshot(sessionId: string, step: string): Promise<string> {
    const response = await fetch(`${this.baseUrl}/screenshot/${sessionId}/${step}`);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const blob = await response.blob();
    return URL.createObjectURL(blob);
  }

  async downloadPdf(sessionId: string): Promise<Blob> {
    const response = await fetch(`${this.baseUrl}/pdf/${sessionId}`);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.blob();
  }

  // Health check
  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/health`);
      return response.ok;
    } catch {
      return false;
    }
  }
}

export const backendAPI = new BackendAPI();

// Hook for polling session status
export function useSessionStatus(sessionId: string | null) {
  const [status, setStatus] = useState<SessionStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!sessionId) {
      setStatus(null);
      setError(null);
      return;
    }

    const pollStatus = async () => {
      try {
        setIsLoading(true);
        const sessionStatus = await backendAPI.getSessionStatus(sessionId);
        setStatus(sessionStatus);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to get session status');
      } finally {
        setIsLoading(false);
      }
    };

    // Initial fetch
    pollStatus();

    // Poll every 2 seconds if session is still active
    const interval = setInterval(() => {
      if (status?.status === 'pending' || status?.status === 'in_progress') {
        pollStatus();
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [sessionId, status?.status]);

  return { status, error, isLoading };
}