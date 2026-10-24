import { defineConfig } from "hardhat/config";
import hardhatEthers from "@nomicfoundation/hardhat-ethers";
import * as dotenv from "dotenv";
dotenv.config();

export default defineConfig({
  plugins: [hardhatEthers],
  solidity: {
    version: "0.8.28",
  },
  networks: {
    // Local chain: `npx hardhat node` (chain id 31337, 20 funded accounts).
    localhost: {
      type: "http",
      url: "http://127.0.0.1:8545",
    },
    // Kept for the later public-testnet version of the project.
    amoy: {
      type: "http",
      url: process.env.POLYGON_AMOY_RPC || "https://polygon-amoy.drpc.org",
      accounts: process.env.PRIVATE_KEY ? [process.env.PRIVATE_KEY] : [],
    },
  },
});
