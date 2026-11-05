import { useState, useEffect, useCallback } from "react";
import { motion } from "framer-motion";
import { ShieldAlert, Check, X, Loader2, ImageOff, RefreshCw, AlertOctagon } from "lucide-react";
import { useAuth } from "../context/AuthContext";

export default function Review() {
  const { user, isLoggedIn, loading: authLoading, authFetch } = useAuth();

  const [tab, setTab] = useState("open"); // "open" | "decided"
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await authFetch(`/api/admin/reviews?decision=${tab}`);
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || `Request failed (${res.status})`);
      setItems(data);
    } catch (err) {
      setError(err.message);
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [authFetch, tab]);

  useEffect(() => {
    if (isLoggedIn && user?.is_admin) load();
  }, [isLoggedIn, user, load]);

  const decide = async (item, action) => {
    const question =
      action === "approve"
        ? `Approve "${item.title}" as an original work? It will be registered on the blockchain.`
        : `Reject "${item.title}" as a copy? ${item.submitted_by || "The submitter"} gets a violation strike.`;
    if (!window.confirm(question)) return;

    setBusyId(item.id);
    setError(null);
    try {
      const res = await authFetch(`/api/admin/reviews/${item.id}/${action}`, { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Action failed");
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  };

  if (authLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-black/40">
        <Loader2 className="animate-spin" size={24} />
      </div>
    );
  }

  if (!isLoggedIn || !user?.is_admin) {
    return (
      <div className="mx-auto max-w-lg rounded-2xl border-4 border-black bg-yellow-200 p-10 text-center shadow-[6px_6px_0_0_#000]">
        <AlertOctagon size={36} className="mx-auto mb-3" />
        <h2 className="mb-2 font-serif text-2xl font-black">Admins only</h2>
        <p className="text-black/60">Log in with an admin account to review flagged artworks.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-2 flex items-center justify-between">
        <motion.h1
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="font-serif text-5xl font-black text-black"
        >
          Review queue
        </motion.h1>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-2 rounded-full border-2 border-black bg-white px-4 py-2 text-sm font-semibold transition-colors hover:bg-black hover:text-white disabled:opacity-50"
        >
          <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          Refresh
        </button>
      </div>
      <p className="mb-8 text-lg text-black/60">
        Works the detector found similar to a registered artwork, but not clearly a copy. Approving
        certifies the work. Rejecting confirms a copy and adds a violation strike for the submitter.
      </p>

      <div className="mb-8 flex gap-2">
        {[
          ["open", "Waiting for review"],
          ["decided", "Decided"],
        ].map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`rounded-full border-2 border-black px-5 py-2 text-sm font-bold transition-colors ${
              tab === key ? "bg-black text-white" : "bg-white hover:bg-black/10"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-6 rounded-2xl border-4 border-black bg-red-200 px-6 py-4 font-medium shadow-[5px_5px_0_0_#000]">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center gap-3 py-16 text-black/40">
          <Loader2 className="animate-spin" size={22} /> Loading...
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-2xl border-4 border-dashed border-black/20 py-16 text-black/40">
          <ShieldAlert size={32} />
          <p className="font-medium">
            {tab === "open" ? "Nothing waiting for review." : "No decisions yet."}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-6">
          {items.map((item) => (
            <ReviewCard key={item.id} item={item} busy={busyId === item.id} onDecide={decide} />
          ))}
        </div>
      )}
    </div>
  );
}

function ReviewCard({ item, busy, onDecide }) {
  const decided = !!item.decision;
  const ratio = item.inlier_ratio != null ? `${(item.inlier_ratio * 100).toFixed(0)}%` : "n/a";

  return (
    <div className="grid gap-6 rounded-2xl border-4 border-black bg-white p-6 shadow-[5px_5px_0_0_#000] md:grid-cols-[1fr_1fr_1.2fr]">
      <ImageBox
        label="Submitted"
        url={item.image_url}
        caption={`"${item.title}" by ${item.author}`}
      />
      <ImageBox
        label="Matches registered work"
        url={item.matched?.image_url}
        caption={`"${item.matched?.title}" by ${item.matched?.author}`}
      />

      <div className="flex flex-col gap-3">
        <div className="grid gap-1 font-mono text-sm">
          <Detail label="Submitted by" value={item.submitted_by || "unknown"} />
          <Detail label="When" value={new Date(item.submitted_at).toLocaleString()} />
          <Detail label="SIFT inliers" value={item.sift_inliers} />
          <Detail label="Consistency" value={ratio} />
          <Detail label="Scale" value={item.scale != null ? `${item.scale.toFixed(2)}x` : "n/a"} />
          {item.mirrored && <Detail label="Type" value="Mirrored (flipped)" />}
        </div>

        {decided ? (
          <div
            className={`mt-auto rounded-xl border-2 border-black px-4 py-3 text-sm font-bold ${
              item.decision === "approved" ? "bg-green-200" : "bg-red-200"
            }`}
          >
            {item.decision === "approved" ? "Approved" : "Rejected"} by {item.decided_by}
            <span className="block text-xs font-medium text-black/60">
              {new Date(item.decided_at).toLocaleString()}
            </span>
          </div>
        ) : (
          <div className="mt-auto flex gap-3">
            <button
              onClick={() => onDecide(item, "approve")}
              disabled={busy}
              className="flex flex-1 items-center justify-center gap-2 rounded-full border-2 border-black bg-green-300 py-3 font-bold transition-colors hover:bg-green-400 disabled:opacity-50"
            >
              {busy ? <Loader2 className="animate-spin" size={16} /> : <Check size={16} />}
              Approve
            </button>
            <button
              onClick={() => onDecide(item, "reject")}
              disabled={busy}
              className="flex flex-1 items-center justify-center gap-2 rounded-full border-2 border-black bg-red-300 py-3 font-bold transition-colors hover:bg-red-400 disabled:opacity-50"
            >
              <X size={16} />
              Reject
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function ImageBox({ label, url, caption }) {
  return (
    <div>
      <p className="mb-2 text-xs font-black uppercase tracking-wide text-black/50">{label}</p>
      <div className="aspect-square overflow-hidden rounded-xl border-4 border-black bg-black/5">
        {url ? (
          <img src={url} alt={caption} className="h-full w-full object-contain" />
        ) : (
          <div className="flex h-full items-center justify-center text-black/20">
            <ImageOff size={28} />
          </div>
        )}
      </div>
      <p className="mt-2 truncate text-sm font-medium text-black/70">{caption}</p>
    </div>
  );
}

function Detail({ label, value }) {
  return (
    <div className="flex gap-2">
      <span className="w-28 shrink-0 font-bold text-black/50">{label}</span>
      <span className="truncate">{value}</span>
    </div>
  );
}
