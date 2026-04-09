'use client';

import { useEffect, useState } from 'react';
import { useParams, useSearchParams, useRouter } from 'next/navigation';
import { AlertCircle, ArrowLeft, GitBranch, Table2, Link2, ZapOff, ShieldAlert } from 'lucide-react';
import { getJobSchema, getJobSuggestions } from '@/lib/api';
import type { ERDSchemaResponse } from '@/types/project';
import type { AISuggestion } from '@/lib/api';

// Lazy-import ERDVisualizer only on client (React Flow uses browser APIs)
import dynamic from 'next/dynamic';
import type { TableRiskMap } from '@/components/erd/ERDVisualizer';

const ERDVisualizer = dynamic(
    () => import('@/components/erd/ERDVisualizer'),
    {
        ssr: false,
        loading: () => (
            <div className="flex items-center justify-center h-full text-slate-500 gap-3">
                <div className="w-5 h-5 border-2 border-slate-600 border-t-blue-500 rounded-full animate-spin" />
                <span className="text-sm">Rendering diagram…</span>
            </div>
        ),
    }
);

// Lazy import buildRiskMap separately (same module, but avoids SSR issues with Map)
async function loadBuildRiskMap() {
    const mod = await import('@/components/erd/ERDVisualizer');
    return mod.buildRiskMap;
}

// ── ERD Page ─────────────────────────────────────────────────────────────────

