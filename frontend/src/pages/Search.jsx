import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { SearchIcon, ShieldCheck, ShieldAlert, ShieldX, Loader2 } from "lucide-react";

const API_BASE = "http://localhost:8000";

export default function Search() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState(null);

  const handleFile = (f) => {
    if (!f) return;
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setResult(null);
  };

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setDragActive(false);
    const f = e.dataTransfer.files?.[0];
    if (f) handleFile(f);
  }, []);

  const runCheck = async () => {
    if (!file) return;
    setChecking(true);
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE}/api/check`, {
        method: "POST",
        body: formData,
      });
      const data = await res.json();
      setResult(data);
    } catch (err) {
      setResult({ status: "ERROR", reason: err.message });
    } finally {
      setChecking(false);
    }
  };

  const reset = () => {
    setFile(null);
    setPreview(null);
    setResult(null);
  };

  return (
    <div className="mx-auto max-w-3xl">
      <motion.h1
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-2 font-serif text-5xl font-black text-black"
      >
        Verify an artwork
      </motion.h1>
      <p className="mb-10 text-lg text-black/60">
        Check if a sketch is already registered — no certification, just a lookup.
      </p>

      <label
        onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
        onDragLeave={() => setDragActive(false)}
        onDrop={onDrop}
        className={`relative flex h-72 cursor-pointer flex-col items-center justify-center rounded-2xl border-4 border-dashed transition-all ${
          dragActive
            ? "border-black bg-black/5 scale-[1.01]"
            : "border-black/30 bg-white hover:border-black/60"
        }`}
      >
        <input
          type="file"
          accept="image/*"
          className="hidden"
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
        {preview ? (
          <img src={preview} alt="preview" className="h-full w-full rounded-xl object-contain p-3" />
        ) : (
          <>
            <SearchIcon size={40} className="mb-3 text-black/40" />
            <p className="font-semibold text-black/70">Drop a sketch to verify</p>
            <p className="text-sm text-black/40">or click to browse</p>
          </>
        )}
      </label>

      <motion.button
        whileHover={file ? { scale: 1.02 } : {}}
        whileTap={file ? { scale: 0.98 } : {}}
        onClick={runCheck}
        disabled={!file || checking}
        className="mt-6 flex w-full items-center justify-center gap-2 rounded-full border-2 border-black bg-black py-4 font-bold text-[#f4f1ea] shadow-[4px_4px_0_0_#000] transition-all hover:shadow-[2px_2px_0_0_#000] disabled:opacity-30 disabled:shadow-none"
      >
        {checking ? (
          <>
            <Loader2 className="animate-spin" size={18} />
            Checking registry and blockchain...
          </>
        ) : (
          "Verify"
        )}
      </motion.button>

      <AnimatePresence>
        {result && <ResultPanel result={result} onReset={reset} />}
      </AnimatePresence>
    </div>
  );
}

function ResultPanel({ result, onReset }) {
  const noMatch = result.status === "NO_MATCH_FOUND";
  const flagged = result.status === "FLAGGED_FOR_REVIEW";
  const matched = result.status === "REJECTED";

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className={`mt-8 rounded-2xl border-4 border-black p-8 shadow-[6px_6px_0_0_#000] ${
        noMatch ? "bg-blue-100" : flagged ? "bg-yellow-200" : "bg-red-200"
      }`}
    >
      <div className="mb-4 flex items-center gap-3">
        {noMatch && <ShieldX size={32} />}
        {flagged && <ShieldAlert size={32} />}
        {matched && <ShieldCheck size={32} />}
        <h2 className="font-serif text-3xl font-black">
          {noMatch && "No match found"}
          {flagged && "Similar artwork found"}
          {matched && "Match found — already registered"}
        </h2>
      </div>

      {noMatch && (
        <p className="font-medium">
          This artwork doesn't match anything currently registered. It would be
          treated as original if submitted for certification.
        </p>
      )}

      {(flagged || matched) && result.matched_with && (
        <div className="grid gap-2 font-mono text-sm">
          <Row label="Title" value={result.matched_with.title} />
          <Row label="Author" value={result.matched_with.author} />
          {result.matched_with.registered_on && (
            <Row label="Registered" value={new Date(result.matched_with.registered_on).toLocaleString()} />
          )}
          {result.sift_inliers != null && (
            <Row
              label="Confidence"
              value={`${result.sift_inliers} SIFT matches (${((result.inlier_ratio || 0) * 100).toFixed(0)}% geometric consistency)`}
            />
          )}
          {result.matched_with.image_url && (
            <a
              href={result.matched_with.image_url}
              target="_blank"
              rel="noreferrer"
              className="mt-2 underline hover:no-underline"
            >
              View original artwork →
            </a>
          )}
        </div>
      )}

      <button
        onClick={onReset}
        className="mt-6 rounded-full border-2 border-black bg-white px-5 py-2 font-semibold hover:bg-black hover:text-white transition-colors"
      >
        Check another
      </button>
    </motion.div>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex gap-2">
      <span className="w-28 shrink-0 font-bold">{label}:</span>
      <span className="truncate">{value}</span>
    </div>
  );
}