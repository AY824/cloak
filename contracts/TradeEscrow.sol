pragma solidity ^0.8.20;



import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

contract TradeEscrow is ReentrancyGuard, Ownable, Pausable {
    using ECDSA for bytes32;


    error TradeNotFound(string tradeId);
    error TradeStatusInvalid(string tradeId, uint8 currentStatus, uint8 expectedStatus);
    error NotTradeParticipant(address caller);
    error InsufficientPayment(uint256 required, uint256 paid);
    error TradeNotExpired(uint256 currentTime, uint256 expireTime);
    error TradeAlreadyExpired(uint256 currentTime, uint256 expireTime);
    error InvalidSignature();
    error ZeroAddress();
    error InvalidAmount();
    error InvalidTradeId(string tradeId);
    error InvalidSellerAddress(address seller);
    error InvalidBuyerAddress(address buyer);


    enum TradeStatus {
        PENDING,
        ESCROWED,
        COMPLETED,
        DISPUTED,
        REFUNDED,
        CANCELLED
    }


    struct Trade {
        string tradeId;
        address payable seller;
        address payable buyer;
        uint128 amount;
        uint64 createdAt;
        uint64 expireAt;
        uint8 status;
        string assetId;
        string nostrEventId;
        bool sellerConfirmed;
        bool buyerConfirmed;
    }

    mapping(string => Trade) private _trades;

    mapping(address => string[]) private _userTrades;

    uint256 public tradeCount;

    uint16 public platformFeeRate = 25;

    address payable public platformFeeReceiver;

    uint64 public defaultTimeout = 7 days;


    event TradeCreated(
        string indexed tradeId,
        address indexed seller,
        address indexed buyer,
        uint256 amount,
        string assetId,
        uint256 createdAt
    );

    event TradeEscrowed(
        string indexed tradeId,
        address indexed buyer,
        uint256 amount,
        uint256 timestamp
    );

    event TradeCompleted(
        string indexed tradeId,
        address indexed seller,
        address indexed buyer,
        uint256 amount,
        uint256 platformFee,
        uint256 timestamp
    );

    event TradeDisputed(
        string indexed tradeId,
        address indexed disputer,
        string reason,
        uint256 timestamp
    );

    event TradeRefunded(
        string indexed tradeId,
        address indexed buyer,
        uint256 amount,
        uint256 timestamp
    );

    event TradeCancelled(
        string indexed tradeId,
        address indexed canceller,
        uint256 timestamp
    );

    event TradeConfirmed(
        string indexed tradeId,
        address indexed confirmer,
        string role,
        uint256 timestamp
    );

    event PlatformFeeRateUpdated(
        uint16 oldRate,
        uint16 newRate,
        address indexed updater
    );

    event PlatformFeeReceiverUpdated(
        address oldReceiver,
        address newReceiver,
        address indexed updater
    );

    event DefaultTimeoutUpdated(
        uint64 oldTimeout,
        uint64 newTimeout,
        address indexed updater
    );



    constructor(address payable feeReceiver) Ownable(msg.sender) {
        if (feeReceiver == address(0)) revert ZeroAddress();
        platformFeeReceiver = feeReceiver;
    }



    function createTrade(
        string memory tradeId,
        address payable seller,
        address payable buyer,
        uint128 amount,
        string memory assetId,
        string memory nostrEventId
    ) public whenNotPaused {
        if (bytes(tradeId).length == 0) revert InvalidTradeId(tradeId);
        if (seller == address(0)) revert InvalidSellerAddress(seller);
        if (buyer == address(0)) revert InvalidBuyerAddress(buyer);
        if (amount == 0) revert InvalidAmount();
        if (bytes(_trades[tradeId].tradeId).length != 0) {
            revert TradeNotFound(tradeId);
        }

        _trades[tradeId] = Trade({
            tradeId: tradeId,
            seller: seller,
            buyer: buyer,
            amount: amount,
            createdAt: uint64(block.timestamp),
            expireAt: uint64(block.timestamp) + defaultTimeout,
            status: uint8(TradeStatus.PENDING),
            assetId: assetId,
            nostrEventId: nostrEventId,
            sellerConfirmed: false,
            buyerConfirmed: false
        });

        _userTrades[seller].push(tradeId);
        _userTrades[buyer].push(tradeId);

        tradeCount++;

        emit TradeCreated(tradeId, seller, buyer, amount, assetId, block.timestamp);
    }


    function payToEscrow(string memory tradeId)
        external
        payable
        nonReentrant
        whenNotPaused
    {
        Trade storage trade = _trades[tradeId];

        if (bytes(trade.tradeId).length == 0) revert TradeNotFound(tradeId);
        if (trade.status != uint8(TradeStatus.PENDING)) {
            revert TradeStatusInvalid(tradeId, trade.status, uint8(TradeStatus.PENDING));
        }
        if (msg.sender != trade.buyer) revert NotTradeParticipant(msg.sender);
        if (msg.value < uint256(trade.amount)) {
            revert InsufficientPayment(uint256(trade.amount), msg.value);
        }

        trade.status = uint8(TradeStatus.ESCROWED);

        if (msg.value > uint256(trade.amount)) {
            uint256 refund = msg.value - uint256(trade.amount);
            (bool success, ) = payable(msg.sender).call{value: refund}("");
            require(success, "Refund failed");
        }

        emit TradeEscrowed(tradeId, msg.sender, uint256(trade.amount), block.timestamp);
    }


    function confirmTrade(string memory tradeId) external nonReentrant whenNotPaused {
        Trade storage trade = _trades[tradeId];

        if (bytes(trade.tradeId).length == 0) revert TradeNotFound(tradeId);
        if (trade.status != uint8(TradeStatus.ESCROWED)) {
            revert TradeStatusInvalid(tradeId, trade.status, uint8(TradeStatus.ESCROWED));
        }
        if (msg.sender != trade.seller && msg.sender != trade.buyer) {
            revert NotTradeParticipant(msg.sender);
        }

        string memory role;
        if (msg.sender == trade.seller) {
            trade.sellerConfirmed = true;
            role = "seller";
        } else {
            trade.buyerConfirmed = true;
            role = "buyer";
        }

        emit TradeConfirmed(tradeId, msg.sender, role, block.timestamp);

        if (trade.sellerConfirmed && trade.buyerConfirmed) {
            _completeTrade(trade);
        }
    }


    function _completeTrade(Trade storage trade) internal {
        uint256 platformFee = (uint256(trade.amount) * platformFeeRate) / 1000;
        uint256 sellerAmount = uint256(trade.amount) - platformFee;

        (bool success, ) = trade.seller.call{value: sellerAmount}("");
        require(success, "Transfer to seller failed");

        if (platformFee > 0) {
            (bool feeSuccess, ) = platformFeeReceiver.call{value: platformFee}("");
            require(feeSuccess, "Transfer platform fee failed");
        }

        trade.status = uint8(TradeStatus.COMPLETED);

        emit TradeCompleted(
            trade.tradeId,
            trade.seller,
            trade.buyer,
            uint256(trade.amount),
            platformFee,
            block.timestamp
        );
    }


    function raiseDispute(string memory tradeId, string memory reason)
        external
        whenNotPaused
    {
        Trade storage trade = _trades[tradeId];

        if (bytes(trade.tradeId).length == 0) revert TradeNotFound(tradeId);
        if (trade.status != uint8(TradeStatus.ESCROWED)) {
            revert TradeStatusInvalid(tradeId, trade.status, uint8(TradeStatus.ESCROWED));
        }
        if (msg.sender != trade.seller && msg.sender != trade.buyer) {
            revert NotTradeParticipant(msg.sender);
        }

        trade.status = uint8(TradeStatus.DISPUTED);

        emit TradeDisputed(tradeId, msg.sender, reason, block.timestamp);
    }


    function refundExpiredTrade(string memory tradeId)
        external
        nonReentrant
        whenNotPaused
    {
        Trade storage trade = _trades[tradeId];

        if (bytes(trade.tradeId).length == 0) revert TradeNotFound(tradeId);
        if (trade.status != uint8(TradeStatus.ESCROWED) &&
            trade.status != uint8(TradeStatus.PENDING)) {
            revert TradeStatusInvalid(tradeId, trade.status, uint8(TradeStatus.ESCROWED));
        }
        if (block.timestamp < trade.expireAt) {
            revert TradeNotExpired(block.timestamp, trade.expireAt);
        }
        if (msg.sender != trade.buyer) revert NotTradeParticipant(msg.sender);

        uint256 refundAmount = trade.status == uint8(TradeStatus.ESCROWED)
            ? uint256(trade.amount)
            : 0;

        if (refundAmount > 0) {
            (bool success, ) = trade.buyer.call{value: refundAmount}("");
            require(success, "Refund failed");
        }

        trade.status = uint8(TradeStatus.REFUNDED);

        emit TradeRefunded(tradeId, trade.buyer, refundAmount, block.timestamp);
    }


    function cancelTrade(string memory tradeId) external whenNotPaused {
        Trade storage trade = _trades[tradeId];

        if (bytes(trade.tradeId).length == 0) revert TradeNotFound(tradeId);
        if (trade.status != uint8(TradeStatus.PENDING)) {
            revert TradeStatusInvalid(tradeId, trade.status, uint8(TradeStatus.PENDING));
        }
        if (msg.sender != trade.seller && msg.sender != trade.buyer) {
            revert NotTradeParticipant(msg.sender);
        }

        trade.status = uint8(TradeStatus.CANCELLED);

        emit TradeCancelled(tradeId, msg.sender, block.timestamp);
    }



    function getTrade(string memory tradeId) public view returns (
        string memory tradeId_,
        address seller,
        address buyer,
        uint256 amount,
        uint256 createdAt,
        uint256 expireAt,
        uint8 status,
        string memory assetId,
        string memory nostrEventId,
        bool sellerConfirmed,
        bool buyerConfirmed
    ) {
        if (bytes(_trades[tradeId].tradeId).length == 0) revert TradeNotFound(tradeId);

        Trade storage trade = _trades[tradeId];
        return (
            trade.tradeId,
            trade.seller,
            trade.buyer,
            uint256(trade.amount),
            uint256(trade.createdAt),
            uint256(trade.expireAt),
            trade.status,
            trade.assetId,
            trade.nostrEventId,
            trade.sellerConfirmed,
            trade.buyerConfirmed
        );
    }


    function getTradeStatus(string memory tradeId) public view returns (uint8) {
        if (bytes(_trades[tradeId].tradeId).length == 0) revert TradeNotFound(tradeId);
        return _trades[tradeId].status;
    }


    function getUserTrades(address user) public view returns (string[] memory) {
        return _userTrades[user];
    }


    function getUserTradeCount(address user) public view returns (uint256) {
        return _userTrades[user].length;
    }


    function isTradeExpired(string memory tradeId) public view returns (bool) {
        if (bytes(_trades[tradeId].tradeId).length == 0) revert TradeNotFound(tradeId);
        return block.timestamp >= _trades[tradeId].expireAt;
    }



    function setPlatformFeeRate(uint16 newRate) external onlyOwner {
        require(newRate <= 100, "Fee rate too high");

        uint16 oldRate = platformFeeRate;
        platformFeeRate = newRate;

        emit PlatformFeeRateUpdated(oldRate, newRate, msg.sender);
    }


    function setPlatformFeeReceiver(address payable newReceiver) external onlyOwner {
        if (newReceiver == address(0)) revert ZeroAddress();

        address oldReceiver = platformFeeReceiver;
        platformFeeReceiver = newReceiver;

        emit PlatformFeeReceiverUpdated(oldReceiver, newReceiver, msg.sender);
    }


    function setDefaultTimeout(uint64 newTimeout) external onlyOwner {
        require(newTimeout >= 1 hours, "Timeout too short");
        require(newTimeout <= 30 days, "Timeout too long");

        uint64 oldTimeout = defaultTimeout;
        defaultTimeout = newTimeout;

        emit DefaultTimeoutUpdated(oldTimeout, newTimeout, msg.sender);
    }


    function pause() external onlyOwner {
        _pause();
    }


    function unpause() external onlyOwner {
        _unpause();
    }


    function resolveDispute(string memory tradeId, uint8 sellerShare)
        external
        nonReentrant
        onlyOwner
    {
        Trade storage trade = _trades[tradeId];

        if (bytes(trade.tradeId).length == 0) revert TradeNotFound(tradeId);
        if (trade.status != uint8(TradeStatus.DISPUTED)) {
            revert TradeStatusInvalid(tradeId, trade.status, uint8(TradeStatus.DISPUTED));
        }
        require(sellerShare <= 100, "Invalid share");

        uint256 amount = uint256(trade.amount);
        uint256 sellerAmount = (amount * sellerShare) / 100;
        uint256 buyerAmount = amount - sellerAmount;

        if (sellerAmount > 0) {
            (bool success, ) = trade.seller.call{value: sellerAmount}("");
            require(success, "Transfer to seller failed");
        }
        if (buyerAmount > 0) {
            (bool success, ) = trade.buyer.call{value: buyerAmount}("");
            require(success, "Transfer to buyer failed");
        }

        trade.status = uint8(TradeStatus.COMPLETED);

        emit TradeCompleted(tradeId, trade.seller, trade.buyer, amount, 0, block.timestamp);
    }



    function getStatusName(uint8 status) public pure returns (string memory) {
        if (status == uint8(TradeStatus.PENDING)) return "PENDING";
        if (status == uint8(TradeStatus.ESCROWED)) return "ESCROWED";
        if (status == uint8(TradeStatus.COMPLETED)) return "COMPLETED";
        if (status == uint8(TradeStatus.DISPUTED)) return "DISPUTED";
        if (status == uint8(TradeStatus.REFUNDED)) return "REFUNDED";
        if (status == uint8(TradeStatus.CANCELLED)) return "CANCELLED";
        return "UNKNOWN";
    }


    function getContractBalance() public view returns (uint256) {
        return address(this).balance;
    }
}
