'use client';

import { useCallback, useEffect } from 'react';
import ReactFlow, {
    addEdge,
    Background,
    BackgroundVariant,
    Controls,
    MiniMap,
    useEdgesState,
    useNodesState,
    type Connection,
    type Edge,
    type Node,
    MarkerType,
} from 'reactflow';
import dagre from '@dagrejs/dagre';
import 'reactflow/dist/style.css';

import TableNode, { type TableNodeData } from './TableNode';
import type { ERDSchemaResponse, ERDTable } from '@/types/project';

// ── Types ─────────────────────────────────────────────────────────────────────

/**
 * Maps table name (lowercase) → { riskLevel, issueCount }.
 * Built from AI suggestions on the ERD page and passed down.
 * Using Record<string, ...> for es5 target compatibility.
 */
export interface TableRiskEntry {
    riskLevel: 'HIGH' | 'MEDIUM' | 'LOW';
    issueCount: number;
}
export type TableRiskMap = Map<string, TableRiskEntry>;

// ── Constants ─────────────────────────────────────────────────────────────────

const NODE_WIDTH = 260;
const NODE_HEIGHT_BASE = 60;
const ROW_HEIGHT = 25;

/** Risk level priority for picking the "highest" from multiple suggestions */
const RISK_PRIORITY: Record<'HIGH' | 'MEDIUM' | 'LOW', number> = {
    HIGH: 3, MEDIUM: 2, LOW: 1,
};

// Register custom node types once (outside component to avoid re-creation)
const NODE_TYPES = { tableNode: TableNode };

// ── Dagre Auto-Layout ─────────────────────────────────────────────────────────

function applyDagreLayout(nodes: Node[], edges: Edge[]): { nodes: Node[]; edges: Edge[] } {
    const g = new dagre.graphlib.Graph();
    g.setDefaultEdgeLabel(() => ({}));
    g.setGraph({ rankdir: 'LR', nodesep: 60, ranksep: 100, edgesep: 20 });

    nodes.forEach((node) => {
        const columnCount = (node.data as TableNodeData).table.columns.length;
        const estimatedHeight = NODE_HEIGHT_BASE + columnCount * ROW_HEIGHT;
        g.setNode(node.id, { width: NODE_WIDTH, height: estimatedHeight });
    });
    edges.forEach((edge) => g.setEdge(edge.source, edge.target));

    dagre.layout(g);

    const layoutedNodes = nodes.map((node) => {
        const pos = g.node(node.id);
        return {
            ...node,
            position: {
                x: pos.x - NODE_WIDTH / 2,
                y: pos.y - (NODE_HEIGHT_BASE + (node.data as TableNodeData).table.columns.length * ROW_HEIGHT) / 2,
            },
        };
    });

    return { nodes: layoutedNodes, edges };
}

// ── Schema → React Flow Converter ─────────────────────────────────────────────

function schemaToGraph(
    schema: ERDSchemaResponse,
    riskMap: TableRiskMap,
): { nodes: Node<TableNodeData>[]; edges: Edge[] } {
    const tableMap = new Map<string, ERDTable>(schema.tables.map((t) => [t.name, t]));

    // Build nodes, injecting risk info from the AI suggestions map
    const nodes: Node<TableNodeData>[] = schema.tables.map((table) => {
        const fkColumns = new Set(table.foreign_keys.map((fk) => fk.column));
        const risk = riskMap.get(table.name.toLowerCase());

        return {
            id: table.name,
            type: 'tableNode',
            position: { x: 0, y: 0 }, // overridden by dagre
            data: {
                table,
                fkColumns,
                riskLevel: risk?.riskLevel ?? null,
                issueCount: risk?.issueCount ?? 0,
            },
        };
    });

    // Build edges from FK relationships
    const edges: Edge[] = [];
    schema.tables.forEach((table) => {
        table.foreign_keys.forEach((fk, idx) => {
            if (!tableMap.has(fk.references_table)) return; // orphan FK — skip edge

            edges.push({
                id: `${table.name}-${fk.column}->${fk.references_table}-${idx}`,
                source: table.name,
                target: fk.references_table,
                type: 'smoothstep',
                animated: false,
                label: `${fk.column} → ${fk.references_column}`,
                labelStyle: { fill: '#64748b', fontSize: 10 },
                labelBgStyle: { fill: '#0f172a', fillOpacity: 0.8 },
                style: { stroke: '#3b82f6', strokeWidth: 1.5 },
                markerEnd: {
                    type: MarkerType.ArrowClosed,
                    color: '#3b82f6',
                    width: 14,
                    height: 14,
                },
            });
        });
    });

    return { nodes, edges };
}

