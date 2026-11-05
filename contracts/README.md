# Contracts

`contracts/ArtworkRegistry.sol` stores, for every certified artwork: title, author, pHash, image id,
metadata id, owner wallet and timestamp. It refuses duplicate pHashes and exposes read functions
(`isPhashRegistered`, `getArtwork`, `getArtworksByOwner`, `getTotalArtworks`). Built with Hardhat 3.

## Local chain

```bash
npm install
npx hardhat node          # chain id 31337, 20 funded accounts, RPC http://127.0.0.1:8545
```

You do **not** need to deploy by hand: when the backend starts and finds no contract on the chain it
deploys `ArtworkRegistry` itself (using the bytecode in `backend/contract_abi.json`) and re-registers
all saved artworks. Hardhat forgets its chain whenever the node stops, which is why this is automatic.

## Optional manual scripts

```bash
npx hardhat compile
npx hardhat run scripts/deploy.js --network localhost     # deploy by hand
npx hardhat run scripts/query.js --network localhost      # read from the contract (needs CONTRACT_ADDRESS in .env)
```

If you change the contract, run `npx hardhat compile` and copy
`artifacts/contracts/ArtworkRegistry.sol/ArtworkRegistry.json` to `backend/contract_abi.json` and
`frontend/src/contractABI.json`.

## Public testnet (later)

`hardhat.config.ts` still contains an `amoy` network (set `POLYGON_AMOY_RPC` and `PRIVATE_KEY` in
`contracts/.env`). Test tokens come from a faucet and are limited, which is why the default setup uses
the local chain.
