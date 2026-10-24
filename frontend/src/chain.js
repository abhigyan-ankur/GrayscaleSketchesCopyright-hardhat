// Talks to the backend to learn about the local Hardhat chain, so nothing
// (chain id, contract address, demo accounts) is hardcoded in the frontend.

export const API_BASE = "http://localhost:8000";

let cached = null;

/** Chain id, RPC url, contract address and demo accounts from the backend.
 *  Pass force=true to refresh (this also heals a restarted node). */
export async function getChainInfo(force = false) {
  if (cached && !force) return cached;
  let res;
  try {
    res = await fetch(`${API_BASE}/api/chain/info`);
  } catch {
    throw new Error("Backend is not running. Start it with: uvicorn api:app --port 8000");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || "Local blockchain is not reachable. Is `npx hardhat node` running?");
  }
  cached = data;
  return data;
}

/** The node is reached through the dev server (/rpc is proxied to the Hardhat
 *  node, see vite.config.js), which avoids browser CORS problems. */
export function browserRpcUrl() {
  return `${window.location.origin}/rpc`;
}
