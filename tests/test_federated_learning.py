
import sys
import os
import unittest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from federated_learning import (
    ModelWeights,
    FederatedClient,
    FederatedAggregator,
    ContributionCalculator,
    TrainingResult,
)


class TestModelWeights(unittest.TestCase):

    def test_create_weights(self):
        weights = [
            np.array([[0.1, 0.2, 0.3]]),
            np.array([0.0])
        ]

        model_weights = ModelWeights(
            weights=weights,
            model_type="logistic_regression"
        )

        self.assertEqual(model_weights.model_type, "logistic_regression")
        self.assertEqual(len(model_weights.weights), 2)
        self.assertEqual(model_weights.weights[0].shape, (1, 3))

    def test_serialize_deserialize(self):
        weights = [
            np.array([[0.1, 0.2], [0.3, 0.4]]),
            np.array([0.5, 0.6])
        ]

        model_weights = ModelWeights(
            weights=weights,
            model_type="logistic_regression"
        )

        serialized = model_weights.serialize()
        self.assertIsInstance(serialized, str)

        deserialized = ModelWeights.deserialize(serialized)
        self.assertEqual(deserialized.model_type, "logistic_regression")
        self.assertEqual(len(deserialized.weights), 2)

        np.testing.assert_array_almost_equal(
            deserialized.weights[0],
            weights[0]
        )
        np.testing.assert_array_almost_equal(
            deserialized.weights[1],
            weights[1]
        )

    def test_get_total_params(self):
        weights = [
            np.zeros((1, 10)),
            np.zeros(1)
        ]

        model_weights = ModelWeights(
            weights=weights,
            model_type="logistic_regression"
        )

        self.assertEqual(model_weights.get_total_params(), 11)


class TestFederatedClient(unittest.TestCase):

    def setUp(self):
        np.random.seed(42)
        self.X_train = np.random.randn(100, 5)
        self.y_train = (np.random.randn(100) > 0).astype(int)

        self.client = FederatedClient(client_id="test_client")
        self.client.load_data(self.X_train, self.y_train)

    def test_load_data(self):
        self.assertEqual(self.client.X_train.shape, (100, 5))
        self.assertEqual(self.client.y_train.shape, (100,))
        self.assertEqual(self.client.num_samples, 100)

    def test_train_local(self):
        result = self.client.train_local(epochs=5)

        self.assertIsInstance(result, TrainingResult)
        self.assertIsNotNone(result.weights)
        self.assertIn("accuracy", result.metrics)
        self.assertIn("loss", result.metrics)

        self.assertGreaterEqual(result.metrics["accuracy"], 0.0)
        self.assertLessEqual(result.metrics["accuracy"], 1.0)

    def test_set_model_weights(self):
        initial_weights = ModelWeights(
            weights=[
                np.zeros((1, 5)),
                np.zeros(1)
            ],
            model_type="logistic_regression"
        )

        self.client.set_model_weights(initial_weights)

        result = self.client.train_local(epochs=1)
        self.assertIsNotNone(result.weights)


class TestFederatedAggregator(unittest.TestCase):

    def setUp(self):
        self.aggregator = FederatedAggregator(
            aggregator_id="test_aggregator",
            num_clients=3
        )

        self.client_weights = []
        self.client_examples = []

        for i in range(3):
            weights = ModelWeights(
                weights=[
                    np.random.randn(1, 5) * 0.1,
                    np.random.randn(1) * 0.1
                ],
                model_type="logistic_regression"
            )
            self.client_weights.append(weights)
            self.client_examples.append(100 + i * 10)

    def test_aggregate_weights_fedavg(self):
        aggregated = self.aggregator.aggregate_weights(
            self.client_weights,
            self.client_examples
        )

        self.assertIsInstance(aggregated, ModelWeights)
        self.assertEqual(len(aggregated.weights), 2)

        self.assertEqual(aggregated.weights[0].shape, (1, 5))
        self.assertEqual(aggregated.weights[1].shape, (1,))

    def test_set_initial_weights(self):
        initial_weights = ModelWeights(
            weights=[
                np.zeros((1, 5)),
                np.zeros(1)
            ],
            model_type="logistic_regression"
        )

        self.aggregator.set_initial_weights(initial_weights)

        self.assertIsNotNone(self.aggregator.global_weights)
        self.assertEqual(self.aggregator.global_weights.model_type, "logistic_regression")

    def test_evaluate_global_model(self):
        initial_weights = ModelWeights(
            weights=[
                np.random.randn(1, 5) * 0.1,
                np.random.randn(1) * 0.1
            ],
            model_type="logistic_regression"
        )
        self.aggregator.set_initial_weights(initial_weights)

        X_test = np.random.randn(50, 5)
        y_test = (np.random.randn(50) > 0).astype(int)

        metrics = self.aggregator.evaluate_global_model(X_test, y_test)

        self.assertIn("accuracy", metrics)
        self.assertIn("precision", metrics)
        self.assertIn("recall", metrics)
        self.assertIn("f1_score", metrics)
        self.assertIn("auc", metrics)


class TestContributionCalculator(unittest.TestCase):

    def test_calculate_by_sample_size(self):
        client_examples = {
            "client1": 100,
            "client2": 200,
            "client3": 300,
        }

        contributions = ContributionCalculator.calculate_by_sample_size(client_examples)

        self.assertEqual(len(contributions), 3)
        self.assertAlmostEqual(sum(contributions.values()), 1.0, places=5)

        self.assertGreater(contributions["client3"], contributions["client2"])
        self.assertGreater(contributions["client2"], contributions["client1"])

    def test_calculate_by_performance(self):
        client_metrics = {
            "client1": {"accuracy": 0.85},
            "client2": {"accuracy": 0.90},
            "client3": {"accuracy": 0.95},
        }

        contributions = ContributionCalculator.calculate_by_performance(
            client_metrics,
            metric_key="accuracy"
        )

        self.assertEqual(len(contributions), 3)
        self.assertAlmostEqual(sum(contributions.values()), 1.0, places=5)

    def test_calculate_combined(self):
        client_examples = {
            "client1": 100,
            "client2": 200,
            "client3": 300,
        }

        client_metrics = {
            "client1": {"accuracy": 0.85},
            "client2": {"accuracy": 0.90},
            "client3": {"accuracy": 0.95},
        }

        contributions = ContributionCalculator.calculate_combined(
            client_examples,
            client_metrics,
            sample_weight=0.6,
            performance_weight=0.4,
            metric_key="accuracy"
        )

        self.assertEqual(len(contributions), 3)
        self.assertAlmostEqual(sum(contributions.values()), 1.0, places=5)

    def test_calculate_shapley(self):
        client_metrics = {
            "client1": {"accuracy": 0.80},
            "client2": {"accuracy": 0.85},
            "client3": {"accuracy": 0.90},
        }

        contributions = ContributionCalculator.calculate_shapley_approx(
            client_metrics,
            metric_key="accuracy"
        )

        self.assertEqual(len(contributions), 3)
        self.assertAlmostEqual(sum(contributions.values()), 1.0, places=5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
