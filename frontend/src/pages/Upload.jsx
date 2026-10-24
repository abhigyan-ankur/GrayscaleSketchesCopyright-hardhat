import { useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Upload as UploadIcon, CheckCircle2, XCircle, AlertTriangle, Loader2 } from "lucide-react";
import { useWallet } from "../context/WalletContext";
import { useAuth } from "../context/AuthContext";
import { registerOnChain } from "../contract";

export default function Upload() {
  const { address, signer, isConnected, isCorrectNetwork } = useWallet();
  const { isLoggedIn, authFetch } = useAuth();

  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [title, setTitle] = useState("");
  const [author, setAuthor] = useState("");
  const [dragActive, setDragActive] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [statusText, setStatusText] = useState("");
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

  const canSubmit = file && title.trim() && author.trim() && !submitting && isLoggedIn;

  const submit = async () => {
    if (!canSubmit) return;
    setSubmitting(true);
    setResult(null);

    try {
      // ── Step 1: Detection + IPFS upload (backend, no blockchain write) ──
      setStatusText("Checking for plagiarism and uploading to IPFS...");
      const formData = new FormData();
      formData.append("file", file);
      formData.append("title", title);
      formData.append("author", author);

      const prepRes = await authFetch("/api/prepare", { method: "POST", body: formData });
      const prepData = await prepRes.json();

      if (!prepRes.ok) {
        setResult({ status: "ERROR", reason: prepData.detail || "Request failed." });
        return;
      }

      if (prepData.status !== "CERTIFIED") {
        setResult(prepData);
        return;
      }

      // ── Step 2: Sign the blockchain transaction via MetaMask ────────────
      setStatusText("Waiting for you to confirm in MetaMask...");
      const cert = prepData.certificate;
      const { txHash, onchainId } = await registerOnChain(signer, {
        title,
        author,
        phash: cert.phash,
        imageCid: cert.image_cid,
        metadataCid: cert.metadata_cid,
      });

      // ── Step 3: Confirm with backend — patch the registry entry ─────────
      setStatusText("Finalizing certificate...");
      const confirmRes = await authFetch("/api/confirm", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entry_id: cert.id,
          tx_hash: txHash,
          onchain_id: onchainId,
          owner_address: address,
        }),
      });
      const confirmedEntry = await confirmRes.json();

      if (!confirmRes.ok) {
        setResult({ status: "ERROR", reason: confirmedEntry.detail || "Could not finalize certificate." });
        return;
      }

      setResult({ status: "CERTIFIED", certificate: confirmedEntry });
    } catch (err) {
      setResult({ status: "ERROR", reason: err.message || "Transaction failed or was rejected." });
    } finally {
      setSubmitting(false);
      setStatusText("");
    }
  };

  const reset = () => {
    setFile(null);
    setPreview(null);
    setTitle("");
    setAuthor("");
    setResult(null);
  };

  return (
    <div className="mx-auto max-w-4xl">
      <motion.h1
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-2 font-serif text-5xl font-black text-black"
      >
        Certify your work
      </motion.h1>
      <p className="mb-10 text-lg text-black/60">
        Upload a sketch to check it against every registered work and certify it on the local blockchain.
      </p>

      {!isLoggedIn && (
        <div className="mb-6 flex items-center gap-3 rounded-xl border-2 border-black bg-yellow-200 px-5 py-4">
          <AlertTriangle size={20} />
          <span className="font-medium">Log in to your Artchain account before registering an artwork.</span>
        </div>
      )}

      {isLoggedIn && !isConnected && (
        <div className="mb-6 flex items-center gap-3 rounded-xl border-2 border-black bg-yellow-200 px-5 py-4">
          <AlertTriangle size={20} />
          <span className="font-medium">Pick a wallet in the top bar (Demo Wallet or MetaMask) to sign the certification transaction.</span>
        </div>
      )}

      {isLoggedIn && isConnected && !isCorrectNetwork && (
        <div className="mb-6 flex items-center gap-3 rounded-xl border-2 border-black bg-yellow-200 px-5 py-4">
          <AlertTriangle size={20} />
          <span className="font-medium">Switch MetaMask to the Hardhat Local network (button in the top bar) to continue.</span>
        </div>
      )}

      <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
        <div>
          <label
            onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
            onDragLeave={() => setDragActive(false)}
            onDrop={onDrop}
            className={`relative flex h-80 cursor-pointer flex-col items-center justify-center rounded-2xl border-4 border-dashed transition-all ${
              dragActive
                ? "border-black bg-black/5 scale-[1.02]"
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
                <UploadIcon size={40} className="mb-3 text-black/40" />
                <p className="font-semibold text-black/70">Drop your sketch here</p>
                <p className="text-sm text-black/40">or click to browse</p>
              </>
            )}
          </label>
        </div>

        <div className="flex flex-col gap-5">
          <div>
            <label className="mb-1 block text-sm font-bold uppercase tracking-wide text-black/60">
              Title
            </label>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Midnight River Sketch"
              className="w-full rounded-lg border-2 border-black px-4 py-3 font-medium outline-none focus:bg-yellow-50"
            />
          </div>

          <div>
            <label className="mb-1 block text-sm font-bold uppercase tracking-wide text-black/60">
              Artist Name
            </label>
            <input
              value={author}
              onChange={(e) => setAuthor(e.target.value)}
              placeholder="Your name"
              className="w-full rounded-lg border-2 border-black px-4 py-3 font-medium outline-none focus:bg-yellow-50"
            />
          </div>

          {address && (
            <div>
              <label className="mb-1 block text-sm font-bold uppercase tracking-wide text-black/60">
                Wallet (owner identity)
              </label>
              <div className="rounded-lg border-2 border-black/20 bg-black/5 px-4 py-3 font-mono text-sm">
                {address}
              </div>
            </div>
          )}

          <motion.button
            whileHover={canSubmit ? { scale: 1.02 } : {}}
            whileTap={canSubmit ? { scale: 0.98 } : {}}
            onClick={submit}
            disabled={!canSubmit || !isConnected || !isCorrectNetwork}
            className="mt-2 flex items-center justify-center gap-2 rounded-full border-2 border-black bg-black py-4 font-bold text-[#f4f1ea] shadow-[4px_4px_0_0_#000] transition-all hover:shadow-[2px_2px_0_0_#000] disabled:opacity-30 disabled:shadow-none"
          >
            {submitting ? (
              <>
                <Loader2 className="animate-spin" size={18} />
                {statusText || "Processing..."}
              </>
            ) : (
              "Certify Artwork"
            )}
          </motion.button>
        </div>
      </div>

      <AnimatePresence>
        {result && <ResultPanel result={result} onReset={reset} />}
      </AnimatePresence>
    </div>
  );
}

function ResultPanel({ result, onReset }) {
  const isCertified = result.status === "CERTIFIED";
  const isReview = result.status === "FLAGGED_FOR_REVIEW";
  const isError = result.status === "ERROR";
  const isRejected = result.status === "REJECTED";

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className={`mt-10 rounded-2xl border-4 border-black p-8 shadow-[6px_6px_0_0_#000] ${
        isCertified ? "bg-green-200" : isReview ? "bg-yellow-200" : "bg-red-200"
      }`}
    >
      <div className="mb-4 flex items-center gap-3">
        {isCertified && <CheckCircle2 size={32} />}
        {isReview && <AlertTriangle size={32} />}
        {(isRejected || isError) && <XCircle size={32} />}
        <h2 className="font-serif text-3xl font-black">
          {isCertified && "Certified on-chain"}
          {isReview && "Flagged for review"}
          {isRejected && "Registration rejected"}
          {isError && "Something went wrong"}
        </h2>
      </div>

      {isCertified && (
        <div className="grid gap-2 font-mono text-sm">
          <Row label="Title" value={result.certificate.title} />
          <Row label="Author" value={result.certificate.author} />
          <Row label="pHash" value={result.certificate.phash} />
          {result.certificate.image_cid && (
            <Row
              label="Image ID"
              value={result.certificate.image_cid}
              link={result.certificate.image_url || undefined}
            />
          )}
          {result.certificate.tx_hash && (
            <Row label="Tx Hash" value={result.certificate.tx_hash} />
          )}
          <p className="mt-3 text-xs font-semibold text-black/60">
            A certificate confirmation email has been sent to your account.
          </p>
        </div>
      )}

      {(isReview || isRejected) && result.matched_with && (
        <div className="grid gap-2 font-mono text-sm">
          <Row label="Matches" value={`"${result.matched_with.title}" by ${result.matched_with.author}`} />
          {result.sift_inliers != null && (
            <Row label="SIFT inliers" value={`${result.sift_inliers} (${((result.inlier_ratio || 0) * 100).toFixed(0)}% match)`} />
          )}
          <p className="mt-3 text-xs font-semibold text-black/60">
            A warning email has been sent to your account.
          </p>
        </div>
      )}

      {(isRejected && !result.matched_with) || isError ? (
        <p className="font-medium">{result.reason}</p>
      ) : null}

      <button
        onClick={onReset}
        className="mt-6 rounded-full border-2 border-black bg-white px-5 py-2 font-semibold hover:bg-black hover:text-white transition-colors"
      >
        Upload another
      </button>
    </motion.div>
  );
}

function Row({ label, value, link }) {
  return (
    <div className="flex gap-2">
      <span className="w-28 shrink-0 font-bold">{label}:</span>
      {link ? (
        <a href={link} target="_blank" rel="noreferrer" className="truncate underline hover:no-underline">
          {value}
        </a>
      ) : (
        <span className="truncate">{value}</span>
      )}
    </div>
  );
}