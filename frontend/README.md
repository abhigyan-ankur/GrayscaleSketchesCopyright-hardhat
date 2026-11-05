# Frontend

React + Vite + Tailwind website for Artchain (pages: Upload, Gallery, Search, Dashboard, Review, Login).

```bash
npm install
npm run dev          # http://localhost:5173
```

The backend must be running at `http://localhost:8000` (see `src/chain.js`) and the Hardhat node at
`127.0.0.1:8545`.

## How it talks to the blockchain

- The chain id, contract address and demo accounts are **not hardcoded**; the site asks
  `GET /api/chain/info` on the backend.
- **Demo Wallet** (top bar): signs with a pre-funded Hardhat account through the dev server, which
  proxies `/rpc` to the node (see `vite.config.js`). No browser extension needed. The dropdown
  switches accounts so you can act as different users.
- **MetaMask** also works: connect it, then press the yellow "Switch to Hardhat Local" button.

## Pages

| Page | Who | Purpose |
|---|---|---|
| Upload | logged in | detection, then the wallet signs the registration; certificate download |
| Gallery | everyone | every certified work and its certificate |
| Search | everyone | check an image without certifying it |
| Dashboard | logged in | your works, caught copies, submissions under review |
| Review | admin | approve or reject works flagged as similar |

Dependencies are in `package.json`; no extra packages are needed beyond `npm install`.
