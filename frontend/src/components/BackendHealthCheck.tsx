import { useState, useEffect } from 'react';
import { backendAPI } from '../lib/backend-api';

export default function BackendHealthCheck() {
  const [isHealthy, setIsHealthy] = useState<boolean | null>(null);
  const [backendUrl, setBackendUrl] = useState<string>('');

  useEffect(() => {
    const checkHealth = async () => {
      // Show both the env var and the actual baseUrl being used
      let envUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'Not set';
      // Clean the display URL for better readability
      if (envUrl.includes('scraverify-production.up.railway.app') && envUrl.includes(':8000')) {
        envUrl = envUrl.replace(':8000', '') + ' (cleaned)';
      }
      const actualUrl = (backendAPI as any).baseUrl || 'Unknown';
      setBackendUrl(`ENV: ${envUrl} | ACTUAL: ${actualUrl}`);
      const healthy = await backendAPI.healthCheck();
      setIsHealthy(healthy);
    };

    checkHealth();
    
    // Check every 30 seconds
    const interval = setInterval(checkHealth, 30000);
    
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="fixed bottom-4 right-4 z-50">
      <div className={`flex items-center px-3 py-2 rounded-lg text-sm font-medium shadow-lg ${
        isHealthy === null 
          ? 'bg-yellow-100 text-yellow-800 border border-yellow-200'
          : isHealthy 
            ? 'bg-green-100 text-green-800 border border-green-200'
            : 'bg-red-100 text-red-800 border border-red-200'
      }`}>
        <div className={`w-2 h-2 rounded-full mr-2 ${
          isHealthy === null 
            ? 'bg-yellow-400 animate-pulse'
            : isHealthy 
              ? 'bg-green-400'
              : 'bg-red-400'
        }`}></div>
        <span className="mr-2">
          Backend: {isHealthy === null ? 'Checking...' : isHealthy ? 'Connected' : 'Disconnected'}
        </span>
        <div className="text-xs opacity-75">
          {backendUrl}
        </div>
      </div>
    </div>
  );
}