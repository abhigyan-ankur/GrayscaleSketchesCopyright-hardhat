import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { ethers } from "ethers";
import { getChainInfo, browserRpcUrl } from "../chain";

const WalletContext = createContext(null);

export function useWallet() {
  const ctx = useContext(WalletContext);
  if (!ctx) throw new Error("useWallet must be used inside <WalletProvider>");
  return ctx;
}

const STORAGE_KEY = "artchain_wallet";

export function WalletProvider({ children }) {
  const [address, setAddress] = useState(null);
  const [provider, setProvider] = useState(null);
  const [signer, setSigner] = useState(null);
  const [chainId, setChainId] = useState(null);
  const [mode, setMode] = useState(null);            // "demo" | "metamask" | null
  const [demoIndex, setDemoIndex] = useState(null);
  const [chainInfo, setChainInfo] = useState(null);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState(null);

  const isConnected = !!address;
  const isCorrectNetwork =
    mode === "demo" || (!!chainInfo && chainId === chainInfo.chain_id_hex);

  // ── Learn about the local chain from the backend ────────────────────────
  useEffect(() => {
    getChainInfo()
      .then(setChainInfo)
      .catch((e) => setError(e.message));
  }, []);

  // ── Demo wallet: a pre-funded Hardhat account, no MetaMask needed ───────
  const connectDemo = useCallback(async (index = 1) => {
    setError(null);
    try {
      setConnecting(true);
      const info = await getChainInfo(true);
      setChainInfo(info);
      const account = info.accounts[index];
      if (!account) throw new Error("That demo account does not exist.");

      const rpc = new ethers.JsonRpcProvider(browserRpcUrl(), Number(info.chain_id), {
        staticNetwork: true,
      });
      const walletSigner = await rpc.getSigner(account);

      setProvider(rpc);
      setSigner(walletSigner);
      setAddress(account.toLowerCase());
      setChainId(info.chain_id_hex);
      setMode("demo");
      setDemoIndex(index);
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ mode: "demo", index }));
    } catch (err) {
      setError(err.message || "Could not connect the demo wallet.");
    } finally {
      setConnecting(false);
    }
  }, []);

  // ── MetaMask ────────────────────────────────────────────────────────────
  const connect = useCallback(async () => {
    setError(null);

    if (!window.ethereum) {
      setError("MetaMask not detected. Use the Demo Wallet, or install MetaMask from metamask.io");
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
      setAddress(accounts[0].toLowerCase());
      setChainId("0x" + network.chainId.toString(16));
      setMode("metamask");
      setDemoIndex(null);
      localStorage.setItem(STORAGE_KEY, JSON.stringify({ mode: "metamask" }));
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

  const disconnect = useCallback(() => {
    setAddress(null);
    setProvider(null);
    setSigner(null);
    setChainId(null);
    setMode(null);
    setDemoIndex(null);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  // ── MetaMask: switch to / add the local Hardhat network ────────────────
  const switchNetwork = useCallback(async () => {
    if (!window.ethereum) return;
    try {
      const info = await getChainInfo(true);
      const params = {
        chainId: info.chain_id_hex,
        chainName: info.chain_name,
        nativeCurrency: { name: "Ether", symbol: "ETH", decimals: 18 },
        rpcUrls: [info.rpc_url],
      };
      try {
        await window.ethereum.request({
          method: "wallet_switchEthereumChain",
          params: [{ chainId: info.chain_id_hex }],
        });
      } catch (switchError) {
        if (switchError.code === 4902) {
          await window.ethereum.request({ method: "wallet_addEthereumChain", params: [params] });
        } else {
          throw switchError;
        }
      }
    } catch (err) {
      setError("Failed to switch network: " + (err.message || err));
    }
  }, []);

  // ── MetaMask account/network changes ────────────────────────────────────
  useEffect(() => {
    if (!window.ethereum || mode !== "metamask") return;

    const handleAccountsChanged = (accounts) => {
      if (accounts.length === 0) disconnect();
      else setAddress(accounts[0].toLowerCase());
    };
    const handleChainChanged = () => window.location.reload();

    window.ethereum.on("accountsChanged", handleAccountsChanged);
    window.ethereum.on("chainChanged", handleChainChanged);
    return () => {
      window.ethereum.removeListener("accountsChanged", handleAccountsChanged);
      window.ethereum.removeListener("chainChanged", handleChainChanged);
    };
  }, [mode, disconnect]);

  // ── Reconnect the same wallet after a page reload ──────────────────────
  useEffect(() => {
    let saved = null;
    try {
      saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
    } catch {
      /* ignore */
    }
    if (saved?.mode === "demo") connectDemo(saved.index ?? 1);
    else if (saved?.mode === "metamask" && window.ethereum) {
      window.ethereum
        .request({ method: "eth_accounts" })
        .then((accounts) => {
          if (accounts.length > 0) connect();
        })
        .catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const value = {
    address,
    provider,
    signer,
    chainId,
    chainInfo,
    mode,
    demoIndex,
    isConnected,
    isCorrectNetwork,
    connecting,
    error,
    connect,
    connectDemo,
    disconnect,
    switchNetwork,
  };

  return <WalletContext.Provider value={value}>{children}</WalletContext.Provider>;
}
