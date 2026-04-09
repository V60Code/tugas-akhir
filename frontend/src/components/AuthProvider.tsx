'use client';

import { useEffect } from 'react';
import { useAuthStore } from '@/store/useAuthStore';

/**
 * AuthProvider — calls hydrate() once on client mount to restore auth state
 * from cookies. This is the client-side counterpart to the middleware.ts
 * server-side check.
 *
 * Must be a Client Component ("use client") because it uses useEffect.
 * Wrap this in the root layout so auth state is available app-wide.
 */
export function AuthProvider({ children }: { children: React.ReactNode }) {
    const hydrate = useAuthStore((state) => state.hydrate);

    useEffect(() => {
        hydrate();
    }, [hydrate]);

    return <>{children}</>;
}
