import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { Mail, Lock, LogIn, UserPlus } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login, signup, error } = useAuth();
  const navigate = useNavigate();

  const [mode, setMode] = useState("login"); // "login" | "signup"
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    const ok = mode === "login" ? await login(email, password) : await signup(email, password);
    setSubmitting(false);
    if (ok) navigate("/dashboard");
  };

  return (
    <div className="mx-auto flex max-w-md flex-col items-center">
      <motion.div
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="w-full"
      >
        <h1 className="mb-2 text-center font-serif text-4xl font-black text-black">
          {mode === "login" ? "Welcome back" : "Join Artchain"}
        </h1>
        <p className="mb-8 text-center text-black/60">
          {mode === "login"
            ? "Log in to certify and manage your artwork."
            : "Create an account to start protecting your work."}
        </p>

        <form
          onSubmit={submit}
          className="rounded-2xl border-4 border-black bg-white p-8 shadow-[6px_6px_0_0_#000]"
        >
          <div className="mb-5">
            <label className="mb-1 flex items-center gap-2 text-sm font-bold uppercase tracking-wide text-black/60">
              <Mail size={14} /> Email
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full rounded-lg border-2 border-black px-4 py-3 font-medium outline-none focus:bg-yellow-50"
            />
          </div>

          <div className="mb-2">
            <label className="mb-1 flex items-center gap-2 text-sm font-bold uppercase tracking-wide text-black/60">
              <Lock size={14} /> Password
            </label>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
              className="w-full rounded-lg border-2 border-black px-4 py-3 font-medium outline-none focus:bg-yellow-50"
            />
          </div>

          {error && <p className="mb-4 mt-2 text-sm font-semibold text-red-600">{error}</p>}

          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            type="submit"
            disabled={submitting}
            className="mt-4 flex w-full items-center justify-center gap-2 rounded-full border-2 border-black bg-black py-3.5 font-bold text-[#f4f1ea] shadow-[4px_4px_0_0_#000] transition-all hover:shadow-[2px_2px_0_0_#000] disabled:opacity-50"
          >
            {mode === "login" ? <LogIn size={18} /> : <UserPlus size={18} />}
            {submitting ? "Please wait..." : mode === "login" ? "Log In" : "Create Account"}
          </motion.button>
        </form>

        <p className="mt-6 text-center text-sm text-black/60">
          {mode === "login" ? "Don't have an account?" : "Already have an account?"}{" "}
          <button
            onClick={() => setMode(mode === "login" ? "signup" : "login")}
            className="font-bold underline hover:no-underline"
          >
            {mode === "login" ? "Sign up" : "Log in"}
          </button>
        </p>
      </motion.div>
    </div>
  );
}