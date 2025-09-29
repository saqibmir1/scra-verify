'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '../contexts/SupabaseAuthContext';

interface Props {
  open: boolean;
  onClose: () => void;
  required?: boolean;
  onCredentialsSaved?: () => void;
}

export default function SettingsModal({ open, onClose, required = false, onCredentialsSaved }: Props) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { user } = useAuth();

  useEffect(() => {
    async function load() {
      try {
        if (!user) return;
        const { getUserSettings } = await import('../lib/supabase');
        const settings = await getUserSettings(user.id);
        if (settings) {
          setUsername(settings.scraUsername || '');
          setPassword(settings.scraPassword || '');
        }
      } catch (e) {
        // ignore
      }
    }
    if (open) load();
  }, [open, user]);

  const save = async () => {
    if (!username.trim() || !password.trim()) {
      setError('Both username and password are required');
      return;
    }

    setSaving(true);
    setError(null);
    try {
      if (!user) throw new Error('Not signed in');
      const { saveUserSettings } = await import('../lib/supabase');
      await saveUserSettings(user.id, {
        scraUsername: username.trim(),
        scraPassword: password.trim()
      });
      
      // Small delay to allow Supabase to propagate changes
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Trigger callback to refresh credentials check
      if (onCredentialsSaved) {
        await onCredentialsSaved();
      }
      
      onClose();
    } catch (error: unknown) {
      setError(error instanceof Error ? error.message : 'Failed to save');
    } finally {
      setSaving(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
        <div className="flex items-center mb-4">
          <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center mr-3">
            <svg className="w-6 h-6 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">SCRA Credentials</h2>
            <p className="text-sm text-gray-600">
              {required ? 'Required to perform verifications' : 'Enter your SCRA web credentials'}
            </p>
          </div>
        </div>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">SCRA Username *</label>
            <input 
              type="text"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              value={username} 
              onChange={e => setUsername(e.target.value)}
              placeholder="Enter your SCRA username"
              disabled={saving}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">SCRA Password *</label>
            <input 
              type="password" 
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              value={password} 
              onChange={e => setPassword(e.target.value)}
              placeholder="Enter your SCRA password"
              disabled={saving}
            />
          </div>
          
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg">
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
            <div className="flex items-start">
              <svg className="w-5 h-5 text-blue-600 mr-2 mt-0.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <p className="text-sm text-blue-800 font-medium">Secure Storage</p>
                <p className="text-xs text-blue-700 mt-1">
                  Your credentials are encrypted and stored securely in your personal Supabase account. 
                  They are only used to authenticate with the SCRA verification system.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between pt-2">
            {!required && (
              <button 
                className="text-gray-600 hover:text-gray-800 text-sm font-medium transition-colors"
                onClick={onClose}
                disabled={saving}
              >
                Skip for now
              </button>
            )}
            <div className="flex space-x-3 ml-auto">
              {required && (
                <button 
                  className="px-4 py-2 text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg font-medium transition-colors"
                  onClick={onClose}
                  disabled={saving}
                >
                  Cancel
                </button>
              )}
              <button 
                disabled={saving || !username.trim() || !password.trim()}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white rounded-lg font-medium transition-colors"
                onClick={save}
              >
                {saving ? (
                  <div className="flex items-center">
                    <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Saving...
                  </div>
                ) : (
                  'Save Credentials'
                )}
              </button>
            </div>
          </div>

          {!required && (
            <div className="border-t border-gray-200 pt-3">
              <p className="text-xs text-gray-500 text-center">
                <strong>Note:</strong> SCRA credentials are required to perform military status verifications. 
                You can add them later, but verifications will fail until they are provided.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


