// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/**
 * @title ArtworkRegistry
 * @dev Blockchain-based digital artwork copyright protection system.
 *
 * Stores per artwork (immutably, on-chain):
 *   - pHash fingerprint (from Python pipeline)
 *   - IPFS CID of the artwork file (from Pinata)
 *   - IPFS CID of the metadata JSON
 *   - Owner wallet address (MetaMask identity)
 *   - Timestamp (block time — tamper-proof)
 *   - Title and author name
 *
 * Key design decisions:
 *   - One contract stores ALL artworks (no per-artwork deployment)
 *   - Owner address is msg.sender — whoever calls registerArtwork()
 *     is recorded as the owner. No separate login needed.
 *   - pHash duplicates are rejected on-chain as a second layer of
 *     protection (Python pipeline is the first layer)
 *   - All data is public and verifiable by anyone
 */
contract ArtworkRegistry {

    // ── Data structures ──────────────────────────────────────────────────────

    struct Artwork {
        uint256 id;           // auto-incremented ID
        string  title;        // artwork title
        string  author;       // artist name
        string  phash;        // perceptual hash (64-bit hex string)
        string  imageCID;     // IPFS CID of the artwork image
        string  metadataCID;  // IPFS CID of the metadata JSON
        address owner;        // wallet address of the registering artist
        uint256 timestamp;    // block.timestamp at registration
        bool    exists;       // used for existence checks
    }

    // ── State variables ───────────────────────────────────────────────────────

    uint256 private _artworkCount;

    // id → Artwork
    mapping(uint256 => Artwork) private _artworks;

    // pHash string → artwork id (for duplicate detection)
    mapping(string => uint256) private _phashToId;

    // owner address → list of their artwork IDs
    mapping(address => uint256[]) private _ownerArtworks;

    // ── Events ────────────────────────────────────────────────────────────────

    // Emitted when a new artwork is successfully certified
    event ArtworkCertified(
        uint256 indexed id,
        address indexed owner,
        string  phash,
        string  imageCID,
        string  metadataCID,
        uint256 timestamp
    );

    // Emitted when a plagiarism attempt is detected and rejected
    event PlagiarismDetected(
        address indexed attacker,
        string  phash,
        uint256 originalId,
        uint256 timestamp
    );

    // ── Core functions ────────────────────────────────────────────────────────

    /**
     * @dev Registers a new artwork on-chain.
     * Called by the Python backend after IPFS upload succeeds.
     *
     * @param title       Artwork title
     * @param author      Artist name
     * @param phash       pHash hex string from Python pipeline
     * @param imageCID    IPFS CID of the image file
     * @param metadataCID IPFS CID of the metadata JSON
     */
    function registerArtwork(
        string memory title,
        string memory author,
        string memory phash,
        string memory imageCID,
        string memory metadataCID
    ) external returns (uint256) {

        // Check for empty inputs
        require(bytes(title).length > 0,       "Title cannot be empty");
        require(bytes(author).length > 0,      "Author cannot be empty");
        require(bytes(phash).length > 0,       "pHash cannot be empty");
        require(bytes(imageCID).length > 0,    "Image CID cannot be empty");
        require(bytes(metadataCID).length > 0, "Metadata CID cannot be empty");

        // On-chain duplicate check via pHash
        // (Python pipeline already does this, but blockchain enforces it too)
        if (_phashToId[phash] != 0) {
            uint256 originalId = _phashToId[phash];
            emit PlagiarismDetected(msg.sender, phash, originalId, block.timestamp);
            revert("Duplicate pHash: artwork already registered");
        }

        // Assign new ID
        _artworkCount++;
        uint256 newId = _artworkCount;

        // Store artwork
        _artworks[newId] = Artwork({
            id:          newId,
            title:       title,
            author:      author,
            phash:       phash,
            imageCID:    imageCID,
            metadataCID: metadataCID,
            owner:       msg.sender,
            timestamp:   block.timestamp,
            exists:      true
        });

        // Index by pHash and owner
        _phashToId[phash]              = newId;
        _ownerArtworks[msg.sender].push(newId);

        emit ArtworkCertified(newId, msg.sender, phash, imageCID, metadataCID, block.timestamp);

        return newId;
    }

    // ── Query functions ───────────────────────────────────────────────────────

    /**
     * @dev Returns full artwork details by ID.
     */
    function getArtwork(uint256 id) external view returns (
        uint256 artId,
        string memory title,
        string memory author,
        string memory phash,
        string memory imageCID,
        string memory metadataCID,
        address owner,
        uint256 timestamp
    ) {
        require(_artworks[id].exists, "Artwork not found");
        Artwork memory a = _artworks[id];
        return (a.id, a.title, a.author, a.phash, a.imageCID, a.metadataCID, a.owner, a.timestamp);
    }

    /**
     * @dev Checks if a pHash is already registered. Returns (true, artworkId)
     * if found, (false, 0) if not. Used by Python backend before registering.
     */
    function isPhashRegistered(string memory phash) external view returns (bool, uint256) {
        uint256 id = _phashToId[phash];
        return (id != 0, id);
    }

    /**
     * @dev Returns all artwork IDs owned by a wallet address.
     */
    function getArtworksByOwner(address owner) external view returns (uint256[] memory) {
        return _ownerArtworks[owner];
    }

    /**
     * @dev Returns total number of registered artworks.
     */
    function getTotalArtworks() external view returns (uint256) {
        return _artworkCount;
    }
}