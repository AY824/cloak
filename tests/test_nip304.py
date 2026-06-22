
import sys
import os
import unittest
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from nip304 import (
    NIP304Factory,
    NIP304EventType,
    RiskType,
    ComputeType,
    TradeStatus,
    DPLevel,
    NIP304Parser,
    NIP304Validator,
)


class TestNIP304EventTypes(unittest.TestCase):

    def test_event_type_values(self):
        self.assertEqual(NIP304EventType.ASSET_PUBLISH.value, 30401)
        self.assertEqual(NIP304EventType.DEMAND_PUBLISH.value, 30402)
        self.assertEqual(NIP304EventType.COMPUTE_PARAMS.value, 30403)
        self.assertEqual(NIP304EventType.TRADE_RECEIPT.value, 30404)
        self.assertEqual(NIP304EventType.REPUTATION_RATING.value, 30405)

    def test_risk_type_values(self):
        self.assertEqual(RiskType.DATA_COMPLIANCE.value, "data_compliance")
        self.assertEqual(RiskType.PATENT_INFRINGEMENT.value, "patent_infringement")
        self.assertEqual(RiskType.ALGORITHM_SECURITY.value, "algorithm_security")

    def test_compute_type_values(self):
        self.assertEqual(ComputeType.FEDERATED_LEARNING.value, "federated_learning")
        self.assertEqual(ComputeType.STATISTICAL_ANALYSIS.value, "statistical_analysis")


class TestNIP304Factory(unittest.TestCase):

    def setUp(self):
        self.factory = NIP304Factory()
        self.test_pubkey = "npub1test1234567890abcdefghijklmnopqrstuvwxyz"

    def test_create_asset_publish_event(self):
        event = self.factory.create_asset_publish_event(
            asset_id="test-asset-001",
            risk_type=RiskType.DATA_COMPLIANCE.value,
            data_dim=["feature1", "feature2"],
            price=500.0,
            dp_level=DPLevel.STRONG.value,
            sample_count=1000,
            data_hash="sha256:abc123",
            time_range="2024-01至2024-12",
            usage_rule="仅用于测试",
        )

        self.assertEqual(event.kind, 30401)
        self.assertIsInstance(event.tags, list)
        self.assertIsInstance(event.content, str)

        d_tags = [t for t in event.tags if t[0] == 'd']
        self.assertEqual(len(d_tags), 1)
        self.assertEqual(d_tags[0][1], "test-asset-001")

        content = json.loads(event.content)
        self.assertIn("risk_type", content)
        self.assertIn("price", content)
        self.assertEqual(content["risk_type"], "data_compliance")
        self.assertEqual(content["price"], 500.0)

    def test_create_demand_publish_event(self):
        event = self.factory.create_demand_publish_event(
            demand_id="test-demand-001",
            risk_type=RiskType.DATA_COMPLIANCE.value,
            compute_type=ComputeType.FEDERATED_LEARNING.value,
            budget_min=1000.0,
            budget_max=5000.0,
            compute_goal="测试建模",
            model_type="logistic_regression",
        )

        self.assertEqual(event.kind, 30402)

        d_tags = [t for t in event.tags if t[0] == 'd']
        self.assertEqual(len(d_tags), 1)
        self.assertEqual(d_tags[0][1], "test-demand-001")

        content = json.loads(event.content)
        self.assertEqual(content["risk_type"], "data_compliance")
        self.assertEqual(content["compute_type"], "federated_learning")

    def test_create_compute_params_event(self):
        event = self.factory.create_compute_params_event(
            trade_id="test-trade-001",
            round_num=1,
            role="aggregator",
            model_type="logistic_regression",
            params={"weights": [[0.1, 0.2], [0.3, 0.4]]},
            num_samples=100,
            metrics={"accuracy": 0.85},
        )

        self.assertEqual(event.kind, 30403)

        d_tags = [t for t in event.tags if t[0] == 'd']
        self.assertEqual(len(d_tags), 1)
        self.assertEqual(d_tags[0][1], "test-trade-001")

        content = json.loads(event.content)
        self.assertEqual(content["round"], 1)
        self.assertEqual(content["role"], "aggregator")

    def test_create_trade_receipt_event(self):
        event = self.factory.create_trade_receipt_event(
            trade_id="test-trade-001",
            seller_pub="npub1seller",
            buyer_pub="npub1buyer",
            tx_hash="0xabc123",
            contract_address="0xdef456",
            amount=3000.0,
            status=TradeStatus.COMPLETED.value,
        )

        self.assertEqual(event.kind, 30404)

        d_tags = [t for t in event.tags if t[0] == 'd']
        self.assertEqual(len(d_tags), 1)
        self.assertEqual(d_tags[0][1], "test-trade-001")

        content = json.loads(event.content)
        self.assertEqual(content["amount"], 3000.0)
        self.assertEqual(content["status"], "completed")

    def test_create_reputation_rating_event(self):
        event = self.factory.create_reputation_event(
            trade_id="test-trade-001",
            target_pub="npub1target",
            rater_pub="npub1rater",
            role="seller",
            overall_score=4.5,
            data_quality_score=4.0,
            contribution_score=4.5,
            compliance_score=5.0,
        )

        self.assertEqual(event.kind, 30405)

        d_tags = [t for t in event.tags if t[0] == 'd']
        self.assertEqual(len(d_tags), 1)

        content = json.loads(event.content)
        self.assertEqual(content["overall_score"], 4.5)
        self.assertEqual(content["role"], "seller")


