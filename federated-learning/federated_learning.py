
import json
import time
import pickle
import base64
import hashlib
from typing import List, Dict, Tuple, Optional, Callable
from dataclasses import dataclass, field
from loguru import logger

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score, f1_score
from sklearn.model_selection import train_test_split

try:
    import flwr as fl
    from flwr.common import Parameters, FitIns, FitRes, EvaluateIns, EvaluateRes
    FLOWER_AVAILABLE = True
except ImportError:
    FLOWER_AVAILABLE = False
    logger.warning("Flower 未安装，部分功能将不可用")

from nip304 import NIP304EventType, ParamType, NIP304Factory
from nostr_client import NostrClient, MockNostrClient


@dataclass
class ModelWeights:
    weights: List[np.ndarray]
    model_type: str = "logistic_regression"

    def serialize(self) -> str:
        data = {
            "weights": [w.tolist() for w in self.weights],
            "model_type": self.model_type
        }
        serialized_bytes = pickle.dumps(data)
        return base64.b64encode(serialized_bytes).decode('utf-8')

    def serialize_bytes(self) -> bytes:
        data = {
            "weights": [w.tolist() for w in self.weights],
            "model_type": self.model_type
        }
        return pickle.dumps(data)

    @classmethod
    def deserialize(cls, data) -> 'ModelWeights':
        if isinstance(data, str):
            data_bytes = base64.b64decode(data.encode('utf-8'))
        else:
            data_bytes = data

        loaded = pickle.loads(data_bytes)
        weights = [np.array(w) for w in loaded["weights"]]
        return cls(weights=weights, model_type=loaded["model_type"])

    def get_hash(self) -> str:
        return hashlib.sha256(self.serialize_bytes()).hexdigest()

    def get_total_params(self) -> int:
        total = 0
        for w in self.weights:
            total += w.size
        return total


@dataclass
class TrainingResult:
    weights: ModelWeights
    num_examples: int
    metrics: Dict
    loss: float = 0.0


