import { createFileRoute, Link, notFound } from "@tanstack/react-router";
import React, { useEffect, useState } from "react";
import {
  MessageCircle,
  Send,
  Book,
  GraduationCap,
  Building2,
  Menu,
  History,
  UserCircle2,
  ChevronRight,
  LogOut,
  MessageCirclePlus,
  Loader2,
} from "lucide-react";
import {
  queryOptions,
  useMutation,
  useQueryClient,
  useSuspenseQuery,
} from "@tanstack/react-query";
import { API_BASE, authQueryOptions, kyInstance } from "@/constants";
import { toast } from "sonner";
import ReactMarkdown from "react-markdown";

type Chat = {
  id: string;
  messages: {
    id: string;
    is_user: boolean;
    content: string;
  }[];
  title: string;
};

const chatQueryOptions = (id: string) =>
  queryOptions({
    queryKey: ["chat", id],
    queryFn: () => kyInstance.get(`conversations/${id}`).json<Chat>(),
  });

export const Route = createFileRoute("/_authenticated/chat/$id")({
  loader: async ({ context: { queryClient }, params: { id } }) => {
    const data = await queryClient.ensureQueryData(chatQueryOptions(id));
    if (!data) throw notFound();
  },
  component: RouteComponent,
  wrapInSuspense: true,
  pendingComponent: () => <div className="min-h-screen flex items-center justify-center">
    <Loader2 className="size-16 animate-spin text-white" />
  </div>
});

