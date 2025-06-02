import { authQueryOptions } from "@/constants";
import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/_auth")({
  beforeLoad: async ({ context: { queryClient } }) => {
    const user = await queryClient.ensureQueryData(authQueryOptions);
    if (user && user.authenticated === true) {
      throw redirect({ to: "/" });
    }
  },
});
