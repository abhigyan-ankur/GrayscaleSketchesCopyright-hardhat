import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { ExternalLink, ImageOff, Loader2 } from "lucide-react";

const API_BASE = "http://localhost:8000";

export default function Gallery() {
  const [entries, setEntries] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/gallery`)
      .then((res) => res.json())
      .then((data) => {
        setEntries(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return (
    <div className="mx-auto max-w-7xl">
      <motion.h1
        initial={{ opacity: 0, y: -10 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-2 font-serif text-5xl font-black text-black"
      >
        Certified Gallery
      </motion.h1>
      <p className="mb-10 text-lg text-black/60">
        Every artwork permanently registered on-chain, in order of certification.
      </p>

      {loading && (
        <div className="flex items-center gap-3 py-20 justify-center text-black/50">
          <Loader2 className="animate-spin" size={22} />
          Loading gallery...
        </div>
      )}

      {error && (
        <div className="rounded-xl border-2 border-black bg-red-200 px-5 py-4 font-medium">
          Could not load gallery: {error}
        </div>
      )}

      {!loading && !error && entries.length === 0 && (
        <div className="flex flex-col items-center gap-3 rounded-2xl border-4 border-dashed border-black/20 py-24 text-black/40">
          <ImageOff size={40} />
          <p className="font-medium">No artworks registered yet.</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {entries.map((entry, i) => (
          <ArtworkCard key={entry.id} entry={entry} index={i} />
        ))}
      </div>
    </div>
  );
}

function ArtworkCard({ entry, index }) {
  const imageUrl = entry.image_cid
    ? `https://gateway.pinata.cloud/ipfs/${entry.image_cid}`
    : null;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      whileHover={{ y: -4 }}
      className="group overflow-hidden rounded-2xl border-4 border-black bg-white shadow-[5px_5px_0_0_#000] transition-shadow hover:shadow-[8px_8px_0_0_#000]"
    >
      <div className="aspect-square overflow-hidden border-b-4 border-black bg-black/5">
        {imageUrl ? (
          <img
            src={imageUrl}
            alt={entry.title}
            className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full items-center justify-center text-black/20">
            <ImageOff size={32} />
          </div>
        )}
      </div>

      <div className="p-5">
        <h3 className="font-serif text-xl font-black leading-tight">{entry.title}</h3>
        <p className="mb-3 text-sm font-medium text-black/50">by {entry.author}</p>

        <div className="flex flex-col gap-1 font-mono text-xs text-black/40">
          <span>pHash: {entry.phash?.slice(0, 16)}...</span>
          <span>{new Date(entry.timestamp).toLocaleDateString()}</span>
        </div>

        {entry.tx_hash && (
          <a
            href={`https://amoy.polygonscan.com/tx/${entry.tx_hash}`}
            target="_blank"
            rel="noreferrer"
            className="mt-3 inline-flex items-center gap-1 rounded-full border-2 border-black bg-green-200 px-3 py-1 text-xs font-bold hover:bg-green-300 transition-colors"
          >
            On-chain <ExternalLink size={12} />
          </a>
        )}
      </div>
    </motion.div>
  );
}