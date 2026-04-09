'use client';

import { memo } from 'react';
import { Handle, Position, type NodeProps } from 'reactflow';
import type { ERDTable } from '@/types/project';

// ── Types ─────────────────────────────────────────────────────────────────────

/** Data shape passed to each React Flow TableNode */
export interface TableNodeData {
    table: ERDTable;
    /** Set of FK column names for this table (pre-computed for perf) */
    fkColumns: Set<string>;
    /** Highest risk level from AI suggestions for this table, or null = no issues */
    riskLevel: 'HIGH' | 'MEDIUM' | 'LOW' | null;
    /** Number of AI issues detected on this table */
    issueCount: number;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const COL_ICON = { pk: '🔑', fk: '🔗', unique: '◈', normal: '○' };

function columnIcon(isPk: boolean, isFk: boolean, isUnique: boolean): string {
    if (isPk) return COL_ICON.pk;
    if (isFk) return COL_ICON.fk;
    if (isUnique) return COL_ICON.unique;
    return COL_ICON.normal;
}

function columnRowClass(isPk: boolean, isFk: boolean): string {
    if (isPk) return 'bg-amber-500/10 border-amber-500/20 text-amber-200';
    if (isFk) return 'border-blue-500/10 text-slate-300 hover:bg-blue-500/5';
    return 'border-slate-700/30 text-slate-400 hover:bg-slate-800/40';
}

/** Border / header / badge colours keyed by risk level */
const RISK_BORDER: Record<string, string> = {
    HIGH: 'border-red-500/70',
    MEDIUM: 'border-amber-400/60',
    LOW: 'border-green-500/40',
};
const RISK_HEADER: Record<string, string> = {
    HIGH: 'bg-red-900/40 border-b border-red-500/30',
    MEDIUM: 'bg-amber-900/30 border-b border-amber-500/30',
    LOW: 'bg-green-900/20 border-b border-slate-700',
};
const RISK_BADGE: Record<string, string> = {
    HIGH: 'bg-red-500/20 text-red-300 border-red-500/30',
    MEDIUM: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
    LOW: 'bg-green-500/10 text-green-400 border-green-500/20',
};
const RISK_LABEL: Record<string, string> = {
    HIGH: '⚠ HIGH',
    MEDIUM: '⚡ MED',
    LOW: '✓ LOW',
};

// ── Component ─────────────────────────────────────────────────────────────────

const TableNode = memo(({ data, selected }: NodeProps<TableNodeData>) => {
    const { table, riskLevel, issueCount } = data;

    const borderClass = selected
        ? 'border-blue-500 shadow-blue-500/20'
        : riskLevel
            ? RISK_BORDER[riskLevel]
            : 'border-slate-700';

    const headerClass = riskLevel
        ? RISK_HEADER[riskLevel]
        : 'bg-slate-800 border-b border-slate-700';

    return (
        <div
            className={`
                min-w-[220px] max-w-[280px] rounded-xl border
                shadow-lg shadow-black/40 transition-all duration-150
                ${borderClass} bg-slate-900
            `}
        >
            {/* Incoming FK edge handle (left) */}
            <Handle
                type="target"
                position={Position.Left}
                className="!w-2 !h-2 !bg-slate-500 !border-slate-600"
            />

            {/* Table header */}
            <div className={`flex items-center gap-2 rounded-t-xl px-3 py-2 ${headerClass}`}>
                <span className="text-base">🗂️</span>
                <span className="font-mono text-sm font-bold text-white truncate flex-1">
                    {table.name}
                </span>

                {/* AI risk badge */}
                {riskLevel && (
                    <span
                        title={`${issueCount} AI issue${issueCount !== 1 ? 's' : ''} detected`}
                        className={`text-[9px] font-bold rounded-full px-1.5 py-0.5 border ${RISK_BADGE[riskLevel]}`}
                    >
                        {RISK_LABEL[riskLevel]}
                    </span>
                )}

                {table.foreign_keys.length > 0 && (
                    <span className="text-[10px] text-blue-400 bg-blue-500/10 rounded-full px-1.5 py-0.5 border border-blue-500/20">
                        {table.foreign_keys.length} FK
                    </span>
                )}
            </div>

            {/* Column rows */}
            <div className="divide-y divide-slate-800/60 rounded-b-xl overflow-hidden">
                {table.columns.map((col) => (
                    <div
                        key={col.name}
                        className={`
                            flex items-center gap-2 px-3 py-[5px] border-b last:border-b-0 text-[11px] transition-colors
                            ${columnRowClass(col.is_primary_key, col.is_foreign_key)}
                        `}
                    >
                        <span className="text-[11px] flex-shrink-0 w-4 text-center">
                            {columnIcon(col.is_primary_key, col.is_foreign_key, col.is_unique)}
                        </span>
                        <span className={`font-mono flex-1 truncate ${col.is_primary_key ? 'font-bold' : ''}`}>
                            {col.name}
                        </span>
                        <span className="ml-auto text-[10px] text-slate-500 font-mono truncate max-w-[80px]">
                            {col.type}
                        </span>
                        {col.is_nullable && !col.is_primary_key && (
                            <span className="text-[9px] text-slate-600" title="Nullable">?</span>
                        )}
                    </div>
                ))}

                {table.columns.length === 0 && (
                    <div className="px-3 py-2 text-[11px] text-slate-600 italic">
                        No columns found
                    </div>
                )}
            </div>

            {/* Outgoing FK edge handle (right) */}
            <Handle
                type="source"
                position={Position.Right}
                className="!w-2 !h-2 !bg-blue-500 !border-blue-600"
            />
        </div>
    );
});

TableNode.displayName = 'TableNode';
export default TableNode;
