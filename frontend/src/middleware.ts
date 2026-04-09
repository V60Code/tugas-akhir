import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// This must match the cookie name used in cookies.ts
const TOKEN_COOKIE = 'auth_token';

const PROTECTED_ROUTES = ['/dashboard'];
const AUTH_ROUTES = ['/login', '/register'];

export function middleware(request: NextRequest) {
    // Reads from cookie (not localStorage) — this is the correct approach
    // for Next.js Edge Runtime which has no access to browser APIs.
    const token = request.cookies.get(TOKEN_COOKIE)?.value;
    const { pathname } = request.nextUrl;

    const isProtected = PROTECTED_ROUTES.some((route) => pathname.startsWith(route));
    const isAuthRoute = AUTH_ROUTES.some((route) => pathname.startsWith(route));

    // Unauthenticated user trying to access protected route → redirect to login
    if (isProtected && !token) {
        const loginUrl = new URL('/login', request.url);
        loginUrl.searchParams.set('from', pathname);
        return NextResponse.redirect(loginUrl);
    }

    // Authenticated user trying to access login/register → redirect to dashboard
    if (isAuthRoute && token) {
        return NextResponse.redirect(new URL('/dashboard', request.url));
    }

    return NextResponse.next();
}

export const config = {
    // Exclude Next.js internals, static assets, and API routes from middleware
    matcher: ['/((?!api|_next/static|_next/image|favicon\\.ico|.*\\..*).*)',],
};
