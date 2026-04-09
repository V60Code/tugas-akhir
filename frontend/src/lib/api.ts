import axios from 'axios';
import { getCookie, setCookie, removeCookie, TOKEN_COOKIE, USER_COOKIE } from './cookies';
import type { Token, UserResponse, LoginCredentials, RegisterCredentials } from '@/types/auth';
import type {
    ProjectResponse,
    ProjectListItem,
    ProjectCreate,
    ProjectUpdate,
    JobSummary,
    AppContext,
    ERDSchemaResponse,
} from '@/types/project';
import type { JobResponse, JobStatusResponse, AISuggestion, JobSuggestionsResponse } from '@/types/job';

// Re-export all project types so existing imports from '@/lib/api' still work
export type { ProjectResponse, ProjectListItem, ProjectCreate, ProjectUpdate, AppContext, ERDSchemaResponse };

// Re-export JobSummary under its legacy alias used in api.ts consumers
export type { JobSummary as JobSummaryResponse };

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const api = axios.create({
    baseURL: BASE_URL,
    headers: { 'Content-Type': 'application/json' },
});

/**
 * Safely extract a human-readable error message from any API error.
 *
 * FastAPI + Pydantic V2 returns validation errors as:
 *   { detail: [{ type, loc, msg, input }] }
 *
 * But business-logic errors return:
 *   { detail: "plain string message" }
 *
 * This helper normalises both forms so they are always safe to render
 * as a React child (never an object or array).
 */
export function extractErrorMessage(error: unknown, fallback = 'An unexpected error occurred.'): string {
    const detail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;

    if (!detail) return fallback;

    // Pydantic V2: array of validation error objects
    if (Array.isArray(detail)) {
        return detail
            .map((e: { msg?: string; loc?: string[]; type?: string }) => {
                const field = e.loc ? e.loc.filter((s) => s !== 'body').join('.') : '';
                return field ? `${field}: ${e.msg ?? e.type}` : (e.msg ?? e.type ?? 'Validation error');
            })
            .join(' | ');
    }

    // Plain string
    if (typeof detail === 'string') return detail;

    // Last resort — serialize whatever we got
    return JSON.stringify(detail);
}

// ── Request Interceptor: auto-attach JWT token ──────────────────────────────
api.interceptors.request.use(
    (config) => {
        const token = getCookie(TOKEN_COOKIE);
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => Promise.reject(error)
);

// ── Response Interceptor: handle session expiry (401/403) ──────────────────
// On 401/403, tokens are removed and the user is redirected to /login.
// Auth pages are excluded from the redirect to prevent redirect loops.
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (
            typeof window !== 'undefined' &&
            (error.response?.status === 401 || error.response?.status === 403)
        ) {
            const currentPath = window.location.pathname;
            // Don't redirect if already on auth pages to avoid infinite loop
            if (currentPath !== '/login' && currentPath !== '/register') {
                removeCookie(TOKEN_COOKIE);
                removeCookie(USER_COOKIE);
                window.location.href = '/login?session_expired=true';
            }
        }
        return Promise.reject(error);
    }
);

// ── AUTH ENDPOINTS ──────────────────────────────────────────────────────────

/**
 * Login — uses URLSearchParams because the backend endpoint uses
 * OAuth2PasswordRequestForm (application/x-www-form-urlencoded).
 * The field must be named 'username' per the OAuth2 spec, even though
 * the application uses email addresses as the credential identifier.
 */
export const loginUser = async (credentials: LoginCredentials): Promise<Token> => {
    const params = new URLSearchParams();
    params.append('username', credentials.email); // OAuth2 requires 'username'
    params.append('password', credentials.password);
    const response = await api.post<Token>('/api/v1/auth/login', params, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    return response.data;
};

export const registerUser = async (credentials: RegisterCredentials): Promise<UserResponse> => {
    const response = await api.post<UserResponse>('/api/v1/auth/register', {
        email: credentials.email,
        password: credentials.password,
        full_name: credentials.full_name,
    });
    return response.data;
};

export const getCurrentUser = async (): Promise<UserResponse> => {
    const response = await api.get<UserResponse>('/api/v1/auth/me');
    return response.data;
};

// ── PROJECTS ENDPOINTS ──────────────────────────────────────────────────────
// Types are defined in @/types/project.ts (single source of truth)

// Returns ProjectListItem[] — includes job_count from backend JOIN query
export const getProjects = async (): Promise<ProjectListItem[]> => {
    const response = await api.get<ProjectListItem[]>('/api/v1/projects/');
    return response.data;
};

export const getProject = async (id: string): Promise<ProjectResponse> => {
    const response = await api.get<ProjectResponse>(`/api/v1/projects/${id}`);
    return response.data;
};

export const createProject = async (data: ProjectCreate): Promise<ProjectResponse> => {
    const response = await api.post<ProjectResponse>('/api/v1/projects/', data);
    return response.data;
};

export const updateProject = async (id: string, data: ProjectUpdate): Promise<ProjectResponse> => {
    const response = await api.patch<ProjectResponse>(`/api/v1/projects/${id}`, data);
    return response.data;
};

export const deleteProject = async (id: string): Promise<void> => {
    await api.delete(`/api/v1/projects/${id}`);
};

export const getProjectJobs = async (id: string): Promise<JobSummary[]> => {
    const response = await api.get<JobSummary[]>(`/api/v1/projects/${id}/jobs`);
    return response.data;
};

// ── JOBS ENDPOINTS ──────────────────────────────────────────────────────────

// Re-export job types so existing imports from '@/lib/api' continue to work
export type { JobResponse, JobStatusResponse, AISuggestion, JobSuggestionsResponse };

export const uploadSqlFile = async (
    file: File,
    projectId: string,
    appContext: 'READ_HEAVY' | 'WRITE_HEAVY',
    dbDialect?: 'mysql' | 'postgres' | 'auto'
): Promise<JobResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('project_id', projectId);
    formData.append('app_context', appContext);
    if (dbDialect && dbDialect !== 'auto') {
        formData.append('db_dialect', dbDialect);
    }
    const response = await api.post<JobResponse>('/api/v1/jobs/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
};

export const getJobStatus = async (jobId: string): Promise<JobStatusResponse> => {
    const response = await api.get<JobStatusResponse>(`/api/v1/jobs/${jobId}/status`);
    return response.data;
};

/** Returns the full suggestions payload including original SQL and AI recommendations. */
export const getJobSuggestions = async (jobId: string): Promise<JobSuggestionsResponse> => {
    const response = await api.get<JobSuggestionsResponse>(`/api/v1/jobs/${jobId}/suggestions`);
    return response.data;
};

export const finalizeJob = async (jobId: string, acceptedIds: string[]): Promise<{ message: string }> => {
    const response = await api.post<{ message: string }>(`/api/v1/jobs/${jobId}/finalize`, {
        accepted_suggestion_ids: acceptedIds,
    });
    return response.data;
};

export const getDownloadUrl = async (jobId: string): Promise<{ download_url: string }> => {
    const response = await api.get<{ download_url: string }>(`/api/v1/jobs/${jobId}/download`);
    return response.data;
};

/** Fetch the full ERD schema for the React Flow visualizer. */
export const getJobSchema = async (jobId: string): Promise<ERDSchemaResponse> => {
    const response = await api.get<ERDSchemaResponse>(`/api/v1/jobs/${jobId}/schema`);
    return response.data;
};
