'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Loader2, Eye, EyeOff, Database } from 'lucide-react';
import { useAuthStore } from '@/store/useAuthStore';

export default function LoginPage() {
    const router = useRouter();
    const { login, isLoading, error, isAuthenticated, clearError, isHydrating } = useAuthStore();

    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [sessionExpired, setSessionExpired] = useState(false);

    // Read session_expired from window.location.search to avoid the Suspense
    // boundary requirement that useSearchParams() imposes in Next.js 14.
    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        if (params.get('session_expired') === 'true') setSessionExpired(true);
    }, []);

    // Wait for cookie hydration before checking auth state to avoid redirecting
    // before the stored session has been restored (which would cause a redirect loop).
    useEffect(() => {
        if (!isHydrating && isAuthenticated) {
            router.replace('/dashboard');
        }
    }, [isAuthenticated, isHydrating, router]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        clearError();
        try {
            await login({ email, password });
            router.replace('/dashboard');
        } catch {
            // Error already set in store
        }
    };

    // Show spinner while restoring auth state — prevents flash
    if (isHydrating) {
        return (
            <div className="min-h-screen bg-slate-950 flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
            </div>
        );
    }

    return (
        <main className="min-h-screen bg-slate-950 flex items-center justify-center p-4 relative overflow-hidden">

            {/* Ambient background orbs */}
            <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
                <div className="absolute -top-40 -right-40 h-96 w-96 rounded-full bg-blue-600/20 blur-3xl animate-pulse" />
                <div
                    className="absolute -bottom-40 -left-40 h-96 w-96 rounded-full bg-violet-600/20 blur-3xl animate-pulse"
                    style={{ animationDelay: '1.5s' }}
                />
            </div>

            <div className="relative z-10 w-full max-w-[420px] animate-fade-in-up">

                {/* Brand header */}
                <div className="mb-8 text-center">
                    <div className="mx-auto mb-4 inline-flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-blue-500 to-violet-600 shadow-lg shadow-blue-500/30">
                        <Database className="h-8 w-8 text-white" />
                    </div>
                    <h1 className="text-2xl font-bold text-white">SQL Optimizer</h1>
                    <p className="mt-1 text-sm text-slate-400">AI-powered Database Analysis Platform</p>
                </div>

                {/* Card */}
                <div className="rounded-2xl border border-slate-800 bg-slate-900/80 p-8 shadow-2xl backdrop-blur-xl">
                    <div className="mb-6">
                        <h2 className="text-xl font-semibold text-white">Welcome back</h2>
                        <p className="mt-1 text-sm text-slate-400">Sign in to your account to continue</p>
                    </div>

                    {/* Session expired notice */}
                    {sessionExpired && (
                        <div className="mb-4 rounded-lg border border-yellow-500/20 bg-yellow-500/10 p-3">
                            <p className="text-sm text-yellow-300">⌛ Session expired. Please sign in again.</p>
                        </div>
                    )}

                    {/* API error */}
                    {error && (
                        <div className="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 p-3">
                            <p className="text-sm text-red-400">{error}</p>
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-5" noValidate>
                        {/* Email */}
                        <div className="space-y-1.5">
                            <label htmlFor="email" className="block text-sm font-medium text-slate-300">
                                Email Address
                            </label>
                            <input
                                id="email"
                                type="email"
                                autoComplete="email"
                                required
                                disabled={isLoading}
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                placeholder="you@example.com"
                                className="w-full rounded-lg border border-slate-700 bg-slate-800/60 px-4 py-2.5 text-white placeholder-slate-500 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                            />
                        </div>

                        {/* Password */}
                        <div className="space-y-1.5">
                            <label htmlFor="password" className="block text-sm font-medium text-slate-300">
                                Password
                            </label>
                            <div className="relative">
                                <input
                                    id="password"
                                    type={showPassword ? 'text' : 'password'}
                                    autoComplete="current-password"
                                    required
                                    disabled={isLoading}
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="••••••••"
                                    className="w-full rounded-lg border border-slate-700 bg-slate-800/60 px-4 py-2.5 pr-11 text-white placeholder-slate-500 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                                />
                                <button
                                    type="button"
                                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                                    onClick={() => setShowPassword((v) => !v)}
                                    className="absolute inset-y-0 right-0 flex items-center px-3 text-slate-400 transition-colors hover:text-slate-200"
                                >
                                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                </button>
                            </div>
                        </div>

                        {/* Submit */}
                        <button
                            id="btn-login"
                            type="submit"
                            disabled={isLoading || !email || !password}
                            className="w-full rounded-lg bg-gradient-to-r from-blue-600 to-violet-600 px-4 py-2.5 font-medium text-white shadow-lg shadow-blue-500/25 transition-all hover:from-blue-500 hover:to-violet-500 disabled:cursor-not-allowed disabled:opacity-50 flex items-center justify-center gap-2"
                        >
                            {isLoading ? (
                                <>
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    Signing in…
                                </>
                            ) : (
                                'Sign In'
                            )}
                        </button>
                    </form>

                    <div className="mt-6 text-center">
                        <p className="text-sm text-slate-400">
                            Don&apos;t have an account?{' '}
                            <Link
                                href="/register"
                                className="font-medium text-blue-400 transition-colors hover:text-blue-300"
                            >
                                Create one →
                            </Link>
                        </p>
                    </div>
                </div>

                <p className="mt-6 text-center text-xs text-slate-600">
                    Your SQL files are sanitized before analysis. Data stays private.
                </p>
            </div>
        </main>
    );
}