export default function ERDPage() {
    const params = useParams<{ projectId: string }>();
    const searchParams = useSearchParams();
    const router = useRouter();

    const jobId = searchParams.get('jobId');

    const [schema, setSchema] = useState<ERDSchemaResponse | null>(null);
    const [riskMap, setRiskMap] = useState<TableRiskMap>(new Map());
    const [highRiskCount, setHighRiskCount] = useState(0);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!jobId) {
            setError('No job ID provided. Please go back and select a job.');
            setLoading(false);
            return;
        }

        (async () => {
            try {
                setLoading(true);

                // Fetch schema + suggestions in parallel
                const [schemaData, suggestionsData] = await Promise.allSettled([
                    getJobSchema(jobId),
                    getJobSuggestions(jobId),
                ]);

                if (schemaData.status === 'fulfilled') {
                    setSchema(schemaData.value);
                } else {
                    throw new Error('Failed to load schema.');
                }

                // Build risk map from AI suggestions (best-effort — don't block ERD)
                if (suggestionsData.status === 'fulfilled') {
                    const suggestions: AISuggestion[] = suggestionsData.value.suggestions;
                    const buildFn = await loadBuildRiskMap();
                    const map = buildFn(suggestions);
                    setRiskMap(map);
                    setHighRiskCount(
                        [...map.values()].filter((v) => v.riskLevel === 'HIGH').length
                    );
                }
            } catch (err: unknown) {
                const msg =
                    err instanceof Error
                        ? err.message
                        : 'Failed to load schema. The job may still be processing.';
                setError(msg);
            } finally {
                setLoading(false);
            }
        })();
    }, [jobId]);

    // ── Loading ───────────────────────────────────────────────────────────────
    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center min-h-screen bg-slate-950 gap-4">
                <div className="w-10 h-10 border-[3px] border-slate-700 border-t-blue-500 rounded-full animate-spin" />
                <p className="text-slate-400 text-sm">Parsing schema & loading AI risk data…</p>
            </div>
        );
    }

    // ── Error ─────────────────────────────────────────────────────────────────
    if (error || !schema) {
        return (
            <div className="flex flex-col items-center justify-center min-h-screen bg-slate-950 gap-4 px-6">
                <AlertCircle className="w-12 h-12 text-red-400 opacity-80" />
                <h2 className="text-lg font-semibold text-white">Failed to load ERD</h2>
                <p className="text-slate-400 text-sm text-center max-w-md">{error}</p>
                <button
                    onClick={() => router.back()}
                    className="mt-2 flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm transition-colors border border-slate-700"
                >
                    <ArrowLeft className="w-4 h-4" />
                    Go Back
                </button>
            </div>
        );
    }

    // ── Empty schema ──────────────────────────────────────────────────────────
    if (schema.tables.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center min-h-screen bg-slate-950 gap-4">
                <ZapOff className="w-12 h-12 text-slate-600" />
                <h2 className="text-lg font-semibold text-white">No tables found</h2>
                <p className="text-slate-400 text-sm">
                    SQLGlot couldn't extract any tables from the uploaded file.
                </p>
                <button
                    onClick={() => router.back()}
                    className="flex items-center gap-2 px-4 py-2 bg-slate-800 border border-slate-700 hover:bg-slate-700 text-slate-300 rounded-lg text-sm"
                >
                    <ArrowLeft className="w-4 h-4" />
                    Go Back
                </button>
            </div>
        );
    }

    // ── Main view ─────────────────────────────────────────────────────────────
    return (
        <div className="flex flex-col h-screen bg-slate-950 overflow-hidden">
            {/* ── Top bar ──────────────────────────────────────────────────── */}
            <header className="flex items-center justify-between px-5 py-3 bg-slate-900 border-b border-slate-800 flex-shrink-0 z-20">
                {/* Left: back + title */}
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => router.back()}
                        className="flex items-center gap-1.5 text-slate-400 hover:text-white transition-colors text-sm"
                    >
                        <ArrowLeft className="w-4 h-4" />
                        Back
                    </button>
                    <div className="w-px h-4 bg-slate-700" />
                    <GitBranch className="w-4 h-4 text-blue-400" />
                    <h1 className="font-semibold text-white text-sm">ERD Visualizer</h1>
                </div>

                {/* Center: stats */}
                <div className="flex items-center gap-3 text-xs">
                    <StatPill icon={<Table2 className="w-3 h-3" />} label="Tables" value={schema.table_count} />
                    <StatPill icon={<Link2 className="w-3 h-3" />} label="Relationships" value={schema.relationship_count} />
                    {schema.errors.length > 0 && (
                        <StatPill
                            icon={<AlertCircle className="w-3 h-3 text-amber-400" />}
                            label="Parse Warnings"
                            value={schema.errors.length}
                            warn
                        />
                    )}
                    {highRiskCount > 0 && (
                        <StatPill
                            icon={<ShieldAlert className="w-3 h-3 text-red-400" />}
                            label="High Risk"
                            value={highRiskCount}
                            danger
                        />
                    )}
                </div>

                {/* Right: job reference */}
                <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono text-slate-600 hidden lg:block">
                        job: {jobId?.slice(0, 8)}…
                    </span>
                </div>
            </header>

            {/* ── Parse warnings banner ─────────────────────────────────── */}
            {schema.errors.length > 0 && (
                <div className="px-5 py-2 bg-amber-500/10 border-b border-amber-500/20 text-amber-300 text-xs flex items-center gap-2">
                    <AlertCircle className="w-3.5 h-3.5 flex-shrink-0" />
                    <span>
                        {schema.errors.length} parsing warning(s) — some tables may be incomplete.{' '}
                        <span className="text-amber-500 hover:underline cursor-pointer"
                            onClick={() => alert(schema.errors.join('\n'))}>
                            View details
                        </span>
                    </span>
                </div>
            )}

            {/* ── Missing FK warning banner ──────────────────────────────── */}
            {schema.has_missing_references && (
                <div className="px-5 py-2 bg-orange-600/10 border-b border-orange-500/20 text-orange-300 text-xs flex items-center gap-2">
                    <AlertCircle className="w-3.5 h-3.5 flex-shrink-0 text-orange-400" />
                    <span>
                        <strong className="text-orange-300">Partial upload:</strong>{' '}
                        {schema.missing_fk_warnings.length} FK reference{schema.missing_fk_warnings.length !== 1 ? 's' : ''} point to tables not found in this file.{' '}
                        <span className="text-orange-400 hover:underline cursor-pointer"
                            onClick={() => alert(schema.missing_fk_warnings.join('\n'))}>
                            View details
                        </span>
                    </span>
                </div>
            )}

            {/* ── React Flow canvas ──────────────────────────────────────── */}
            <main className="flex-1 relative overflow-hidden">
                <ERDVisualizer schema={schema} riskMap={riskMap} />
            </main>
        </div>
    );
}

// ── Helper: small stat pill ───────────────────────────────────────────────────

function StatPill({
    icon,
    label,
    value,
    warn = false,
    danger = false,
}: {
    icon: React.ReactNode;
    label: string;
    value: number;
    warn?: boolean;
    danger?: boolean;
}) {
    const colorClass = danger
        ? 'bg-red-500/10 border-red-500/20 text-red-400'
        : warn
            ? 'bg-amber-500/10 border-amber-500/20 text-amber-400'
            : 'bg-slate-800 border-slate-700 text-slate-300';

    return (
        <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border ${colorClass}`}>
            {icon}
            <span className="font-semibold">{value}</span>
            <span className="text-slate-500">{label}</span>
        </div>
    );
}
