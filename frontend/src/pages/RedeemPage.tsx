import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { AlertCircle } from "lucide-react";
import { setTokens, api } from "@/api";
import { useAuth } from "@/auth";
import { Spinner } from "@/components/Spinner";

export function RedeemPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();
  const { reload } = useAuth();

  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F7F8FA] px-4">
        <div className="flex items-center gap-2 text-sm text-rose-600">
          <AlertCircle className="h-4 w-4 shrink-0" />
          Invalid or missing invite token.
        </div>
      </div>
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const { access_token, refresh_token } = await api.redeemInvite(token, name.trim(), password);
      setTokens(access_token, refresh_token);
      await reload();
      navigate("/portal", { replace: true });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Invite redemption failed. The link may have expired.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#F7F8FA] px-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2.5 mb-8">
          <div className="w-8 h-8 rounded-md bg-[#3B6CF6] flex items-center justify-center">
            <svg className="w-4 h-4 text-white" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h4a1 1 0 100-2H7z" clipRule="evenodd" />
            </svg>
          </div>
          <span className="text-lg font-semibold text-[#1F2A44]">Audit Bee</span>
        </div>

        <h1 className="text-xl font-semibold text-[#16181D] mb-1">Set up your account</h1>
        <p className="text-sm text-[#5B6270] mb-6">
          Your CPA has invited you to Audit Bee. Create a password to access your portal.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="name" className="block text-xs font-medium text-[#16181D] mb-1.5">
              Your name
            </label>
            <input
              id="name"
              type="text"
              required
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Jane Smith"
              className="w-full rounded-md border border-[#E6E8EC] px-3 py-2 text-sm text-[#16181D] placeholder:text-[#A0A6B3] focus:outline-none focus:ring-2 focus:ring-[#3B6CF6] focus:border-transparent"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-xs font-medium text-[#16181D] mb-1.5">
              Password
            </label>
            <input
              id="password"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              className="w-full rounded-md border border-[#E6E8EC] px-3 py-2 text-sm text-[#16181D] placeholder:text-[#A0A6B3] focus:outline-none focus:ring-2 focus:ring-[#3B6CF6] focus:border-transparent"
            />
          </div>

          <div>
            <label htmlFor="confirm" className="block text-xs font-medium text-[#16181D] mb-1.5">
              Confirm password
            </label>
            <input
              id="confirm"
              type="password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="Repeat password"
              className="w-full rounded-md border border-[#E6E8EC] px-3 py-2 text-sm text-[#16181D] placeholder:text-[#A0A6B3] focus:outline-none focus:ring-2 focus:ring-[#3B6CF6] focus:border-transparent"
            />
          </div>

          {error && (
            <div className="flex items-center gap-1.5 text-sm text-rose-600 bg-rose-50 border border-rose-200 rounded-md px-3 py-2">
              <AlertCircle className="h-4 w-4 shrink-0" />
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading || !name.trim() || !password || !confirm}
            className="w-full flex items-center justify-center gap-2 rounded-md bg-[#3B6CF6] text-white text-sm font-medium py-2.5 hover:bg-[#2f5ed4] disabled:opacity-50 disabled:cursor-not-allowed transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-[#3B6CF6] focus-visible:ring-offset-2"
          >
            {loading && <Spinner className="h-4 w-4 text-white" />}
            Create account & sign in
          </button>
        </form>
      </div>
    </div>
  );
}
