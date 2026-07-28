/**
 * query.js
 * --------
 * Tests the read-only query functions on ArtworkRegistry.
 * These cost NO gas — they're free to call, unlike registerArtwork().
 *
 * This is what the Python backend should call BEFORE attempting
 * registerArtwork(), to avoid wasting gas on a transaction that
 * will just revert due to a duplicate.
 */

import hre from "hardhat";
import * as dotenv from "dotenv";
dotenv.config();

const CONTRACT_ADDRESS = process.env.CONTRACT_ADDRESS;

async function main() {
  const connection = await hre.network.getOrCreate();
  const { ethers } = connection;

  const [signer] = await ethers.getSigners();
  const ArtworkRegistry = await ethers.getContractFactory("ArtworkRegistry");
  const contract = ArtworkRegistry.attach(CONTRACT_ADDRESS);

  console.log("=== Query 1: Total artworks registered ===");
  const total = await contract.getTotalArtworks();
  console.log("Total:", total.toString());

  console.log("\n=== Query 2: Check if a pHash is already registered ===");
  const existingPhash = "a3f1b2c4d5e6f708";  // the one we registered earlier
  const newPhash      = "0000000000000000";  // one that shouldn't exist

  const [existsA, idA] = await contract.isPhashRegistered(existingPhash);
  console.log(`pHash "${existingPhash}" -> exists: ${existsA}, id: ${idA}`);

  const [existsB, idB] = await contract.isPhashRegistered(newPhash);
  console.log(`pHash "${newPhash}" -> exists: ${existsB}, id: ${idB}`);

  console.log("\n=== Query 3: Get full artwork details by ID ===");
  const artwork = await contract.getArtwork(1);
  console.log("Artwork #1:");
  console.log("  Title      :", artwork[1]);
  console.log("  Author     :", artwork[2]);
  console.log("  pHash      :", artwork[3]);
  console.log("  Image CID  :", artwork[4]);
  console.log("  Metadata CID:", artwork[5]);
  console.log("  Owner      :", artwork[6]);
  console.log("  Timestamp  :", new Date(Number(artwork[7]) * 1000).toISOString());

  console.log("\n=== Query 4: Get all artworks owned by current wallet ===");
  const ownedIds = await contract.getArtworksByOwner(signer.address);
  console.log(`Wallet ${signer.address} owns artwork IDs:`, ownedIds.map(id => id.toString()));
}

main().catch((error) => {
  console.error("Error:", error.message);
  process.exit(1);
});