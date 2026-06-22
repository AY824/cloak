
import json
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from loguru import logger

try:
    from web3 import Web3
    from eth_account import Account
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    logger.warning("web3.py 未安装，部分功能将不可用")


@dataclass
class ContractConfig:
    name: str
    address: str
    abi: List[Dict]


class BlockchainClient:

    def __init__(
        self,
        rpc_url: str,
        private_key: str = "",
        chain_id: int = 11155111
    ):
        if not WEB3_AVAILABLE:
            raise ImportError("web3.py 未安装，请运行 pip install web3")

        self.w3 = Web3(Web3.HTTPProvider(rpc_url))
        self.chain_id = chain_id

        if private_key:
            self.account = Account.from_key(private_key)
            self.address = self.account.address
        else:
            self.account = Account.create()
            self.address = self.account.address

        logger.info(f"区块链客户端初始化完成，地址: {self.address}")

        self._contracts: Dict[str, any] = {}

    def is_connected(self) -> bool:
        return self.w3.is_connected()

    def get_balance(self, address: str = "") -> float:
        addr = address or self.address
        balance_wei = self.w3.eth.get_balance(addr)
        return self.w3.from_wei(balance_wei, 'ether')

    def load_contract(self, name: str, address: str, abi: List[Dict]):
        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(address),
            abi=abi
        )
        self._contracts[name] = contract
        logger.info(f"合约加载完成: {name} @ {address}")
        return contract

    def get_contract(self, name: str):
        if name not in self._contracts:
            raise ValueError(f"合约未加载: {name}")
        return self._contracts[name]

    def _send_transaction(self, contract_function, value: int = 0) -> str:
        transaction = contract_function.build_transaction({
            "from": self.address,
            "value": value,
            "gas": 2000000,
            "gasPrice": self.w3.eth.gas_price,
            "nonce": self.w3.eth.get_transaction_count(self.address),
            "chainId": self.chain_id,
        })

        signed_txn = self.account.sign_transaction(transaction)

        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        tx_hash_hex = tx_hash.hex()

        logger.info(f"交易已发送: {tx_hash_hex}")
        return tx_hash_hex

    def wait_for_receipt(self, tx_hash: str, timeout: int = 120) -> Dict:
        logger.info(f"等待交易确认: {tx_hash}")
        receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
        logger.info(f"交易已确认，状态: {receipt['status']}")
        return dict(receipt)


class RiskAssetNFTClient:

    def __init__(self, blockchain: BlockchainClient, contract_address: str, abi: List[Dict]):
        self.blockchain = blockchain
        self.contract = blockchain.load_contract("RiskAssetNFT", contract_address, abi)

    def mint_asset_nft(
        self,
        asset_id: str,
        nostr_event_id: str,
        data_hash: str,
        metadata_uri: str = ""
    ) -> str:
        logger.info(f"铸造资产 NFT: asset_id={asset_id}")

        tx_hash = self.blockchain._send_transaction(
            self.contract.functions.mint(
                asset_id,
                nostr_event_id,
                data_hash,
                metadata_uri
            )
        )

        return tx_hash

    def get_asset_info(self, token_id: int) -> Dict:
        try:
            result = self.contract.functions.getAssetInfo(token_id).call()
            return {
                "asset_id": result[0],
                "nostr_event_id": result[1],
                "data_hash": result[2],
                "owner": result[3],
                "mint_time": result[4],
                "metadata_uri": result[5]
            }
        except Exception as e:
            logger.error(f"获取资产信息失败: {e}")
            return {}

    def get_token_id_by_asset_id(self, asset_id: str) -> int:
        try:
            return self.contract.functions.getTokenIdByAssetId(asset_id).call()
        except Exception as e:
            logger.error(f"获取 token ID 失败: {e}")
            return 0

    def balance_of(self, owner: str = "") -> int:
        addr = owner or self.blockchain.address
        return self.contract.functions.balanceOf(addr).call()

    def owner_of(self, token_id: int) -> str:
        return self.contract.functions.ownerOf(token_id).call()


