import { kyInstance } from "@/constants";
import { createFileRoute, redirect } from "@tanstack/react-router";
import { Loader2 } from "lucide-react";

export const Route = createFileRoute("/_authenticated/")({
  beforeLoad: async ({context : {queryClient}}) => {
    const newConversation = await kyInstance
      .post(`conversations`, { json: { title: "محادثة جديدة" } })
      .json<{ id: string; title: string }>();



    // queryClient.setQueryData<{
    //   conversations: {
    //     id: string;
    //     title: string;
    //   }[];
    // }>(["previous-conversations"], (old) => {
    //   if (!old) return old;
    //   return {conversations: [ newConversation,...old.conversations]};
    // })

    throw redirect({
      to: "/chat/$id",
      params: {
        id: newConversation.id,
      },
    });
  },
  wrapInSuspense: true,
  pendingComponent : () => <div className="min-h-screen flex items-center justify-center"><Loader2 className="size-12 text-white animate-spin" /></div>
});
