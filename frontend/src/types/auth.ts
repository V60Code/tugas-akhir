// Centralized TypeScript interfaces for Auth domain

export interface UserResponse {
    id: string;
    email: string;
    full_name: string | null;
    tier: 'FREE' | 'PRO' | 'ENTERPRISE';
    credits_balance: number;
}

export interface Token {
    access_token: string;
    token_type: string;
}

export interface LoginCredentials {
    email: string;
    password: string;
}

export interface RegisterCredentials {
    email: string;
    password: string;
    full_name: string;
}
