import Link from 'next/link';
import { Database, Zap, Shield, BarChart3 } from 'lucide-react';

const FEATURES = [
    { icon: Zap, title: 'AI-powered Analysis', desc: 'Google Gemini analyzes your schema and suggests optimizations.' },
    { icon: Shield, title: 'Privacy First', desc: 'INSERT/COPY/VALUES statements are stripped before any analysis.' },
    { icon: Database, title: 'Sandbox Testing', desc: 'Every SQL patch is validated in an isolated Docker container.' },
    { icon: BarChart3, title: 'Detailed Reports', desc: 'Risk levels, confidence scores, and ready-to-apply SQL patches.' },
];

export default function HomePage() {
    return (
        <main className="min-h-screen bg-slate-950 text-white relative overflow-hidden">

            {/* Background */}
            <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden">
                <div className="absolute -top-60 left-1/2 -translate-x-1/2 h-[600px] w-[600px] rounded-full bg-blue-600/10 blur-3xl" />
                <div className="absolute bottom-0 right-0 h-96 w-96 rounded-full bg-violet-600/10 blur-3xl" />
            </div>

            {/* Navbar */}
            <nav className="relative z-10 mx-auto flex max-w-6xl items-center justify-between px-6 py-5">
                <div className="flex items-center gap-2.5">
                    <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-violet-600">
                        <Database className="h-5 w-5 text-white" />
                    </div>
                    <span className="font-bold text-white text-lg">SQL Optimizer</span>
                </div>
                <div className="flex items-center gap-3">
                    <Link
                        href="/login"
                        className="rounded-lg px-4 py-2 text-sm font-medium text-slate-300 transition-colors hover:text-white"
                    >
                        Sign In
                    </Link>
                    <Link
                        href="/register"
                        className="rounded-lg bg-gradient-to-r from-blue-600 to-violet-600 px-4 py-2 text-sm font-medium text-white shadow-lg shadow-blue-500/25 transition-all hover:from-blue-500 hover:to-violet-500"
                    >
                        Get Started →
                    </Link>
                </div>
            </nav>

            {/* Hero */}
            <section className="relative z-10 mx-auto max-w-4xl px-6 py-24 text-center">
                <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 px-4 py-1.5 text-xs font-medium text-blue-300">
                    <span className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />
                    Powered by Google Gemini AI
                </div>
                <h1 className="mt-4 bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-5xl font-bold leading-tight tracking-tight text-transparent md:text-6xl">
                    Optimize your SQL<br />schema with AI
                </h1>
                <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-400">
                    Upload your SQL schema, get AI-powered optimization suggestions, and download battle-tested SQL patches — all in minutes, with zero data exposure.
                </p>
                <div className="mt-10 flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
                    <Link
                        href="/register"
                        className="rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 px-8 py-3.5 font-semibold text-white shadow-lg shadow-blue-500/30 transition-all hover:from-blue-500 hover:to-violet-500 hover:shadow-blue-500/50"
                    >
                        Start for Free →
                    </Link>
                    <Link
                        href="/login"
                        className="rounded-xl border border-slate-700 bg-slate-800/50 px-8 py-3.5 font-semibold text-slate-200 transition-all hover:border-slate-600 hover:bg-slate-800"
                    >
                        Sign In
                    </Link>
                </div>
            </section>

            {/* Features */}
            <section className="relative z-10 mx-auto max-w-6xl px-6 pb-24">
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                    {FEATURES.map(({ icon: Icon, title, desc }) => (
                        <div
                            key={title}
                            className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 backdrop-blur-sm transition-all hover:border-slate-700 hover:bg-slate-900/80"
                        >
                            <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500/20 to-violet-600/20 ring-1 ring-white/5">
                                <Icon className="h-5 w-5 text-blue-400" />
                            </div>
                            <h3 className="mb-1 font-semibold text-white">{title}</h3>
                            <p className="text-sm text-slate-400">{desc}</p>
                        </div>
                    ))}
                </div>
            </section>
        </main>
    );
}