class FederatedClient:

    def __init__(
        self,
        nostr_client=None,
        client_id: str = "",
        model_type: str = "logistic_regression"
    ):
        if nostr_client is None:
            self.nostr = MockNostrClient()
        else:
            self.nostr = nostr_client

        if client_id:
            self.client_id = client_id
        else:
            try:
                self.client_id = self.nostr.get_public_key(bech32=False)
            except:
                self.client_id = f"client_{id(self)}"

        self.model_type = model_type

        self.model = self._create_model()

        self.current_trade_id = ""

        self.is_training = False
        self.current_round = 0

        self.X_train = None
        self.X_test = None
        self.y_train = None
        self.y_test = None
        self.num_samples = 0
        self.num_examples = 0

        logger.info(f"联邦学习客户端初始化完成: {self.client_id[:16]}...")

    def _create_model(self):
        if self.model_type == "logistic_regression":
            return LogisticRegression(
                max_iter=100,
                solver='lbfgs',
                warm_start=True
            )
        else:
            raise ValueError(f"不支持的模型类型: {self.model_type}")

    def load_data(self, X: np.ndarray, y: np.ndarray, test_size: float = 0.0):
        if test_size > 0:
            self.X_train, self.X_test, self.y_train, self.y_test = train_test_split(
                X, y, test_size=test_size, random_state=42
            )
        else:
            self.X_train = X
            self.y_train = y
            self.X_test = X
            self.y_test = y

        self.num_examples = len(self.X_train)
        self.num_samples = len(self.X_train)
        logger.info(f"数据加载完成: 训练集 {len(self.X_train)} 条, 测试集 {len(self.X_test)} 条")

    def get_model_weights(self) -> ModelWeights:
        if self.model_type == "logistic_regression":
            weights = [self.model.coef_, self.model.intercept_]
            return ModelWeights(weights=weights, model_type=self.model_type)
        else:
            raise ValueError(f"不支持的模型类型: {self.model_type}")

    def set_model_weights(self, weights: ModelWeights):
        if self.model_type != weights.model_type:
            raise ValueError(f"模型类型不匹配: {self.model_type} vs {weights.model_type}")

        if self.model_type == "logistic_regression":
            self.model.coef_ = weights.weights[0]
            self.model.intercept_ = weights.weights[1]
            self.model.classes_ = np.array([0, 1])
        else:
            raise ValueError(f"不支持的模型类型: {self.model_type}")

    def train_local(self, epochs: int = 1) -> TrainingResult:
        logger.info(f"开始本地训练，轮次: {epochs}")

        for _ in range(epochs):
            self.model.fit(self.X_train, self.y_train)

        y_pred = self.model.predict(self.X_test)
        y_pred_proba = self.model.predict_proba(self.X_test)[:, 1]

        from sklearn.metrics import log_loss
        loss = log_loss(self.y_test, y_pred_proba)

        metrics = {
            "accuracy": accuracy_score(self.y_test, y_pred),
            "precision": float(np.mean(y_pred[self.y_test == 1])) if np.sum(self.y_test == 1) > 0 else 0.0,
            "recall": float(np.mean(y_pred[self.y_test == 1])) if np.sum(self.y_test == 1) > 0 else 0.0,
            "f1_score": f1_score(self.y_test, y_pred, zero_division=0),
            "auc": roc_auc_score(self.y_test, y_pred_proba) if len(np.unique(self.y_test)) > 1 else 0.5,
            "loss": loss
        }

        weights = self.get_model_weights()

        logger.info(f"本地训练完成: accuracy={metrics['accuracy']:.4f}, loss={metrics['loss']:.4f}")

        return TrainingResult(
            weights=weights,
            num_examples=self.num_examples,
            metrics=metrics,
            loss=loss
        )

    def evaluate_local(self) -> Dict:
        y_pred = self.model.predict(self.X_test)
        y_pred_proba = self.model.predict_proba(self.X_test)[:, 1]

        metrics = {
            "accuracy": accuracy_score(self.y_test, y_pred),
            "auc": roc_auc_score(self.y_test, y_pred_proba),
            "f1_score": f1_score(self.y_test, y_pred),
            "num_examples": len(self.X_test)
        }

        return metrics

    def send_gradient_via_nostr(self, trade_id: str, round_num: int, weights: ModelWeights):
        weights_bytes = weights.serialize()

        encrypted_params = weights_bytes

        event_id = self.nostr.publish_compute_param_event(
            trade_id=trade_id,
            round_num=round_num,
            client_pub=self.client_id,
            param_type=ParamType.GRADIENT.value,
            encrypted_params=encrypted_params,
            model_hash=weights.get_hash(),
            encryption="none"
        )

        logger.info(f"梯度已通过 Nostr 发送: round={round_num}, event_id={event_id[:16]}...")
        return event_id

    def receive_global_weights_via_nostr(self, trade_id: str, round_num: int) -> Optional[ModelWeights]:
        events = self.nostr.query_events(
            kinds=[NIP304EventType.COMPUTE_PARAM.value],
            tag_filters={
                "d": trade_id,
                "round": str(round_num),
                "param_type": ParamType.WEIGHT.value
            },
            limit=10
        )

        if not events:
            logger.warning(f"未找到第 {round_num} 轮的全局权重")
            return None

        event = events[-1]

        encrypted_params = event.get_encrypted_params()
        weights = ModelWeights.deserialize(encrypted_params)

        logger.info(f"从 Nostr 接收到全局权重: round={round_num}, hash={weights.get_hash()[:16]}...")
        return weights

    def participate_in_training(
        self,
        trade_id: str,
        num_rounds: int = 5,
        local_epochs: int = 1
    ):
        logger.info(f"开始参与联邦学习: trade_id={trade_id}, rounds={num_rounds}")
        self.current_trade_id = trade_id
        self.is_training = True

        for round_num in range(1, num_rounds + 1):
            self.current_round = round_num
            logger.info(f"=== 第 {round_num}/{num_rounds} 轮训练 ===")

            global_weights = self.receive_global_weights_via_nostr(trade_id, round_num)

            if global_weights:
                self.set_model_weights(global_weights)
                logger.info("已更新本地模型权重")

            result = self.train_local(epochs=local_epochs)

            self.send_gradient_via_nostr(trade_id, round_num, result.weights)

            time.sleep(1)

        self.is_training = False
        logger.info("联邦学习参与完成")


