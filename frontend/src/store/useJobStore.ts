import { create } from 'zustand';
import {
    uploadSqlFile,
    getJobStatus,
    getJobSuggestions,
    finalizeJob,
    getDownloadUrl,
    AISuggestion,
    extractErrorMessage,
} from '@/lib/api';
import type { AppContext } from '@/types/project';

export type JobStatus = 'IDLE' | 'UPLOADING' | 'PROCESSING' | 'COMPLETED' | 'FINALIZED' | 'FINALIZING' | 'FAILED';

export interface JobResults {
    original_sql: string;
    suggestions: AISuggestion[];
    /** Concatenated SQL patches shown in the preview panel */
    optimized_sql_preview: string;
    /** Missing FK reference warnings from partial SQL uploads */
    missing_fk_warnings: string[];
    has_missing_references: boolean;
}

/**
 * _pollingTimerId is intentionally kept at module level rather than inside
 * Zustand state. It is an implementation detail (not observable UI state)
 * and including it in the state graph would pollute devtools snapshots and
 * risk accidental mutations from components that spread/read the full state.
 */
let _pollingTimerId: ReturnType<typeof setTimeout> | null = null;

interface JobState {
    jobId: string | null;
    status: JobStatus;
    results: JobResults | null;
    downloadUrl: string | null;
    downloadError: string | null; // Separate from `error` so download failures remain visible even when status=FINALIZED
    error: string | null;
    progressMessage: string;

    // Actions
    startAnalysis: (file: File, projectId: string, appContext: AppContext, dbDialect?: 'mysql' | 'postgres' | 'auto') => Promise<void>;
    pollStatus: () => Promise<void>;
    cancelPolling: () => void;
    triggerFinalize: (acceptedIds: string[]) => Promise<void>;
    fetchDownloadUrl: () => Promise<void>;
    resetJob: () => void;
    /**
     * Load a past job's results from the API without re-uploading.
     * Called when user clicks a history row to restore its analysis view.
     */
    loadJobFromHistory: (jobId: string, status: string) => Promise<void>;
}

