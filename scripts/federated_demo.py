import sys
import os
import json
import time
import numpy as np
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from federated_learning import (
    FederatedClient,
    FederatedAggregator,
    ModelWeights,
    DifferentialPrivacy,
    TrainingHistory,
    calculate_comprehensive_metrics,
    ContributionCalculator
)
from nostr_client import MockNostrClient


def generate_non_iid_data(num_clients=3, n_samples=1000, n_features=10, random_state=42):
    np.random.seed(random_state)

    X, y = make_classification(
        n_samples=n_samples,
        n_features=n_features,
        n_informative=8,
        n_redundant=2,
        n_classes=2,
        random_state=random_state
    )

    client_data = []
    samples_per_client = n_samples // num_clients

    for i in range(num_clients):
        start_idx = i * samples_per_client
        end_idx = (i + 1) * samples_per_client

        X_client = X[start_idx:end_idx].copy()
        y_client = y[start_idx:end_idx].copy()

        offset = (i - num_clients / 2) * 0.3
        X_client += offset

        X_train, X_test, y_train, y_test = train_test_split(
            X_client, y_client, test_size=0.2, random_state=random_state
        )

        client_data.append((X_train, y_train, X_test, y_test))

        print(f"客户端 {i+1}: 训练集 {len(X_train)} 条, 测试集 {len(X_test)} 条, "
              f"正样本比例 {y_train.mean():.2%}")

    return client_data


