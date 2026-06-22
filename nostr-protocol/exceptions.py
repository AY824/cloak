
from typing import Optional, Dict, Any


class CloakError(Exception):

    def __init__(
        self,
        message: str = "Cloak发生未知错误",
        error_code: str = "UNKNOWN_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self) -> str:
        base = f"[{self.error_code}] {self.message}"
        if self.details:
            base += f" | Details: {self.details}"
        return base



class NostrError(CloakError):

    def __init__(self, message: str = "Nostr 操作失败", **kwargs):
        super().__init__(message, error_code="NOSTR_ERROR", **kwargs)


class NostrConnectionError(NostrError):

    def __init__(self, relay_url: str = "", message: str = "Nostr 中继连接失败", **kwargs):
        details = kwargs.pop("details", {})
        details["relay_url"] = relay_url
        super().__init__(message, error_code="NOSTR_CONNECTION_ERROR", details=details, **kwargs)


class NostrSubscriptionError(NostrError):

    def __init__(self, subscription_id: str = "", message: str = "Nostr 订阅失败", **kwargs):
        details = kwargs.pop("details", {})
        details["subscription_id"] = subscription_id
        super().__init__(message, error_code="NOSTR_SUBSCRIPTION_ERROR", details=details, **kwargs)


class NostrEventError(NostrError):

    def __init__(self, event_id: str = "", message: str = "Nostr 事件处理失败", **kwargs):
        details = kwargs.pop("details", {})
        details["event_id"] = event_id
        super().__init__(message, error_code="NOSTR_EVENT_ERROR", details=details, **kwargs)


class NostrSignError(NostrError):

    def __init__(self, message: str = "Nostr 事件签名失败", **kwargs):
        super().__init__(message, error_code="NOSTR_SIGN_ERROR", **kwargs)


class NostrTimeoutError(NostrError):

    def __init__(self, operation: str = "", timeout: float = 0, message: str = "Nostr 操作超时", **kwargs):
        details = kwargs.pop("details", {})
        details["operation"] = operation
        details["timeout"] = timeout
        super().__init__(message, error_code="NOSTR_TIMEOUT_ERROR", details=details, **kwargs)



class NIP304Error(CloakError):

    def __init__(self, message: str = "NIP-304 协议错误", **kwargs):
        super().__init__(message, error_code="NIP304_ERROR", **kwargs)


class NIP304ValidationError(NIP304Error):

    def __init__(self, field: str = "", message: str = "NIP-304 字段验证失败", **kwargs):
        details = kwargs.pop("details", {})
        details["field"] = field
        super().__init__(message, error_code="NIP304_VALIDATION_ERROR", details=details, **kwargs)


class NIP304EventTypeError(NIP304Error):

    def __init__(self, event_type: int = 0, message: str = "无效的 NIP-304 事件类型", **kwargs):
        details = kwargs.pop("details", {})
        details["event_type"] = event_type
        super().__init__(message, error_code="NIP304_EVENT_TYPE_ERROR", details=details, **kwargs)


class NIP304TagError(NIP304Error):

    def __init__(self, tag_name: str = "", message: str = "NIP-304 标签处理失败", **kwargs):
        details = kwargs.pop("details", {})
        details["tag_name"] = tag_name
        super().__init__(message, error_code="NIP304_TAG_ERROR", details=details, **kwargs)



class FederatedLearningError(CloakError):

    def __init__(self, message: str = "联邦学习操作失败", **kwargs):
        super().__init__(message, error_code="FEDERATED_LEARNING_ERROR", **kwargs)


class ModelError(FederatedLearningError):

    def __init__(self, model_type: str = "", message: str = "模型操作失败", **kwargs):
        details = kwargs.pop("details", {})
        details["model_type"] = model_type
        super().__init__(message, error_code="MODEL_ERROR", details=details, **kwargs)


class TrainingError(FederatedLearningError):

    def __init__(self, round_num: int = 0, message: str = "模型训练失败", **kwargs):
        details = kwargs.pop("details", {})
        details["round"] = round_num
        super().__init__(message, error_code="TRAINING_ERROR", details=details, **kwargs)


class AggregationError(FederatedLearningError):

    def __init__(self, message: str = "模型聚合失败", **kwargs):
        super().__init__(message, error_code="AGGREGATION_ERROR", **kwargs)


class WeightsFormatError(FederatedLearningError):

    def __init__(self, message: str = "模型权重格式错误", **kwargs):
        super().__init__(message, error_code="WEIGHTS_FORMAT_ERROR", **kwargs)


class DataError(FederatedLearningError):

    def __init__(self, message: str = "数据处理失败", **kwargs):
        super().__init__(message, error_code="DATA_ERROR", **kwargs)


class DataShapeError(DataError):

    def __init__(self, expected_shape: tuple = (), actual_shape: tuple = (), message: str = "数据形状不匹配", **kwargs):
        details = kwargs.pop("details", {})
        details["expected_shape"] = expected_shape
        details["actual_shape"] = actual_shape
        super().__init__(message, error_code="DATA_SHAPE_ERROR", details=details, **kwargs)



class BlockchainError(CloakError):

    def __init__(self, message: str = "区块链操作失败", **kwargs):
        super().__init__(message, error_code="BLOCKCHAIN_ERROR", **kwargs)


class ContractError(BlockchainError):

    def __init__(self, contract_name: str = "", message: str = "智能合约操作失败", **kwargs):
        details = kwargs.pop("details", {})
        details["contract_name"] = contract_name
        super().__init__(message, error_code="CONTRACT_ERROR", details=details, **kwargs)


class TransactionError(BlockchainError):

    def __init__(self, tx_hash: str = "", message: str = "交易执行失败", **kwargs):
        details = kwargs.pop("details", {})
        details["tx_hash"] = tx_hash
        super().__init__(message, error_code="TRANSACTION_ERROR", details=details, **kwargs)


class WalletError(BlockchainError):

    def __init__(self, message: str = "钱包操作失败", **kwargs):
        super().__init__(message, error_code="WALLET_ERROR", **kwargs)


class InsufficientBalanceError(BlockchainError):

    def __init__(self, required: float = 0, actual: float = 0, message: str = "账户余额不足", **kwargs):
        details = kwargs.pop("details", {})
        details["required"] = required
        details["actual"] = actual
        super().__init__(message, error_code="INSUFFICIENT_BALANCE_ERROR", details=details, **kwargs)



class TradeError(CloakError):

    def __init__(self, trade_id: str = "", message: str = "交易操作失败", **kwargs):
        details = kwargs.pop("details", {})
        details["trade_id"] = trade_id
        super().__init__(message, error_code="TRADE_ERROR", details=details, **kwargs)


class TradeStatusError(TradeError):

    def __init__(self, current_status: str = "", expected_status: str = "", message: str = "交易状态不匹配", **kwargs):
        details = kwargs.pop("details", {})
        details["current_status"] = current_status
        details["expected_status"] = expected_status
        super().__init__(message, error_code="TRADE_STATUS_ERROR", details=details, **kwargs)


class TradeNotFoundError(TradeError):

    def __init__(self, trade_id: str = "", message: str = "交易不存在", **kwargs):
        super().__init__(trade_id, message, error_code="TRADE_NOT_FOUND_ERROR", **kwargs)



class ConfigError(CloakError):

    def __init__(self, message: str = "配置错误", **kwargs):
        super().__init__(message, error_code="CONFIG_ERROR", **kwargs)


class ConfigNotFoundError(ConfigError):

    def __init__(self, config_path: str = "", message: str = "配置文件不存在", **kwargs):
        details = kwargs.pop("details", {})
        details["config_path"] = config_path
        super().__init__(message, error_code="CONFIG_NOT_FOUND_ERROR", details=details, **kwargs)


class ConfigValueError(ConfigError):

    def __init__(self, key: str = "", message: str = "配置值无效", **kwargs):
        details = kwargs.pop("details", {})
        details["key"] = key
        super().__init__(message, error_code="CONFIG_VALUE_ERROR", details=details, **kwargs)



def is_retryable_error(error: Exception) -> bool:
    retryable_errors = (
        NostrConnectionError,
        NostrTimeoutError,
        BlockchainError,
        TransactionError,
    )

    return isinstance(error, retryable_errors)


def get_error_category(error: Exception) -> str:
    if isinstance(error, NostrError):
        return "nostr"
    elif isinstance(error, NIP304Error):
        return "nip304"
    elif isinstance(error, FederatedLearningError):
        return "federated_learning"
    elif isinstance(error, BlockchainError):
        return "blockchain"
    elif isinstance(error, TradeError):
        return "trade"
    elif isinstance(error, ConfigError):
        return "config"
    else:
        return "unknown"


__all__ = [
    "CloakError",
    "NostrError",
    "NostrConnectionError",
    "NostrSubscriptionError",
    "NostrEventError",
    "NostrSignError",
    "NostrTimeoutError",
    "NIP304Error",
    "NIP304ValidationError",
    "NIP304EventTypeError",
    "NIP304TagError",
    "FederatedLearningError",
    "ModelError",
    "TrainingError",
    "AggregationError",
    "WeightsFormatError",
    "DataError",
    "DataShapeError",
    "BlockchainError",
    "ContractError",
    "TransactionError",
    "WalletError",
    "InsufficientBalanceError",
    "TradeError",
    "TradeStatusError",
    "TradeNotFoundError",
    "ConfigError",
    "ConfigNotFoundError",
    "ConfigValueError",
    "is_retryable_error",
    "get_error_category",
]
