'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/store/useAuthStore';
import { useProjectStore } from '@/store/useProjectStore';
import { CreateProjectModal } from '@/components/CreateProjectModal';
import {
    Database, Plus, FolderOpen, Loader2, LogOut, User,
    Briefcase, AlertCircle, Trash2, ChevronRight
} from 'lucide-react';

/** Skeleton card shown while projects are loading */
function ProjectCardSkeleton() {
    return (
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 animate-pulse">
            <div className="mb-3 h-5 w-3/4 rounded-md bg-slate-800" />
            <div className="mb-4 h-3 w-full rounded-md bg-slate-800" />
            <div className="mb-4 h-3 w-2/3 rounded-md bg-slate-800" />
            <div className="flex justify-between items-center">
                <div className="h-3 w-16 rounded-md bg-slate-800" />
                <div className="h-8 w-20 rounded-lg bg-slate-800" />
            </div>
        </div>
    );
}

/** Empty state when user has no projects */
function EmptyState({ onCreateClick }: { onCreateClick: () => void }) {
    return (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-800 py-20 text-center">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-800/80">
                <Database className="h-8 w-8 text-slate-500" />
            </div>
            <h3 className="mb-2 text-lg font-semibold text-white">No projects yet</h3>
            <p className="mb-6 max-w-sm text-sm text-slate-400">
                Create a project to start uploading SQL schemas and get AI-powered optimization suggestions.
            </p>
            <button
                id="btn-create-first-project"
                onClick={onCreateClick}
                className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 px-6 py-2.5 font-medium text-white shadow-lg shadow-blue-500/25 transition-all hover:from-blue-500 hover:to-violet-500"
            >
                <Plus className="h-4 w-4" />
                Create Your First Project
            </button>
        </div>
    );
}

export default function DashboardPage() {
    const router = useRouter();
    const { user, logout, isHydrating } = useAuthStore();
    const { projects, isLoading, error, fetchProjects, deleteProject } = useProjectStore();

    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [deletingId, setDeletingId] = useState<string | null>(null);
    const [deleteError, setDeleteError] = useState<string | null>(null);

    const handleLogout = () => {
        logout();
        router.push('/login');
    };

    // Fetch projects on mount
    useEffect(() => {
        if (!isHydrating) {
            fetchProjects();
        }
    }, [isHydrating, fetchProjects]);

    const handleDelete = async (e: React.MouseEvent, projectId: string, projectName: string) => {
        e.stopPropagation(); // Prevent card click navigation
        if (!confirm(`Delete project "${projectName}" and all its analysis jobs? This cannot be undone.`)) return;

        setDeletingId(projectId);
        setDeleteError(null);
        try {
            await deleteProject(projectId);
        } catch {
            setDeleteError('Failed to delete project. Please try again.');
        } finally {
            setDeletingId(null);
        }
    };

    const formatDate = (dateStr: string) =>
        new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

    if (isHydrating) {
        return (
            <div className="min-h-screen bg-slate-950 flex items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-slate-950">
            {/* Top Navbar */}
            <header className="sticky top-0 z-20 border-b border-slate-800 bg-slate-900/90 backdrop-blur-sm">
                <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
                    <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-violet-600">
                            <Database className="h-5 w-5 text-white" />
                        </div>
                        <div>
                            <span className="font-bold text-white">SQL Optimizer</span>
                            <p className="text-xs text-slate-400 leading-none mt-0.5">AI-powered Analysis</p>
                        </div>
                    </div>
                    <div className="flex items-center gap-4">
                        {user && (
                            <div className="hidden sm:flex items-center gap-2 text-sm text-slate-400">
                                <User className="h-4 w-4" />
                                <span>{user.email}</span>
                            </div>
                        )}
                        <button
                            id="btn-logout"
                            onClick={handleLogout}
                            className="flex items-center gap-2 rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-slate-600 hover:text-white"
                        >
                            <LogOut className="h-4 w-4" />
                            Sign Out
                        </button>
                    </div>
                </div>
            </header>

            <main className="mx-auto max-w-6xl px-6 py-8">
                {/* Page Header */}
                <div className="mb-8 flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-white">My Projects</h1>
                        <p className="mt-1 text-sm text-slate-400">
                            Select a project to analyze its SQL schema.
                        </p>
                    </div>
                    <button
                        id="btn-new-project"
                        onClick={() => setIsCreateOpen(true)}
                        className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 px-4 py-2.5 text-sm font-medium text-white shadow-lg shadow-blue-500/25 transition-all hover:from-blue-500 hover:to-violet-500"
                    >
                        <Plus className="h-4 w-4" />
                        New Project
                    </button>
                </div>

                {/* Error banner */}
                {(error || deleteError) && (
                    <div className="mb-6 flex items-center gap-3 rounded-xl border border-red-500/20 bg-red-500/10 p-4">
                        <AlertCircle className="h-5 w-5 flex-shrink-0 text-red-400" />
                        <p className="text-sm text-red-400">
                            {typeof (deleteError || error) === 'string'
                                ? (deleteError || error)
                                : JSON.stringify(deleteError || error)}
                        </p>
                    </div>
                )}

                {/* Project Grid */}
                {isLoading ? (
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                        {[...Array(3)].map((_, i) => <ProjectCardSkeleton key={i} />)}
                    </div>
                ) : projects.length === 0 ? (
                    <EmptyState onCreateClick={() => setIsCreateOpen(true)} />
                ) : (
                    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                        {projects.map((project) => (
                            <div
                                key={project.id}
                                onClick={() => router.push(`/dashboard/${project.id}`)}
                                className="group relative flex cursor-pointer flex-col rounded-2xl border border-slate-800 bg-slate-900/60 p-6 transition-all hover:border-slate-700 hover:bg-slate-900 hover:shadow-lg hover:shadow-blue-500/5"
                            >
                                {/* Delete button */}
                                <button
                                    aria-label={`Delete project ${project.name}`}
                                    onClick={(e) => handleDelete(e, project.id, project.name)}
                                    disabled={deletingId === project.id}
                                    className="absolute right-4 top-4 hidden rounded-lg p-1.5 text-slate-600 transition-all group-hover:flex hover:bg-red-500/10 hover:text-red-400 disabled:opacity-50"
                                >
                                    {deletingId === project.id ? (
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                    ) : (
                                        <Trash2 className="h-4 w-4" />
                                    )}
                                </button>

                                {/* Icon */}
                                <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-blue-500/10 ring-1 ring-blue-500/20">
                                    <FolderOpen className="h-5 w-5 text-blue-400" />
                                </div>

                                {/* Name */}
                                <h2 className="mb-1 truncate pr-6 text-base font-semibold text-white">
                                    {project.name}
                                </h2>

                                {/* Description */}
                                {project.description && (
                                    <p className="mb-3 line-clamp-2 text-sm text-slate-400">
                                        {project.description}
                                    </p>
                                )}

                                {/* Stats row */}
                                <div className="mt-auto flex items-center justify-between pt-4">
                                    <div className="flex items-center gap-1.5 text-xs text-slate-500">
                                        <Briefcase className="h-3.5 w-3.5" />
                                        <span>{project.job_count} {project.job_count === 1 ? 'job' : 'jobs'}</span>
                                        <span className="mx-1">·</span>
                                        <span>{formatDate(project.created_at)}</span>
                                    </div>
                                    <ChevronRight className="h-4 w-4 text-slate-600 transition-all group-hover:text-blue-400 group-hover:translate-x-0.5" />
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </main>

            <CreateProjectModal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} />
        </div>
    );
}
