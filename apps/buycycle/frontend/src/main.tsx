import React from "react";
import { createRoot } from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from "@tanstack/react-router";
import { PrimerProvider } from "@f0rge/primer";
import { App } from "./App";
import "./style.css";
const rootRoute = createRootRoute({
  validateSearch: (input: Record<string, unknown>): Record<string, string> =>
    Object.fromEntries(
      Object.entries(input).filter(
        (entry): entry is [string, string] => typeof entry[1] === "string",
      ),
    ),
});
const appRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/$",
  component: App,
});
const router = createRouter({ routeTree: rootRoute.addChildren([appRoute]) });
declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, staleTime: 30000 },
    mutations: { retry: false },
  },
});
const element = document.getElementById("root");
if (!element) throw new Error("Missing application root");
createRoot(element).render(
  <React.StrictMode>
    <PrimerProvider>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </PrimerProvider>
  </React.StrictMode>,
);
