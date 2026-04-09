import { create } from 'zustand';
import {
    getProjects,
    getProject,
    createProject as apiCreateProject,
    updateProject as apiUpdateProject,
    deleteProject as apiDeleteProject,
    getProjectJobs,
    extractErrorMessage,
} from '@/lib/api';
import type { ProjectListItem, ProjectResponse, ProjectCreate, ProjectUpdate, JobSummary } from '@/types/project';

interface ProjectState {
    projects: ProjectListItem[];
    currentProject: ProjectResponse | null;
    jobHistory: JobSummary[];
    isLoading: boolean;
    isFetchingCurrent: boolean;
    isLoadingHistory: boolean;
    error: string | null;

    // Actions
    fetchProjects: () => Promise<void>;
    fetchProject: (id: string) => Promise<void>;
    fetchProjectJobs: (id: string) => Promise<void>; // Job history is fetched and owned by the store, not individual pages
    createProject: (data: ProjectCreate) => Promise<ProjectResponse>;
    updateProject: (id: string, data: ProjectUpdate) => Promise<void>;
    deleteProject: (id: string) => Promise<void>;
    clearProjects: () => void;   // Called on logout to prevent data leakage
    clearError: () => void;      // Allows UI to dismiss stale errors between operations
}

export const useProjectStore = create<ProjectState>((set, get) => ({
    projects: [],
    currentProject: null,
    jobHistory: [],
    isLoading: false,
    isFetchingCurrent: false,
    isLoadingHistory: false,
    error: null,

    fetchProjects: async () => {
        set({ isLoading: true, error: null });
        try {
            const projects = await getProjects();
            set({ projects, isLoading: false });
        } catch (error: unknown) {
            set({ isLoading: false, error: extractErrorMessage(error, 'Failed to load projects.') });
        }
    },

    fetchProject: async (id: string) => {
        set({ isFetchingCurrent: true, error: null });
        try {
            const project = await getProject(id);
            set({ currentProject: project, isFetchingCurrent: false });
        } catch (error: unknown) {
            set({
                isFetchingCurrent: false,
                error: extractErrorMessage(error, 'Failed to load project.'),
                currentProject: null,
            });
            throw error; // Re-throw so calling page can redirect on 403/404
        }
    },

    // Job history is managed in the store so it can be shared by any component
    // without duplicating fetch logic in individual pages.
    fetchProjectJobs: async (id: string) => {
        set({ isLoadingHistory: true });
        try {
            const jobHistory = await getProjectJobs(id);
            set({ jobHistory, isLoadingHistory: false });
        } catch {
            set({ jobHistory: [], isLoadingHistory: false });
        }
    },

    createProject: async (data: ProjectCreate) => {
        set({ error: null });
        try {
            const newProject = await apiCreateProject(data);
            // Optimistic update: prepend to list with job_count = 0
            const optimisticItem: ProjectListItem = { ...newProject, job_count: 0 };
            set((state) => ({ projects: [optimisticItem, ...state.projects] }));
            return newProject;
        } catch (error: unknown) {
            const msg = extractErrorMessage(error, 'Failed to create project.');
            set({ error: msg });
            throw error;
        }
    },

    updateProject: async (id: string, data: ProjectUpdate) => {
        set({ error: null });
        try {
            const updated = await apiUpdateProject(id, data);
            // Update both the list and currentProject
            set((state) => ({
                currentProject: state.currentProject?.id === id ? updated : state.currentProject,
                projects: state.projects.map((p) =>
                    p.id === id ? { ...p, name: updated.name, description: updated.description } : p
                ),
            }));
        } catch (error: unknown) {
            const msg = extractErrorMessage(error, 'Failed to update project.');
            set({ error: msg });
            throw error;
        }
    },

    deleteProject: async (id: string) => {
        // Optimistic removal for instant UI feedback
        const previousProjects = get().projects;
        set((state) => ({ projects: state.projects.filter((p) => p.id !== id), error: null }));
        try {
            await apiDeleteProject(id);
        } catch (error: unknown) {
            // Rollback on failure
            set({ projects: previousProjects });
            const msg = extractErrorMessage(error, 'Failed to delete project.');
            set({ error: msg });
            throw error;
        }
    },

    clearProjects: () => {
        set({ projects: [], currentProject: null, jobHistory: [], error: null });
    },

    clearError: () => set({ error: null }),
}));
