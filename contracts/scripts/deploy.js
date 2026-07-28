import hre from "hardhat";

async function main() {
  console.log("Deploying ArtworkRegistry contract...");

  const connection = await hre.network.getOrCreate();
  const { ethers } = connection;

  // Get the deployer wallet
  const [deployer] = await ethers.getSigners();
  console.log("Deploying with wallet:", deployer.address);

  // Check balance
  const balance = await ethers.provider.getBalance(deployer.address);
  console.log("Wallet balance:", ethers.formatEther(balance), "POL");

  // Deploy
  const ArtworkRegistry = await ethers.getContractFactory("ArtworkRegistry");
  const contract = await ArtworkRegistry.deploy();
  await contract.waitForDeployment();

  const address = await contract.getAddress();
  console.log("✓ ArtworkRegistry deployed to:", address);
  console.log("Save this address — you'll need it in Part 4!");
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});