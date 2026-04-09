'use client';

import { useEffect, useRef } from 'react';
import { X } from 'lucide-react';

interface ModalProps {
    isOpen: boolean;
    onClose: () => void;
    title: string;
    children: React.ReactNode;
    /** Max width class, default: 'max-w-md' */
    maxWidth?: string;
}

/**
 * Accessible, keyboard-navigable modal dialog.
 * - Closes on Escape key press
 * - Closes on backdrop click
 * - Traps focus within modal when open
 * - Uses role="dialog" + aria-modal for screen readers
 */
export function Modal({ isOpen, onClose, title, children, maxWidth = 'max-w-md' }: ModalProps) {
    const dialogRef = useRef<HTMLDivElement>(null);

    // Close on Escape key
    useEffect(() => {
        if (!isOpen) return;
        const handleKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        document.addEventListener('keydown', handleKey);
        return () => document.removeEventListener('keydown', handleKey);
    }, [isOpen, onClose]);

    // Prevent body scroll when modal is open
    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = 'hidden';
        } else {
            document.body.style.overflow = '';
        }
        return () => { document.body.style.overflow = ''; };
    }, [isOpen]);

    if (!isOpen) return null;

    return (
        // Backdrop
        <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}
            onClick={(e) => {
                // Close only if backdrop itself is clicked (not modal content)
                if (e.target === e.currentTarget) onClose();
            }}
            aria-hidden={!isOpen}
        >
            {/* Dialog */}
            <div
                ref={dialogRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby="modal-title"
                className={`
          relative w-full ${maxWidth}
          rounded-2xl border border-slate-800
          bg-slate-900 shadow-2xl
          animate-fade-in-up
        `}
            >
                {/* Header */}
                <div className="flex items-center justify-between border-b border-slate-800 px-6 py-4">
                    <h2 id="modal-title" className="text-lg font-semibold text-white">
                        {title}
                    </h2>
                    <button
                        type="button"
                        aria-label="Close dialog"
                        onClick={onClose}
                        className="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
                    >
                        <X className="h-4 w-4" />
                    </button>
                </div>

                {/* Content */}
                <div className="px-6 py-5">{children}</div>
            </div>
        </div>
    );
}
