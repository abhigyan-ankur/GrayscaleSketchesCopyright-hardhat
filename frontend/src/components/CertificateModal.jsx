import { motion, AnimatePresence } from "framer-motion";
import { X, ShieldCheck, ExternalLink } from "lucide-react";

export default function CertificateModal({ entry, onClose }) {
  if (!entry) return null;

  const imageUrl = entry.image_url || null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4"
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.9, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: 20 }}
          onClick={(e) => e.stopPropagation()}
          className="relative w-full max-w-lg overflow-hidden rounded-2xl border-4 border-black bg-[#f4f1ea] shadow-[8px_8px_0_0_#000]"
        >
          <button
            onClick={onClose}
            className="absolute right-4 top-4 z-10 flex h-9 w-9 items-center justify-center rounded-full border-2 border-black bg-white hover:bg-black hover:text-white transition-colors"
          >
            <X size={16} />
          </button>

          {imageUrl && (
            <div className="aspect-video w-full border-b-4 border-black bg-black/5">
              <img src={imageUrl} alt={entry.title} className="h-full w-full object-cover" />
            </div>
          )}

          <div className="p-8">
            <div className="mb-4 flex items-center gap-2">
              <ShieldCheck size={22} className="text-green-700" />
              <span className="rounded-full border-2 border-black bg-green-200 px-3 py-1 text-xs font-black uppercase tracking-wide">
                Certified on Artchain
              </span>
            </div>

            <h2 className="mb-1 font-serif text-3xl font-black">{entry.title}</h2>
            <p className="mb-6 text-black/60">by {entry.author}</p>

            <div className="flex flex-col gap-3 border-t-2 border-dashed border-black/20 pt-5 font-mono text-sm">
              <Field label="Certificate ID" value={`ARTCHAIN-${String(entry.id).padStart(6, "0")}`} />
              <Field label="pHash" value={entry.phash} />
              {entry.image_cid && (
                <Field
                  label="Image ID"
                  value={entry.image_cid}
                  link={entry.image_url || undefined}
                />
              )}
              {entry.onchain_id != null && (
                <Field label="On-chain ID" value={`#${entry.onchain_id}`} />
              )}
              {entry.tx_hash && <Field label="Blockchain Tx" value={entry.tx_hash} />}
              <Field
                label="Registered"
                value={new Date(entry.timestamp).toLocaleString(undefined, {
                  dateStyle: "long",
                  timeStyle: "short",
                })}
              />
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

function Field({ label, value, link }) {
  return (
    <div className="flex justify-between gap-4">
      <span className="shrink-0 font-bold text-black/50">{label}</span>
      {link ? (
        <a
          href={link}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1 truncate text-right underline hover:no-underline"
        >
          <span className="truncate">{value}</span>
          <ExternalLink size={12} className="shrink-0" />
        </a>
      ) : (
        <span className="truncate text-right">{value}</span>
      )}
    </div>
  );
}