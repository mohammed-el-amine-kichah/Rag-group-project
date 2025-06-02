import { authQueryOptions } from "@/constants";
import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/_authenticated")({
  beforeLoad: async ({ context: { queryClient } }) => {
    const user = await queryClient.ensureQueryData(authQueryOptions);
    if (!user || user.authenticated === false) {
      throw redirect({
        to: "/login",
      });
    }
  },
});
