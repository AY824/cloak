
import numpy as np
import pandas as pd
from sklearn.datasets import make_classification
from sklearn.preprocessing import StandardScaler
import json
import os
from pathlib import Path


def generate_risk_dataset(
    n_samples: int = 1000,
    n_features: int = 20,
    risk_type: str = "data_compliance",
    random_state: int = 42
) -> pd.DataFrame:
    np.random.seed(random_state)

    X, y = make_classification(
        n_samples=n_samples,
        n_features=n_features,
        n_informative=max(5, n_features // 3),
        n_redundant=max(2, n_features // 5),
        n_classes=2,
        weights=[0.7, 0.3],
        random_state=random_state
    )

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    feature_names = [f"feature_{i:02d}" for i in range(n_features)]

    df = pd.DataFrame(X_scaled, columns=feature_names)
    df["risk_label"] = y
    df["risk_type"] = risk_type

    df["company_id"] = [f"COMP_{i:05d}" for i in range(n_samples)]
    df["industry"] = np.random.choice(
        ["人工智能", "生物医药", "集成电路", "新能源", "新材料", "量子计算"],
        size=n_samples
    )
    df["company_size"] = np.random.choice(
        ["初创", "小型", "中型", "大型"],
        size=n_samples,
        p=[0.3, 0.3, 0.25, 0.15]
    )
    df["region"] = np.random.choice(
        ["华东", "华南", "华北", "西南", "华中", "西北"],
        size=n_samples
    )

    return df


def generate_federated_datasets(
    n_clients: int = 3,
    samples_per_client: int = 500,
    n_features: int = 20,
    risk_type: str = "data_compliance",
    output_dir: str = "../data"
) -> list:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    file_paths = []

    for i in range(n_clients):
        random_state = 42 + i * 100
        df = generate_risk_dataset(
            n_samples=samples_per_client,
            n_features=n_features,
            risk_type=risk_type,
            random_state=random_state
        )

        df["client_id"] = f"client_{i+1}"

        file_path = output_path / f"client_{i+1}_data.csv"
        df.to_csv(file_path, index=False, encoding="utf-8-sig")
        file_paths.append(str(file_path))

        print(f"生成客户端 {i+1} 数据: {len(df)} 条样本 -> {file_path}")

    return file_paths


def generate_all_risk_types(
    samples_per_type: int = 500,
    n_features: int = 20,
    output_dir: str = "../data"
) -> dict:
    risk_types = [
        "data_compliance",
        "patent_infringement",
        "algorithm_security",
        "rd_failure",
        "geopolitical",
        "tech_ethics"
    ]

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    result = {}

    for i, risk_type in enumerate(risk_types):
        random_state = 100 + i * 50
        df = generate_risk_dataset(
            n_samples=samples_per_type,
            n_features=n_features,
            risk_type=risk_type,
            random_state=random_state
        )

        file_path = output_path / f"risk_{risk_type}_data.csv"
        df.to_csv(file_path, index=False, encoding="utf-8-sig")
        result[risk_type] = str(file_path)

        print(f"生成 {risk_type} 风险数据: {len(df)} 条样本 -> {file_path}")

    return result


def generate_dataset_metadata(
    output_dir: str = "../data"
) -> dict:
    metadata = {
        "dataset_name": "企业风险评估数据集",
        "version": "1.0.0",
        "description": "用于联邦学习的风险模拟数据集",
        "risk_types": [
            {
                "code": "data_compliance",
                "name": "数据合规风险",
                "description": "企业数据收集、存储、使用过程中违反法律法规的风险"
            },
            {
                "code": "patent_infringement",
                "name": "专利侵权风险",
                "description": "企业技术研发可能侵犯他人专利权的风险"
            },
            {
                "code": "algorithm_security",
                "name": "算法安全风险",
                "description": "算法模型存在漏洞、被攻击或产生歧视性结果的风险"
            },
            {
                "code": "rd_failure",
                "name": "研发失败风险",
                "description": "技术研发项目未能达到预期目标的风险"
            },
            {
                "code": "geopolitical",
                "name": "地缘管制风险",
                "description": "受国际政治形势、出口管制等影响的风险"
            },
            {
                "code": "tech_ethics",
                "name": "科技伦理风险",
                "description": "技术应用引发的伦理道德争议风险"
            }
        ],
        "features": {
            "count": 20,
            "type": "numerical",
            "description": "标准化后的数值特征，代表企业各维度风险指标"
        },
        "label": {
            "name": "risk_label",
            "type": "binary",
            "description": "0=低风险, 1=高风险"
        },
        "data_distribution": {
            "positive_ratio": "约30%",
            "note": "模拟真实场景中风险样本占比较低的情况"
        },
        "federated_learning": {
            "n_clients": 3,
            "samples_per_client": 500,
            "description": "模拟3个数据提供方的非IID数据分布"
        }
    }

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    metadata_path = output_path / "dataset_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"生成数据集元数据 -> {metadata_path}")

    return metadata


def main():
    print("=" * 60)
    print("风险数据生成脚本")
    print("=" * 60)

    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / "data"

    print(f"\n数据输出目录: {data_dir}")
    print()

    print("-" * 40)
    print("1. 生成联邦学习多客户端数据集")
    print("-" * 40)
    federated_files = generate_federated_datasets(
        n_clients=3,
        samples_per_client=500,
        n_features=20,
        risk_type="data_compliance",
        output_dir=str(data_dir / "federated")
    )

    print()
    print("-" * 40)
    print("2. 生成所有风险类型数据集")
    print("-" * 40)
    risk_files = generate_all_risk_types(
        samples_per_type=500,
        n_features=20,
        output_dir=str(data_dir / "risk_types")
    )

    print()
    print("-" * 40)
    print("3. 生成数据集元数据")
    print("-" * 40)
    metadata = generate_dataset_metadata(output_dir=str(data_dir))

    print()
    print("=" * 60)
    print("数据生成完成！")
    print("=" * 60)
    print(f"\n联邦学习数据集: {len(federated_files)} 个文件")
    print(f"风险类型数据集: {len(risk_files)} 个文件")
    print(f"\n数据目录: {data_dir}")


if __name__ == "__main__":
    main()
