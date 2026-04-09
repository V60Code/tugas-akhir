import React from 'react';
import ReactDiffViewer, { DiffMethod } from 'react-diff-viewer-continued';

interface SqlDiffViewerProps {
    oldValue: string;
    newValue: string;
    splitView?: boolean;
}

export const SqlDiffViewer: React.FC<SqlDiffViewerProps> = ({ oldValue, newValue, splitView = false }) => {
    return (
        <div className="rounded-xl overflow-hidden border border-slate-800 text-xs text-left">
            <ReactDiffViewer
                oldValue={oldValue}
                newValue={newValue}
                splitView={splitView}
                useDarkTheme={true}
                compareMethod={DiffMethod.WORDS}
                hideLineNumbers={false}
                showDiffOnly={false}
                styles={{
                    variables: {
                        dark: {
                            diffViewerBackground: '#020617', // slate-950
                            diffViewerColor: '#cbd5e1', // slate-300
                            addedBackground: '#064e3b', // emerald-900 (stronger)
                            addedColor: '#34d399', // emerald-400
                            removedBackground: '#7f1d1d', // red-900 (stronger)
                            removedColor: '#f87171', // red-400
                            wordAddedBackground: '#047857', // emerald-700
                            wordRemovedBackground: '#991b1b', // red-800
                            addedGutterBackground: '#064e3b',
                            removedGutterBackground: '#7f1d1d',
                            gutterBackground: '#0f172a', // slate-900
                            gutterColor: '#64748b', // slate-500
                            emptyLineBackground: '#0f172a',
                        }
                    },
                    line: {
                        padding: '4px 2px',
                    },
                    contentText: {
                        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
                        lineHeight: '1.5',
                    }
                }}
            />
        </div>
    );
};