class FederatedAggregator:

    def __init__(
        self,
        nostr_client=None,
        aggregator_id: str = "",
        model_type: str = "logistic_regression",
        num_clients: int = 3
    ):
        if nostr_client is None:
            self.nostr = MockNostrClient()
        else:
            self.nostr = nostr_client

        if aggregator_id:
            self.aggregator_id = aggregator_id
        else:
            try:
                self.aggregator_id = self.nostr.get_public_key(bech32=False)
            except:
                self.aggregator_id = f"aggregator_{id(self)}"

        self.model_type = model_type
        self.num_clients = num_clients

        self.global_model = self._create_model()
        self.global_weights = self._get_initial_weights()

        self.current_trade_id = ""
        self.current_round = 0
        self.is_aggregating = False

        self.client_weights: Dict[str, ModelWeights] = {}
        self.client_examples: Dict[str, int] = {}

        logger.info(f"联邦学习聚合端初始化完成: {self.aggregator_id[:16]}...")

    def _create_model(self):
        if self.model_type == "logistic_regression":
            return LogisticRegression(
                max_iter=100,
                solver='lbfgs',
                warm_start=True
            )
        else:
            raise ValueError(f"不支持的模型类型: {self.model_type}")

    def _get_initial_weights(self) -> ModelWeights:
        if self.model_type == "logistic_regression":
            coef = np.zeros((1, 10))
            intercept = np.zeros(1)
            return ModelWeights(
                weights=[coef, intercept],
                model_type=self.model_type
            )
        else:
            raise ValueError(f"不支持的模型类型: {self.model_type}")

    def set_initial_weights(self, weights: ModelWeights):
        self.global_weights = weights
        logger.info(f"已设置初始权重，哈希: {weights.get_hash()[:16]}...")

    def aggregate_weights(
        self,
        client_weights,
        client_examples
    ) -> ModelWeights:
        if isinstance(client_weights, dict):
            weights_list = list(client_weights.values())
            examples_list = list(client_examples.values())
        else:
            weights_list = list(client_weights)
            examples_list = list(client_examples)

        if not weights_list:
            raise ValueError("没有客户端权重可供聚合")

        logger.info(f"开始聚合 {len(weights_list)} 个客户端的权重")

        total_examples = sum(examples_list)

        first_weights = weights_list[0]
        num_weight_arrays = len(first_weights.weights)

        aggregated_weights = []

        for i in range(num_weight_arrays):
            weighted_sum = None

            for j, weights in enumerate(weights_list):
                num_ex = examples_list[j]
                weight = weights.weights[i]

                if weighted_sum is None:
                    weighted_sum = weight * (num_ex / total_examples)
                else:
                    weighted_sum += weight * (num_ex / total_examples)

            aggregated_weights.append(weighted_sum)

        result = ModelWeights(
            weights=aggregated_weights,
            model_type=self.model_type
        )

        logger.info(f"权重聚合完成，哈希: {result.get_hash()[:16]}...")
        return result

    def send_global_weights_via_nostr(self, trade_id: str, round_num: int):
        weights_bytes = self.global_weights.serialize()

        encrypted_params = weights_bytes

        event_id = self.nostr.publish_compute_param_event(
            trade_id=trade_id,
            round_num=round_num,
            client_pub=self.aggregator_id,
            param_type=ParamType.WEIGHT.value,
            encrypted_params=encrypted_params,
            model_hash=self.global_weights.get_hash(),
            encryption="none"
        )

        logger.info(f"全局权重已通过 Nostr 发送: round={round_num}, event_id={event_id[:16]}...")
        return event_id

    def collect_client_weights_via_nostr(
        self,
        trade_id: str,
        round_num: int,
        timeout: int = 60
    ) -> Tuple[Dict[str, ModelWeights], Dict[str, int]]:
        logger.info(f"收集客户端权重: round={round_num}, 预期 {self.num_clients} 个客户端")

        start_time = time.time()
        collected_weights: Dict[str, ModelWeights] = {}
        collected_examples: Dict[str, int] = {}

        while len(collected_weights) < self.num_clients:
            events = self.nostr.query_events(
                kinds=[NIP304EventType.COMPUTE_PARAM.value],
                tag_filters={
                    "d": trade_id,
                    "round": str(round_num),
                    "param_type": ParamType.GRADIENT.value
                },
                limit=20
            )

            for event in events:
                client_pub = event.client_pub
                if client_pub not in collected_weights:
                    try:
                        encrypted_params = event.get_encrypted_params()
                        weights = ModelWeights.deserialize(encrypted_params)
                        collected_weights[client_pub] = weights
                        collected_examples[client_pub] = 100
                    except Exception as e:
                        logger.error(f"解析客户端权重失败: {e}")

            if len(collected_weights) >= self.num_clients:
                break

            if time.time() - start_time > timeout:
                logger.warning(f"收集超时，已收集 {len(collected_weights)}/{self.num_clients} 个客户端")
                break

            time.sleep(2)

        logger.info(f"收集完成: {len(collected_weights)} 个客户端")
        return collected_weights, collected_examples

    def run_federated_training(
        self,
        trade_id: str,
        num_rounds: int = 5,
        timeout_per_round: int = 60
    ) -> ModelWeights:
        logger.info(f"开始联邦学习训练: trade_id={trade_id}, rounds={num_rounds}")
        self.current_trade_id = trade_id
        self.is_aggregating = True

        for round_num in range(1, num_rounds + 1):
            self.current_round = round_num
            logger.info(f"=== 第 {round_num}/{num_rounds} 轮聚合 ===")

            self.send_global_weights_via_nostr(trade_id, round_num)

            client_weights, client_examples = self.collect_client_weights_via_nostr(
                trade_id, round_num, timeout_per_round
            )

            if not client_weights:
                logger.error("未收集到任何客户端权重，训练终止")
                break

            self.global_weights = self.aggregate_weights(client_weights, client_examples)

            contributions = self.calculate_contributions(client_weights, client_examples)
            logger.info(f"本轮贡献度: { {k[:8]: round(v, 4) for k, v in contributions.items()} }")

        self.send_global_weights_via_nostr(trade_id, num_rounds + 1)

        self.is_aggregating = False
        logger.info("联邦学习训练完成")

        return self.global_weights

    def calculate_contributions(
        self,
        client_weights: Dict[str, ModelWeights],
        client_examples: Dict[str, int]
    ) -> Dict[str, float]:
        total_examples = sum(client_examples.values())
        contributions = {}

        for client_id, num_ex in client_examples.items():
            contributions[client_id] = num_ex / total_examples

        return contributions

    def evaluate_global_model(self, X_test: np.ndarray, y_test: np.ndarray) -> Dict:
        if self.model_type == "logistic_regression":
            self.global_model.coef_ = self.global_weights.weights[0]
            self.global_model.intercept_ = self.global_weights.weights[1]
            self.global_model.classes_ = np.array([0, 1])

        y_pred = self.global_model.predict(X_test)
        y_pred_proba = self.global_model.predict_proba(X_test)[:, 1]

        from sklearn.metrics import precision_score, recall_score

        metrics = {
            "accuracy": accuracy_score(y_test, y_pred),
            "precision": precision_score(y_test, y_pred, zero_division=0),
            "recall": recall_score(y_test, y_pred, zero_division=0),
            "f1_score": f1_score(y_test, y_pred, zero_division=0),
            "auc": roc_auc_score(y_test, y_pred_proba) if len(np.unique(y_test)) > 1 else 0.5,
        }

        logger.info(f"全局模型评估: accuracy={metrics['accuracy']:.4f}, auc={metrics['auc']:.4f}")
        return metrics


