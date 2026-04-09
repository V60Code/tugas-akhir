'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Loader2, Eye, EyeOff, Database, CheckCircle2 } from 'lucide-react';
import { useAuthStore } from '@/store/useAuthStore';

const FEATURES = ['AI-powered Analysis', 'Docker Sandbox Testing', 'Privacy First', 'Instant Results'];

/** Simple password strength meter */
function getStrength(pwd: string): { label: string; color: string; pct: string } {
    if (!pwd) return { label: '', color: '', pct: '0%' };
    if (pwd.length < 6) return { label: 'Weak', color: 'bg-red-500', pct: '33%' };
    if (pwd.length < 10) return { label: 'Fair', color: 'bg-yellow-500', pct: '66%' };
    return { label: 'Strong', color: 'bg-green-500', pct: '100%' };
}

export default function RegisterPage() {
    const router = useRouter();
    const { register, isLoading, error, isAuthenticated, clearError, isHydrating } = useAuthStore();

    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [showPwd, setShowPwd] = useState(false);
    const [showConfirm, setShowConfirm] = useState(false);
    const [localError, setLocalError] = useState<string | null>(null);

    // Redirect already-authenticated users away from the register page.
    useEffect(() => {
        if (!isHydrating && isAuthenticated) router.replace('/dashboard');
    }, [isAuthenticated, isHydrating, router]);

    const strength = getStrength(password);
    const passwordMismatch = confirmPassword.length > 0 && password !== confirmPassword;

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        clearError();
        setLocalError(null);

        // Client-side validation (Critical Gap #9)
        if (password.length < 8) {
            setLocalError('Password must be at least 8 characters.');
            return;
        }
        if (password !== confirmPassword) {
            setLocalError('Passwords do not match.');
            return;
        }

        try {
            await register({ email, password, full_name: fullName });
            router.replace('/dashboard');
        } catch {
            // error already set in store
        }
    };

    if (isHydrating) {
        return (
            <div className="min-h-screen bg-slate-950 flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
            </div>
        );
    }

    const displayError = localError ?? error;

    return (
        <main className="min-h-screen bg-slate-950 flex items-center justify-center p-4 relative overflow-hidden">

            {/* Ambient background orbs */}
            <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
                <div className="absolute -top-40 -left-40 h-96 w-96 rounded-full bg-violet-600/20 blur-3xl animate-pulse" />
                <div
                    className="absolute -bottom-40 -right-40 h-96 w-96 rounded-full bg-blue-600/20 blur-3xl animate-pulse"
                    style={{ animationDelay: '1s' }}
                />
            </div>

            <div className="relative z-10 w-full max-w-[440px] animate-fade-in-up">

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
                    <div className="mb-5">
                        <h2 className="text-xl font-semibold text-white">Create an account</h2>
                        <p className="mt-1 text-sm text-slate-400">Start optimizing your SQL schemas today</p>
                    </div>

                    {/* Feature pills */}
                    <div className="mb-5 grid grid-cols-2 gap-2">
                        {FEATURES.map((f) => (
                            <div key={f} className="flex items-center gap-1.5 text-xs text-slate-400">
                                <CheckCircle2 className="h-3.5 w-3.5 flex-shrink-0 text-green-400" />
                                {f}
                            </div>
                        ))}
                    </div>

                    {/* Error banner */}
                    {displayError && (
                        <div className="mb-4 rounded-lg border border-red-500/20 bg-red-500/10 p-3">
                            <p className="text-sm text-red-400">{displayError}</p>
                        </div>
                    )}

                    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
                        {/* Full Name */}
                        <div className="space-y-1.5">
                            <label htmlFor="fullName" className="block text-sm font-medium text-slate-300">
                                Full Name
                            </label>
                            <input
                                id="fullName"
                                type="text"
                                autoComplete="name"
                                disabled={isLoading}
                                value={fullName}
                                onChange={(e) => setFullName(e.target.value)}
                                placeholder="John Doe"
                                className="w-full rounded-lg border border-slate-700 bg-slate-800/60 px-4 py-2.5 text-white placeholder-slate-500 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                            />
                        </div>

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
                                    type={showPwd ? 'text' : 'password'}
                                    autoComplete="new-password"
                                    required
                                    disabled={isLoading}
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    placeholder="min. 8 characters"
                                    className="w-full rounded-lg border border-slate-700 bg-slate-800/60 px-4 py-2.5 pr-11 text-white placeholder-slate-500 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                                />
                                <button
                                    type="button"
                                    aria-label={showPwd ? 'Hide password' : 'Show password'}
                                    onClick={() => setShowPwd((v) => !v)}
                                    className="absolute inset-y-0 right-0 flex items-center px-3 text-slate-400 transition-colors hover:text-slate-200"
                                >
                                    {showPwd ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                </button>
                            </div>
                            {/* Password strength bar */}
                            {password && (
                                <div className="space-y-1 pt-1">
                                    <div className="h-1 overflow-hidden rounded-full bg-slate-700">
                                        <div
                                            className={`h-full transition-all duration-300 ${strength.color}`}
                                            style={{ width: strength.pct }}
                                        />
                                    </div>
                                    <p className="text-xs text-slate-500">
                                        Strength:{' '}
                                        <span className="font-medium text-slate-300">{strength.label}</span>
                                    </p>
                                </div>
                            )}
                        </div>

                        {/* Confirm Password */}
                        <div className="space-y-1.5">
                            <label htmlFor="confirmPassword" className="block text-sm font-medium text-slate-300">
                                Confirm Password
                            </label>
                            <div className="relative">
                                <input
                                    id="confirmPassword"
                                    type={showConfirm ? 'text' : 'password'}
                                    autoComplete="new-password"
                                    required
                                    disabled={isLoading}
                                    value={confirmPassword}
                                    onChange={(e) => setConfirmPassword(e.target.value)}
                                    placeholder="••••••••"
                                    className={`w-full rounded-lg border bg-slate-800/60 px-4 py-2.5 pr-11 text-white placeholder-slate-500 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50 ${passwordMismatch ? 'border-red-500' : 'border-slate-700'
                                        }`}
                                />
                                <button
                                    type="button"
                                    aria-label={showConfirm ? 'Hide password' : 'Show password'}
                                    onClick={() => setShowConfirm((v) => !v)}
                                    className="absolute inset-y-0 right-0 flex items-center px-3 text-slate-400 transition-colors hover:text-slate-200"
                                >
                                    {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                                </button>
                            </div>
                            {passwordMismatch && (
                                <p className="text-xs text-red-400">Passwords do not match.</p>
                            )}
                        </div>

                        {/* Submit */}
                        <button
                            id="btn-register"
                            type="submit"
                            disabled={isLoading || !email || !password}
                            className="mt-2 w-full rounded-lg bg-gradient-to-r from-blue-600 to-violet-600 px-4 py-2.5 font-medium text-white shadow-lg shadow-blue-500/25 transition-all hover:from-blue-500 hover:to-violet-500 disabled:cursor-not-allowed disabled:opacity-50 flex items-center justify-center gap-2"
                        >
                            {isLoading ? (
                                <>
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    Creating account…
                                </>
                            ) : (
                                'Create Account'
                            )}
                        </button>
                    </form>

                    <div className="mt-6 text-center">
                        <p className="text-sm text-slate-400">
                            Already have an account?{' '}
                            <Link
                                href="/login"
                                className="font-medium text-blue-400 transition-colors hover:text-blue-300"
                            >
                                Sign in →
                            </Link>
                        </p>
                    </div>
                </div>

                <p className="mt-6 text-center text-xs text-slate-600">
                    By creating an account you agree to our terms of service.
                </p>
            </div>
        </main>
    );
}
