import { Outlet, createRootRouteWithContext } from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/react-router-devtools";

import TanStackQueryLayout from "../integrations/tanstack-query/layout.tsx";

import { Toaster } from "sonner";

import type { QueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

interface MyRouterContext {
  queryClient: QueryClient;
}

export const Route = createRootRouteWithContext<MyRouterContext>()({
  component: () => (
    <div className="min-h-screen bg-gradient-to-b from-emerald-800 to-emerald-950">
      <Outlet />
      <TanStackRouterDevtools />
      <Toaster richColors />
      <TanStackQueryLayout />
    </div>
  ),
  pendingComponent :() => <div className="min-h-screen bg-gradient-to-b from-emerald-800 to-emerald-950 flex items-center justify-center"><Loader2 className="size-12 text-white animate-spin" /></div>,
  wrapInSuspense: true,
  
});
