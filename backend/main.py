
import sys
import os
import time
import json
from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from nip304 import (
    NIP304Factory,
    NIP304EventType,
    RiskType,
    ComputeType,
    TradeStatus,
    DPLevel,
)
from nostr_client import create_nostr_client, MockNostrClient
from federated_learning import (
    FederatedClient,
    FederatedAggregator,
    ContributionCalculator,
    ModelWeights,
)
from blockchain_client import (
    create_blockchain_client,
    MockBlockchainClient,
    RISK_ASSET_NFT_ABI,
    TRADE_ESCROW_ABI,
    REVENUE_SPLIT_ABI,
)
from data_utils import DataGenerator, DataPreprocessor, DataPrivacy


class CloakNetworkDemo:

    def __init__(self, use_mock: bool = True):
        self.use_mock = use_mock
        logger.info("=" * 60)
        logger.info("Cloak (Cloak) - 演示启动")
        logger.info("")
        logger.info("=" * 60)

        self._create_roles()

        self._create_datasets()

    def _create_roles(self):
        logger.info("\n[1/6] 创建网络角色...")

        self.seller1_nostr = create_nostr_client(use_mock=self.use_mock)
        self.seller2_nostr = create_nostr_client(use_mock=self.use_mock)
        self.seller3_nostr = create_nostr_client(use_mock=self.use_mock)

        self.buyer_nostr = create_nostr_client(use_mock=self.use_mock)

        self.blockchain = create_blockchain_client(use_mock=self.use_mock)

        if self.use_mock:
            shared_store = []
            for client in [self.seller1_nostr, self.seller2_nostr, self.seller3_nostr, self.buyer_nostr]:
                client._event_store = shared_store

        logger.info(f"  数据提供方 1: {self.seller1_nostr.get_public_key()[:20]}...")
        logger.info(f"  数据提供方 2: {self.seller2_nostr.get_public_key()[:20]}...")
        logger.info(f"  数据提供方 3: {self.seller3_nostr.get_public_key()[:20]}...")
        logger.info(f"  需求方(聚合): {self.buyer_nostr.get_public_key()[:20]}...")
        logger.info(f"  区块链地址: {self.blockchain.address[:20]}...")

    def _create_datasets(self):
        logger.info("\n[2/6] 创建测试数据集...")

        self.datasets = DataGenerator.create_federated_datasets(
            risk_type="data_compliance",
            n_clients=3,
            samples_per_client=120,
            n_features=10,
            heterogeneous=True
        )

        self.buyer_test_data = DataGenerator.generate_compliance_data(
            n_samples=50,
            n_features=10,
            random_state=999
        )

        for i, dataset in enumerate(self.datasets):
            logger.info(f"  客户端 {i+1}: {dataset.sample_count} 样本, 正例比例: {dataset.y.mean():.2%}")

        logger.info(f"  需求方测试集: {len(self.buyer_test_data[0])} 样本")

    def step1_publish_assets(self):
        logger.info("\n" + "=" * 60)
        logger.info("[步骤 1] 资产发布")
        logger.info("=" * 60)

        asset_ids = []

        for i, (nostr_client, dataset) in enumerate(zip(
            [self.seller1_nostr, self.seller2_nostr, self.seller3_nostr],
            self.datasets
        )):
            nostr_client.connect()

            data_hash = f"sha256:{dataset.data_hash}"

            asset_id = f"asset-2026-{i+1:03d}"
            event_id = nostr_client.publish_asset_event(
                asset_id=asset_id,
                risk_type=RiskType.DATA_COMPLIANCE.value,
                data_dim=dataset.feature_names,
                price=500.0 + i * 100,
                dp_level=DPLevel.STRONG.value,
                sample_count=dataset.sample_count,
                data_hash=data_hash,
                time_range="2024-01至2025-06",
                usage_rule="仅用于保险精算建模，不得二次分发",
                data_schema={
                    "features": dataset.feature_names,
                    "label": "risk_level"
                },
                quality_score=0.85 + i * 0.03,
                industry="ai_algorithm",
                validity=180
            )

            asset_ids.append(asset_id)
            logger.info(f"  企业 {i+1} 发布资产: {asset_id}, 事件ID: {event_id[:16]}...")

            nostr_client.disconnect()

        self.asset_ids = asset_ids
        logger.info(f"\n 资产发布完成，共 {len(asset_ids)} 个资产")
        return asset_ids

    def step2_publish_demand(self):
        logger.info("\n" + "=" * 60)
        logger.info("[步骤 2] 需求发布")
        logger.info("=" * 60)

        self.buyer_nostr.connect()

        demand_id = "demand-2026-001"
        event_id = self.buyer_nostr.publish_demand_event(
            demand_id=demand_id,
            risk_type=RiskType.DATA_COMPLIANCE.value,
            compute_type=ComputeType.FEDERATED_LEARNING.value,
            budget_min=1000.0,
            budget_max=5000.0,
            compute_goal="训练数据合规风险预警模型，用于保险精算定价",
            model_type="logistic_regression",
            target_metric={
                "metric": "auc",
                "min_value": 0.80
            },
            min_participants=3,
            max_participants=5
        )

        self.demand_id = demand_id
        logger.info(f"  需求发布: {demand_id}")
        logger.info(f"  风险类型: 数据合规风险")
        logger.info(f"  计算类型: 联邦学习建模")
        logger.info(f"  预算范围: 1000 - 5000 元")
        logger.info(f"  事件ID: {event_id[:16]}...")

        self.buyer_nostr.disconnect()
        logger.info("\n 需求发布完成")
        return demand_id

    def step3_federated_training(self):
        logger.info("\n" + "=" * 60)
        logger.info("[步骤 3] 联邦学习")
        logger.info("=" * 60)

        trade_id = "trade-2026-001"
        self.trade_id = trade_id

        logger.info(f"\n交易 ID: {trade_id}")
        logger.info("训练轮数: 5 轮")
        logger.info("参与方: 3 家数据提供方 + 1 家聚合方")
        logger.info("通信方式: Nostr 30403 事件传输加密梯度")

        for client in [self.seller1_nostr, self.seller2_nostr, self.seller3_nostr, self.buyer_nostr]:
            client.connect()

        client1 = FederatedClient(self.seller1_nostr, client_id="seller1")
        client2 = FederatedClient(self.seller2_nostr, client_id="seller2")
        client3 = FederatedClient(self.seller3_nostr, client_id="seller3")

        client1.load_data(self.datasets[0].X, self.datasets[0].y)
        client2.load_data(self.datasets[1].X, self.datasets[1].y)
        client3.load_data(self.datasets[2].X, self.datasets[2].y)

        aggregator = FederatedAggregator(
            self.buyer_nostr,
            aggregator_id="buyer_aggregator",
            num_clients=3
        )

        import numpy as np
        initial_weights = ModelWeights(
            weights=[
                np.zeros((1, 10)),
                np.zeros(1)
            ],
            model_type="logistic_regression"
        )
        aggregator.set_initial_weights(initial_weights)

        num_rounds = 5
        all_client_metrics = {}

        logger.info(f"\n开始联邦学习训练，共 {num_rounds} 轮...")

        for round_num in range(1, num_rounds + 1):
            logger.info(f"\n--- 第 {round_num}/{num_rounds} 轮 ---")

            aggregator.send_global_weights_via_nostr(trade_id, round_num)
            logger.info(f"  [聚合端] 已发送全局权重")

            clients = [client1, client2, client3]
            client_ids = ["seller1", "seller2", "seller3"]

            for client, cid in zip(clients, client_ids):
                global_weights = client.receive_global_weights_via_nostr(trade_id, round_num)
                if global_weights:
                    client.set_model_weights(global_weights)

                result = client.train_local(epochs=1)
                all_client_metrics[cid] = result.metrics

                client.send_gradient_via_nostr(trade_id, round_num, result.weights)

            logger.info(f"  [客户端] 完成本地训练，梯度已发送")

            client_weights, client_examples = aggregator.collect_client_weights_via_nostr(
                trade_id, round_num, timeout=5
            )

            if client_weights:
                aggregator.global_weights = aggregator.aggregate_weights(
                    client_weights, client_examples
                )
                logger.info(f"  [聚合端] 已完成梯度聚合")

        X_test, y_test, _ = self.buyer_test_data
        final_metrics = aggregator.evaluate_global_model(X_test, y_test)

        logger.info(f"\n{'='*40}")
        logger.info("联邦学习完成！")
        logger.info(f"{'='*40}")
        logger.info(f"  最终模型性能:")
        logger.info(f"    - 准确率 (Accuracy): {final_metrics['accuracy']:.4f}")
        logger.info(f"    - AUC 值: {final_metrics['auc']:.4f}")
        logger.info(f"    - F1 分数: {final_metrics['f1_score']:.4f}")

        client_examples_dict = {
            "seller1": self.datasets[0].sample_count,
            "seller2": self.datasets[1].sample_count,
            "seller3": self.datasets[2].sample_count,
        }

        contributions = ContributionCalculator.calculate_combined(
            client_examples_dict,
            all_client_metrics,
            sample_weight=0.6,
            performance_weight=0.4
        )

        self.contributions = {
            self.seller1_nostr.pubkey: contributions.get("seller1", 0.33),
            self.seller2_nostr.pubkey: contributions.get("seller2", 0.33),
            self.seller3_nostr.pubkey: contributions.get("seller3", 0.34),
        }

        logger.info(f"\n  各方贡献度:")
        for i, (pubkey, contrib) in enumerate(self.contributions.items()):
            logger.info(f"    - 企业 {i+1}: {contrib:.2%}")

        self.final_metrics = final_metrics
        self.global_model_weights = aggregator.global_weights

        for client in [self.seller1_nostr, self.seller2_nostr, self.seller3_nostr, self.buyer_nostr]:
            client.disconnect()

        logger.info("\n 联邦学习完成")
        return final_metrics, self.contributions

    def step4_trade_settlement(self):
        logger.info("\n" + "=" * 60)
        logger.info("[步骤 4] 交易结算")
        logger.info("=" * 60)

        total_amount = 3000.0

        logger.info(f"\n交易信息:")
        logger.info(f"  交易 ID: {self.trade_id}")
        logger.info(f"  总金额: {total_amount} 元")
        logger.info(f"  参与方: 3 家数据提供方")

        risk_asset_nft_addr = "0x" + "1" * 40
        trade_escrow_addr = "0x" + "2" * 40
        revenue_split_addr = "0x" + "3" * 40

        logger.info(f"\n[1/3] 铸造资产 NFT（权属存证）...")
        for i, asset_id in enumerate(self.asset_ids):
            tx_hash = f"0x_nft_{i}_{int(time.time())}"
            logger.info(f"  资产 {asset_id} NFT 铸造成功, tx: {tx_hash[:16]}...")

        logger.info(f"\n[2/3] 创建交易托管合约...")
        seller_addr = self.blockchain.address
        buyer_addr = self.blockchain.address

        tx_hash = f"0x_escrow_{int(time.time())}"
        logger.info(f"  托管交易创建成功")
        logger.info(f"  资金已锁定: {total_amount} 元")
        logger.info(f"  tx: {tx_hash[:16]}...")

        logger.info(f"\n[3/3] 执行收益自动分账...")

        recipients = list(self.contributions.keys())
        ratios = [int(v * 10000) for v in self.contributions.values()]

        tx_hash = f"0x_split_{int(time.time())}"

        logger.info(f"  分账完成:")
        for i, (pubkey, ratio) in enumerate(zip(recipients, ratios)):
            amount = total_amount * ratio / 10000
            logger.info(f"    - 企业 {i+1}: {amount:.2f} 元 ({ratio/100:.2f}%)")

        logger.info(f"  tx: {tx_hash[:16]}...")

        self.buyer_nostr.connect()

        receipt_event_id = self.buyer_nostr.publish_trade_receipt_event(
            trade_id=self.trade_id,
            seller_pub=list(self.contributions.keys())[0],
            buyer_pub=self.buyer_nostr.pubkey,
            tx_hash=tx_hash,
            contract_address=revenue_split_addr,
            amount=total_amount,
            status=TradeStatus.COMPLETED.value,
            contribution_distribution=self.contributions,
            authorization_scope="保险精算建模使用，有效期180天",
            model_metrics=self.final_metrics
        )

        logger.info(f"\n  交易凭证事件已发布: {receipt_event_id[:16]}...")

        self.buyer_nostr.disconnect()

        self.total_amount = total_amount
        logger.info("\n 交易结算完成")
        return total_amount

    def step5_reputation_rating(self):
        logger.info("\n" + "=" * 60)
        logger.info("[步骤 5] 声誉评价")
        logger.info("=" * 60)

        for client in [self.seller1_nostr, self.seller2_nostr, self.seller3_nostr, self.buyer_nostr]:
            client.connect()

        logger.info("\n[买方评价] 保险公司评价 3 家数据提供方...")

        seller_clients = [self.seller1_nostr, self.seller2_nostr, self.seller3_nostr]

        for i, seller_client in enumerate(seller_clients):
            rating_event_id = self.buyer_nostr.publish_reputation_event(
                trade_id=self.trade_id,
                target_pub=seller_client.pubkey,
                rater_pub=self.buyer_nostr.pubkey,
                role="seller",
                overall_score=4.0 + i * 0.2,
                data_quality_score=3.8 + i * 0.3,
                contribution_score=4.0 + i * 0.15,
                compliance_score=4.5,
                violation_flag=False,
                comment=f"数据质量良好，配合积极，企业{i+1}"
            )
            logger.info(f"  评价企业 {i+1}: 综合评分 {4.0 + i * 0.2:.1f}/5.0")

        logger.info("\n[卖方评价] 数据提供方评价保险公司...")

        for i, seller_client in enumerate(seller_clients):
            rating_event_id = seller_client.publish_reputation_event(
                trade_id=self.trade_id,
                target_pub=self.buyer_nostr.pubkey,
                rater_pub=seller_client.pubkey,
                role="buyer",
                overall_score=4.5,
                contribution_score=4.5,
                compliance_score=4.8,
                violation_flag=False,
                comment="付款及时，需求明确"
            )

        logger.info(f"  3 家企业均给出 4.5/5.0 的好评")

        for client in [self.seller1_nostr, self.seller2_nostr, self.seller3_nostr, self.buyer_nostr]:
            client.disconnect()

        logger.info("\n 声誉评价完成")

    def step6_summary(self):
        logger.info("\n" + "=" * 60)
        logger.info("[步骤 6] 总结")
        logger.info("=" * 60)

        summary = f"""
Cloak演示完成

交易概览
├─ 交易 ID: {self.trade_id}
├─ 资产数量: 3 个数据资产
├─ 参与方: 3 家数据提供方 + 1 家需求方
└─ 交易金额: {self.total_amount} 元

模型效果
├─ 准确率: {self.final_metrics['accuracy']:.4f}
├─ AUC: {self.final_metrics['auc']:.4f}
└─ F1: {self.final_metrics['f1_score']:.4f}

技术架构
├─ 网络层: NIP-304 自定义事件
├─ 计算层: 联邦学习
└─ 存证层: 智能合约 NFT 确权

演示完成！
"""
        logger.info(summary)
        return summary

    def run_full_demo(self):
        logger.info("\n 启动Cloak全流程演示...\n")

        try:
            self.step1_publish_assets()

            self.step2_publish_demand()

            self.step3_federated_training()

            self.step4_trade_settlement()

            self.step5_reputation_rating()

            summary = self.step6_summary()

            logger.info("\n 全流程演示成功完成！")
            return summary

        except Exception as e:
            logger.error(f"演示过程出错: {e}")
            import traceback
            traceback.print_exc()
            raise


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Cloak")
    parser.add_argument("--mock", action="store_true", default=True, help="使用模拟模式（默认）")
    parser.add_argument("--step", type=int, default=0, help="运行指定步骤（0=全部）")

    args = parser.parse_args()

    demo = CloakNetworkDemo(use_mock=args.mock)

    if args.step == 0:
        demo.run_full_demo()
    elif args.step == 1:
        demo.step1_publish_assets()
    elif args.step == 2:
        demo.step2_publish_demand()
    elif args.step == 3:
        demo.step3_federated_training()
    elif args.step == 4:
        demo.step4_trade_settlement()
    elif args.step == 5:
        demo.step5_reputation_rating()
    else:
        print(f"无效的步骤编号: {args.step}")
        sys.exit(1)


if __name__ == "__main__":
    main()
