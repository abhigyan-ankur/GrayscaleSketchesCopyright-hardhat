# Terminal 1: blockchain (start this first; leave it running)
cd ~/projects/Artwork-Copyright-System-Unified-/contracts
npx hardhat node

# Terminal 2: backend
cd ~/projects/Artwork-Copyright-System-Unified-/backend
ds
uvicorn api:app --reload --port 8000

# Terminal 3: website
cd ~/projects/Artwork-Copyright-System-Unified-/frontend
npm run dev