export const useJobStore = create<JobState>((set, get) => ({
    jobId: null,
    status: 'IDLE',
    results: null,
    downloadUrl: null,
    downloadError: null,
    error: null,
    progressMessage: '',

    startAnalysis: async (file: File, projectId: string, appContext: AppContext, dbDialect?: 'mysql' | 'postgres' | 'auto') => {
        get().cancelPolling(); // Cancel any previous polling before starting new job
        set({
            status: 'UPLOADING',
            error: null,
            downloadError: null,
            progressMessage: 'Uploading SQL file…',
            results: null,
            downloadUrl: null,
        });

        try {
            const response = await uploadSqlFile(file, projectId, appContext, dbDialect);
            set({
                jobId: response.job_id,
                status: 'PROCESSING',
                progressMessage: 'File uploaded. AI analysis in progress…',
            });
            await get().pollStatus();
        } catch (error: unknown) {
            // Use extractErrorMessage to safely handle Pydantic V2 validation errors.
            // Without this, `detail` can be an array of objects [{type, loc, msg, input}]
            // which would be stored in state and crash React when rendered as a child.
            const msg = extractErrorMessage(error, 'Failed to upload file.');
            set({ status: 'FAILED', error: msg, progressMessage: '' });
        }
    },

    pollStatus: async () => {
        const { jobId, status } = get();
        if (
            !jobId ||
            status === 'FAILED' ||
            status === 'COMPLETED' ||
            status === 'FINALIZED'
        ) return;

        try {
            const jobStatus = await getJobStatus(jobId);

            if (jobStatus.status === 'COMPLETED') {
                set({ progressMessage: 'Analysis complete. Fetching suggestions…' });
                const { original_sql, suggestions, missing_fk_warnings, has_missing_references } = await getJobSuggestions(jobId);
                set({
                    status: 'COMPLETED',
                    results: {
                        original_sql,
                        suggestions: suggestions,
                        optimized_sql_preview: suggestions
                            .map((s) => `-- [${s.risk_level}] ${s.issue}\n${s.sql_patch}`)
                            .join('\n\n'),
                        missing_fk_warnings: missing_fk_warnings ?? [],
                        has_missing_references: has_missing_references ?? false,
                    },
                    progressMessage: '',
                });
            } else if (jobStatus.status === 'FINALIZED') {
                set({ status: 'FINALIZED', progressMessage: '' });
            } else if (jobStatus.status === 'FAILED') {
                set({
                    status: 'FAILED',
                    error: jobStatus.error ?? 'Job processing failed.',
                    progressMessage: '',
                });
            } else {
                // Still QUEUED or PROCESSING — schedule next poll
                set({ progressMessage: `Analyzing… (${jobStatus.status})` });
                // Timer ID is kept at module level to avoid polluting the Zustand state graph.
                _pollingTimerId = setTimeout(() => get().pollStatus(), 2500);
            }
        } catch {
            set({ status: 'FAILED', error: 'Failed to check job status.', progressMessage: '' });
        }
    },

    /**
     * Cancel any in-progress polling by clearing the module-level timer.
     * Call this in the useEffect cleanup of any component that triggers polling
     * to prevent memory leaks and stale state updates after navigation.
     */
    cancelPolling: () => {
        if (_pollingTimerId !== null) {
            clearTimeout(_pollingTimerId);
            _pollingTimerId = null;
        }
    },

    triggerFinalize: async (acceptedIds: string[]) => {
        const { jobId } = get();
        if (!jobId) return;
        set({ status: 'FINALIZING', progressMessage: 'Running sandbox validation…', error: null });
        try {
            await finalizeJob(jobId, acceptedIds);
            // Resume polling to detect FINALIZED or FAILED status
            set({ status: 'PROCESSING' });
            _pollingTimerId = setTimeout(() => get().pollStatus(), 2500);
        } catch (error: unknown) {
            const msg = extractErrorMessage(error, 'Finalization failed.');
            set({ status: 'FAILED', error: msg, progressMessage: '' });
        }
    },

    fetchDownloadUrl: async () => {
        const { jobId } = get();
        if (!jobId) return;
        set({ downloadError: null }); // Clear previous download error
        try {
            const { download_url } = await getDownloadUrl(jobId);
            set({ downloadUrl: download_url });
        } catch {
            // Stored in downloadError so the failure remains visible even when status=FINALIZED.
            set({ downloadError: 'Failed to generate download link. Please try again.' });
        }
    },

    /**
     * Restore a past COMPLETED / FINALIZED job's results panel from history.
     *
     * Called when the user clicks "View Results" on a history row.
     * Fetches suggestions from the API and hydrates the store so the
     * results section renders without requiring a new file upload.
     */
    loadJobFromHistory: async (jobId: string, jobStatus: string) => {
        get().cancelPolling();
        set({
            jobId,
            status: 'PROCESSING',
            error: null,
            downloadError: null,
            results: null,
            downloadUrl: null,
            progressMessage: 'Loading results from history…',
        });

        try {
            const { original_sql, suggestions, missing_fk_warnings, has_missing_references } =
                await getJobSuggestions(jobId);

            const resolvedStatus: JobStatus =
                jobStatus === 'FINALIZED' ? 'FINALIZED' : 'COMPLETED';

            set({
                status: resolvedStatus,
                results: {
                    original_sql,
                    suggestions,
                    optimized_sql_preview: suggestions
                        .map((s) => `-- [${s.risk_level}] ${s.issue}\n${s.sql_patch}`)
                        .join('\n\n'),
                    missing_fk_warnings: missing_fk_warnings ?? [],
                    has_missing_references: has_missing_references ?? false,
                },
                progressMessage: '',
            });
        } catch (err: unknown) {
            const msg = extractErrorMessage(err, 'Failed to load job results.');
            set({ status: 'FAILED', error: msg, progressMessage: '' });
        }
    },

    /**
     * Reset all job state and cancel any in-flight polling.
     * Call this when entering a new project to prevent stale results
     * from a previous project from showing in the new context.
     */
    resetJob: () => {
        get().cancelPolling();
        set({
            jobId: null,
            status: 'IDLE',
            results: null,
            downloadUrl: null,
            downloadError: null,
            error: null,
            progressMessage: '',
        });
    },
}));