class ContributionCalculator:

    @staticmethod
    def calculate_sample_based(client_examples: Dict[str, int]) -> Dict[str, float]:
        total = sum(client_examples.values())
        return {k: v / total for k, v in client_examples.items()}

    @staticmethod
    def calculate_by_sample_size(client_examples: Dict[str, int]) -> Dict[str, float]:
        return ContributionCalculator.calculate_sample_based(client_examples)

    @staticmethod
    def calculate_performance_based(
        client_metrics: Dict[str, Dict],
        metric_name: str = "auc"
    ) -> Dict[str, float]:
        scores = {k: v.get(metric_name, 0) for k, v in client_metrics.items()}
        total = sum(scores.values())

        if total == 0:
            return {k: 1.0 / len(scores) for k in scores}

        return {k: v / total for k, v in scores.items()}

    @staticmethod
    def calculate_by_performance(
        client_metrics: Dict[str, Dict],
        metric_key: str = "auc"
    ) -> Dict[str, float]:
        return ContributionCalculator.calculate_performance_based(client_metrics, metric_key)

    @staticmethod
    def calculate_combined(
        client_examples: Dict[str, int],
        client_metrics: Dict[str, Dict],
        sample_weight: float = 0.6,
        performance_weight: float = 0.4,
        metric_name: str = "auc",
        metric_key: str = "auc"
    ) -> Dict[str, float]:
        actual_metric = metric_key if metric_key != "auc" else metric_name

        sample_contrib = ContributionCalculator.calculate_sample_based(client_examples)
        perf_contrib = ContributionCalculator.calculate_performance_based(client_metrics, actual_metric)

        combined = {}
        for client_id in sample_contrib.keys():
            combined[client_id] = (
                sample_weight * sample_contrib.get(client_id, 0) +
                performance_weight * perf_contrib.get(client_id, 0)
            )

        total = sum(combined.values())
        if total > 0:
            combined = {k: v / total for k, v in combined.items()}

        return combined

    @staticmethod
    def calculate_shapley_approx(
        client_metrics: Dict[str, Dict],
        metric_key: str = "accuracy"
    ) -> Dict[str, float]:
        clients = list(client_metrics.keys())
        n = len(clients)

        if n == 0:
            return {}

        scores = {k: v.get(metric_key, 0) for k, v in client_metrics.items()}

        sorted_clients = sorted(clients, key=lambda c: scores[c], reverse=True)

        contributions = {}
        total_score = sum(scores.values())

        if total_score == 0:
            return {k: 1.0 / n for k in clients}

        for i, client in enumerate(sorted_clients):
            rank_weight = 1.0 / (i + 1)
            score_weight = scores[client] / total_score
            contributions[client] = rank_weight * score_weight

        total = sum(contributions.values())
        if total > 0:
            contributions = {k: v / total for k, v in contributions.items()}

        return contributions


