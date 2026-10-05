import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../store/authStore";
import { MessageCircle, Eye, EyeOff, Loader2 } from "lucide-react";

type Tab = "login" | "register";

export function LoginPage() {
  const navigate = useNavigate();
  const login = useAuthStore((state) => state.login);
  const register = useAuthStore((state) => state.register);

  const [tab, setTab] = useState<Tab>("login");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  // Login form state
  const [loginEmail, setLoginEmail] = useState("");
  const [loginPassword, setLoginPassword] = useState("");

  // Register form state
  const [regEmail, setRegEmail] = useState("");
  const [regUsername, setRegUsername] = useState("");
  const [regPassword, setRegPassword] = useState("");
  const [regConfirm, setRegConfirm] = useState("");

  const switchTab = (t: Tab) => {
    setTab(t);
    setError(null);
  };

  const validateEmail = (email: string) =>
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

  const handleLogin = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!validateEmail(loginEmail)) {
      setError("Email không hợp lệ");
      return;
    }
    if (loginPassword.length < 8) {
      setError("Mật khẩu phải có ít nhất 8 ký tự");
      return;
    }

    setIsLoading(true);
    try {
      await login(loginEmail, loginPassword);
      navigate("/chat");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Đăng nhập thất bại");
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!validateEmail(regEmail)) {
      setError("Email không hợp lệ");
      return;
    }
    if (regUsername.trim().length < 3) {
      setError("Tên người dùng phải có ít nhất 3 ký tự");
      return;
    }
    if (regPassword.length < 8) {
      setError("Mật khẩu phải có ít nhất 8 ký tự");
      return;
    }
    if (regPassword !== regConfirm) {
      setError("Mật khẩu xác nhận không khớp");
      return;
    }

    setIsLoading(true);
    try {
      await register(regEmail, regUsername.trim(), regPassword);
      navigate("/chat");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Đăng ký thất bại");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center p-4">
      {/* Ambient glow */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -left-40 w-96 h-96 bg-blue-600/20 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -right-40 w-96 h-96 bg-purple-600/20 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Logo / Brand */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-2xl mb-4 shadow-lg shadow-blue-500/25">
            <MessageCircle className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-white tracking-tight">ChatApp</h1>
          <p className="text-gray-400 mt-1 text-sm">Kết nối mọi người, mọi nơi</p>
        </div>

        {/* Card */}
        <div className="bg-[#16161e]/80 backdrop-blur-xl border border-white/10 rounded-2xl shadow-2xl overflow-hidden">
          {/* Tab switcher */}
          <div className="flex border-b border-white/10">
            <button
              id="tab-login"
              onClick={() => switchTab("login")}
              className={`flex-1 py-4 text-sm font-semibold transition-all duration-200 ${
                tab === "login"
                  ? "text-white border-b-2 border-blue-500 bg-blue-500/5"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              Đăng nhập
            </button>
            <button
              id="tab-register"
              onClick={() => switchTab("register")}
              className={`flex-1 py-4 text-sm font-semibold transition-all duration-200 ${
                tab === "register"
                  ? "text-white border-b-2 border-blue-500 bg-blue-500/5"
                  : "text-gray-500 hover:text-gray-300"
              }`}
            >
              Đăng ký
            </button>
          </div>

          <div className="p-8">
            {/* Error banner */}
            {error && (
              <div className="mb-5 px-4 py-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-400 text-sm text-center">
                {error}
              </div>
            )}

            {/* ─── LOGIN FORM ─── */}
            {tab === "login" && (
              <form onSubmit={handleLogin} className="space-y-5">
                <div>
                  <label htmlFor="login-email" className="block text-xs font-medium text-gray-400 mb-2 uppercase tracking-wider">
                    Email
                  </label>
                  <input
                    id="login-email"
                    type="email"
                    autoComplete="email"
                    required
                    value={loginEmail}
                    onChange={(e) => setLoginEmail(e.target.value)}
                    placeholder="you@example.com"
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-600 text-sm focus:outline-none focus:border-blue-500/60 focus:bg-blue-500/5 transition-all"
                  />
                </div>

                <div>
                  <label htmlFor="login-password" className="block text-xs font-medium text-gray-400 mb-2 uppercase tracking-wider">
                    Mật khẩu
                  </label>
                  <div className="relative">
                    <input
                      id="login-password"
                      type={showPassword ? "text" : "password"}
                      autoComplete="current-password"
                      required
                      value={loginPassword}
                      onChange={(e) => setLoginPassword(e.target.value)}
                      placeholder="••••••••"
                      className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 pr-11 text-white placeholder-gray-600 text-sm focus:outline-none focus:border-blue-500/60 focus:bg-blue-500/5 transition-all"
                    />
                    <button
                      type="button"
                      tabIndex={-1}
                      onClick={() => setShowPassword((v) => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors"
                    >
                      {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                    </button>
                  </div>
                </div>

                <button
                  id="btn-login"
                  type="submit"
                  disabled={isLoading}
                  className="w-full mt-2 py-3 rounded-xl bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-semibold text-sm transition-all duration-200 shadow-lg shadow-blue-500/20 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {isLoading ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Đang đăng nhập...
                    </>
                  ) : (
                    "Đăng nhập"
                  )}
                </button>
              </form>
            )}

            {/* ─── REGISTER FORM ─── */}
            {tab === "register" && (
              <form onSubmit={handleRegister} className="space-y-4">
                <div>
                  <label htmlFor="reg-email" className="block text-xs font-medium text-gray-400 mb-2 uppercase tracking-wider">
                    Email
                  </label>
                  <input
                    id="reg-email"
                    type="email"
                    autoComplete="email"
                    required
                    value={regEmail}
                    onChange={(e) => setRegEmail(e.target.value)}
                    placeholder="you@example.com"
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-600 text-sm focus:outline-none focus:border-blue-500/60 focus:bg-blue-500/5 transition-all"
                  />
                </div>

                <div>
                  <label htmlFor="reg-username" className="block text-xs font-medium text-gray-400 mb-2 uppercase tracking-wider">
                    Tên người dùng
                  </label>
                  <input
                    id="reg-username"
                    type="text"
                    autoComplete="username"
                    required
                    value={regUsername}
                    onChange={(e) => setRegUsername(e.target.value)}
                    placeholder="username"
                    className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-600 text-sm focus:outline-none focus:border-blue-500/60 focus:bg-blue-500/5 transition-all"
                  />
                </div>

                <div>
                  <label htmlFor="reg-password" className="block text-xs font-medium text-gray-400 mb-2 uppercase tracking-wider">
                    Mật khẩu
                  </label>
                  <div className="relative">
                    <input
                      id="reg-password"
                      type={showPassword ? "text" : "password"}
                      autoComplete="new-password"
                      required
                      value={regPassword}
                      onChange={(e) => setRegPassword(e.target.value)}
                      placeholder="Ít nhất 8 ký tự"
                      className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 pr-11 text-white placeholder-gray-600 text-sm focus:outline-none focus:border-blue-500/60 focus:bg-blue-500/5 transition-all"
                    />
                    <button
                      type="button"
                      tabIndex={-1}
                      onClick={() => setShowPassword((v) => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors"
                    >
                      {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                    </button>
                  </div>
                </div>

                <div>
                  <label htmlFor="reg-confirm" className="block text-xs font-medium text-gray-400 mb-2 uppercase tracking-wider">
                    Xác nhận mật khẩu
                  </label>
                  <div className="relative">
                    <input
                      id="reg-confirm"
                      type={showConfirm ? "text" : "password"}
                      autoComplete="new-password"
                      required
                      value={regConfirm}
                      onChange={(e) => setRegConfirm(e.target.value)}
                      placeholder="Nhập lại mật khẩu"
                      className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 pr-11 text-white placeholder-gray-600 text-sm focus:outline-none focus:border-blue-500/60 focus:bg-blue-500/5 transition-all"
                    />
                    <button
                      type="button"
                      tabIndex={-1}
                      onClick={() => setShowConfirm((v) => !v)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300 transition-colors"
                    >
                      {showConfirm ? <EyeOff size={17} /> : <Eye size={17} />}
                    </button>
                  </div>
                </div>

                <button
                  id="btn-register"
                  type="submit"
                  disabled={isLoading}
                  className="w-full mt-2 py-3 rounded-xl bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 text-white font-semibold text-sm transition-all duration-200 shadow-lg shadow-purple-500/20 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {isLoading ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Đang đăng ký...
                    </>
                  ) : (
                    "Tạo tài khoản"
                  )}
                </button>
              </form>
            )}
          </div>
        </div>

        <p className="text-center text-xs text-gray-600 mt-6">
          © 2025 ChatApp. Bảo mật · Điều khoản
        </p>
      </div>
    </div>
  );
}
