import { Link, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { Wallet, Palette, LogIn, LogOut, User } from "lucide-react";
import { useWallet } from "../context/WalletContext";
import { useAuth } from "../context/AuthContext";

function shortenAddress(addr) {
  if (!addr) return "";
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
}

const navLinks = [
  { label: "Upload", path: "/" },
  { label: "Gallery", path: "/gallery" },
  { label: "Search", path: "/search" },
  { label: "Dashboard", path: "/dashboard" },
];

export default function Navbar() {
  const { address, isConnected, isCorrectNetwork, connecting, error, connect, switchToAmoy } =
    useWallet();
  const { user, isLoggedIn, logout } = useAuth();
  const location = useLocation();

  return (
    <nav className="sticky top-0 z-50 border-b-4 border-black bg-[#f4f1ea]">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 group">
          <motion.div
            whileHover={{ rotate: -12, scale: 1.1 }}
            className="flex h-10 w-10 items-center justify-center rounded-lg bg-black text-[#f4f1ea]"
          >
            <Palette size={20} />
          </motion.div>
          <span className="font-serif text-2xl font-black tracking-tight text-black">
            Artchain
          </span>
        </Link>

        {/* Nav links */}
        <div className="hidden gap-1 md:flex">
          {navLinks.map((link) => {
            const active = location.pathname === link.path;
            return (
              <Link
                key={link.path}
                to={link.path}
                className={`relative px-4 py-2 font-medium transition-colors ${
                  active ? "text-black" : "text-black/50 hover:text-black"
                }`}
              >
                {link.label}
                {active && (
                  <motion.div
                    layoutId="nav-underline"
                    className="absolute -bottom-1 left-4 right-4 h-[3px] bg-black"
                  />
                )}
              </Link>
            );
          })}
        </div>

        {/* Account — primary — then Wallet — secondary */}
        <div className="flex items-center gap-3">
          {/* Login / Account */}
          {isLoggedIn ? (
            <button
              onClick={logout}
              className="flex items-center gap-2 rounded-full border-2 border-black bg-white px-4 py-2 text-sm font-semibold transition-colors hover:bg-black hover:text-white"
            >
              <User size={14} />
              {user?.email?.split("@")[0]}
              <LogOut size={14} />
            </button>
          ) : (
            <Link
              to="/login"
              className="flex items-center gap-2 rounded-full border-2 border-black bg-black px-5 py-2.5 font-semibold text-[#f4f1ea] shadow-[3px_3px_0_0_#000] transition-all hover:shadow-[1px_1px_0_0_#000]"
            >
              <LogIn size={16} />
              Log In
            </Link>
          )}

          {/* Wallet */}
          <div className="flex flex-col items-end gap-1">
            {!isConnected ? (
              <motion.button
                whileHover={{ scale: 1.03 }}
                whileTap={{ scale: 0.97 }}
                onClick={connect}
                disabled={connecting}
                className="flex items-center gap-2 rounded-full border-2 border-black bg-white px-4 py-2 text-sm font-semibold transition-colors hover:bg-black hover:text-white disabled:opacity-50"
              >
                <Wallet size={14} />
                {connecting ? "Connecting..." : "Connect Wallet"}
              </motion.button>
            ) : !isCorrectNetwork ? (
              <button
                onClick={switchToAmoy}
                className="flex items-center gap-2 rounded-full border-2 border-black bg-yellow-300 px-4 py-2 text-sm font-semibold text-black transition-colors hover:bg-yellow-400"
              >
                Switch to Polygon Amoy
              </button>
            ) : (
              <div className="flex items-center gap-2 rounded-full border-2 border-black bg-green-300 px-4 py-2 text-sm font-semibold text-black">
                <span className="h-2 w-2 rounded-full bg-green-700" />
                {shortenAddress(address)}
              </div>
            )}
            {error && <span className="text-xs font-medium text-red-600">{error}</span>}
          </div>
        </div>
      </div>
    </nav>
  );
}