import { create } from 'zustand';
import { loginUser, registerUser, getCurrentUser, extractErrorMessage } from '@/lib/api';
import { getCookie, setCookie, removeCookie, TOKEN_COOKIE, USER_COOKIE } from '@/lib/cookies';
import type { UserResponse, LoginCredentials, RegisterCredentials } from '@/types/auth';

interface AuthState {
    user: UserResponse | null;
    token: string | null;
    isAuthenticated: boolean;
    // isHydrating: true while cookie state is being restored; prevents auth flash on page refresh
    isHydrating: boolean;
    isLoading: boolean;
    error: string | null;

    // Actions
    hydrate: () => void;
    login: (credentials: LoginCredentials) => Promise<void>;
    register: (credentials: RegisterCredentials) => Promise<void>;
    logout: () => void;
    clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
    user: null,
    token: null,
    isAuthenticated: false,
    isHydrating: true,
    isLoading: false,
    error: null,

    /**
     * Restore auth state from cookies on page load/refresh.
     * Called once by <AuthProvider> on mount.
     * Reads the token and user profile from cookies so that session state
     * survives page refreshes without requiring a new login.
     */
    hydrate: () => {
        const token = getCookie(TOKEN_COOKIE);
        const userStr = getCookie(USER_COOKIE);
        let user: UserResponse | null = null;
        if (userStr) {
            try {
                user = JSON.parse(userStr) as UserResponse;
            } catch {
                user = null;
            }
        }
        set({ token: token || null, user, isAuthenticated: !!token, isHydrating: false });
    },

    login: async (credentials: LoginCredentials) => {
        set({ isLoading: true, error: null });
        try {
            // Step 1: Exchange credentials for JWT
            const tokenData = await loginUser(credentials);

            // Step 2: Persist token in cookie BEFORE calling /me
            // so the interceptor can attach it automatically
            setCookie(TOKEN_COOKIE, tokenData.access_token);

            // Step 3: Fetch user profile
            const user = await getCurrentUser();

            // Step 4: Persist user in cookie for hydration
            setCookie(USER_COOKIE, JSON.stringify(user));

            set({ user, token: tokenData.access_token, isAuthenticated: true, isLoading: false });
        } catch (error: unknown) {
            const message = extractErrorMessage(error, 'Login failed. Please check your credentials.');
            set({ isLoading: false, error: message, isAuthenticated: false });
            throw error;
        }
    },

    register: async (credentials: RegisterCredentials) => {
        set({ isLoading: true, error: null });
        try {
            // Step 1: Create account
            await registerUser(credentials);

            // Step 2: Auto-login after successful registration
            const tokenData = await loginUser({
                email: credentials.email,
                password: credentials.password,
            });

            setCookie(TOKEN_COOKIE, tokenData.access_token);
            const user = await getCurrentUser();
            setCookie(USER_COOKIE, JSON.stringify(user));

            set({ user, token: tokenData.access_token, isAuthenticated: true, isLoading: false });
        } catch (error: unknown) {
            const message = extractErrorMessage(error, 'Registration failed. Please try again.');
            set({ isLoading: false, error: message });
            throw error;
        }
    },

    logout: () => {
        removeCookie(TOKEN_COOKIE);
        removeCookie(USER_COOKIE);
        // Clear the project store on logout to prevent data leakage when a
        // different user logs in on the same browser within the same session.
        import('@/store/useProjectStore').then(({ useProjectStore }) => {
            useProjectStore.getState().clearProjects();
        });
        set({ user: null, token: null, isAuthenticated: false, error: null });
    },

    clearError: () => set({ error: null }),
}));