function RouteComponent() {
  const queryClient = useQueryClient();

  const lastEleRef = React.useRef<HTMLDivElement>(null);

  const navigate = Route.useNavigate();

  const { id } = Route.useParams();

  const { data: conversation } = useSuspenseQuery(chatQueryOptions(id));

  const { data: user } = useSuspenseQuery(authQueryOptions);

  const { data: previousConversations } = useSuspenseQuery({
    queryKey: ["previous-conversations"],
    queryFn: () =>
      kyInstance.get("conversations").json<{
        conversations: {
          id: string;
          title: string;
        }[];
      }>(),
  });

  const { mutate: logout, isPending: isLogingOut } = useMutation({
    mutationFn: () => kyInstance.post("logout").json(),
    onSuccess: () => {
      toast.success("تم تسجيل الخروج بنجاح");
      queryClient.clear();
      navigate({ to: "/login" });
    },
    onError: (err) => {
      toast.error("حدث خطأ أثناء تسجيل الخروج");
      console.log(err);
    },
  });

  // const { mutate , isPending : isSendingMessage } = useMutation({
  //   mutationFn: (message: string) =>
  //     kyInstance
  //       .post(`conversations/${id}/messages`, {
  //         json: {
  //           message,
  //         },
  //       })
  //       .json<{ id: string; is_user: false; content: string }>(),

  //   onSuccess: (data) => {
  //     queryClient.setQueryData<Chat>(["chat", id], (chat) => {
  //       if (!chat) return chat;
  //       return { ...chat, messages: [data, ...chat.messages] };
  //     });
  //     queryClient.refetchQueries({queryKey : ["previous-conversations"]});
  //   },

  //   onError: () => {
  //     queryClient.setQueryData<Chat>(["chat", id], (chat) => {
  //       if (!chat) return chat;
  //       return {
  //         ...chat,
  //         messages: [
  //           {
  //             id: crypto.randomUUID() as string,
  //             content: "عذراً، حدث خطأ في النظام. يرجى المحاولة مرة أخرى.",
  //             is_user: false,
  //           },
  //           ...chat.messages,
  //         ],
  //       };
  //     });
  //   },
  // });

  const {mutate : sendMessageStream , isPending : isSendingMessageStream} = useMutation({
    mutationFn: async (message: string) => {
      const response = await fetch(`${API_BASE}/api/stream-answer/${id}/messages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",

        },
        body: JSON.stringify({ message }),
        credentials : 'include'
      });
      
      queryClient.refetchQueries({queryKey : ["previous-conversations"]});

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();
      let fullAnswer = "";
      let done = false;

      const newId = crypto.randomUUID() as string

      queryClient.setQueryData<Chat>(['chat',id],(old) => {
        if(!old) return old
        const messages = [{id: newId, content : '' ,is_user : false},...old.messages]

        return {...old , messages}

      })
    
      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        const chunk = decoder.decode(value || new Uint8Array(), { stream: !done });
        fullAnswer += chunk;
        
        queryClient.setQueryData<Chat>(['chat',id],(old) => {
          if(!old) return old
          return {...old , messages : old.messages.map(msg => (msg.id === newId ? {...msg , content : fullAnswer} : msg))}
        })
      }
    
      console.log("Final Answer:", fullAnswer);

      await fetch(`${API_BASE}/api/stream-answer/${id}/ai-message`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",

        },
        body: JSON.stringify({ message : fullAnswer }),
        credentials : 'include'
      })

      return true;
    }
  })

  const {mutate: createNewConversation , isPending : isCreatingNewPage} = useMutation({
    mutationFn: () => kyInstance
    .post(`conversations`, { json: { title: "محادثة جديدة" } })
    .json<{ id: string; title: string }>(),
    onSuccess: (data) => {
      queryClient.setQueryData<{
        conversations: {
          id: string;
          title: string;
        }[];
      }>(["previous-conversations"], (old) => {
        if (!old) return old;
        const isAlreadyExists = old.conversations.find(
          (conv) => conv.id === data.id
        );
        if (isAlreadyExists) {
          toast.info("أنت بالفعل في محادثة جديدة");
          return old
        };
        return { conversations: [data, ...old.conversations] };
      });
      navigate({
        to: "/chat/$id",
        params: {
          id: data.id,
        },
      });
    }
  })
  useEffect(() => {
    if (lastEleRef.current) {
      lastEleRef.current.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
      });
    }
  }, [conversation]);

  const chat = [
    ...conversation.messages,
    {
      content:
        "مرحبا بكم في نظام الدردشة الآلي لوزارة التعليم العالي والبحث العلمي",
      is_user: false,
    },
  ];

  const [message, setMessage] = useState("");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!message.trim()) return;

    queryClient.setQueryData<Chat>(["chat", id], (chat) => {
      if (!chat) return chat;
      return {
        ...chat,
        messages: [
          { id: crypto.randomUUID(), is_user: true, content: message },
          ...chat.messages,
        ],
      };
    });

    // mutate(message);

    sendMessageStream(message)

    setMessage("");
  };

  return (
    <div
      className="bg-gradient-to-b from-emerald-800 to-emerald-950 overflow-y-clip text-white flex"
      dir="rtl"
    >
      {/* Overlay for mobile when sidebar is open */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-10 lg:hidden"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div
        className={`fixed h-screen right-0 w-[280px] sm:w-[320px] lg:w-64 bg-emerald-900 transform ${
          isSidebarOpen ? "translate-x-0" : "translate-x-full"
        } lg:translate-x-0 transition-transform duration-300 ease-in-out z-20`}
      >
        <div className="p-4 space-y-8 w-full h-full">
          <div className="flex items-center justify-between">
            <h2 className="text-xl font-bold">القائمة</h2>
            <button
              onClick={() => setIsSidebarOpen(false)}
              className="p-2 hover:bg-emerald-800 rounded-lg lg:hidden"
            >
              <ChevronRight className="h-6 w-6" />
            </button>
          </div>

          
            <div className="w-full" >
 <button disabled={isCreatingNewPage} className={`flex w-full cursor-pointer items-center px-2 gap-x-4 hover:bg-emerald-800 py-2 rounded-lg ${isCreatingNewPage ?  "bg-emeraled-800" : ""}`} onClick={() => {
  createNewConversation()
 }} >
              <MessageCirclePlus />  
              {isCreatingNewPage ? <Loader2 className="size-5 text-white animate-spin" /> : <h3 className="text-lg font-semibold">محادثة جديدة</h3>  }
 </button>
              </div>  
          
          <div className="gap-y-4 h-full w-full grid grid-flow-row grid-rows-[auto_1fr_auto_auto]">
            <h4 className="w-full flex items-center gap-3 p-3">
              <History className="h-5 w-5" />
              <span>المحادثات السابقة</span>
            </h4>
            <div className="overflow-y-auto space-y-2 w-full">
              {previousConversations.conversations.map((conv) => (
                <Link
                  className="hover:bg-emerald-800 block rounded-lg p-3 transition-colors w-full"
                  key={conv.id}
                  to="/chat/$id"
                  params={{ id: conv.id }}
                  activeProps={{
                    className: "bg-emerald-800",
                  }}
                >
                  {conv.title}
                </Link>
              ))}
            </div>
            <button
              disabled={isLogingOut}
              onClick={() => {
                console.log("smth");
                logout();
              }}
              className="w-full flex items-center cursor-pointer gap-3 p-3 hover:bg-emerald-800 rounded-lg transition-colors text-red-400"
            >
              <LogOut className="h-5 w-5" />
              <span>تسجيل الخروج</span>
            </button>
            <div className="h-32" />
          </div>
        </div>
      </div>

      <div className="flex-1 h-full lg:mr-64">
        {/* Header */}
        <header className="bg-emerald-900 shadow-lg p-4">
          <div className="container mx-auto">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="flex items-center gap-3 w-full sm:w-auto">
                <button
                  onClick={() => setIsSidebarOpen(true)}
                  className="p-2 hover:bg-emerald-800 rounded-lg transition-colors lg:hidden"
                >
                  <Menu className="h-6 w-6" />
                </button>
                <Building2 className="h-8 w-8 hidden sm:block" />
                <div className="text-center sm:text-right">
                  <h1 className="text-xl sm:text-2xl font-bold">
                    وزارة التعليم العالي والبحث العلمي
                  </h1>
                  <p className="text-emerald-200 text-sm">
                    الجمهورية الجزائرية الديمقراطية الشعبية
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-4">
                <GraduationCap className="h-6 w-6 hidden sm:block" />
                <Book className="h-6 w-6 hidden sm:block" />
                <div className="flex items-center gap-2 p-2 hover:bg-emerald-800 rounded-lg transition-colors">
                  <UserCircle2 className="h-6 w-6" />
                  <span className="text-sm">
                    {user.authenticated === true && user.user.name}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <main className="container mx-auto p-4 flex flex-col h-[calc(100vh-88px)]">
          <div className="flex-1 bg-white/10 rounded-lg p-2 sm:p-4 mb-4 overflow-y-auto">
            <div className="flex flex-col-reverse gap-y-4">
              <div ref={lastEleRef} />
              {/* {isSendingMessage && (
                <div className="flex justify-end" >
                  <div className="animate-pulse shrink-0 h-5 w-5 rounded-full bg-white" />
                </div>)} */}
                {isSendingMessageStream && (
                <div className="flex justify-end" >
                  <div className="animate-pulse shrink-0 h-5 w-5 rounded-full bg-white" />
                </div>)}
              {chat.map((msg, index) => (
                <div
                  key={index}
                  className={`flex ${
                    msg.is_user ? "justify-start" : "justify-end"
                  }`}
                >
                  <div
                    className={`max-w-[90%] sm:max-w-[80%] rounded-lg p-2 sm:p-3 ${
                      msg.is_user
                        ? "bg-emerald-600 text-white"
                        : "bg-white/20 text-white"
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      {!msg.is_user && (
                        <MessageCircle className="shrink-0 h-5 w-5 mt-1" />
                      )}
                      <div className="prose [&>*]:text-white">
                        <ReactMarkdown  >
                        {msg.content}
                        </ReactMarkdown>
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Chat Input */}
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="اكتب سؤالك هنا..."
              className="flex-1 bg-white/10 rounded-lg px-3 sm:px-4 py-2 text-white placeholder-white/50 focus:outline-none focus:ring-2 focus:ring-emerald-500 text-base sm:text-lg"
            />
            <button
              // disabled={isSendingMessage}
              disabled={isSendingMessageStream}
              type="submit"
              className="bg-emerald-600 hover:bg-emerald-700 rounded-lg px-4 sm:px-6 py-2 flex items-center gap-2 transition-colors whitespace-nowrap"
            >
              <span className="hidden sm:inline">إرسال</span>
              <Send className="h-5 w-5" />
            </button>
          </form>
        </main>
      </div>
    </div>
  );
}