class DifferentialPrivacy:

    @staticmethod
    def add_laplace_noise(
        weights: List[np.ndarray],
        epsilon: float,
        sensitivity: float = 1.0
    ) -> List[np.ndarray]:
        if epsilon <= 0:
            raise ValueError("epsilon 必须大于 0")

        scale = sensitivity / epsilon
        noisy_weights = []

        for w in weights:
            noise = np.random.laplace(0, scale, size=w.shape)
            noisy_weights.append(w + noise)

        logger.debug(f"已添加 Laplace 噪声: epsilon={epsilon}, sensitivity={sensitivity}")
        return noisy_weights

    @staticmethod
    def add_gaussian_noise(
        weights: List[np.ndarray],
        epsilon: float,
        delta: float = 1e-5,
        sensitivity: float = 1.0
    ) -> List[np.ndarray]:
        if epsilon <= 0 or delta <= 0:
            raise ValueError("epsilon 和 delta 必须大于 0")

        sigma = sensitivity * np.sqrt(2 * np.log(1.25 / delta)) / epsilon
        noisy_weights = []

        for w in weights:
            noise = np.random.normal(0, sigma, size=w.shape)
            noisy_weights.append(w + noise)

        logger.debug(f"已添加 Gaussian 噪声: epsilon={epsilon}, delta={delta}")
        return noisy_weights

    @staticmethod
    def get_privacy_budget_per_round(
        total_epsilon: float,
        num_rounds: int,
        delta: float = 1e-5
    ) -> float:
        return total_epsilon / (2 * np.sqrt(num_rounds * np.log(1 / delta)))

    @staticmethod
    def calculate_privacy_loss(
        num_rounds: int,
        epsilon_per_round: float,
        delta: float = 1e-5
    ) -> float:
        return epsilon_per_round * np.sqrt(2 * num_rounds * np.log(1 / delta))


