import { queryOptions } from "@tanstack/react-query";
import ky from "ky";

type AuthenticatedUser =
  | { authenticated: false }
  | {
      authenticated: true;
      user: {
        id: string;
        name: string;
        email: string;
      };
    };

export const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const authQueryOptions = queryOptions({
  queryKey: ["auth-user"],
  queryFn: () => kyInstance.get(`session`).json<AuthenticatedUser>(),
});

export const kyInstance = ky.create({
  credentials: "include",
  prefixUrl: `${API_BASE}/api`,
  retry: 0,
});
