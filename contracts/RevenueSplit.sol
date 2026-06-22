pragma solidity ^0.8.20;



import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/Pausable.sol";

contract RevenueSplit is ReentrancyGuard, Ownable, Pausable {

    error TradeNotFound(string tradeId);
    error TradeNotCompleted(string tradeId, uint8 status);
    error InvalidContribution(address contributor, uint256 contribution);
    error TotalContributionMismatch(uint256 total, uint256 expected);
    error NoRevenueToDistribute(string tradeId);
    error AlreadyDistributed(string tradeId);
    error ZeroAddress();
    error InvalidAmount();
    error ContributionTooHigh(uint256 contribution, uint256 max);


    struct RevenueDistribution {
        string tradeId;
        uint128 totalAmount;
        uint64 distributedAt;
        bool isDistributed;
        address[] contributors;
        uint256[] contributions;
        uint256[] amounts;
    }

    mapping(string => RevenueDistribution) private _distributions;

    mapping(address => uint256) public totalEarned;

    mapping(address => string[]) private _userTrades;

    uint256 public distributionCount;


    event RevenueDeposited(
        string indexed tradeId,
        uint256 amount,
        address indexed from,
        uint256 timestamp
    );

    event RevenueDistributed(
        string indexed tradeId,
        uint256 totalAmount,
        uint256 contributorCount,
        uint256 timestamp
    );

    event ContributorPaid(
        string indexed tradeId,
        address indexed contributor,
        uint256 amount,
        uint256 contribution
    );

    event ContributionRecorded(
        string indexed tradeId,
        address indexed contributor,
        uint256 contribution,
        uint256 timestamp
    );



    constructor() Ownable(msg.sender) {}



    function depositRevenue(string memory tradeId)
        external
        payable
        nonReentrant
        whenNotPaused
    {
        if (bytes(tradeId).length == 0) revert TradeNotFound(tradeId);
        if (msg.value == 0) revert InvalidAmount();

        RevenueDistribution storage dist = _distributions[tradeId];

        if (bytes(dist.tradeId).length == 0) {
            dist.tradeId = tradeId;
            dist.totalAmount = uint128(msg.value);
            dist.isDistributed = false;
            distributionCount++;
        } else {
            dist.totalAmount += uint128(msg.value);
        }

        emit RevenueDeposited(tradeId, msg.value, msg.sender, block.timestamp);
    }


    function setContributionsAndDistribute(
        string memory tradeId,
        address[] memory contributors,
        uint256[] memory contributions
    ) external nonReentrant whenNotPaused onlyOwner {
        RevenueDistribution storage dist = _distributions[tradeId];

        if (bytes(dist.tradeId).length == 0) revert TradeNotFound(tradeId);
        if (dist.isDistributed) revert AlreadyDistributed(tradeId);
        if (dist.totalAmount == 0) revert NoRevenueToDistribute(tradeId);
        if (contributors.length != contributions.length) {
            revert TotalContributionMismatch(contributors.length, contributions.length);
        }
        if (contributors.length == 0) {
            revert TotalContributionMismatch(0, 1);
        }

        uint256 totalContribution = 0;
        for (uint256 i = 0; i < contributions.length; i++) {
            if (contributors[i] == address(0)) revert ZeroAddress();
            if (contributions[i] == 0) revert InvalidContribution(contributors[i], contributions[i]);
            if (contributions[i] > 10000) revert ContributionTooHigh(contributions[i], 10000);
            totalContribution += contributions[i];
        }

        if (totalContribution < 9999 || totalContribution > 10001) {
            revert TotalContributionMismatch(totalContribution, 10000);
        }

        dist.contributors = contributors;
        dist.contributions = contributions;
        dist.amounts = new uint256[](contributors.length);

        uint256 totalDistributed = 0;
        uint256 totalAmount = uint256(dist.totalAmount);

        for (uint256 i = 0; i < contributors.length; i++) {
            uint256 amount = (totalAmount * contributions[i]) / 10000;
            dist.amounts[i] = amount;
            totalDistributed += amount;

            totalEarned[contributors[i]] += amount;

            _userTrades[contributors[i]].push(tradeId);

            emit ContributorPaid(tradeId, contributors[i], amount, contributions[i]);
            emit ContributionRecorded(tradeId, contributors[i], contributions[i], block.timestamp);
        }

        for (uint256 i = 0; i < contributors.length; i++) {
            (bool success, ) = payable(contributors[i]).call{value: dist.amounts[i]}("");
            require(success, "Transfer failed");
        }

        dist.isDistributed = true;
        dist.distributedAt = uint64(block.timestamp);

        emit RevenueDistributed(tradeId, totalAmount, contributors.length, block.timestamp);
    }


    function batchSetContributions(
        string[] memory tradeIds,
        address[][] memory contributorsList,
        uint256[][] memory contributionsList
    ) external nonReentrant whenNotPaused onlyOwner {
        require(
            tradeIds.length == contributorsList.length &&
            tradeIds.length == contributionsList.length,
            "Array length mismatch"
        );

        for (uint256 i = 0; i < tradeIds.length; i++) {
            setContributionsAndDistribute(
                tradeIds[i],
                contributorsList[i],
                contributionsList[i]
            );
        }
    }



    function getDistribution(string memory tradeId) public view returns (
        string memory tradeId_,
        uint256 totalAmount,
        uint256 distributedAt,
        bool isDistributed,
        uint256 contributorCount
    ) {
        if (bytes(_distributions[tradeId].tradeId).length == 0) {
            revert TradeNotFound(tradeId);
        }

        RevenueDistribution storage dist = _distributions[tradeId];
        return (
            dist.tradeId,
            uint256(dist.totalAmount),
            uint256(dist.distributedAt),
            dist.isDistributed,
            dist.contributors.length
        );
    }


    function getContributors(string memory tradeId) public view returns (
        address[] memory contributors,
        uint256[] memory contributions,
        uint256[] memory amounts
    ) {
        if (bytes(_distributions[tradeId].tradeId).length == 0) {
            revert TradeNotFound(tradeId);
        }

        RevenueDistribution storage dist = _distributions[tradeId];
        return (
            dist.contributors,
            dist.contributions,
            dist.amounts
        );
    }


    function getTotalEarned(address user) public view returns (uint256) {
        return totalEarned[user];
    }


    function getUserTrades(address user) public view returns (string[] memory) {
        return _userTrades[user];
    }


    function getUserTradeCount(address user) public view returns (uint256) {
        return _userTrades[user].length;
    }


    function isDistributed(string memory tradeId) public view returns (bool) {
        if (bytes(_distributions[tradeId].tradeId).length == 0) {
            return false;
        }
        return _distributions[tradeId].isDistributed;
    }



    function pause() external onlyOwner {
        _pause();
    }


    function unpause() external onlyOwner {
        _unpause();
    }


    function emergencyWithdraw(uint256 amount) external onlyOwner nonReentrant {
        require(amount <= address(this).balance, "Insufficient balance");
        (bool success, ) = payable(owner()).call{value: amount}("");
        require(success, "Transfer failed");
    }



    function getContractBalance() public view returns (uint256) {
        return address(this).balance;
    }


    function calculateShare(uint256 totalAmount, uint256 contribution)
        public
        pure
        returns (uint256)
    {
        return (totalAmount * contribution) / 10000;
    }

    receive() external payable {}
    fallback() external payable {}
}
