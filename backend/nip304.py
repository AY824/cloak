
import json
import time
import hashlib
import base64
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


class NIP304EventType(Enum):
    ASSET_PUBLISH = 30401
    DEMAND_PUBLISH = 30402
    COMPUTE_PARAMS = 30403
    TRADE_RECEIPT = 30404
    REPUTATION_RATING = 30405


class RiskType(Enum):
    DATA_COMPLIANCE = "data_compliance"
    PATENT_INFRINGEMENT = "patent_infringement"
    ALGORITHM_SECURITY = "algorithm_security"
    RD_FAILURE = "rd_failure"
    GEOPOLITICAL = "geopolitical"
    TECH_ETHICS = "tech_ethics"


class ComputeType(Enum):
    FEDERATED_LEARNING = "federated_learning"
    STATISTICAL_ANALYSIS = "statistical_analysis"
    FEATURE_MATCHING = "feature_matching"
    RISK_SCORING = "risk_scoring"


class ParamType(Enum):
    GRADIENT = "gradient"
    WEIGHT = "weight"
    EVALUATION = "evaluation"


class TradeStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DISPUTED = "disputed"
    REFUNDED = "refunded"


class DPLevel(Enum):
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"


@dataclass
class NIP304Event:
    kind: int
    d_tag: str
    pubkey: str = ""
    created_at: int = 0
    tags: List[List[str]] = field(default_factory=list)
    content: str = ""
    sig: str = ""
    event_id: str = ""
    version: str = "1.0"

    def __post_init__(self):
        if self.created_at == 0:
            self.created_at = int(time.time())
        self._ensure_base_tags()

    def _ensure_base_tags(self):
        tag_names = [tag[0] for tag in self.tags]

        if "d" not in tag_names:
            self.tags.insert(0, ["d", self.d_tag])

        if "version" not in tag_names:
            self.tags.append(["version", self.version])

    def to_dict(self) -> Dict:
        return {
            "id": self.event_id,
            "pubkey": self.pubkey,
            "created_at": self.created_at,
            "kind": self.kind,
            "tags": self.tags,
            "content": self.content,
            "sig": self.sig
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'NIP304Event':
        event = cls(
            kind=data["kind"],
            d_tag="",
            pubkey=data.get("pubkey", ""),
            created_at=data.get("created_at", 0),
            tags=data.get("tags", []),
            content=data.get("content", ""),
            sig=data.get("sig", ""),
            event_id=data.get("id", "")
        )
        for tag in event.tags:
            if tag[0] == "d":
                event.d_tag = tag[1]
                break
        return event

    def get_tag_value(self, tag_name: str) -> Optional[str]:
        for tag in self.tags:
            if tag[0] == tag_name and len(tag) > 1:
                return tag[1]
        return None

    def get_content_json(self) -> Dict:
        if not self.content:
            return {}
        try:
            return json.loads(self.content)
        except json.JSONDecodeError:
            return {}


class AssetPublishEvent(NIP304Event):

    def __init__(
        self,
        asset_id: str,
        risk_type: str,
        data_dim: List[str],
        price: float,
        dp_level: str,
        sample_count: int,
        content_data: Dict,
        industry: str = "",
        region: str = "",
        validity: int = 180,
        **kwargs
    ):
        tags = [
            ["d", asset_id],
            ["risk_type", risk_type],
            ["data_dim", ",".join(data_dim)],
            ["price", str(price)],
            ["dp_level", dp_level],
            ["sample_count", str(sample_count)],
        ]

        if industry:
            tags.append(["industry", industry])
        if region:
            tags.append(["region", region])
        if validity:
            tags.append(["validity", str(validity)])

        super().__init__(
            kind=NIP304EventType.ASSET_PUBLISH.value,
            d_tag=asset_id,
            tags=tags,
            content=json.dumps(content_data, ensure_ascii=False),
            **kwargs
        )

    @property
    def asset_id(self) -> str:
        return self.d_tag

    @property
    def risk_type(self) -> str:
        return self.get_tag_value("risk_type") or ""

    @property
    def price(self) -> float:
        return float(self.get_tag_value("price") or 0)

    @property
    def sample_count(self) -> int:
        return int(self.get_tag_value("sample_count") or 0)

    @property
    def data_hash(self) -> str:
        return self.get_content_json().get("data_hash", "")


class DemandPublishEvent(NIP304Event):

    def __init__(
        self,
        demand_id: str,
        risk_type: str,
        compute_type: str,
        budget_min: float,
        budget_max: float,
        content_data: Dict,
        min_participants: int = 0,
        max_participants: int = 0,
        deadline: int = 0,
        **kwargs
    ):
        tags = [
            ["d", demand_id],
            ["risk_type", risk_type],
            ["compute_type", compute_type],
            ["budget_min", str(budget_min)],
            ["budget_max", str(budget_max)],
        ]

        if min_participants > 0:
            tags.append(["min_participants", str(min_participants)])
        if max_participants > 0:
            tags.append(["max_participants", str(max_participants)])
        if deadline > 0:
            tags.append(["deadline", str(deadline)])

        super().__init__(
            kind=NIP304EventType.DEMAND_PUBLISH.value,
            d_tag=demand_id,
            tags=tags,
            content=json.dumps(content_data, ensure_ascii=False),
            **kwargs
        )

    @property
    def demand_id(self) -> str:
        return self.d_tag

    @property
    def risk_type(self) -> str:
        return self.get_tag_value("risk_type") or ""

    @property
    def compute_type(self) -> str:
        return self.get_tag_value("compute_type") or ""

    @property
    def budget_range(self) -> Tuple[float, float]:
        return (
            float(self.get_tag_value("budget_min") or 0),
            float(self.get_tag_value("budget_max") or 0)
        )


class ComputeParamEvent(NIP304Event):

    def __init__(
        self,
        trade_id: str,
        round_num: int,
        role: str = "",
        model_type: str = "",
        params: Dict = None,
        num_samples: int = 0,
        metrics: Dict = None,
        client_pub: str = "",
        param_type: str = "",
        encrypted_params: bytes = None,
        model_hash: str = "",
        encryption: str = "",
        content_data: Dict = None,
        **kwargs
    ):
        tags = [
            ["d", trade_id],
            ["round", str(round_num)],
        ]

        if role:
            tags.append(["role", role])
        if client_pub:
            tags.append(["client_pub", client_pub])
        if param_type:
            tags.append(["param_type", param_type])
        if model_hash:
            tags.append(["model_hash", model_hash])
        if encryption:
            tags.append(["encryption", encryption])

        if content_data is None:
            content_data = {}

        content_data["round"] = round_num
        if role:
            content_data["role"] = role
        if model_type:
            content_data["model_type"] = model_type
        if params is not None:
            content_data["params"] = params
        if num_samples > 0:
            content_data["num_samples"] = num_samples
        if metrics is not None:
            content_data["metrics"] = metrics

        if encrypted_params is not None:
            content_data["encrypted_params"] = base64.b64encode(encrypted_params).decode('utf-8')

        super().__init__(
            kind=NIP304EventType.COMPUTE_PARAMS.value,
            d_tag=trade_id,
            tags=tags,
            content=json.dumps(content_data, ensure_ascii=False),
            **kwargs
        )

    @property
    def trade_id(self) -> str:
        return self.d_tag

    @property
    def round_num(self) -> int:
        return int(self.get_tag_value("round") or 0)

    @property
    def param_type(self) -> str:
        return self.get_tag_value("param_type") or ""

    @property
    def client_pub(self) -> str:
        return self.get_tag_value("client_pub") or ""

    @property
    def role(self) -> str:
        return self.get_tag_value("role") or ""

    def get_encrypted_params(self) -> bytes:
        content = self.get_content_json()
        if "encrypted_params" in content:
            return base64.b64decode(content["encrypted_params"].encode('utf-8'))
        return b""


class TradeReceiptEvent(NIP304Event):

    def __init__(
        self,
        trade_id: str,
        seller_pub: str,
        buyer_pub: str,
        tx_hash: str,
        contract_address: str,
        amount: float,
        status: str,
        content_data: Dict,
        **kwargs
    ):
        tags = [
            ["d", trade_id],
            ["seller_pub", seller_pub],
            ["buyer_pub", buyer_pub],
            ["tx_hash", tx_hash],
            ["contract_address", contract_address],
            ["amount", str(amount)],
            ["status", status],
        ]

        super().__init__(
            kind=NIP304EventType.TRADE_RECEIPT.value,
            d_tag=trade_id,
            tags=tags,
            content=json.dumps(content_data, ensure_ascii=False),
            **kwargs
        )

    @property
    def trade_id(self) -> str:
        return self.d_tag

    @property
    def status(self) -> str:
        return self.get_tag_value("status") or ""

    @property
    def amount(self) -> float:
        return float(self.get_tag_value("amount") or 0)

    @property
    def tx_hash(self) -> str:
        return self.get_tag_value("tx_hash") or ""


class ReputationRatingEvent(NIP304Event):

    def __init__(
        self,
        trade_id: str,
        target_pub: str,
        rater_pub: str,
        role: str,
        overall_score: float,
        violation_flag: bool = False,
        data_quality_score: float = 0,
        contribution_score: float = 0,
        compliance_score: float = 0,
        comment: str = "",
        violation_type: str = "",
        **kwargs
    ):
        tags = [
            ["d", trade_id],
            ["target_pub", target_pub],
            ["rater_pub", rater_pub],
            ["role", role],
        ]

        content_data = {
            "role": role,
            "overall_score": overall_score,
            "violation_flag": violation_flag,
            "target_pub": target_pub,
            "rater_pub": rater_pub,
        }

        if data_quality_score > 0:
            content_data["data_quality_score"] = data_quality_score
        if contribution_score > 0:
            content_data["contribution_score"] = contribution_score
        if compliance_score > 0:
            content_data["compliance_score"] = compliance_score
        if comment:
            content_data["comment"] = comment
        if violation_type:
            content_data["violation_type"] = violation_type

        super().__init__(
            kind=NIP304EventType.REPUTATION_RATING.value,
            d_tag=trade_id,
            tags=tags,
            content=json.dumps(content_data, ensure_ascii=False),
            **kwargs
        )

    @property
    def trade_id(self) -> str:
        return self.d_tag

    @property
    def target_pub(self) -> str:
        return self.get_tag_value("target_pub") or ""

    @property
    def role(self) -> str:
        return self.get_tag_value("role") or ""

    @property
    def overall_score(self) -> float:
        return self.get_content_json().get("overall_score", 0)

    @property
    def violation_flag(self) -> bool:
        return self.get_content_json().get("violation_flag", False)


class NIP304Factory:

    @staticmethod
    def create_asset_publish(
        asset_id: str,
        risk_type: str,
        data_dim: List[str],
        price: float,
        dp_level: str,
        sample_count: int,
        data_hash: str = "",
        time_range: str = "",
        usage_rule: str = "",
        data_schema: Dict = None,
        quality_score: float = 0,
        **kwargs
    ) -> AssetPublishEvent:
        content_data = {
            "risk_type": risk_type,
            "price": price,
            "dp_level": dp_level,
            "sample_count": sample_count,
            "data_dim": data_dim,
            "data_hash": data_hash,
            "time_range": time_range,
            "usage_rule": usage_rule,
        }

        if data_schema:
            content_data["data_schema"] = data_schema
        if quality_score > 0:
            content_data["quality_score"] = quality_score

        return AssetPublishEvent(
            asset_id=asset_id,
            risk_type=risk_type,
            data_dim=data_dim,
            price=price,
            dp_level=dp_level,
            sample_count=sample_count,
            content_data=content_data,
            **kwargs
        )

    @staticmethod
    def create_demand_publish(
        demand_id: str,
        risk_type: str,
        compute_type: str,
        budget_min: float,
        budget_max: float,
        compute_goal: str,
        model_type: str = "",
        target_metric: Dict = None,
        **kwargs
    ) -> DemandPublishEvent:
        content_data = {
            "risk_type": risk_type,
            "compute_type": compute_type,
            "budget_min": budget_min,
            "budget_max": budget_max,
            "compute_goal": compute_goal,
        }

        if model_type:
            content_data["model_type"] = model_type
        if target_metric:
            content_data["target_metric"] = target_metric

        return DemandPublishEvent(
            demand_id=demand_id,
            risk_type=risk_type,
            compute_type=compute_type,
            budget_min=budget_min,
            budget_max=budget_max,
            content_data=content_data,
            **kwargs
        )

    @staticmethod
    def create_compute_param(
        trade_id: str,
        round_num: int,
        client_pub: str,
        param_type: str,
        encrypted_params: bytes,
        **kwargs
    ) -> ComputeParamEvent:
        return ComputeParamEvent(
            trade_id=trade_id,
            round_num=round_num,
            client_pub=client_pub,
            param_type=param_type,
            encrypted_params=encrypted_params,
            **kwargs
        )

    @staticmethod
    def create_trade_receipt(
        trade_id: str,
        seller_pub: str,
        buyer_pub: str,
        tx_hash: str,
        contract_address: str,
        amount: float,
        status: str,
        contribution_distribution: Dict[str, float] = None,
        authorization_scope: str = "",
        model_metrics: Dict = None,
        **kwargs
    ) -> TradeReceiptEvent:
        content_data = {
            "amount": amount,
            "status": status,
            "seller_pub": seller_pub,
            "buyer_pub": buyer_pub,
            "tx_hash": tx_hash,
            "contract_address": contract_address,
        }

        if contribution_distribution is not None:
            content_data["contribution_distribution"] = contribution_distribution
        if authorization_scope:
            content_data["authorization_scope"] = authorization_scope
        if model_metrics:
            content_data["model_metrics"] = model_metrics

        return TradeReceiptEvent(
            trade_id=trade_id,
            seller_pub=seller_pub,
            buyer_pub=buyer_pub,
            tx_hash=tx_hash,
            contract_address=contract_address,
            amount=amount,
            status=status,
            content_data=content_data,
            **kwargs
        )

    @staticmethod
    def create_reputation_rating(
        trade_id: str,
        target_pub: str,
        rater_pub: str,
        role: str,
        overall_score: float,
        violation_flag: bool = False,
        **kwargs
    ) -> ReputationRatingEvent:
        return ReputationRatingEvent(
            trade_id=trade_id,
            target_pub=target_pub,
            rater_pub=rater_pub,
            role=role,
            overall_score=overall_score,
            violation_flag=violation_flag,
            **kwargs
        )

    @staticmethod
    def parse_event(event_data: Dict) -> NIP304Event:
        kind = event_data.get("kind", 0)

        if kind == NIP304EventType.ASSET_PUBLISH.value:
            return AssetPublishEvent.from_dict(event_data)
        elif kind == NIP304EventType.DEMAND_PUBLISH.value:
            return DemandPublishEvent.from_dict(event_data)
        elif kind == NIP304EventType.COMPUTE_PARAMS.value:
            return ComputeParamEvent.from_dict(event_data)
        elif kind == NIP304EventType.TRADE_RECEIPT.value:
            return TradeReceiptEvent.from_dict(event_data)
        elif kind == NIP304EventType.REPUTATION_RATING.value:
            return ReputationRatingEvent.from_dict(event_data)
        else:
            return NIP304Event.from_dict(event_data)


    @staticmethod
    def create_asset_publish_event(*args, **kwargs) -> AssetPublishEvent:
        return NIP304Factory.create_asset_publish(*args, **kwargs)

    @staticmethod
    def create_demand_publish_event(*args, **kwargs) -> DemandPublishEvent:
        return NIP304Factory.create_demand_publish(*args, **kwargs)

    @staticmethod
    def create_compute_params_event(
        trade_id: str,
        round_num: int,
        role: str = "",
        model_type: str = "",
        params: Dict = None,
        num_samples: int = 0,
        metrics: Dict = None,
        **kwargs
    ) -> ComputeParamEvent:
        return ComputeParamEvent(
            trade_id=trade_id,
            round_num=round_num,
            role=role,
            model_type=model_type,
            params=params,
            num_samples=num_samples,
            metrics=metrics,
            **kwargs
        )

    @staticmethod
    def create_trade_receipt_event(*args, **kwargs) -> TradeReceiptEvent:
        return NIP304Factory.create_trade_receipt(*args, **kwargs)

    @staticmethod
    def create_reputation_event(*args, **kwargs) -> ReputationRatingEvent:
        return NIP304Factory.create_reputation_rating(*args, **kwargs)


def compute_event_id(event: Dict) -> str:
    serialized = json.dumps([
        0,
        event["pubkey"],
        event["created_at"],
        event["kind"],
        event["tags"],
        event["content"]
    ], separators=(',', ':'), ensure_ascii=False)

    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


def verify_event_signature(event: Dict) -> bool:
    raise NotImplementedError("请使用 nostr-sdk 进行签名验证")


class NIP304Validator:

    VALID_KINDS = {30401, 30402, 30403, 30404, 30405}

    def __init__(self):
        pass

    def validate_event(self, event) -> Tuple[bool, List[str]]:
        errors = []

        if not hasattr(event, 'kind'):
            errors.append("事件缺少 kind 属性")
        elif event.kind not in self.VALID_KINDS:
            errors.append(f"无效的事件类型: {event.kind}，应为 30401-30405")

        if not hasattr(event, 'tags'):
            errors.append("事件缺少 tags 属性")
        else:
            has_d_tag = any(tag[0] == 'd' for tag in event.tags if len(tag) >= 2)
            if not has_d_tag:
                errors.append("事件缺少 d 标签（唯一标识符）")

        if hasattr(event, 'content') and event.content:
            try:
                json.loads(event.content)
            except json.JSONDecodeError as e:
                errors.append(f"content 不是有效的 JSON: {str(e)}")

        if hasattr(event, 'kind') and event.kind in self.VALID_KINDS:
            kind_errors = self._validate_by_kind(event)
            errors.extend(kind_errors)

        return len(errors) == 0, errors

    def _validate_by_kind(self, event) -> List[str]:
        errors = []
        kind = event.kind

        try:
            content = json.loads(event.content) if event.content else {}
        except json.JSONDecodeError:
            return errors

        if kind == 30401:
            required_fields = ['risk_type', 'price']
            for field in required_fields:
                if field not in content:
                    errors.append(f"资产发布事件缺少必填字段: {field}")

        elif kind == 30402:
            required_fields = ['risk_type', 'compute_type']
            for field in required_fields:
                if field not in content:
                    errors.append(f"需求发布事件缺少必填字段: {field}")

        elif kind == 30403:
            required_fields = ['round', 'role']
            for field in required_fields:
                if field not in content:
                    errors.append(f"计算参数事件缺少必填字段: {field}")

        elif kind == 30404:
            required_fields = ['amount', 'status']
            for field in required_fields:
                if field not in content:
                    errors.append(f"交易凭证事件缺少必填字段: {field}")

        elif kind == 30405:
            required_fields = ['overall_score', 'role']
            for field in required_fields:
                if field not in content:
                    errors.append(f"声誉评价事件缺少必填字段: {field}")

        return errors

    def is_valid_kind(self, kind: int) -> bool:
        return kind in self.VALID_KINDS


class NIP304Parser:

    KIND_TO_NAME = {
        30401: "asset_publish",
        30402: "demand_publish",
        30403: "compute_params",
        30404: "trade_receipt",
        30405: "reputation_rating",
    }

    NAME_TO_KIND = {v: k for k, v in KIND_TO_NAME.items()}

    def __init__(self):
        pass

    def parse_event(self, event) -> Optional[Dict]:
        try:
            result = {}

            result['kind'] = event.kind
            result['event_type'] = self.get_event_type_name(event.kind)
            result['pubkey'] = getattr(event, 'pubkey', '')
            result['created_at'] = getattr(event, 'created_at', 0)

            if hasattr(event, 'tags'):
                for tag in event.tags:
                    if tag[0] == 'd' and len(tag) >= 2:
                        result['id'] = tag[1]
                        if event.kind == 30401:
                            result['asset_id'] = tag[1]
                        elif event.kind == 30402:
                            result['demand_id'] = tag[1]
                        elif event.kind == 30403:
                            result['trade_id'] = tag[1]
                        elif event.kind == 30404:
                            result['trade_id'] = tag[1]
                        elif event.kind == 30405:
                            result['trade_id'] = tag[1]
                        break

            if hasattr(event, 'content') and event.content:
                try:
                    content_data = json.loads(event.content)
                    result.update(content_data)
                except json.JSONDecodeError:
                    result['content_raw'] = event.content

            if hasattr(event, 'tags'):
                tags_dict = {}
                for tag in event.tags:
                    if len(tag) >= 2:
                        tags_dict[tag[0]] = tag[1]
                result['tags'] = tags_dict

            return result

        except Exception as e:
            print(f"解析事件失败: {e}")
            return None

    def get_event_type_name(self, kind: int) -> Optional[str]:
        return self.KIND_TO_NAME.get(kind)

    def get_event_kind(self, type_name: str) -> Optional[int]:
        return self.NAME_TO_KIND.get(type_name)

    def extract_d_tag(self, tags: List[List[str]]) -> Optional[str]:
        for tag in tags:
            if tag[0] == 'd' and len(tag) >= 2:
                return tag[1]
        return None


__all__ = [
    "NIP304EventType",
    "RiskType",
    "ComputeType",
    "ParamType",
    "TradeStatus",
    "DPLevel",
    "NIP304Event",
    "AssetPublishEvent",
    "DemandPublishEvent",
    "ComputeParamEvent",
    "TradeReceiptEvent",
    "ReputationRatingEvent",
    "NIP304Factory",
    "NIP304Validator",
    "NIP304Parser",
    "compute_event_id",
    "verify_event_signature",
]
