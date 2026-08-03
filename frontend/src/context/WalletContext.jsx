import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { ethers } from "ethers";

// ── Context setup ────────────────────────────────────────────────────────────
const WalletContext = createContext(null);

export function useWallet() {
  const ctx = useContext(WalletContext);
  if (!ctx) throw new Error("useWallet must be used inside <WalletProvider>");
  return ctx;
}

// Polygon Amoy Testnet — must match what the smart contract is deployed to
const AMOY_CHAIN_ID = "0x13882"; // 80002 in hex
const AMOY_PARAMS = {
  chainId: AMOY_CHAIN_ID,
  chainName: "Polygon Amoy Testnet",
  nativeCurrency: { name: "POL", symbol: "POL", decimals: 18 },
  rpcUrls: ["https://80002.rpc.thirdweb.com"],
  blockExplorerUrls: ["https://amoy.polygonscan.com"],
};

export function WalletProvider({ children }) {
  const [address, setAddress] = useState(null);
  const [provider, setProvider] = useState(null);
  const [signer, setSigner] = useState(null);
  const [chainId, setChainId] = useState(null);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState(null);

  const isConnected = !!address;
  const isCorrectNetwork = chainId === AMOY_CHAIN_ID;

  // ── Connect wallet ──────────────────────────────────────────────────────
  const connect = useCallback(async () => {
    setError(null);

    if (!window.ethereum) {
      setError("MetaMask not detected. Please install it from metamask.io");
      return;
    }

    try {
      setConnecting(true);
      const browserProvider = new ethers.BrowserProvider(window.ethereum);
      const accounts = await browserProvider.send("eth_requestAccounts", []);
      const network = await browserProvider.getNetwork();
      const walletSigner = await browserProvider.getSigner();

      setProvider(browserProvider);
      setSigner(walletSigner);
      setAddress(accounts[0]);
      setChainId("0x" + network.chainId.toString(16));
    } catch (err) {
      if (err.code === 4001) {
        setError("Connection request rejected.");
      } else {
        setError(err.message || "Failed to connect wallet.");
      }
    } finally {
      setConnecting(false);
    }
  }, []);

  // ── Disconnect (local state only — MetaMask has no real disconnect) ─────
  const disconnect = useCallback(() => {
    setAddress(null);
    setProvider(null);
    setSigner(null);
    setChainId(null);
  }, []);

  // ── Switch to / add Polygon Amoy network ─────────────────────────────────
  const switchToAmoy = useCallback(async () => {
    if (!window.ethereum) return;
    try {
      await window.ethereum.request({
        method: "wallet_switchEthereumChain",
        params: [{ chainId: AMOY_CHAIN_ID }],
      });
    } catch (switchError) {
      // 4902 = chain not added to MetaMask yet
      if (switchError.code === 4902) {
        try {
          await window.ethereum.request({
            method: "wallet_addEthereumChain",
            params: [AMOY_PARAMS],
          });
        } catch (addError) {
          setError("Failed to add Polygon Amoy network: " + addError.message);
        }
      } else {
        setError("Failed to switch network: " + switchError.message);
      }
    }
  }, []);

  // ── Listen for account/network changes in MetaMask ──────────────────────
  useEffect(() => {
    if (!window.ethereum) return;

    const handleAccountsChanged = (accounts) => {
      if (accounts.length === 0) {
        disconnect();
      } else {
        setAddress(accounts[0]);
      }
    };

    const handleChainChanged = (newChainId) => {
      setChainId(newChainId);
      // Reload signer on chain change to avoid stale provider issues
      window.location.reload();
    };

    window.ethereum.on("accountsChanged", handleAccountsChanged);
    window.ethereum.on("chainChanged", handleChainChanged);

    return () => {
      window.ethereum.removeListener("accountsChanged", handleAccountsChanged);
      window.ethereum.removeListener("chainChanged", handleChainChanged);
    };
  }, [disconnect]);

  // ── Auto-reconnect on page load if already authorized ───────────────────
  useEffect(() => {
    if (!window.ethereum) return;
    window.ethereum
      .request({ method: "eth_accounts" })
      .then((accounts) => {
        if (accounts.length > 0) connect();
      })
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const value = {
    address,
    provider,
    signer,
    chainId,
    isConnected,
    isCorrectNetwork,
    connecting,
    error,
    connect,
    disconnect,
    switchToAmoy,
  };

  return <WalletContext.Provider value={value}>{children}</WalletContext.Provider>;
}