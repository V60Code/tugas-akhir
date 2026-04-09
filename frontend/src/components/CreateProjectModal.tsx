'use client';

import { useState } from 'react';
import { Loader2, FolderPlus } from 'lucide-react';
import { Modal } from '@/components/ui/modal';
import { useProjectStore } from '@/store/useProjectStore';
import { useRouter } from 'next/navigation';
import { extractErrorMessage } from '@/lib/api';

interface CreateProjectModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export function CreateProjectModal({ isOpen, onClose }: CreateProjectModalProps) {
    const router = useRouter();
    const { createProject } = useProjectStore();

    const [name, setName] = useState('');
    const [description, setDescription] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleClose = () => {
        if (isLoading) return; // Prevent closing while submitting
        setName('');
        setDescription('');
        setError(null);
        onClose();
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);

        // Client-side validation
        if (!name.trim()) {
            setError('Project name is required.');
            return;
        }
        if (name.trim().length > 150) {
            setError('Project name must be 150 characters or fewer.');
            return;
        }

        setIsLoading(true);
        try {
            const newProject = await createProject({ name: name.trim(), description: description.trim() || undefined });
            handleClose();
            // Navigate to the newly created project immediately
            router.push(`/dashboard/${newProject.id}`);
        } catch (err: unknown) {
            setError(extractErrorMessage(err, 'Failed to create project. Please try again.'));
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <Modal isOpen={isOpen} onClose={handleClose} title="Create New Project">
            <form onSubmit={handleSubmit} className="space-y-4" noValidate>
                {error && (
                    <div className="rounded-lg border border-red-500/20 bg-red-500/10 p-3">
                        <p className="text-sm text-red-400">{error}</p>
                    </div>
                )}

                {/* Project Name */}
                <div className="space-y-1.5">
                    <label htmlFor="project-name" className="block text-sm font-medium text-slate-300">
                        Project Name <span className="text-red-400">*</span>
                    </label>
                    <input
                        id="project-name"
                        type="text"
                        required
                        maxLength={150}
                        disabled={isLoading}
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="e.g. Blog Database, E-commerce Schema"
                        autoFocus
                        className="w-full rounded-lg border border-slate-700 bg-slate-800/60 px-4 py-2.5 text-white placeholder-slate-500 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                    />
                    <p className="text-xs text-slate-500">{name.length}/150 characters</p>
                </div>

                {/* Description */}
                <div className="space-y-1.5">
                    <label htmlFor="project-desc" className="block text-sm font-medium text-slate-300">
                        Description{' '}
                        <span className="text-slate-500 font-normal">(optional)</span>
                    </label>
                    <textarea
                        id="project-desc"
                        rows={3}
                        disabled={isLoading}
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder="Brief description of this database schema…"
                        className="w-full resize-none rounded-lg border border-slate-700 bg-slate-800/60 px-4 py-2.5 text-white placeholder-slate-500 transition-all focus:border-transparent focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                    />
                </div>

                {/* Actions */}
                <div className="flex justify-end gap-3 pt-1">
                    <button
                        type="button"
                        onClick={handleClose}
                        disabled={isLoading}
                        className="rounded-lg border border-slate-700 px-4 py-2 text-sm font-medium text-slate-300 transition-colors hover:border-slate-600 hover:text-white disabled:opacity-50"
                    >
                        Cancel
                    </button>
                    <button
                        id="btn-create-project"
                        type="submit"
                        disabled={isLoading || !name.trim()}
                        className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-blue-600 to-violet-600 px-5 py-2 text-sm font-medium text-white shadow-lg shadow-blue-500/25 transition-all hover:from-blue-500 hover:to-violet-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {isLoading ? (
                            <>
                                <Loader2 className="h-4 w-4 animate-spin" />
                                Creating…
                            </>
                        ) : (
                            <>
                                <FolderPlus className="h-4 w-4" />
                                Create Project
                            </>
                        )}
                    </button>
                </div>
            </form>
        </Modal>
    );
}