class TradeEscrowClient:

    def __init__(self, blockchain: BlockchainClient, contract_address: str, abi: List[Dict]):
        self.blockchain = blockchain
        self.contract = blockchain.load_contract("TradeEscrow", contract_address, abi)

    def create_trade(
        self,
        trade_id: str,
        seller: str,
        buyer: str,
        amount_eth: float,
        nostr_trade_event_id: str = ""
    ) -> str:
        logger.info(f"创建托管交易: trade_id={trade_id}, amount={amount_eth} ETH")

        amount_wei = self.blockchain.w3.to_wei(amount_eth, 'ether')

        tx_hash = self.blockchain._send_transaction(
            self.contract.functions.createTrade(
                trade_id,
                Web3.to_checksum_address(seller),
                Web3.to_checksum_address(buyer),
                nostr_trade_event_id
            ),
            value=amount_wei
        )

        return tx_hash

    def confirm_trade(self, trade_id: str) -> str:
        logger.info(f"确认交易完成: trade_id={trade_id}")

        tx_hash = self.blockchain._send_transaction(
            self.contract.functions.confirmTrade(trade_id)
        )

        return tx_hash

    def refund_trade(self, trade_id: str) -> str:
        logger.info(f"退款交易: trade_id={trade_id}")

        tx_hash = self.blockchain._send_transaction(
            self.contract.functions.refundTrade(trade_id)
        )

        return tx_hash

    def get_trade_info(self, trade_id: str) -> Dict:
        try:
            result = self.contract.functions.getTradeInfo(trade_id).call()
            return {
                "trade_id": result[0],
                "seller": result[1],
                "buyer": result[2],
                "amount": self.blockchain.w3.from_wei(result[3], 'ether'),
                "status": result[4],
                "nostr_event_id": result[5],
                "create_time": result[6]
            }
        except Exception as e:
            logger.error(f"获取交易信息失败: {e}")
            return {}

    def get_trade_status(self, trade_id: str) -> int:
        try:
            return self.contract.functions.getTradeStatus(trade_id).call()
        except Exception as e:
            logger.error(f"获取交易状态失败: {e}")
            return -1


class RevenueSplitClient:

    def __init__(self, blockchain: BlockchainClient, contract_address: str, abi: List[Dict]):
        self.blockchain = blockchain
        self.contract = blockchain.load_contract("RevenueSplit", contract_address, abi)

    def split_revenue(
        self,
        trade_id: str,
        recipients: List[str],
        ratios: List[int],
        total_amount_eth: float
    ) -> str:
        logger.info(f"执行收益分账: trade_id={trade_id}, recipients={len(recipients)}人")

        amount_wei = self.blockchain.w3.to_wei(total_amount_eth, 'ether')

        checksum_recipients = [Web3.to_checksum_address(addr) for addr in recipients]

        tx_hash = self.blockchain._send_transaction(
            self.contract.functions.splitRevenue(
                trade_id,
                checksum_recipients,
                ratios
            ),
            value=amount_wei
        )

        return tx_hash

    def set_royalty_rate(self, original_asset_id: str, royalty_rate: int) -> str:
        logger.info(f"设置版税率: asset_id={original_asset_id}, rate={royalty_rate/100}%")

        tx_hash = self.blockchain._send_transaction(
            self.contract.functions.setRoyaltyRate(
                original_asset_id,
                royalty_rate
            )
        )

        return tx_hash

    def get_split_history(self, trade_id: str) -> Dict:
        try:
            result = self.contract.functions.getSplitHistory(trade_id).call()
            return {
                "trade_id": result[0],
                "total_amount": self.blockchain.w3.from_wei(result[1], 'ether'),
                "recipients": result[2],
                "ratios": result[3],
                "split_time": result[4]
            }
        except Exception as e:
            logger.error(f"获取分账历史失败: {e}")
            return {}

    def get_royalty_rate(self, original_asset_id: str) -> int:
        try:
            return self.contract.functions.getRoyaltyRate(original_asset_id).call()
        except Exception as e:
            logger.error(f"获取版税率失败: {e}")
            return 0


