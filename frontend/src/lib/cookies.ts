// Cookie utility functions — used by both Zustand store and Axios interceptor.
// Cookies are readable by Next.js middleware (unlike localStorage), fixing the
// critical gap where middleware.ts cannot access localStorage.

export const TOKEN_COOKIE = 'auth_token';
export const USER_COOKIE = 'auth_user';
const COOKIE_EXPIRY_DAYS = 7;

/**
 * Read a cookie by name. Returns null if not found or in server environment.
 */
export const getCookie = (name: string): string | null => {
    if (typeof document === 'undefined') return null;
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) {
        return decodeURIComponent(parts.pop()?.split(';').shift() ?? '');
    }
    return null;
};

/**
 * Set a cookie with SameSite=Strict for CSRF protection.
 */
export const setCookie = (
    name: string,
    value: string,
    days: number = COOKIE_EXPIRY_DAYS
): void => {
    if (typeof document === 'undefined') return;
    const expires = new Date();
    expires.setTime(expires.getTime() + days * 24 * 60 * 60 * 1000);
    document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires.toUTCString()}; path=/; SameSite=Strict`;
};

/**
 * Delete a cookie by setting its expiry to the past.
 */
export const removeCookie = (name: string): void => {
    if (typeof document === 'undefined') return;
    document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
};
