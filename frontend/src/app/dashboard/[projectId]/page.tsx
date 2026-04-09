'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/useAuthStore';
import { useProjectStore } from '@/store/useProjectStore';
import { useJobStore } from '@/store/useJobStore';
import type { AppContext } from '@/types/project';
import {
    ArrowLeft, Upload, Loader2, Database, CheckCircle2,
    AlertCircle, Download, Zap, ChevronRight, Clock,
    FileText, LogOut, GitBranch, AlertTriangle,
} from 'lucide-react';
import { SqlDiffViewer } from '@/components/ui/SqlDiffViewer';

const STATUS_STYLES: Record<string, string> = {
    COMPLETED: 'bg-green-500/10 text-green-400 border-green-500/20',
    FINALIZED: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    PROCESSING: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    QUEUED: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
    FAILED: 'bg-red-500/10 text-red-400 border-red-500/20',
};

const RISK_STYLES: Record<string, string> = {
    LOW: 'bg-green-500/10 text-green-400',
    MEDIUM: 'bg-yellow-500/10 text-yellow-400',
    HIGH: 'bg-red-500/10 text-red-400',
};

export default function ProjectDetailPage({ params }: { params: { projectId: string } }) {
    const { projectId } = params;
    const router = useRouter();

    const { user, logout, isHydrating } = useAuthStore();
    const {
        fetchProject,
        fetchProjectJobs, // Job history is owned by the store, not fetched in the page
        currentProject,
        jobHistory,
        isFetchingCurrent,
        isLoadingHistory,
    } = useProjectStore();
    const {
        status, results, error, progressMessage,
        downloadUrl, downloadError,
        startAnalysis, cancelPolling, resetJob, triggerFinalize, fetchDownloadUrl,
        loadJobFromHistory,
        jobId: currentJobId,
    } = useJobStore();

    const [appContext, setAppContext] = useState<AppContext>('READ_HEAVY');
    const [dbDialect, setDbDialect] = useState<'auto' | 'postgres' | 'mysql'>('auto');
    const [file, setFile] = useState<File | null>(null);

    // fileInputRef is used to imperatively reset the native file input after each submit.
    const fileInputRef = useRef<HTMLInputElement>(null);

    const handleLogout = () => { logout(); router.push('/login'); };

    // Stable callbacks to avoid stale closures in useEffect dependency array
    const stableFetchProject = useCallback(fetchProject, []);
    const stableFetchProjectJobs = useCallback(fetchProjectJobs, []);
    const stableResetJob = useCallback(resetJob, []);
    const stableCancelPolling = useCallback(cancelPolling, []);

    // On mount: fetch project + job history, reset stale job state from previous project
    // On unmount: cancel any running polling to prevent memory leaks
    useEffect(() => {
        stableResetJob(); // Clear previous project's results before loading new project

        // Fetch project detail — redirect if unauthorized or not found
        stableFetchProject(projectId).catch(() => {
            router.replace('/dashboard');
        });

        // Load job history through the store so it's available to all child components
        stableFetchProjectJobs(projectId);

        return () => {
            stableCancelPolling(); // Cancel polling on unmount to prevent memory leaks
        };
    }, [projectId, stableFetchProject, stableFetchProjectJobs, stableResetJob, stableCancelPolling, router]);

    // Refresh job history each time an analysis completes or is finalized
    useEffect(() => {
        if (status === 'COMPLETED' || status === 'FINALIZED') {
            fetchProjectJobs(projectId);
        }
    }, [status, projectId, fetchProjectJobs]);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files?.[0]) setFile(e.target.files[0]);
    };

    const handleAnalyze = () => {
        if (!file) return;
        startAnalysis(file, projectId, appContext, dbDialect === 'auto' ? undefined : dbDialect);
        // Reset the file input after submit so user gets visual confirmation the file cleared.
        setFile(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    const handleDownload = async () => {
        await fetchDownloadUrl();
    };

    // Auto-open download URL in new tab once it's ready
    useEffect(() => {
        if (downloadUrl) window.open(downloadUrl, '_blank');
    }, [downloadUrl]);

    // Local state for tracking accepted suggestions
    const [acceptedSuggestions, setAcceptedSuggestions] = useState<Set<string>>(new Set());

    useEffect(() => {
        if (results?.suggestions) {
            setAcceptedSuggestions(new Set(results.suggestions.map(s => s.id)));
        }
    }, [results?.suggestions]);

    const toggleSuggestion = (id: string) => {
        setAcceptedSuggestions(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    const computedNewSql = results?.suggestions
        ? results.original_sql + '\n\n/* --- AI OPTIMIZATIONS --- */\n\n' + results.suggestions
            .filter(s => acceptedSuggestions.has(s.id))
            .map(s => `-- Issue: ${s.issue}\n${s.sql_patch}`)
            .join('\n\n')
        : '';

    const isAnalyzing = status === 'UPLOADING' || status === 'PROCESSING' || status === 'FINALIZING';

    const formatDate = (d: string) =>
        new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

    if (isHydrating || isFetchingCurrent) {
        return (
            <div className="min-h-screen bg-slate-950 flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-950">
            {/* Navbar */}
            <header className="sticky top-0 z-20 border-b border-slate-800 bg-slate-900/90 backdrop-blur-sm">
                <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
                    <div className="flex items-center gap-3">
                        <button
                            onClick={() => router.push('/dashboard')}
                            className="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-slate-600 hover:text-white"
                        >
                            <ArrowLeft className="h-4 w-4" /> My Projects
                        </button>
                        {currentProject && (
                            <>
                                <ChevronRight className="h-4 w-4 text-slate-600" />
                                <span className="font-semibold text-white truncate max-w-[200px]">
                                    {currentProject.name}
                                </span>
                            </>
                        )}
                    </div>
                    <div className="flex items-center gap-3">
                        {user && (
                            <span className="hidden sm:block text-sm text-slate-400">{user.email}</span>
                        )}
                        <button
                            aria-label="Sign out"
                            onClick={handleLogout}
                            className="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-slate-600 hover:text-white"
                        >
                            <LogOut className="h-4 w-4" />
                        </button>
                    </div>
                </div>
            </header>

            <main className="mx-auto max-w-6xl space-y-6 px-6 py-8">

                {/* ── Upload & Analysis Card ─────────────────────────────── */}
                <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
                    <div className="mb-5 flex items-center gap-3">
                        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/10 ring-1 ring-blue-500/20">
                            <Database className="h-5 w-5 text-blue-400" />
                        </div>
                        <div>
                            <h2 className="font-semibold text-white">Analyze SQL Schema</h2>
                            <p className="text-xs text-slate-400">
                                Upload a .sql file — INSERT/VALUES clauses are stripped before analysis
                            </p>
                        </div>
                    </div>

                    <div className="flex flex-wrap gap-3">
                        {/* App Context Selector with tooltip explanation */}
                        <div className="flex flex-col gap-1.5">
                            <label htmlFor="app-context" className="text-xs font-medium text-slate-400">
                                Workload Type
                                <span
                                    title="READ_HEAVY: optimizes for SELECT queries (adds indexes). WRITE_HEAVY: optimizes for INSERT/UPDATE (reduces index overhead)."
                                    className="ml-1.5 cursor-help text-slate-600 hover:text-slate-400"
                                >
                                    ⓘ
                                </span>
                            </label>
                            <select
                                id="app-context"
                                value={appContext}
                                onChange={(e) => setAppContext(e.target.value as AppContext)}
                                disabled={isAnalyzing}
                                className="rounded-lg border border-slate-700 bg-slate-800/80 px-4 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                            >
                                <option value="READ_HEAVY">READ_HEAVY — Optimize for SELECTs</option>
                                <option value="WRITE_HEAVY">WRITE_HEAVY — Optimize for INSERTs</option>
                            </select>
                        </div>

                        {/* SQL Dialect Selector */}
                        <div className="flex flex-col gap-1.5">
                            <label htmlFor="db-dialect" className="text-xs font-medium text-slate-400">
                                SQL Dialect
                                <span
                                    title="Select the dialect of your SQL file. Auto-detect works for most files."
                                    className="ml-1.5 cursor-help text-slate-600 hover:text-slate-400"
                                >
                                    ⓘ
                                </span>
                            </label>
                            <select
                                id="db-dialect"
                                value={dbDialect}
                                onChange={(e) => setDbDialect(e.target.value as 'auto' | 'postgres' | 'mysql')}
                                disabled={isAnalyzing}
                                className="rounded-lg border border-slate-700 bg-slate-800/80 px-4 py-2.5 text-sm text-white focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                            >
                                <option value="auto">Auto-Detect</option>
                                <option value="postgres">PostgreSQL</option>
                                <option value="mysql">MySQL</option>
                            </select>
                        </div>

                        {/* File Input */}
                        <div className="flex flex-col gap-1.5 flex-1 min-w-[200px]">
                            <label htmlFor="sql-file" className="text-xs font-medium text-slate-400">
                                SQL File (.sql)
                            </label>
                            <div className="flex gap-2">
                                <input
                                    id="sql-file"
                                    ref={fileInputRef}
                                    type="file"
                                    accept=".sql"
                                    onChange={handleFileChange}
                                    disabled={isAnalyzing}
                                    className="flex-1 rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-2 text-sm text-white file:mr-3 file:rounded file:border-0 file:bg-blue-500/20 file:px-3 file:py-1 file:text-xs file:font-medium file:text-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                                />
                                <button
                                    id="btn-analyze"
                                    onClick={handleAnalyze}
                                    disabled={!file || isAnalyzing}
                                    className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-blue-600 to-violet-600 px-5 py-2 text-sm font-medium text-white shadow-lg shadow-blue-500/25 transition-all hover:from-blue-500 hover:to-violet-500 disabled:cursor-not-allowed disabled:opacity-50"
                                >
                                    {isAnalyzing ? (
                                        <><Loader2 className="h-4 w-4 animate-spin" /> Analyzing…</>
                                    ) : (
                                        <><Upload className="h-4 w-4" /> Analyze</>
                                    )}
                                </button>
                            </div>
                        </div>
                    </div>

                    {/* Progress indicator */}
                    {isAnalyzing && progressMessage && (
                        <div className="mt-4 flex items-center gap-2 rounded-lg border border-blue-500/20 bg-blue-500/10 p-3 text-sm text-blue-300">
                            <Loader2 className="h-4 w-4 animate-spin flex-shrink-0" />
                            {progressMessage}
                        </div>
                    )}

                    {/* Analysis error */}
                    {status === 'FAILED' && error && (
                        <div className="mt-4 flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-sm text-red-400">
                            <AlertCircle className="h-4 w-4 flex-shrink-0" />
                            {error}
                        </div>
                    )}
                </section>

                {/* ── Analysis Results ───────────────────────────────────── */}
                {(status === 'COMPLETED' || status === 'FINALIZED') && results && (
                    <section className="space-y-4">
                        <div className="flex items-center justify-between flex-wrap gap-3">
                            <div className="flex items-center gap-2">
                                <CheckCircle2 className="h-5 w-5 text-green-400" />
                                <h2 className="text-lg font-semibold text-white">Analysis Complete</h2>
                            </div>
                            <div className="flex flex-wrap gap-2">
                                {/* Download error is shown here so it remains visible even when status=FINALIZED */}
                                {downloadError && (
                                    <div className="flex items-center gap-2 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-1.5 text-xs text-red-400">
                                        <AlertCircle className="h-3.5 w-3.5 flex-shrink-0" />
                                        {downloadError}
                                    </div>
                                )}
                                {status === 'COMPLETED' && (
                                    <button
                                        id="btn-finalize"
                                        onClick={() => triggerFinalize(Array.from(acceptedSuggestions))}
                                        className="flex items-center gap-2 rounded-lg border border-violet-500/30 bg-violet-500/10 px-4 py-2 text-sm font-medium text-violet-300 transition-all hover:bg-violet-500/20"
                                    >
                                        <Zap className="h-4 w-4" /> Finalize &amp; Apply Changes
                                    </button>
                                )}
                                {status === 'FINALIZED' && (
                                    <button
                                        id="btn-download"
                                        onClick={handleDownload}
                                        className="flex items-center gap-2 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white transition-all hover:bg-green-500"
                                    >
                                        <Download className="h-4 w-4" /> Download Optimized SQL
                                    </button>
                                )}
                                {/* View ERD button — available once job is COMPLETED or FINALIZED */}
                                {currentJobId && (
                                    <button
                                        id="btn-view-erd"
                                        onClick={() => router.push(`/dashboard/${projectId}/erd?jobId=${currentJobId}`)}
                                        className="flex items-center gap-2 rounded-lg border border-blue-500/30 bg-blue-500/10 px-4 py-2 text-sm font-medium text-blue-300 transition-all hover:bg-blue-500/20"
                                    >
                                        <GitBranch className="h-4 w-4" /> View ERD
                                    </button>
                                )}
                            </div>
                        </div>

                        {/* ── Missing FK Warning Banner ──────────────────────── */}
                        {results.has_missing_references && (
                            <details className="group rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
                                <summary className="flex cursor-pointer list-none items-start gap-3">
                                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
                                    <div className="flex-1">
                                        <p className="text-sm font-medium text-amber-300">
                                            Partial Upload Detected — {results.missing_fk_warnings.length} missing FK reference{results.missing_fk_warnings.length !== 1 ? 's' : ''}
                                        </p>
                                        <p className="mt-0.5 text-xs text-amber-500">
                                            Some tables referenced by FOREIGN KEY constraints are not in this file. AI analysis may be incomplete. Click to expand.
                                        </p>
                                    </div>
                                    <ChevronRight className="h-4 w-4 shrink-0 text-amber-600 transition-transform group-open:rotate-90" />
                                </summary>
                                <ul className="mt-3 space-y-1 pl-7">
                                    {results.missing_fk_warnings.map((w, i) => (
                                        <li key={i} className="font-mono text-xs text-amber-400">
                                            {w}
                                        </li>
                                    ))}
                                </ul>
                            </details>
                        )}

                        <div className="grid gap-6 lg:grid-cols-2">
                            {/* Suggestions */}
                            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
                                <h3 className="mb-4 flex items-center gap-2 font-semibold text-white">
                                    <FileText className="h-4 w-4 text-blue-400" />
                                    {results.suggestions.length} Optimization{results.suggestions.length !== 1 ? 's' : ''} Found
                                </h3>
                                {results.suggestions.length === 0 ? (
                                    <p className="text-sm text-slate-400">No issues found. Schema looks well optimized!</p>
                                ) : (
                                    <ul className="space-y-3">
                                        {results.suggestions.map((s) => (
                                            <li key={s.id} className={`rounded-xl border p-4 transition-colors ${acceptedSuggestions.has(s.id) ? 'border-blue-500/50 bg-slate-800/80' : 'border-slate-800 bg-slate-900/40 opacity-50'}`}>
                                                <div className="mb-2 flex items-start flex-row gap-3">
                                                    <input
                                                        type="checkbox"
                                                        title="Accept this suggestion"
                                                        checked={acceptedSuggestions.has(s.id)}
                                                        onChange={() => toggleSuggestion(s.id)}
                                                        disabled={status === 'FINALIZED'}
                                                        className="mt-1 h-4 w-4 shrink-0 rounded border-slate-600 bg-slate-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-slate-900 cursor-pointer"
                                                    />
                                                    <div className="flex-1">
                                                        <div className="mb-2 flex items-start justify-between gap-2">
                                                            <span className="text-sm font-medium text-white">{s.issue}</span>
                                                            <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${RISK_STYLES[s.risk_level] ?? ''}`}>
                                                                {s.risk_level}
                                                            </span>
                                                        </div>
                                                        <p className="mb-2 text-xs text-slate-400">{s.suggestion}</p>
                                                        <div className="flex items-center gap-2 text-xs text-slate-500">
                                                            <span className="font-mono text-slate-400">{s.table_name}</span>
                                                            <span>·</span>
                                                            <span>{Math.round(s.confidence * 100)}% confidence</span>
                                                        </div>
                                                    </div>
                                                </div>
                                            </li>
                                        ))}
                                    </ul>
                                )}
                            </div>

                            {/* SQL Preview */}
                            <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5 flex flex-col h-full overflow-hidden">
                                <h3 className="mb-4 font-semibold text-white">SQL Diff Preview</h3>
                                <div className="flex-1 overflow-auto rounded-xl bg-slate-950 border border-slate-800">
                                    {results.original_sql ? (
                                        <SqlDiffViewer
                                            oldValue={results.original_sql}
                                            newValue={computedNewSql === results.original_sql + '\n\n/* --- AI OPTIMIZATIONS --- */\n\n' ? results.original_sql : computedNewSql}
                                            splitView={false}
                                        />
                                    ) : (
                                        <div className="p-4 text-xs font-mono text-slate-500">
                                            Original SQL not available for diff rendering.
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    </section>
                )}

                {/* ── Job History ────────────────────────────────────────── */}
                <section className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6">
                    <h2 className="mb-4 flex items-center gap-2 font-semibold text-white">
                        <Clock className="h-4 w-4 text-slate-400" />
                        Job History
                    </h2>

                    {isLoadingHistory ? (
                        <div className="space-y-3">
                            {[...Array(3)].map((_, i) => (
                                <div key={i} className="h-12 animate-pulse rounded-lg bg-slate-800" />
                            ))}
                        </div>
                    ) : jobHistory.length === 0 ? (
                        <p className="text-sm text-slate-500">No analysis jobs yet. Upload a SQL file to get started.</p>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-slate-800 text-left text-xs text-slate-500">
                                        <th className="pb-3 font-medium">File</th>
                                        <th className="pb-3 font-medium">Status</th>
                                        <th className="pb-3 font-medium">Context</th>
                                        <th className="pb-3 font-medium">Date</th>
                                        <th className="pb-3 font-medium">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-800/50">
                                    {jobHistory.map((job) => (
                                        <tr key={job.id}>
                                            <td className="py-3 pr-4 font-mono text-xs text-slate-300">
                                                {job.original_filename}
                                            </td>
                                            <td className="py-3 pr-4">
                                                <span className={`inline-flex rounded-full border px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[job.status] ?? ''}`}>
                                                    {job.status}
                                                </span>
                                            </td>
                                            <td className="py-3 pr-4">
                                                <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs text-slate-400">
                                                    {job.app_context}
                                                </span>
                                            </td>
                                            <td className="py-3 text-xs text-slate-500">
                                                {formatDate(job.created_at)}
                                            </td>
                                            {/* View ERD action — available for all jobs with uploaded SQL */}
                                            <td className="py-3">
                                                <div className="flex items-center gap-2">
                                                    {/* View Results — only for completed/finalized jobs */}
                                                    {(job.status === 'COMPLETED' || job.status === 'FINALIZED') && (
                                                        <button
                                                            onClick={() => loadJobFromHistory(job.id, job.status)}
                                                            title="Restore analysis results"
                                                            className="flex items-center gap-1.5 rounded-lg border border-green-500/20 bg-green-500/5 px-2.5 py-1 text-xs text-green-400 hover:bg-green-500/15 transition-colors"
                                                        >
                                                            <CheckCircle2 className="h-3 w-3" />
                                                            Results
                                                        </button>
                                                    )}
                                                    {/* View ERD action */}
                                                    <button
                                                        onClick={() => router.push(`/dashboard/${projectId}/erd?jobId=${job.id}`)}
                                                        title="View ERD Diagram"
                                                        className="flex items-center gap-1.5 rounded-lg border border-blue-500/20 bg-blue-500/5 px-2.5 py-1 text-xs text-blue-400 hover:bg-blue-500/15 transition-colors"
                                                    >
                                                        <GitBranch className="h-3 w-3" />
                                                        ERD
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </section>
            </main>
        </div>
    );
}
