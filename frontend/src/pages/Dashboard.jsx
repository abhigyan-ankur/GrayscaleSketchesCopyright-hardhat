import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import {
  ShieldCheck, ShieldAlert, ShieldX, Link2, Loader2,
  ImageOff, ExternalLink, AlertOctagon, RefreshCw,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { useWallet } from "../context/WalletContext";
import CertificateModal from "../components/CertificateModal";

export default function Dashboard() {
  const { user, isLoggedIn, loading: authLoading, authFetch, linkWallet } = useAuth();
  const { address, isConnected, connectDemo } = useWallet();

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [linking, setLinking] = useState(false);
  const [fetchError, setFetchError] = useState(null);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const res = await authFetch("/api/dashboard");
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || `Request failed (${res.status})`);
      }
      const json = await res.json();
      setData(json);
    } catch (err) {
      setFetchError(err.message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [authFetch]);

  useEffect(() => {
    if (isLoggedIn) fetchDashboard();
  }, [isLoggedIn, fetchDashboard]);

  const handleLinkWallet = async () => {
    if (!address) return;
    setLinking(true);
    await linkWallet(address);
    await fetchDashboard();
    setLinking(false);
  };

  if (authLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-black/40">
        <Loader2 className="animate-spin" size={24} />
      </div>
    );
  }

  if (!isLoggedIn) {
    return (
      <div className="mx-auto max-w-lg rounded-2xl border-4 border-black bg-yellow-200 p-10 text-center shadow-[6px_6px_0_0_#000]">
        <AlertOctagon size={36} className="mx-auto mb-3" />
        <h2 className="mb-2 font-serif text-2xl font-black">Log in to view your dashboard</h2>
        <p className="text-black/60">Your certified artworks and account status live here.</p>
      </div>
    );
  }

  const walletLinked = !!user?.wallet_address;

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-2 flex items-center justify-between">
        <motion.h1
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="font-serif text-5xl font-black text-black"
        >
          Dashboard
        </motion.h1>
        <button
          onClick={fetchDashboard}
          disabled={loading}
          className="flex items-center gap-2 rounded-full border-2 border-black bg-white px-4 py-2 text-sm font-semibold transition-colors hover:bg-black hover:text-white disabled:opacity-50"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>
      <p className="mb-8 text-lg text-black/60">{user?.email}</p>

      {fetchError && (
        <div className="mb-8 rounded-2xl border-4 border-black bg-red-200 px-6 py-4 font-medium shadow-[5px_5px_0_0_#000]">
          Could not load dashboard: {fetchError}
        </div>
      )}

      {data?.is_withheld && (
        <div className="mb-8 flex items-center gap-3 rounded-2xl border-4 border-black bg-red-300 px-6 py-5 shadow-[5px_5px_0_0_#000]">
          <ShieldX size={28} />
          <div>
            <p className="font-serif text-xl font-black">Account withheld</p>
            <p className="text-sm font-medium">
              You've reached 3 flagged submissions and can no longer certify new artwork.
            </p>
          </div>
        </div>
      )}

      {!walletLinked && (
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4 rounded-2xl border-4 border-black bg-blue-100 px-6 py-5 shadow-[5px_5px_0_0_#000]">
          <div className="flex items-center gap-3">
            <Link2 size={24} />
            <div>
              <p className="font-serif text-lg font-black">Link your wallet</p>
              <p className="text-sm text-black/60">
                Connect and link a wallet to see your certified artworks here.
              </p>
            </div>
          </div>
          {!isConnected ? (
            <button
              onClick={() => connectDemo(1)}
              className="rounded-full border-2 border-black bg-black px-5 py-2.5 font-semibold text-white"
            >
              Use Demo Wallet
            </button>
          ) : (
            <button
              onClick={handleLinkWallet}
              disabled={linking}
              className="rounded-full border-2 border-black bg-black px-5 py-2.5 font-semibold text-white disabled:opacity-50"
            >
              {linking ? "Linking..." : "Link this wallet"}
            </button>
          )}
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-3 justify-center py-16 text-black/40">
          <Loader2 className="animate-spin" size={22} /> Loading dashboard...
        </div>
      ) : data ? (
        <>
          <div className="mb-10 grid grid-cols-1 gap-5 sm:grid-cols-3">
            <StatCard
              icon={<ShieldCheck size={26} />}
              label="Artworks Certified"
              value={data.certified_count}
              tone="bg-green-200"
            />
            <StatCard
              icon={<ShieldAlert size={26} />}
              label="Copies of Your Work Caught"
              value={data.copies_caught_count}
              tone="bg-yellow-200"
            />
            <StatCard
              icon={<ShieldX size={26} />}
              label="Your Violations"
              value={`${data.violation_count} / 3`}
              tone={data.violation_count > 0 ? "bg-red-200" : "bg-white"}
            />
          </div>

          <h2 className="mb-4 font-serif text-2xl font-black">Your Certified Artworks</h2>
          {data.my_artworks.length === 0 ? (
            <div className="mb-10 flex flex-col items-center gap-2 rounded-2xl border-4 border-dashed border-black/20 py-16 text-black/40">
              <ImageOff size={32} />
              <p className="font-medium">Nothing certified yet.</p>
            </div>
          ) : (
            <div className="mb-10 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {data.my_artworks.map((entry) => (
                <ArtworkCard key={entry.id} entry={entry} />
              ))}
            </div>
          )}

          {data.copies_of_my_work.length > 0 && (
            <>
              <h2 className="mb-4 font-serif text-2xl font-black">Copy Attempts Caught</h2>
              <div className="flex flex-col gap-3">
                {data.copies_of_my_work.map((attempt, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between rounded-xl border-2 border-black bg-white px-5 py-4"
                  >
                    <div>
                      <p className="font-semibold">"{attempt.attempted_title}"</p>
                      <p className="text-sm text-black/50">
                        submitted by {attempt.attempted_author} —{" "}
                        {new Date(attempt.timestamp).toLocaleDateString()}
                      </p>
                    </div>
                    <span className="rounded-full border-2 border-black bg-red-200 px-3 py-1 text-xs font-bold">
                      {attempt.verdict}
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
        </>
      ) : null}
    </div>
  );
}

function StatCard({ icon, label, value, tone }) {
  return (
    <div className={`rounded-2xl border-4 border-black p-6 shadow-[4px_4px_0_0_#000] ${tone}`}>
      <div className="mb-3">{icon}</div>
      <p className="text-3xl font-black">{value}</p>
      <p className="text-sm font-medium text-black/60">{label}</p>
    </div>
  );
}

function ArtworkCard({ entry }) {
  const [showCert, setShowCert] = useState(false);
  const imageUrl = entry.image_url || null;

  return (
    <>
      <div className="overflow-hidden rounded-2xl border-4 border-black bg-white shadow-[4px_4px_0_0_#000]">
        <div className="aspect-square border-b-4 border-black bg-black/5">
          {imageUrl ? (
            <img src={imageUrl} alt={entry.title} className="h-full w-full object-cover" />
          ) : (
            <div className="flex h-full items-center justify-center text-black/20">
              <ImageOff size={28} />
            </div>
          )}
        </div>
        <div className="p-4">
          <h3 className="font-serif text-lg font-black">{entry.title}</h3>
          <p className="mb-3 text-xs text-black/50">
            Artchain #{entry.id} — {new Date(entry.timestamp).toLocaleDateString()}
          </p>
          <button
            onClick={() => setShowCert(true)}
            className="w-full rounded-full border-2 border-black bg-black py-2 text-sm font-bold text-white transition-colors hover:bg-white hover:text-black"
          >
            View Certificate
          </button>
        </div>
      </div>

      {showCert && <CertificateModal entry={entry} onClose={() => setShowCert(false)} />}
    </>
  );
}