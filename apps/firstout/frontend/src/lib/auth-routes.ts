export function isPublicAuthPath(pathname: string): boolean {
  return pathname === "/login" || pathname === "/forgot-password" ||
    pathname === "/reset-password" || pathname === "/onboarding" ||
    pathname.startsWith("/clerk-login") || pathname.startsWith("/sign-up") ||
    pathname.startsWith("/trade");
}

export function missingSessionDestination(clerkSignedIn: boolean): string {
  return clerkSignedIn ? "/onboarding" : "/clerk-login";
}