@dataclass
class TrainingHistory:
    rounds: List[int] = field(default_factory=list)
    losses: List[float] = field(default_factory=list)
    accuracies: List[float] = field(default_factory=list)
    precisions: List[float] = field(default_factory=list)
    recalls: List[float] = field(default_factory=list)
    f1_scores: List[float] = field(default_factory=list)
    aucs: List[float] = field(default_factory=list)
    client_participation: List[int] = field(default_factory=list)
    contributions: List[Dict[str, float]] = field(default_factory=list)
    timestamps: List[float] = field(default_factory=list)

    def add_round_metrics(
        self,
        round_num: int,
        metrics: Dict[str, float],
        num_clients: int,
        contributions: Optional[Dict[str, float]] = None
    ):
        self.rounds.append(round_num)
        self.losses.append(metrics.get("loss", 0.0))
        self.accuracies.append(metrics.get("accuracy", 0.0))
        self.precisions.append(metrics.get("precision", 0.0))
        self.recalls.append(metrics.get("recall", 0.0))
        self.f1_scores.append(metrics.get("f1_score", 0.0))
        self.aucs.append(metrics.get("auc", 0.0))
        self.client_participation.append(num_clients)
        self.timestamps.append(time.time())

        if contributions:
            self.contributions.append(contributions)

    def get_summary(self) -> Dict:
        if not self.rounds:
            return {}

        return {
            "total_rounds": len(self.rounds),
            "final_accuracy": self.accuracies[-1] if self.accuracies else 0,
            "final_auc": self.aucs[-1] if self.aucs else 0,
            "final_f1": self.f1_scores[-1] if self.f1_scores else 0,
            "best_accuracy": max(self.accuracies) if self.accuracies else 0,
            "best_auc": max(self.aucs) if self.aucs else 0,
            "avg_clients": np.mean(self.client_participation) if self.client_participation else 0,
            "total_time": self.timestamps[-1] - self.timestamps[0] if len(self.timestamps) >= 2 else 0
        }

    def to_dict(self) -> Dict:
        return {
            "rounds": self.rounds,
            "losses": self.losses,
            "accuracies": self.accuracies,
            "precisions": self.precisions,
            "recalls": self.recalls,
            "f1_scores": self.f1_scores,
            "aucs": self.aucs,
            "client_participation": self.client_participation,
            "contributions": [
                {k[:16]: v for k, v in c.items()}
                for c in self.contributions
            ],
            "timestamps": self.timestamps
        }


def calculate_comprehensive_metrics(y_true, y_pred, y_pred_proba=None) -> Dict:
    metrics = {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1_score": f1_score(y_true, y_pred, zero_division=0),
    }

    if y_pred_proba is not None:
        try:
            metrics["auc"] = roc_auc_score(y_true, y_pred_proba)
        except ValueError:
            metrics["auc"] = 0.0

    cm = confusion_matrix(y_true, y_pred)
    if cm.shape == (2, 2):
        tn, fp, fn, tp = cm.ravel()
        metrics["true_positive"] = int(tp)
        metrics["true_negative"] = int(tn)
        metrics["false_positive"] = int(fp)
        metrics["false_negative"] = int(fn)
        metrics["specificity"] = tn / (tn + fp) if (tn + fp) > 0 else 0

    return metrics


__all__ = [
    "ModelWeights",
    "TrainingResult",
    "FederatedClient",
    "FederatedAggregator",
    "ContributionCalculator",
    "DifferentialPrivacy",
    "TrainingHistory",
    "calculate_comprehensive_metrics",
]
