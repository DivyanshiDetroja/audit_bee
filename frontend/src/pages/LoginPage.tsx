import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/auth";
import { Spinner } from "@/components/Spinner";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await login(email, password);
      // Redirect based on role — auth context will update, let App route
      navigate("/", { replace: true });
    } catch (err: unknown) {
      setError(
        err instanceof Error && err.message !== "Request failed"
          ? err.message
          : "Incorrect email or password."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#F7F8FA] flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Brand */}
        <div className="flex items-center gap-3 mb-8">
          <div className="w-9 h-9 rounded-lg bg-[#1F2A44] flex items-center justify-center shrink-0">
            <svg className="w-5 h-5 text-white" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
              <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h4a1 1 0 100-2H7z" clipRule="evenodd" />
            </svg>
          </div>
          <div>
            <p className="text-base font-semibold text-[#16181D] leading-tight">Audit Bee</p>
            <p className="text-xs text-[#5B6270]">AI document intake · Acme CPA Partners</p>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-[#E6E8EC] shadow-card p-6">
          <h1 className="text-lg font-semibold text-[#16181D] mb-1">Sign in</h1>
          <p className="text-sm text-[#5B6270] mb-6">Use your firm credentials.</p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-[#16181D] mb-1.5">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@acmecpa.com"
                className="w-full rounded-md border border-[#E6E8EC] bg-white px-3 py-2 text-sm text-[#16181D] placeholder:text-[#5B6270] focus:outline-none focus:ring-2 focus:ring-[#3B6CF6] focus:border-transparent transition-shadow"
              />
            </div>
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-[#16181D] mb-1.5">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full rounded-md border border-[#E6E8EC] bg-white px-3 py-2 text-sm text-[#16181D] placeholder:text-[#5B6270] focus:outline-none focus:ring-2 focus:ring-[#3B6CF6] focus:border-transparent transition-shadow"
              />
            </div>

            {error && (
              <p role="alert" className="text-xs text-rose-600 bg-rose-50 border border-rose-200 rounded-md px-3 py-2">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 rounded-md bg-[#1F2A44] text-white text-sm font-medium px-4 py-2.5 hover:bg-[#283552] focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3B6CF6] focus-visible:ring-offset-2 transition-colors disabled:opacity-60"
            >
              {loading && <Spinner className="h-4 w-4" />}
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </form>
        </div>

        <p className="mt-6 text-center text-xs text-[#5B6270]">
          Demo credentials — admin: <span className="font-mono">admin@acmecpa.com</span> / <span className="font-mono">Admin1234!</span>
        </p>
      </div>
    </div>
  );
}
