/**
 * register.js
 * -----------
 * Calls registerArtwork() on the deployed ArtworkRegistry contract.
 *
 * Usage:
 *   node scripts/register.js "<title>" "<author>" "<phash>" "<imageCID>" "<metadataCID>"
 *
 * Example (using dummy values to test):
 *   npx hardhat run scripts/register.js --network amoy
 *
 * In Part 4, the Python backend will call this same contract function
 * automatically after a successful IPFS upload — this script is for
 * manual testing right now.
 */

import hre from "hardhat";
import * as dotenv from "dotenv";
dotenv.config();

const CONTRACT_ADDRESS = process.env.CONTRACT_ADDRESS;

async function main() {
  if (!CONTRACT_ADDRESS) {
    throw new Error("CONTRACT_ADDRESS not set in .env");
  }

  const connection = await hre.network.getOrCreate();
  const { ethers } = connection;

  const [signer] = await ethers.getSigners();
  console.log("Calling contract as:", signer.address);

  const ArtworkRegistry = await ethers.getContractFactory("ArtworkRegistry");
  const contract = ArtworkRegistry.attach(CONTRACT_ADDRESS);

  // ── Test data (replace with real values from your Python pipeline) ────────
  const title       = "Test Sketch";
  const author      = "Ankur";
  const phash       = "a3f1b2c4d5e6f708";  // example pHash
  const imageCID    = "bafybeigdyrexampleimagecid1234567890";
  const metadataCID = "bafybeihdyrexamplemetacid1234567890";

  console.log("\nRegistering artwork...");
  console.log("  Title  :", title);
  console.log("  Author :", author);
  console.log("  pHash  :", phash);

  const tx = await contract.registerArtwork(title, author, phash, imageCID, metadataCID);
  console.log("\nTransaction sent:", tx.hash);
  console.log("Waiting for confirmation...");

  const receipt = await tx.wait();
  console.log("✓ Confirmed in block:", receipt.blockNumber);

  // Read back the total count
  const total = await contract.getTotalArtworks();
  console.log("✓ Total artworks now registered:", total.toString());

  console.log("\nView on explorer:");
  console.log(`https://amoy.polygonscan.com/tx/${tx.hash}`);
}

main().catch((error) => {
  console.error("Error:", error.message);
  process.exit(1);
});