class TestNIP304Validator(unittest.TestCase):

    def setUp(self):
        self.factory = NIP304Factory()
        self.validator = NIP304Validator()

    def test_validate_valid_asset_event(self):
        event = self.factory.create_asset_publish_event(
            asset_id="test-asset-001",
            risk_type=RiskType.DATA_COMPLIANCE.value,
            data_dim=["f1", "f2"],
            price=500.0,
            dp_level=DPLevel.STRONG.value,
            sample_count=100,
            data_hash="sha256:abc",
        )

        is_valid, errors = self.validator.validate_event(event)
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)

    def test_validate_event_missing_d_tag(self):
        from dataclasses import dataclass

        @dataclass
        class MockEvent:
            kind: int
            tags: list
            content: str

        event = MockEvent(
            kind=30401,
            tags=[],
            content='{"test": "value"}'
        )

        is_valid, errors = self.validator.validate_event(event)
        self.assertFalse(is_valid)
        self.assertTrue(any("d 标签" in str(e) for e in errors))

    def test_validate_invalid_event_kind(self):
        from dataclasses import dataclass

        @dataclass
        class MockEvent:
            kind: int
            tags: list
            content: str

        event = MockEvent(
            kind=99999,
            tags=[['d', 'test']],
            content='{}'
        )

        is_valid, errors = self.validator.validate_event(event)
        self.assertFalse(is_valid)
        self.assertTrue(any("事件类型" in str(e) for e in errors))

    def test_validate_invalid_json_content(self):
        from dataclasses import dataclass

        @dataclass
        class MockEvent:
            kind: int
            tags: list
            content: str

        event = MockEvent(
            kind=30401,
            tags=[['d', 'test']],
            content='not valid json {{{'
        )

        is_valid, errors = self.validator.validate_event(event)
        self.assertFalse(is_valid)
        self.assertTrue(any("JSON" in str(e) for e in errors))


class TestNIP304Parser(unittest.TestCase):

    def setUp(self):
        self.factory = NIP304Factory()
        self.parser = NIP304Parser()

    def test_parse_asset_event(self):
        event = self.factory.create_asset_publish_event(
            asset_id="test-asset-001",
            risk_type=RiskType.DATA_COMPLIANCE.value,
            data_dim=["f1", "f2"],
            price=500.0,
            dp_level=DPLevel.STRONG.value,
            sample_count=100,
            data_hash="sha256:abc",
        )

        parsed = self.parser.parse_event(event)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["event_type"], "asset_publish")
        self.assertEqual(parsed["asset_id"], "test-asset-001")
        self.assertEqual(parsed["risk_type"], "data_compliance")

    def test_parse_demand_event(self):
        event = self.factory.create_demand_publish_event(
            demand_id="test-demand-001",
            risk_type=RiskType.DATA_COMPLIANCE.value,
            compute_type=ComputeType.FEDERATED_LEARNING.value,
            budget_min=1000.0,
            budget_max=5000.0,
            compute_goal="测试",
        )

        parsed = self.parser.parse_event(event)

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["event_type"], "demand_publish")
        self.assertEqual(parsed["demand_id"], "test-demand-001")

    def test_get_event_type_name(self):
        self.assertEqual(
            self.parser.get_event_type_name(30401),
            "asset_publish"
        )
        self.assertEqual(
            self.parser.get_event_type_name(30402),
            "demand_publish"
        )
        self.assertEqual(
            self.parser.get_event_type_name(30403),
            "compute_params"
        )
        self.assertEqual(
            self.parser.get_event_type_name(30404),
            "trade_receipt"
        )
        self.assertEqual(
            self.parser.get_event_type_name(30405),
            "reputation_rating"
        )
        self.assertIsNone(self.parser.get_event_type_name(99999))


if __name__ == '__main__':
    unittest.main(verbosity=2)