class MockBlockchainClient:

    def __init__(self, private_key: str = ""):
        import secrets

        if private_key:
            self.private_key = private_key
        else:
            self.private_key = secrets.token_hex(32)

        self.address = "0x" + hashlib.sha256(self.private_key.encode()).hexdigest()[:40]

        self._balances: Dict[str, float] = {self.address: 100.0}

        self._transactions: List[Dict] = []

        self._contract_states: Dict[str, Dict] = {}

        logger.info(f"[模拟] 区块链客户端初始化完成，地址: {self.address[:16]}...")
        self.connected = True

    def is_connected(self) -> bool:
        return self.connected

    def get_balance(self, address: str = "") -> float:
        addr = address or self.address
        return self._balances.get(addr, 0.0)

    def _send_transaction(self, contract_name: str, function_name: str, params: Dict, value: float = 0) -> str:
        import uuid
        tx_hash = "0x" + uuid.uuid4().hex

        tx = {
            "hash": tx_hash,
            "contract": contract_name,
            "function": function_name,
            "params": params,
            "value": value,
            "from": self.address,
            "status": 1,
            "timestamp": int(time.time())
        }
        self._transactions.append(tx)

        if value > 0:
            self._balances[self.address] = self._balances.get(self.address, 0) - value

        logger.info(f"[模拟] 交易已发送: {tx_hash[:16]}...")
        return tx_hash

    def wait_for_receipt(self, tx_hash: str, timeout: int = 120) -> Dict:
        logger.info(f"[模拟] 交易已确认: {tx_hash[:16]}...")
        return {
            "transactionHash": tx_hash,
            "status": 1,
            "blockNumber": 12345
        }


import hashlib


def create_blockchain_client(
    rpc_url: str = "",
    private_key: str = "",
    use_mock: bool = False
) -> BlockchainClient:
    if use_mock or not WEB3_AVAILABLE or not rpc_url:
        if not use_mock:
            logger.warning("web3.py 不可用或未提供 RPC URL，使用模拟客户端")
        return MockBlockchainClient(private_key)
    else:
        return BlockchainClient(rpc_url, private_key)


RISK_ASSET_NFT_ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "assetId", "type": "string"},
            {"internalType": "string", "name": "nostrEventId", "type": "string"},
            {"internalType": "string", "name": "dataHash", "type": "string"},
            {"internalType": "string", "name": "metadataUri", "type": "string"}
        ],
        "name": "mint",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "uint256", "name": "tokenId", "type": "uint256"}],
        "name": "getAssetInfo",
        "outputs": [
            {"internalType": "string", "name": "", "type": "string"},
            {"internalType": "string", "name": "", "type": "string"},
            {"internalType": "string", "name": "", "type": "string"},
            {"internalType": "address", "name": "", "type": "address"},
            {"internalType": "uint256", "name": "", "type": "uint256"},
            {"internalType": "string", "name": "", "type": "string"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]

TRADE_ESCROW_ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "tradeId", "type": "string"},
            {"internalType": "address", "name": "seller", "type": "address"},
            {"internalType": "address", "name": "buyer", "type": "address"},
            {"internalType": "string", "name": "nostrEventId", "type": "string"}
        ],
        "name": "createTrade",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "string", "name": "tradeId", "type": "string"}],
        "name": "confirmTrade",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "string", "name": "tradeId", "type": "string"}],
        "name": "refundTrade",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]

REVENUE_SPLIT_ABI = [
    {
        "inputs": [
            {"internalType": "string", "name": "tradeId", "type": "string"},
            {"internalType": "address[]", "name": "recipients", "type": "address[]"},
            {"internalType": "uint256[]", "name": "ratios", "type": "uint256[]"}
        ],
        "name": "splitRevenue",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "string", "name": "originalAssetId", "type": "string"},
            {"internalType": "uint256", "name": "royaltyRate", "type": "uint256"}
        ],
        "name": "setRoyaltyRate",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    }
]


__all__ = [
    "ContractConfig",
    "BlockchainClient",
    "RiskAssetNFTClient",
    "TradeEscrowClient",
    "RevenueSplitClient",
    "MockBlockchainClient",
    "create_blockchain_client",
    "RISK_ASSET_NFT_ABI",
    "TRADE_ESCROW_ABI",
    "REVENUE_SPLIT_ABI",
]
