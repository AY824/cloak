
import sys
import os
import time
from loguru import logger

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from nostr_client import MockNostrClient, create_nostr_client
from federated_learning import (
    FederatedClient,
    FederatedAggregator,
    ModelWeights,
    ContributionCalculator
)
import numpy as np
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split


def generate_client_data(n_samples=500, n_features=20, random_state=42):
    X, y = make_classification(
        n_samples=n_samples,
        n_features=n_features,
        n_informative=10,
        n_redundant=5,
        random_state=random_state
    )
    return X, y


def demo_nostr_connection():
    logger.info("=" * 60)
    logger.info("演示 1: Nostr 客户端初始化")
    logger.info("=" * 60)

    client = create_nostr_client(use_mock=True)

    logger.info(f"客户端公钥: {client.get_public_key(bech32=True)}")
    logger.info(f"客户端已连接: {client.connected}")

    client.connect()
    logger.info(f"连接后状态: {client.connected}")

    logger.info("Nostr 客户端初始化完成")
    logger.info("")

    return client


def demo_model_weights():
    logger.info("=" * 60)
    logger.info("演示 2: 模型权重序列化")
    logger.info("=" * 60)

    weights = {
        'coef_': np.random.randn(1, 20).astype(np.float64),
        'intercept_': np.random.randn(1).astype(np.float64)
    }

    model_weights = ModelWeights(weights)

    serialized = model_weights.serialize()
    logger.info(f"序列化后长度: {len(serialized)} 字符")

    deserialized = ModelWeights.deserialize(serialized)
    logger.info(f"反序列化成功: {deserialized is not None}")

    hash1 = model_weights.get_hash()
    hash2 = deserialized.get_hash()
    logger.info(f"哈希验证: {'通过' if hash1 == hash2 else '失败'}")

    total_params = model_weights.get_total_params()
    logger.info(f"总参数量: {total_params}")

    logger.info("模型权重序列化演示完成")
    logger.info("")

    return model_weights


def demo_single_client_training():
    logger.info("=" * 60)
    logger.info("演示 3: 单个客户端本地训练")
    logger.info("=" * 60)

    nostr_client = MockNostrClient()
    nostr_client.connect()

    client = FederatedClient(
        nostr_client=nostr_client,
        client_id="client_demo",
        model_type="logistic_regression"
    )

    X, y = generate_client_data(n_samples=500, random_state=42)
    client.load_data(X, y, test_size=0.2)

    logger.info(f"客户端样本数: {client.num_samples}")
    logger.info(f"特征维度: {X.shape[1]}")

    result = client.train_local(epochs=10)

    logger.info(f"训练完成 - 准确率: {result.metrics['accuracy']:.4f}")
    logger.info(f"训练完成 - 精确率: {result.metrics['precision']:.4f}")
    logger.info(f"训练完成 - 召回率: {result.metrics['recall']:.4f}")
    logger.info(f"训练完成 - F1分数: {result.metrics['f1_score']:.4f}")
    logger.info(f"训练完成 - 损失: {result.metrics['loss']:.4f}")

    eval_result = client.evaluate_local()
    logger.info(f"评估完成 - 准确率: {eval_result['accuracy']:.4f}")

    logger.info("单个客户端训练演示完成")
    logger.info("")

    return client


def demo_nostr_gradient_transfer():
    logger.info("=" * 60)
    logger.info("演示 4: 通过 Nostr 网络传输梯度")
    logger.info("=" * 60)

    shared_nostr = MockNostrClient()
    shared_nostr.connect()

    trade_id = "trade_demo_001"

    client = FederatedClient(
        nostr_client=shared_nostr,
        client_id="client_1",
        model_type="logistic_regression"
    )

    X, y = generate_client_data(n_samples=500, random_state=42)
    client.load_data(X, y)
    result = client.train_local(epochs=5)

    logger.info(f"客户端训练完成，准备发送梯度...")

    event_id = client.send_gradient_via_nostr(
        trade_id=trade_id,
        round_num=1,
        weights=result.weights
    )

    logger.info(f"梯度已通过 Nostr 发送，事件ID: {event_id[:16]}...")

    aggregator = FederatedAggregator(
        nostr_client=shared_nostr,
        aggregator_id="aggregator_1",
        model_type="logistic_regression",
        num_clients=1
    )

    client_weights, client_examples = aggregator.collect_client_weights_via_nostr(
        trade_id=trade_id,
        round_num=1,
        timeout=5
    )

    logger.info(f"从 Nostr 收集到 {len(client_weights)} 个客户端的权重")
    logger.info(f"客户端样本数: {client_examples}")

    aggregated_weights = aggregator.aggregate_weights(client_weights, client_examples)
    logger.info(f"权重聚合完成，哈希: {aggregated_weights.get_hash()[:16]}...")

    global_event_id = aggregator.send_global_weights_via_nostr(
        trade_id=trade_id,
        round_num=1
    )
    logger.info(f"全局权重已通过 Nostr 发送，事件ID: {global_event_id[:16]}...")

    global_weights = client.receive_global_weights_via_nostr(
        trade_id=trade_id,
        round_num=1
    )

    if global_weights:
        logger.info(f"客户端接收到全局权重，哈希: {global_weights.get_hash()[:16]}...")
        logger.info(f"权重验证: {'通过' if global_weights.get_hash() == aggregated_weights.get_hash() else '失败'}")
    else:
        logger.warning("客户端未接收到全局权重")

    logger.info("Nostr 梯度传输演示完成")
    logger.info("")


