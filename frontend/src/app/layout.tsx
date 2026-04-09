import './globals.css';
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { AuthProvider } from '@/components/AuthProvider';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
    title: 'SQL Optimizer & Architect',
    description: 'AI-powered SQL schema analysis and optimization platform',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en">
            <body className={`${inter.className} antialiased`}>
                {/*
          AuthProvider wraps the entire app so useAuthStore is hydrated
          from cookies on every page load — preventing the "reset on refresh" bug.
        */}
                <AuthProvider>{children}</AuthProvider>
            </body>
        </html>
    );
}
