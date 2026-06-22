pragma solidity ^0.8.20;



import "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/utils/Counters.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

contract RiskAssetNFT is ERC721, ERC721URIStorage, Ownable, Pausable {
    using Counters for Counters.Counter;
    using ECDSA for bytes32;


    error AssetAlreadyExists(string assetId);
    error AssetNotFound(uint256 tokenId);
    error AssetNotActive(uint256 tokenId);
    error InvalidAssetId(string assetId);
    error InvalidDataHash(string dataHash);
    error InvalidSignature();
    error NotAssetOwner(address caller, address owner);
    error InvalidMetadataUri(string uri);
    error ZeroAddress();


    Counters.Counter private _tokenIdCounter;

    struct AssetInfo {
        string assetId;
        string nostrEventId;
        string dataHash;
        address owner;
        uint64 mintTime;
        string metadataUri;
        bool isActive;
        uint8 riskType;
    }

    mapping(uint256 => AssetInfo) private _assetInfos;

    mapping(string => uint256) private _assetIdToTokenId;

    mapping(address => uint256[]) private _userAssets;

    mapping(address => bool) private _authorizedSigners;


    event AssetMinted(
        uint256 indexed tokenId,
        string assetId,
        string nostrEventId,
        address indexed owner,
        string dataHash,
        uint8 riskType
    );

    event AssetDeactivated(
        uint256 indexed tokenId,
        string assetId,
        address indexed owner,
        uint256 timestamp
    );

    event AssetActivated(
        uint256 indexed tokenId,
        string assetId,
        address indexed owner,
        uint256 timestamp
    );

    event AssetMetadataUpdated(
        uint256 indexed tokenId,
        string oldUri,
        string newUri
    );

    event AuthorizedSignerAdded(
        address indexed signer,
        address indexed addedBy
    );

    event AuthorizedSignerRemoved(
        address indexed signer,
        address indexed removedBy
    );



    constructor() ERC721("RiskAssetNFT", "RANFT") Ownable(msg.sender) {
        _authorizedSigners[msg.sender] = true;
    }



    function mint(
        string memory assetId,
        string memory nostrEventId,
        string memory dataHash,
        string memory metadataUri,
        uint8 riskType
    ) public whenNotPaused returns (uint256) {
        if (bytes(assetId).length == 0) revert InvalidAssetId(assetId);
        if (bytes(dataHash).length == 0) revert InvalidDataHash(dataHash);
        if (_assetIdToTokenId[assetId] != 0) revert AssetAlreadyExists(assetId);

        _tokenIdCounter.increment();
        uint256 tokenId = _tokenIdCounter.current();

        _safeMint(msg.sender, tokenId);
        _setTokenURI(tokenId, metadataUri);

        _assetInfos[tokenId] = AssetInfo({
            assetId: assetId,
            nostrEventId: nostrEventId,
            dataHash: dataHash,
            owner: msg.sender,
            mintTime: uint64(block.timestamp),
            metadataUri: metadataUri,
            isActive: true,
            riskType: riskType
        });

        _assetIdToTokenId[assetId] = tokenId;

        _userAssets[msg.sender].push(tokenId);

        emit AssetMinted(tokenId, assetId, nostrEventId, msg.sender, dataHash, riskType);

        return tokenId;
    }


    function mintWithSignature(
        string memory assetId,
        string memory nostrEventId,
        string memory dataHash,
        string memory metadataUri,
        uint8 riskType,
        bytes memory signature
    ) public whenNotPaused returns (uint256) {
        bytes32 messageHash = keccak256(abi.encodePacked(assetId, dataHash, msg.sender));
        address signer = messageHash.toEthSignedMessageHash().recover(signature);

        if (!_authorizedSigners[signer]) revert InvalidSignature();

        return mint(assetId, nostrEventId, dataHash, metadataUri, riskType);
    }


    function mintBatch(
        string[] memory assetIds,
        string[] memory nostrEventIds,
        string[] memory dataHashes,
        string[] memory metadataUris,
        uint8[] memory riskTypes
    ) public whenNotPaused returns (uint256[] memory) {
        require(
            assetIds.length == nostrEventIds.length &&
            assetIds.length == dataHashes.length &&
            assetIds.length == metadataUris.length &&
            assetIds.length == riskTypes.length,
            "Array length mismatch"
        );

        uint256[] memory tokenIds = new uint256[](assetIds.length);

        for (uint256 i = 0; i < assetIds.length; i++) {
            tokenIds[i] = mint(
                assetIds[i],
                nostrEventIds[i],
                dataHashes[i],
                metadataUris[i],
                riskTypes[i]
            );
        }

        return tokenIds;
    }



    function getAssetInfo(uint256 tokenId) public view returns (
        string memory assetId,
        string memory nostrEventId,
        string memory dataHash,
        address owner,
        uint256 mintTime,
        string memory metadataUri,
        bool isActive,
        uint8 riskType
    ) {
        if (!_exists(tokenId)) revert AssetNotFound(tokenId);

        AssetInfo storage info = _assetInfos[tokenId];
        return (
            info.assetId,
            info.nostrEventId,
            info.dataHash,
            info.owner,
            uint256(info.mintTime),
            info.metadataUri,
            info.isActive,
            info.riskType
        );
    }


    function getTokenIdByAssetId(string memory assetId) public view returns (uint256) {
        return _assetIdToTokenId[assetId];
    }


    function isAssetActive(string memory assetId) public view returns (bool) {
        uint256 tokenId = _assetIdToTokenId[assetId];
        if (tokenId == 0) return false;
        return _assetInfos[tokenId].isActive;
    }


    function getUserAssets(address user) public view returns (uint256[] memory) {
        return _userAssets[user];
    }


    function getUserAssetCount(address user) public view returns (uint256) {
        return _userAssets[user].length;
    }



    function deactivateAsset(uint256 tokenId) public {
        if (!_exists(tokenId)) revert AssetNotFound(tokenId);
        if (ownerOf(tokenId) != msg.sender) revert NotAssetOwner(msg.sender, ownerOf(tokenId));
        if (!_assetInfos[tokenId].isActive) revert AssetNotActive(tokenId);

        _assetInfos[tokenId].isActive = false;

        emit AssetDeactivated(tokenId, _assetInfos[tokenId].assetId, msg.sender, block.timestamp);
    }


    function activateAsset(uint256 tokenId) public {
        if (!_exists(tokenId)) revert AssetNotFound(tokenId);
        if (ownerOf(tokenId) != msg.sender) revert NotAssetOwner(msg.sender, ownerOf(tokenId));
        if (_assetInfos[tokenId].isActive) revert AssetAlreadyExists(_assetInfos[tokenId].assetId);

        _assetInfos[tokenId].isActive = true;

        emit AssetActivated(tokenId, _assetInfos[tokenId].assetId, msg.sender, block.timestamp);
    }


    function updateMetadataUri(uint256 tokenId, string memory newUri) public {
        if (!_exists(tokenId)) revert AssetNotFound(tokenId);
        if (ownerOf(tokenId) != msg.sender) revert NotAssetOwner(msg.sender, ownerOf(tokenId));
        if (bytes(newUri).length == 0) revert InvalidMetadataUri(newUri);

        string memory oldUri = tokenURI(tokenId);
        _setTokenURI(tokenId, newUri);
        _assetInfos[tokenId].metadataUri = newUri;

        emit AssetMetadataUpdated(tokenId, oldUri, newUri);
    }


    function verifyDataHash(uint256 tokenId, string memory dataHash) public view returns (bool) {
        if (!_exists(tokenId)) revert AssetNotFound(tokenId);
        return keccak256(abi.encodePacked(_assetInfos[tokenId].dataHash)) ==
               keccak256(abi.encodePacked(dataHash));
    }



    function addAuthorizedSigner(address signer) public onlyOwner {
        if (signer == address(0)) revert ZeroAddress();
        _authorizedSigners[signer] = true;
        emit AuthorizedSignerAdded(signer, msg.sender);
    }


    function removeAuthorizedSigner(address signer) public onlyOwner {
        _authorizedSigners[signer] = false;
        emit AuthorizedSignerRemoved(signer, msg.sender);
    }


    function isAuthorizedSigner(address signer) public view returns (bool) {
        return _authorizedSigners[signer];
    }



    function pause() public onlyOwner {
        _pause();
    }


    function unpause() public onlyOwner {
        _unpause();
    }



    function balanceOf(address owner) public view override returns (uint256) {
        return super.balanceOf(owner);
    }


    function tokenURI(uint256 tokenId)
        public
        view
        override(ERC721, ERC721URIStorage)
        returns (string memory)
    {
        return super.tokenURI(tokenId);
    }


    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(ERC721, ERC721URIStorage)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }


    function totalSupply() public view returns (uint256) {
        return _tokenIdCounter.current();
    }



    function _transfer(
        address from,
        address to,
        uint256 tokenId
    ) internal override {
        super._transfer(from, to, tokenId);

        _assetInfos[tokenId].owner = to;

        _userAssets[to].push(tokenId);
    }
}