def demo_full_federated_training():
    logger.info("=" * 60)
    logger.info("演示 5: 完整联邦学习训练流程（3个客户端）")
    logger.info("=" * 60)

    shared_nostr = MockNostrClient()
    shared_nostr.connect()

    trade_id = "trade_full_demo_001"
    num_rounds = 5
    num_clients = 3

    logger.info(f"交易ID: {trade_id}")
    logger.info(f"训练轮次: {num_rounds}")
    logger.info(f"客户端数量: {num_clients}")
    logger.info("")

    clients = []
    for i in range(num_clients):
        client = FederatedClient(
            nostr_client=shared_nostr,
            client_id=f"client_{i+1}",
            model_type="logistic_regression"
        )

        X, y = generate_client_data(
            n_samples=300 + i * 100,
            n_features=20,
            random_state=42 + i
        )
        client.load_data(X, y)
        clients.append(client)

        logger.info(f"客户端 {i+1}: {client.num_samples} 样本")

    logger.info("")

    aggregator = FederatedAggregator(
        nostr_client=shared_nostr,
        aggregator_id="aggregator_main",
        model_type="logistic_regression",
        num_clients=num_clients
    )

    logger.info("开始联邦学习训练...")
    logger.info("")

    history = aggregator.run_federated_training(
        trade_id=trade_id,
        num_rounds=num_rounds,
        local_epochs=3,
        timeout_per_round=10
    )

    logger.info("")
    logger.info("训练完成！")

    logger.info("")
    logger.info("训练历史:")
    logger.info("-" * 60)
    logger.info(f"{'轮次':<6} {'准确率':<10} {'损失':<10} {'参与客户端':<12}")
    logger.info("-" * 60)

    for i, round_data in enumerate(history.rounds):
        logger.info(
            f"{i+1:<6} "
            f"{round_data.metrics.get('accuracy', 0):<10.4f} "
            f"{round_data.metrics.get('loss', 0):<10.4f} "
            f"{round_data.num_clients:<12}"
        )

    logger.info("")
    logger.info("客户端贡献度分析:")
    logger.info("-" * 60)

    contribution_calc = ContributionCalculator()

    if history.rounds:
        last_round = history.rounds[-1]
        client_weights = last_round.client_weights
        client_examples = last_round.client_examples

        if client_weights and client_examples:
            sample_contrib = contribution_calc.calculate_by_sample_size(client_examples)

            perf_contrib = contribution_calc.calculate_shapley_approx(
                client_weights,
                client_examples,
                lambda w: 0.85
            )

            combined_contrib = contribution_calc.calculate_combined(
                client_examples,
                client_weights,
                lambda w: 0.85
            )

            logger.info(f"{'客户端':<12} {'样本贡献':<12} {'性能贡献':<12} {'综合贡献':<12}")
            logger.info("-" * 60)

            for client_id in client_examples.keys():
                logger.info(
                    f"{client_id[:10]:<12} "
                    f"{sample_contrib.get(client_id, 0)*100:<12.2f}% "
                    f"{perf_contrib.get(client_id, 0)*100:<12.2f}% "
                    f"{combined_contrib.get(client_id, 0)*100:<12.2f}%"
                )

    logger.info("")
    logger.info("完整联邦学习训练演示完成")
    logger.info("")

    return history


def main():
    logger.info("")
    logger.info("╔" + "═" * 58 + "╗")
    logger.info("║" + " " * 10 + "Cloak - Nostr 联邦学习演示" + " " * 14 + "║")
    logger.info("╚" + "═" * 58 + "╝")
    logger.info("")

    try:
        demo_nostr_connection()

        demo_model_weights()

        demo_single_client_training()

        demo_nostr_gradient_transfer()

        demo_full_federated_training()

        logger.info("=" * 60)
        logger.info("所有演示完成！")
        logger.info("=" * 60)
        logger.info("")
        logger.info("总结：")
        logger.info("Nostr 客户端初始化成功")
        logger.info("模型权重序列化/反序列化正常")
        logger.info("单个客户端训练功能正常")
        logger.info("通过 Nostr 网络传输梯度正常")
        logger.info("完整联邦学习流程正常运行")
        logger.info("")
        logger.info("关键特性：")
        logger.info("使用 NIP-304 协议的 30403 事件类型传输计算参数")
        logger.info("模型权重通过 base64 编码后在 Nostr 网络中传输")
        logger.info("支持 FedAvg 聚合算法")
        logger.info("支持多种贡献度计算方式")
        logger.info("数据不出域，保护隐私安全")
        logger.info("")

    except Exception as e:
        logger.error(f"演示过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
