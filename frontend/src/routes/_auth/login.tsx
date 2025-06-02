import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Building2, Mail, Lock, Loader2 } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { kyInstance } from "@/constants";
import { toast } from "sonner";
import type { HTTPError } from "ky";

export const Route = createFileRoute("/_auth/login")({
  component: RouteComponent,
});

export function RouteComponent() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState({
    email: "",
    password: "",
    general: "",
  });

  const navigate = Route.useNavigate();
  const queryClient = useQueryClient();

  const { mutate, isPending } = useMutation({
    mutationFn: () =>
      kyInstance.post(`login`, { json: { email, password } }).json(),
    onSuccess: async () => {
      toast.success("تم تسجيل الدخول بنجاح");
      await queryClient.refetchQueries({ queryKey: ["auth-user"] });
      navigate({ to: "/" });
    },
    onError: async (err: HTTPError) => {
      const errors: { detail: string } = await err.response.json();

      toast.error("فشل تسجيل الدخول");
      setErrors((lastError) => ({ ...lastError, general: errors.detail }));
    },
  });

  const validateForm = () => {
    const newErrors = {
      email: "",
      password: "",
      general: "",
    };

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email)) {
      newErrors.email = "يرجى إدخال بريد إلكتروني صحيح";
    }

    if (password.length < 8) {
      newErrors.password = "يجب أن تتكون كلمة المرور من 8 أحرف على الأقل";
    }

    setErrors(newErrors);
    return !newErrors.email && !newErrors.password;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm()) return;

    mutate();
  };

  return (
    <div
      className="min-h-screen bg-gradient-to-b from-emerald-800 to-emerald-950 flex items-center justify-center p-4"
      dir="rtl"
    >
      <div className="bg-emerald-900/50 p-8 rounded-lg shadow-xl max-w-md w-full backdrop-blur-sm">
        <div className="flex items-center justify-center mb-8 gap-3">
          <Building2 className="h-8 w-8" />
          <h1 className="text-2xl font-bold text-white text-center">
            تسجيل الدخول
          </h1>
        </div>

        {errors.general && (
          <div className="mb-4 p-3 bg-red-500/20 border border-red-500 rounded-lg text-red-200 text-sm text-center">
            {errors.general}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label
              htmlFor="email"
              className="block text-sm font-medium text-emerald-100 mb-2"
            >
              البريد الإلكتروني
            </label>
            <div className="relative">
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={`w-full bg-white/10 border rounded-lg px-4 py-2 pr-10 text-white placeholder-emerald-300 ${
                  errors.email ? "border-red-500" : "border-emerald-600"
                }`}
                placeholder="أدخل بريدك الإلكتروني"
                required
              />
              <Mail className="absolute left-3 top-2.5 h-5 w-5 text-emerald-300" />
            </div>
            {errors.email && (
              <p className="mt-1 text-sm text-red-400">{errors.email}</p>
            )}
          </div>

          <div>
            <label
              htmlFor="password"
              className="block text-sm font-medium text-emerald-100 mb-2"
            >
              كلمة المرور
            </label>
            <div className="relative">
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={`w-full bg-white/10 border rounded-lg px-4 py-2 pr-10 text-white placeholder-emerald-300 ${
                  errors.password ? "border-red-500" : "border-emerald-600"
                }`}
                placeholder="أدخل كلمة المرور"
                required
              />
              <Lock className="absolute left-3 top-2.5 h-5 w-5 text-emerald-300" />
            </div>
            {errors.password && (
              <p className="mt-1 text-sm text-red-400">{errors.password}</p>
            )}
          </div>

          <button
            disabled={isPending}
            type="submit"
            className="w-full flex items-center justify-center bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg px-4 py-2 transition-colors"
          >
            {!isPending ? (
              "تسجيل الدخول"
            ) : (
              <Loader2 className="size-5 animate-spin shrink-0" />
            )}
          </button>
        </form>

        <p className="mt-4 text-center text-emerald-100">
          ليس لديك حساب؟{" "}
          <button
            onClick={() => {
              navigate({ to: "/signup" });
            }}
            className="text-emerald-400 hover:text-emerald-300 transition-colors"
          >
            إنشاء حساب جديد
          </button>
        </p>
      </div>
    </div>
  );
}
