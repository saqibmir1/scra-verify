'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Image from 'next/image';
import { VerificationScreenshot } from '../lib/supabase';

interface RealTimeScreenshotsProps {
  screenshots: VerificationScreenshot[];
  loading: boolean;
  className?: string;
}

interface ImageWithFallbackProps {
  src: string;
  alt: string;
  className?: string;
  filename: string;
  description?: string;
  onLoad?: () => void;
  onError?: () => void;
}

function ImageWithFallback({ 
  src, 
  alt, 
  className, 
  filename, 
  description,
  onLoad,
  onError 
}: ImageWithFallbackProps) {
  const [hasError, setHasError] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  
  const handleError = useCallback(() => {
    setHasError(true);
    setIsLoading(false);
    onError?.();
  }, [onError]);
  
  const handleLoad = useCallback(() => {
    setIsLoading(false);
    onLoad?.();
  }, [onLoad]);

  if (!src) {
    return (
      <div className={`flex items-center justify-center h-64 bg-gray-100 rounded-lg ${className || ''}`}>
        <p className="text-gray-500 text-sm">No image URL provided</p>
      </div>
    );
  }

  if (hasError) {
    return (
      <div className={`flex flex-col items-center justify-center h-64 bg-red-50 border border-red-200 rounded-lg ${className || ''}`}>
        <div className="text-red-500 text-sm text-center p-4">
          <p className="font-medium">Failed to load screenshot</p>
          <p className="text-xs mt-1">{filename}</p>
          {description && <p className="text-xs mt-1 text-gray-600">{description}</p>}
        </div>
      </div>
    );
  }

  return (
    <div className={`relative ${className || ''}`}>
      {isLoading && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-100 rounded-lg">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
        </div>
      )}
      <Image
        src={src}
        alt={alt}
        width={400}
        height={300}
        className={`rounded-lg border shadow-sm transition-opacity duration-200 ${
          isLoading ? 'opacity-0' : 'opacity-100'
        }`}
        style={{ objectFit: 'contain' }}
        onLoad={handleLoad}
        onError={handleError}
        unoptimized={true} // For Supabase signed URLs
      />
      {!isLoading && (
        <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-75 text-white p-2 rounded-b-lg">
          <p className="text-xs font-medium truncate">{filename}</p>
          {description && (
            <p className="text-xs opacity-90 truncate">{description}</p>
          )}
        </div>
      )}
    </div>
  );
}

export default function RealTimeScreenshots({ 
  screenshots, 
  loading, 
  className = '' 
}: RealTimeScreenshotsProps) {
  const [selectedScreenshot, setSelectedScreenshot] = useState<VerificationScreenshot | null>(null);
  const [loadedCount, setLoadedCount] = useState(0);

  // Auto-scroll to latest screenshot
  const scrollToLatest = useCallback(() => {
    if (screenshots.length > 0) {
      const container = document.getElementById('screenshots-container');
      if (container) {
        container.scrollTop = container.scrollHeight;
      }
    }
  }, [screenshots.length]);

  useEffect(() => {
    // Scroll to latest when new screenshots arrive
    const timer = setTimeout(scrollToLatest, 100);
    return () => clearTimeout(timer);
  }, [scrollToLatest]);

  const handleImageLoad = useCallback(() => {
    setLoadedCount(prev => prev + 1);
  }, []);

  if (loading && screenshots.length === 0) {
    return (
      <div className={`p-6 text-center ${className}`}>
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
        <p className="text-gray-600">Initializing screenshot tracking...</p>
      </div>
    );
  }

  if (screenshots.length === 0) {
    return (
      <div className={`p-6 text-center bg-gray-50 rounded-lg ${className}`}>
        <div className="text-gray-500">
          <svg className="mx-auto h-12 w-12 mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} 
              d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
          </svg>
          <p className="text-lg font-medium">No screenshots yet</p>
          <p className="text-sm">Screenshots will appear here in real-time as verification progresses</p>
        </div>
      </div>
    );
  }

  return (
    <div className={className}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            Real-time Screenshots
          </h3>
          <p className="text-sm text-gray-600">
            {screenshots.length} screenshot{screenshots.length !== 1 ? 's' : ''} captured
            {loadedCount < screenshots.length && ` (${loadedCount}/${screenshots.length} loaded)`}
          </p>
        </div>
        
        {loading && (
          <div className="flex items-center text-blue-600">
            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600 mr-2"></div>
            <span className="text-sm">Live updates</span>
          </div>
        )}
      </div>

      {/* Screenshots Grid */}
      <div 
        id="screenshots-container"
        className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 max-h-96 overflow-y-auto p-2 bg-gray-50 rounded-lg"
        style={{ scrollBehavior: 'smooth' }}
      >
        {screenshots.map((screenshot, index) => (
          <div key={screenshot.id} className="relative">
            {/* Step indicator */}
            <div className="absolute top-2 left-2 bg-blue-500 text-white text-xs px-2 py-1 rounded z-10">
              Step {index + 1}
            </div>
            
            {/* Timestamp */}
            <div className="absolute top-2 right-2 bg-black bg-opacity-75 text-white text-xs px-2 py-1 rounded z-10">
              {new Date(screenshot.uploaded_at).toLocaleTimeString()}
            </div>

            <ImageWithFallback
              src={screenshot.url || ''}
              alt={`Screenshot ${index + 1}: ${screenshot.step}`}
              filename={screenshot.filename}
              description={screenshot.description}
              className="w-full cursor-pointer hover:scale-105 transition-transform duration-200"
              onLoad={handleImageLoad}
              onError={() => console.error('Failed to load screenshot:', screenshot.filename)}
            />
          </div>
        ))}
      </div>

      {/* Selected Screenshot Modal */}
      {selectedScreenshot && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedScreenshot(null)}
        >
          <div className="max-w-4xl max-h-full bg-white rounded-lg overflow-hidden">
            <div className="p-4 border-b">
              <div className="flex justify-between items-center">
                <div>
                  <h4 className="font-semibold">{selectedScreenshot.step}</h4>
                  <p className="text-sm text-gray-600">{selectedScreenshot.description}</p>
                </div>
                <button
                  onClick={() => setSelectedScreenshot(null)}
                  className="text-gray-500 hover:text-gray-700"
                >
                  <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
            <div className="p-4">
              <Image
                src={selectedScreenshot.url || ''}
                alt={selectedScreenshot.step}
                width={800}
                height={600}
                className="rounded-lg"
                style={{ objectFit: 'contain' }}
                unoptimized={true}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}