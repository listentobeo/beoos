import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

const isPublicRoute = createRouteMatcher([
  "/",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/api/beoos(.*)",
  "/quotes(.*)",
  "/about",
  "/privacy",
  "/terms",
  "/support",
  "/data-deletion",
  "/cookies",
]);

export default clerkMiddleware(async (auth, request) => {
  if (request.nextUrl.hostname === "www.beoos.com.ng") {
    const url = request.nextUrl.clone();
    url.hostname = "beoos.com.ng";
    return NextResponse.redirect(url, 308);
  }

  if (!isPublicRoute(request)) {
    const signInUrl = new URL("/sign-in", request.url);
    signInUrl.searchParams.set("redirect_url", request.url);
    await auth.protect({ unauthenticatedUrl: signInUrl.toString() });
  }
});

export const config = {
  matcher: [
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
