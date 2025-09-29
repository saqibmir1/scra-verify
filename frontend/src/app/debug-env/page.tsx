'use client';

export default function DebugEnvPage() {
  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Environment Variables Debug</h1>
      
      <div className="space-y-4">
        <div className="bg-gray-100 p-4 rounded">
          <strong>NEXT_PUBLIC_SUPABASE_URL:</strong>
          <div className="mt-2 font-mono text-sm bg-white p-2 rounded border">
            {process.env.NEXT_PUBLIC_SUPABASE_URL || 'undefined'}
          </div>
        </div>
        
        <div className="bg-gray-100 p-4 rounded">
          <strong>NEXT_PUBLIC_SUPABASE_ANON_KEY:</strong>
          <div className="mt-2 font-mono text-sm bg-white p-2 rounded border">
            {process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ? 
              `${process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY.substring(0, 50)}...` : 
              'undefined'
            }
          </div>
        </div>
        
        <div className="bg-gray-100 p-4 rounded">
          <strong>NEXT_PUBLIC_BACKEND_URL:</strong>
          <div className="mt-2 font-mono text-sm bg-white p-2 rounded border">
            {process.env.NEXT_PUBLIC_BACKEND_URL || 'undefined'}
          </div>
        </div>
        
        <div className="bg-gray-100 p-4 rounded">
          <strong>NEXT_PUBLIC_SITE_URL:</strong>
          <div className="mt-2 font-mono text-sm bg-white p-2 rounded border">
            {process.env.NEXT_PUBLIC_SITE_URL || 'undefined'}
          </div>
        </div>

        <div className="bg-gray-100 p-4 rounded">
          <strong>All NEXT_PUBLIC_* variables:</strong>
          <div className="mt-2 font-mono text-xs bg-white p-2 rounded border">
            <pre>
              {JSON.stringify(
                Object.keys(process.env)
                  .filter(key => key.startsWith('NEXT_PUBLIC_'))
                  .reduce((obj, key) => ({
                    ...obj,
                    [key]: process.env[key]
                  }), {}),
                null,
                2
              )}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}