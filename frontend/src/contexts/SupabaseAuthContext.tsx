'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import type { User } from '@supabase/supabase-js';
import { supabase, getCurrentUser, onAuthStateChange } from '../lib/supabase';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  signInWithGoogle: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

interface AuthProviderProps {
  children: React.ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Check if we're in development mode
  const isDevMode = process.env.NEXT_PUBLIC_DEV_MODE === 'true';

  useEffect(() => {
    // Development mode bypass - create mock user
    if (isDevMode) {
      console.log('🚀 Development mode: Bypassing authentication');
      const mockUser: User = {
        id: 'dev-user-123',
        email: 'dev@example.com',
        user_metadata: {
          name: 'Dev User',
          avatar_url: 'https://via.placeholder.com/40'
        },
        app_metadata: {},
        aud: 'authenticated',
        created_at: new Date().toISOString(),
        role: 'authenticated',
        updated_at: new Date().toISOString()
      } as User;
      
      setUser(mockUser);
      setLoading(false);
      return;
    }

    // Production mode - normal auth flow
    getCurrentUser().then((user) => {
      setUser(user);
      setLoading(false);
    });

    // Listen for auth changes
    const { data: { subscription } } = onAuthStateChange((user) => {
      setUser(user);
      setLoading(false);
      
      // Handle OAuth callback - clean up URL after successful authentication
      if (user && typeof window !== 'undefined') {
        const url = new URL(window.location.href);
        if (url.hash.includes('access_token=')) {
          // Clear the hash and redirect to clean URL
          window.history.replaceState({}, document.title, url.pathname + url.search);
        }
      }
    });

    return () => subscription.unsubscribe();
  }, [isDevMode]);

  const handleSignInWithGoogle = async () => {
    try {
      setLoading(true);
      
      // Development mode - simulate sign in
      if (isDevMode) {
        console.log('🚀 Development mode: Simulating Google sign in');
        const mockUser: User = {
          id: 'dev-user-123',
          email: 'dev@example.com',
          user_metadata: {
            name: 'Dev User',
            avatar_url: 'https://via.placeholder.com/40'
          },
          app_metadata: {},
          aud: 'authenticated',
          created_at: new Date().toISOString(),
          role: 'authenticated',
          updated_at: new Date().toISOString()
        } as User;
        
        setUser(mockUser);
        setLoading(false);
        return;
      }

      // Production mode - real Google OAuth
      const { error } = await supabase.auth.signInWithOAuth({
        provider: 'google',
        options: {
          redirectTo: `${window.location.origin}/`,
        }
      });
      
      if (error) throw error;
    } catch (error) {
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const handleSignOut = async () => {
    try {
      setLoading(true);
      
      // Development mode - simulate sign out
      if (isDevMode) {
        console.log('🚀 Development mode: Simulating sign out');
        setUser(null);
        setLoading(false);
        return;
      }

      // Production mode - real sign out
      const { error } = await supabase.auth.signOut();
      if (error) throw error;
    } catch (error) {
      throw error;
    } finally {
      setLoading(false);
    }
  };

  const value = {
    user,
    loading,
    signInWithGoogle: handleSignInWithGoogle,
    signOut: handleSignOut,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}