def run_federated_demo(
    num_clients=3,
    num_rounds=10,
    dp_enabled=True,
    dp_epsilon=2.0,
    output_file="training_history.json"
):
    print("=" * 70)
    print("Cloak - 联邦学习多节点演示")
    print("=" * 70)
    print(f"\n配置参数:")
    print(f"  客户端数量: {num_clients}")
    print(f"  训练轮数: {num_rounds}")
    print(f"  差分隐私: {'启用' if dp_enabled else '禁用'}")
    if dp_enabled:
        print(f"  隐私预算 (ε): {dp_epsilon}")
    print()

    print("-" * 70)
    print("步骤 1: 生成模拟数据 (Non-IID 分布)")
    print("-" * 70)
    client_data_list = generate_non_iid_data(num_clients=num_clients)
    print()

    print("-" * 70)
    print("步骤 2: 初始化 Nostr 网络连接")
    print("-" * 70)
    mock_nostr = MockNostrClient()
    print("Mock Nostr 客户端已创建")
    print()

    print("-" * 70)
    print("步骤 3: 初始化联邦学习客户端")
    print("-" * 70)
    clients = []
    for i in range(num_clients):
        client_nostr = MockNostrClient()
        client_nostr.event_store = mock_nostr.event_store

        client = FederatedClient(
            nostr_client=client_nostr,
            client_id=f"client_{i+1}",
            model_type="logistic_regression"
        )

        X_train, y_train, X_test, y_test = client_data_list[i]
        client.load_data(X_train, y_train, test_size=0.0)
        client.X_test = X_test
        client.y_test = y_test
        client.num_examples = len(X_train)

        clients.append(client)
        print(f"客户端 {i+1} 初始化完成 (ID: client_{i+1})")
    print()

    print("-" * 70)
    print("步骤 4: 初始化联邦学习聚合端")
    print("-" * 70)
    aggregator_nostr = MockNostrClient()
    aggregator_nostr.event_store = mock_nostr.event_store

    aggregator = FederatedAggregator(
        nostr_client=aggregator_nostr,
        aggregator_id="aggregator_1",
        model_type="logistic_regression",
        num_clients=num_clients
    )

    n_features = client_data_list[0][0].shape[1]
    initial_weights = ModelWeights(
        weights=[np.zeros((1, n_features)), np.zeros(1)],
        model_type="logistic_regression"
    )
    aggregator.set_initial_weights(initial_weights)
    print(f"聚合端初始化完成 (ID: aggregator_1)")
    print(f"初始权重已设置 (特征数: {n_features})")
    print()

    print("-" * 70)
    print(f"步骤 5: 开始联邦学习训练 ({num_rounds} 轮)")
    print("-" * 70)

    training_history = TrainingHistory()
    trade_id = "demo-trade-001"

    X_test_global = np.vstack([data[2] for data in client_data_list])
    y_test_global = np.hstack([data[3] for data in client_data_list])

    for round_num in range(1, num_rounds + 1):
        print(f"\n--- 第 {round_num}/{num_rounds} 轮 ---")

        print(f"[聚合端] 发送全局权重...")
        aggregator.send_global_weights_via_nostr(trade_id, round_num)

        client_weights = {}
        client_examples = {}
        client_metrics = {}

        for i, client in enumerate(clients):
            global_weights = client.receive_global_weights_via_nostr(trade_id, round_num)
            if global_weights:
                client.set_model_weights(global_weights)

            result = client.train_local(epochs=1)

            if dp_enabled:
                epsilon_per_round = DifferentialPrivacy.get_privacy_budget_per_round(
                    total_epsilon=dp_epsilon,
                    num_rounds=num_rounds
                )

                noisy_weights_list = DifferentialPrivacy.add_laplace_noise(
                    weights=result.weights.weights,
                    epsilon=epsilon_per_round,
                    sensitivity=0.1
                )
                result.weights = ModelWeights(
                    weights=noisy_weights_list,
                    model_type=result.weights.model_type
                )

            client.send_gradient_via_nostr(trade_id, round_num, result.weights)

            client_weights[client.client_id] = result.weights
            client_examples[client.client_id] = result.num_examples
            client_metrics[client.client_id] = result.metrics

            print(f"  [客户端 {i+1}] 训练完成 - "
                  f"Accuracy: {result.metrics['accuracy']:.4f}, "
                  f"AUC: {result.metrics['auc']:.4f}, "
                  f"样本数: {result.num_examples}")

        print(f"[聚合端] 收集并聚合权重...")
        aggregated_weights = aggregator.aggregate_weights(client_weights, client_examples)
        aggregator.global_weights = aggregated_weights

        contributions = ContributionCalculator.calculate_combined(
            client_examples=client_examples,
            client_metrics=client_metrics,
            sample_weight=0.6,
            performance_weight=0.4
        )

        global_metrics = aggregator.evaluate_global_model(X_test_global, y_test_global)

        training_history.add_round_metrics(
            round_num=round_num,
            metrics=global_metrics,
            num_clients=num_clients,
            contributions=contributions
        )

        print(f"[聚合端] 全局模型评估 - "
              f"Accuracy: {global_metrics['accuracy']:.4f}, "
              f"AUC: {global_metrics['auc']:.4f}, "
              f"F1: {global_metrics['f1_score']:.4f}")

        print(f"[聚合端] 本轮贡献度:")
        for client_id, contrib in sorted(contributions.items(), key=lambda x: -x[1]):
            print(f"    {client_id}: {contrib:.2%}")

    print()

    print("-" * 70)
    print("步骤 6: 训练完成 - 结果总结")
    print("-" * 70)

    summary = training_history.get_summary()

    print(f"\n训练总结:")
    print(f"  总轮数: {summary['total_rounds']}")
    print(f"  最终准确率: {summary['final_accuracy']:.4f} ({summary['final_accuracy']:.2%})")
    print(f"  最终 AUC: {summary['final_auc']:.4f}")
    print(f"  最终 F1: {summary['final_f1']:.4f}")
    print(f"  最佳准确率: {summary['best_accuracy']:.4f} ({summary['best_accuracy']:.2%})")
    print(f"  最佳 AUC: {summary['best_auc']:.4f}")
    print(f"  平均参与客户端数: {summary['avg_clients']:.1f}")

    if dp_enabled:
        total_privacy_loss = DifferentialPrivacy.calculate_privacy_loss(
            num_rounds=num_rounds,
            epsilon_per_round=DifferentialPrivacy.get_privacy_budget_per_round(
                total_epsilon=dp_epsilon,
                num_rounds=num_rounds
            )
        )
        print(f"\n隐私保护:")
        print(f"  总隐私预算 (ε): {dp_epsilon}")
        print(f"  累计隐私损失: {total_privacy_loss:.4f}")
        print(f"  隐私等级: {'强' if dp_epsilon <= 1 else '中' if dp_epsilon <= 5 else '弱'}")

    print(f"\n保存训练历史到: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(training_history.to_dict(), f, indent=2, ensure_ascii=False)
    print("训练历史已保存")

    print(f"\n最终模型详细评估:")
    final_metrics = calculate_comprehensive_metrics(
        y_true=y_test_global,
        y_pred=aggregator.global_model.predict(X_test_global),
        y_pred_proba=aggregator.global_model.predict_proba(X_test_global)[:, 1]
    )

    for metric_name, metric_value in final_metrics.items():
        if isinstance(metric_value, float):
            print(f"  {metric_name}: {metric_value:.4f}")
        else:
            print(f"  {metric_name}: {metric_value}")

    print()
    print("=" * 70)
    print("演示完成！")
    print("=" * 70)

    return training_history, final_metrics


def main():
    import argparse

    parser = argparse.ArgumentParser(description='Cloak - 联邦学习多节点演示')
    parser.add_argument('--clients', type=int, default=3, help='客户端数量 (默认: 3)')
    parser.add_argument('--rounds', type=int, default=10, help='训练轮数 (默认: 10)')
    parser.add_argument('--no-dp', action='store_true', help='禁用差分隐私')
    parser.add_argument('--epsilon', type=float, default=2.0, help='差分隐私 epsilon 值 (默认: 2.0)')
    parser.add_argument('--output', type=str, default='training_history.json', help='输出文件')

    args = parser.parse_args()

    run_federated_demo(
        num_clients=args.clients,
        num_rounds=args.rounds,
        dp_enabled=not args.no_dp,
        dp_epsilon=args.epsilon,
        output_file=args.output
    )


if __name__ == "__main__":
    main()