// ── MiniMap node colour ────────────────────────────────────────────────────────

function miniMapNodeColor(node: Node<TableNodeData>): string {
    const risk = node.data.riskLevel;
    if (risk === 'HIGH') return '#ef4444';   // red-500
    if (risk === 'MEDIUM') return '#f59e0b';   // amber-500
    if (risk === 'LOW') return '#22c55e';   // green-500
    return '#334155'; // slate-700
}

// ── Main Component ────────────────────────────────────────────────────────────

interface ERDVisualizerProps {
    schema: ERDSchemaResponse;
    /** Optional pre-computed risk map; built from AI suggestions on the parent page. */
    riskMap?: TableRiskMap;
}

export default function ERDVisualizer({ schema, riskMap = new Map() }: ERDVisualizerProps) {
    const [nodes, setNodes, onNodesChange] = useNodesState<TableNodeData>([]);
    const [edges, setEdges, onEdgesChange] = useEdgesState([]);

    // Re-build graph whenever schema or riskMap changes.
    // useNodesState / useEdgesState only pick up the *initial* value; we must
    // call setNodes / setEdges explicitly to react to async prop updates
    // (e.g. riskMap arrives after the AI suggestions fetch completes).
    useEffect(() => {
        const { nodes: n, edges: e } = schemaToGraph(schema, riskMap);
        const { nodes: laid, edges: laidEdges } = applyDagreLayout(n, e);
        setNodes(laid);
        setEdges(laidEdges);
    }, [schema, riskMap, setNodes, setEdges]);

    const onConnect = useCallback(
        (params: Connection) => setEdges((eds) => addEdge(params, eds)),
        [setEdges],
    );

    const hasRiskData = riskMap.size > 0;

    return (
        <div className="w-full h-full relative">
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                nodeTypes={NODE_TYPES}
                fitView
                fitViewOptions={{ padding: 0.2 }}
                minZoom={0.2}
                maxZoom={2}
                proOptions={{ hideAttribution: true }}
                className="bg-slate-950"
            >
                <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="#1e293b" />
                <Controls className="!bg-slate-800 !border-slate-700 !shadow-lg" showInteractive={false} />
                <MiniMap
                    nodeColor={miniMapNodeColor}
                    maskColor="rgba(15, 23, 42, 0.75)"
                    className="!bg-slate-900 !border-slate-700"
                />
            </ReactFlow>

            {/* Legend overlay (top-right) */}
            <div className="absolute top-3 right-3 bg-slate-900/90 backdrop-blur border border-slate-700 rounded-lg px-3 py-2 text-[11px] text-slate-400 space-y-1 z-10 pointer-events-none">
                <p className="font-semibold text-slate-300 mb-1">Legend</p>
                <p><span className="mr-1">🔑</span>Primary Key</p>
                <p><span className="mr-1">🔗</span>Foreign Key</p>
                <p><span className="mr-1">◈</span>Unique</p>
                <p><span className="mr-1">○</span>Column</p>
                <p className="mt-1 border-t border-slate-700 pt-1">
                    <span className="inline-block w-4 h-[1.5px] bg-blue-500 mr-1 align-middle" />
                    Relationship
                </p>

                {/* AI risk legend — only shown when suggestions are loaded */}
                {hasRiskData && (
                    <>
                        <p className="mt-1 border-t border-slate-700 pt-1 font-semibold text-slate-300">AI Risk</p>
                        <p><span className="inline-block w-2 h-2 rounded-full bg-red-500 mr-1.5 align-middle" />HIGH</p>
                        <p><span className="inline-block w-2 h-2 rounded-full bg-amber-400 mr-1.5 align-middle" />MEDIUM</p>
                        <p><span className="inline-block w-2 h-2 rounded-full bg-green-500 mr-1.5 align-middle" />LOW</p>
                    </>
                )}
            </div>
        </div>
    );
}

// ── Re-export helper so callers can build the map without importing internals ─

export function buildRiskMap(suggestions: Array<{ table_name: string; risk_level: 'HIGH' | 'MEDIUM' | 'LOW' }>): TableRiskMap {
    const map: TableRiskMap = new Map();

    for (const s of suggestions) {
        const key = s.table_name.toLowerCase();
        const existing = map.get(key);
        if (!existing || RISK_PRIORITY[s.risk_level] > RISK_PRIORITY[existing.riskLevel]) {
            map.set(key, { riskLevel: s.risk_level, issueCount: (existing?.issueCount ?? 0) + 1 });
        } else {
            // Same or lower risk — just increment issue count
            map.set(key, { ...existing, issueCount: existing.issueCount + 1 });
        }
    }

    return map;
}
