import { ethers } from "ethers";
import artifact from "./contractABI.json";

// Deployed on Polygon Amoy Testnet — must match backend/.env CONTRACT_ADDRESS
export const CONTRACT_ADDRESS = "0x8cb8602857b244fD9ccB27775B6D642bc4b157b2";

const ABI = artifact.abi;

/**
 * Returns a contract instance connected to the given signer or provider.
 *   - Pass a SIGNER (from useWallet().signer) to send transactions
 *     (e.g. registerArtwork — requires MetaMask to sign and pay gas).
 *   - Pass a PROVIDER for read-only calls (getArtwork, isPhashRegistered, etc.)
 *     if you don't want to require a connected wallet just to read data.
 */
export function getContract(signerOrProvider) {
  return new ethers.Contract(CONTRACT_ADDRESS, ABI, signerOrProvider);
}

/**
 * Sends the registerArtwork transaction via the user's own wallet (MetaMask).
 * Waits for confirmation and extracts the new on-chain artwork ID from the
 * emitted ArtworkCertified event (safer than reading getTotalArtworks(),
 * which can race if multiple registrations happen close together).
 *
 * Returns: { txHash, onchainId }
 */
export async function registerOnChain(signer, { title, author, phash, imageCid, metadataCid }) {
  const contract = getContract(signer);

  const tx = await contract.registerArtwork(title, author, phash, imageCid, metadataCid);
  const receipt = await tx.wait();

  // Find the ArtworkCertified event in the transaction receipt logs
  let onchainId = null;
  for (const log of receipt.logs) {
    try {
      const parsed = contract.interface.parseLog(log);
      if (parsed.name === "ArtworkCertified") {
        onchainId = Number(parsed.args.id);
        break;
      }
    } catch {
      // not a log from this contract's ABI — skip
    }
  }

  return { txHash: receipt.hash, onchainId };
}