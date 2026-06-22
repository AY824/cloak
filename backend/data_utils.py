
import hashlib
import json
from typing import Tuple, List, Dict
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler, LabelEncoder
from loguru import logger


@dataclass
class RiskDataset:
    name: str
    X: np.ndarray
    y: np.ndarray
    feature_names: List[str]
    risk_type: str
    sample_count: int
    data_hash: str

    def get_data_hash(self) -> str:
        data_str = json.dumps({
            "X_shape": list(self.X.shape),
            "y_shape": list(self.y.shape),
            "feature_names": self.feature_names,
            "X_sum": float(np.sum(self.X)),
            "y_sum": float(np.sum(self.y))
        })
        return hashlib.sha256(data_str.encode()).hexdigest()


class DataGenerator:

    @staticmethod
    def generate_compliance_data(
        n_samples: int = 200,
        n_features: int = 10,
        random_state: int = 42
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        np.random.seed(random_state)

        feature_names = [
            "company_size",
            "industry_risk",
            "data_volume",
            "compliance_score",
            "audit_frequency",
            "employee_count",
            "data_sensitivity",
            "security_investment",
            "incident_history",
            "regulation_complexity"
        ][:n_features]

        X = np.random.randn(n_samples, n_features)

        risk_score = (
            -0.3 * X[:, 3] +
            -0.2 * X[:, 7] +
            0.25 * X[:, 2] +
            0.15 * X[:, 8] +
            np.random.randn(n_samples) * 0.3
        )

        y = (risk_score > 0).astype(int)

        logger.info(f"生成数据合规风险数据: {n_samples} 样本, {n_features} 特征, 正例比例: {np.mean(y):.2%}")
        return X, y, feature_names

    @staticmethod
    def generate_patent_data(
        n_samples: int = 150,
        n_features: int = 8,
        random_state: int = 42
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        np.random.seed(random_state)

        feature_names = [
            "patent_count",
            "tech_similarity",
            "market_overlap",
            "legal_budget",
            "innovation_rate",
            "litigation_history",
            "competitor_density",
            "ip_awareness"
        ][:n_features]

        X = np.random.randn(n_samples, n_features)

        risk_score = (
            0.3 * X[:, 1] +
            0.25 * X[:, 2] +
            0.2 * X[:, 5] +
            -0.15 * X[:, 3] +
            np.random.randn(n_samples) * 0.3
        )

        y = (risk_score > 0).astype(int)

        logger.info(f"生成专利侵权风险数据: {n_samples} 样本, {n_features} 特征, 正例比例: {np.mean(y):.2%}")
        return X, y, feature_names

    @staticmethod
    def generate_algorithm_security_data(
        n_samples: int = 180,
        n_features: int = 10,
        random_state: int = 42
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        np.random.seed(random_state)

        feature_names = [
            "model_complexity",
            "data_quality",
            "adversarial_testing",
            "security_audit",
            "input_validation",
            "model_transparency",
            "update_frequency",
            "vulnerability_count",
            "monitoring_coverage",
            "incident_response"
        ][:n_features]

        X = np.random.randn(n_samples, n_features)

        risk_score = (
            0.25 * X[:, 0] +
            -0.2 * X[:, 2] +
            -0.15 * X[:, 3] +
            0.2 * X[:, 7] +
            -0.2 * X[:, 8] +
            np.random.randn(n_samples) * 0.3
        )

        y = (risk_score > 0).astype(int)

        logger.info(f"生成算法安全风险数据: {n_samples} 样本, {n_features} 特征, 正例比例: {np.mean(y):.2%}")
        return X, y, feature_names

    @staticmethod
    def create_federated_datasets(
        risk_type: str = "data_compliance",
        n_clients: int = 3,
        samples_per_client: int = 100,
        n_features: int = 10,
        heterogeneous: bool = True
    ) -> List[RiskDataset]:
        datasets = []

        for i in range(n_clients):
            seed = 42 + i * 100

            if heterogeneous:
                n_samples = samples_per_client + np.random.randint(-30, 30)
                n_feat = n_features
            else:
                n_samples = samples_per_client
                n_feat = n_features

            if risk_type == "data_compliance":
                X, y, feature_names = DataGenerator.generate_compliance_data(
                    n_samples=n_samples,
                    n_features=n_feat,
                    random_state=seed
                )
            elif risk_type == "patent_infringement":
                X, y, feature_names = DataGenerator.generate_patent_data(
                    n_samples=n_samples,
                    n_features=n_feat,
                    random_state=seed
                )
            elif risk_type == "algorithm_security":
                X, y, feature_names = DataGenerator.generate_algorithm_security_data(
                    n_samples=n_samples,
                    n_features=n_feat,
                    random_state=seed
                )
            else:
                X, y, feature_names = DataGenerator.generate_compliance_data(
                    n_samples=n_samples,
                    n_features=n_feat,
                    random_state=seed
                )

            data_str = json.dumps({
                "X_shape": list(X.shape),
                "y_shape": list(y.shape),
                "seed": seed
            })
            data_hash = hashlib.sha256(data_str.encode()).hexdigest()

            dataset = RiskDataset(
                name=f"client_{i+1}_{risk_type}",
                X=X,
                y=y,
                feature_names=feature_names,
                risk_type=risk_type,
                sample_count=len(X),
                data_hash=data_hash
            )

            datasets.append(dataset)

        logger.info(f"创建 {n_clients} 个联邦学习数据集，风险类型: {risk_type}")
        return datasets


class DataPreprocessor:

    def __init__(self):
        self.scaler = StandardScaler()
        self.label_encoder = LabelEncoder()
        self.fitted = False

    def fit_transform(self, X: np.ndarray, y: np.ndarray = None) -> Tuple[np.ndarray, np.ndarray]:
        X_scaled = self.scaler.fit_transform(X)

        if y is not None:
            y_encoded = self.label_encoder.fit_transform(y)
        else:
            y_encoded = y

        self.fitted = True
        logger.info("数据预处理器拟合完成")
        return X_scaled, y_encoded

    def transform(self, X: np.ndarray, y: np.ndarray = None) -> Tuple[np.ndarray, np.ndarray]:
        if not self.fitted:
            raise RuntimeError("预处理器尚未拟合")

        X_scaled = self.scaler.transform(X)

        if y is not None:
            y_encoded = self.label_encoder.transform(y)
        else:
            y_encoded = y

        return X_scaled, y_encoded


class DataPrivacy:

    @staticmethod
    def add_differential_privacy(
        X: np.ndarray,
        epsilon: float = 1.0,
        sensitivity: float = 1.0
    ) -> np.ndarray:
        scale = sensitivity / epsilon
        noise = np.random.laplace(0, scale, X.shape)
        X_noisy = X + noise

        logger.info(f"添加差分隐私噪声: epsilon={epsilon}, 噪声量级={scale:.4f}")
        return X_noisy

    @staticmethod
    def k_anonymize(
        df: pd.DataFrame,
        quasi_identifiers: List[str],
        k: int = 5
    ) -> pd.DataFrame:
        df_anon = df.copy()

        for col in quasi_identifiers:
            if col in df.columns:
                if df[col].dtype in ['int64', 'float64']:
                    df_anon[col] = pd.cut(df[col], bins=10, labels=False)
                else:
                    df_anon[col] = df[col].astype(str).str[:3] + "***"

        logger.info(f"K-匿名化处理完成: k={k}, 准标识符: {quasi_identifiers}")
        return df_anon


def load_csv_data(file_path: str, target_column: str = "risk_level") -> Tuple[np.ndarray, np.ndarray, List[str]]:
    df = pd.read_csv(file_path)

    y = df[target_column].values
    X = df.drop(columns=[target_column]).values
    feature_names = df.drop(columns=[target_column]).columns.tolist()

    logger.info(f"从 CSV 加载数据: {len(X)} 样本, {len(feature_names)} 特征")
    return X, y, feature_names


def save_dataset_info(dataset: RiskDataset, output_path: str):
    info = {
        "name": dataset.name,
        "risk_type": dataset.risk_type,
        "sample_count": dataset.sample_count,
        "feature_count": len(dataset.feature_names),
        "feature_names": dataset.feature_names,
        "data_hash": dataset.data_hash,
        "positive_ratio": float(np.mean(dataset.y))
    }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(info, f, indent=2, ensure_ascii=False)

    logger.info(f"数据集信息已保存到: {output_path}")


__all__ = [
    "RiskDataset",
    "DataGenerator",
    "DataPreprocessor",
    "DataPrivacy",
    "load_csv_data",
    "save_dataset_info",
]
