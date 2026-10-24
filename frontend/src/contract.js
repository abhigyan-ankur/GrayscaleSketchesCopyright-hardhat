import { ethers } from "ethers";
import artifact from "./contractABI.json";
import { getChainInfo } from "./chain";

const ABI = artifact.abi;

/** Returns a contract instance for the given address, signer or provider. */
export function getContract(address, signerOrProvider) {
  return new ethers.Contract(address, ABI, signerOrProvider);
}

/**
 * Sends the registerArtwork transaction from the connected wallet (Demo Wallet
 * or MetaMask) to the local Hardhat chain, waits for it to be mined and reads
 * the new on-chain artwork id from the ArtworkCertified event.
 *
 * Returns: { txHash, onchainId }
 */
export async function registerOnChain(signer, { title, author, phash, imageCid, metadataCid }) {
  // Refresh each time: if the node was restarted, this makes the backend
  // redeploy the contract and re-sync before we send anything.
  const info = await getChainInfo(true);
  const contract = getContract(info.contract_address, signer);

  const tx = await contract.registerArtwork(title, author, phash, imageCid, metadataCid);
  const receipt = await tx.wait();

  let onchainId = null;
  for (const log of receipt.logs) {
    try {
      const parsed = contract.interface.parseLog(log);
      if (parsed && parsed.name === "ArtworkCertified") {
        onchainId = Number(parsed.args.id);
        break;
      }
    } catch {
      // not a log from this contract's ABI — skip
    }
  }

  return { txHash: receipt.hash, onchainId };
}
