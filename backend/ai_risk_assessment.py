
import numpy as np
import pickle
import os
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional
import json


@dataclass
class RiskAssessmentResult:
    overall_risk_level: str
    overall_risk_score: float
    risk_breakdown: Dict[str, float]
    risk_factors: List[str]
    suggestions: List[str]
    confidence: float

    def to_dict(self):
        return asdict(self)

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class RiskAssessmentModel:

    RISK_DIMENSIONS = [
        'data_compliance',
        'patent_risk',
        'algorithm_security',
        'rd_failure',
        'geopolitical',
        'tech_ethics'
    ]

    RISK_DIMENSION_NAMES = {
        'data_compliance': '数据合规风险',
        'patent_risk': '专利侵权风险',
        'algorithm_security': '算法安全风险',
        'rd_failure': '研发失败风险',
        'geopolitical': '地缘管制风险',
        'tech_ethics': '科技伦理风险'
    }

    def __init__(self, model_path: Optional[str] = None):
        self.model = None
        self.scaler = None
        self.feature_names = self.RISK_DIMENSIONS

        if model_path and os.path.exists(model_path):
            self._load_model(model_path)
        else:
            self._create_default_model()

    def _create_default_model(self):
        self.weights = np.array([
            0.20,
            0.18,
            0.15,
            0.17,
            0.15,
            0.15
        ])

        self.model = LogisticRegression(random_state=42)
        self.scaler = StandardScaler()

        self._train_with_simulated_data()

    def _train_with_simulated_data(self):
        np.random.seed(42)
        n_samples = 1000

        X = np.random.rand(n_samples, 6)

        weighted_sum = X @ self.weights
        threshold = np.median(weighted_sum)
        y = (weighted_sum > threshold).astype(int)

        self.scaler.fit(X)
        X_scaled = self.scaler.transform(X)
        self.model.fit(X_scaled, y)

    def _load_model(self, model_path: str):
        with open(model_path, 'rb') as f:
            data = pickle.load(f)
            self.model = data['model']
            self.scaler = data['scaler']
            self.weights = data.get('weights', self.weights)

    def save_model(self, save_path: str):
        data = {
            'model': self.model,
            'scaler': self.scaler,
            'weights': self.weights
        }
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'wb') as f:
            pickle.dump(data, f)

    def assess(self, risk_factors: Dict[str, float]) -> RiskAssessmentResult:
        features = []
        for dim in self.RISK_DIMENSIONS:
            features.append(risk_factors.get(dim, 0.5))

        X = np.array(features).reshape(1, -1)

        X_scaled = self.scaler.transform(X)
        prob = self.model.predict_proba(X_scaled)[0][1]

        risk_breakdown = {}
        for i, dim in enumerate(self.RISK_DIMENSIONS):
            risk_breakdown[self.RISK_DIMENSION_NAMES[dim]] = round(features[i], 3)

        if prob < 0.33:
            risk_level = '低风险'
        elif prob < 0.66:
            risk_level = '中风险'
        else:
            risk_level = '高风险'

        sorted_risks = sorted(risk_breakdown.items(), key=lambda x: x[1], reverse=True)
        main_risk_factors = [f"{name}（{score:.1%}）" for name, score in sorted_risks[:3]]

        suggestions = self._generate_suggestions(risk_breakdown, risk_level)

        confidence = 0.75 + 0.2 * abs(prob - 0.5) * 2

        return RiskAssessmentResult(
            overall_risk_level=risk_level,
            overall_risk_score=round(prob, 3),
            risk_breakdown=risk_breakdown,
            risk_factors=main_risk_factors,
            suggestions=suggestions,
            confidence=round(confidence, 3)
        )

    def _generate_suggestions(self, risk_breakdown: Dict[str, float], risk_level: str) -> List[str]:
        suggestions = []

        suggestion_map = {
            '数据合规风险': [
                '建立完善的数据合规管理制度',
                '定期进行数据安全审计',
                '加强员工数据安全培训',
                '引入数据脱敏和匿名化技术'
            ],
            '专利侵权风险': [
                '建立专利检索和预警机制',
                '加强研发过程中的专利审查',
                '购买专利保险降低风险',
                '建立知识产权法务团队'
            ],
            '算法安全风险': [
                '进行算法安全测试和评估',
                '建立算法伦理审查机制',
                '加强算法可解释性研究',
                '定期更新和维护算法模型'
            ],
            '研发失败风险': [
                '建立多路径研发策略',
                '加强项目风险管理',
                '建立技术储备和备胎方案',
                '加强产学研合作'
            ],
            '地缘管制风险': [
                '多元化供应链布局',
                '加强合规审查和风险预警',
                '建立应急响应机制',
                '拓展多元化市场'
            ],
            '科技伦理风险': [
                '建立科技伦理委员会',
                '制定伦理准则和规范',
                '加强员工伦理培训',
                '建立公众沟通机制'
            ]
        }

        sorted_risks = sorted(risk_breakdown.items(), key=lambda x: x[1], reverse=True)
        for name, score in sorted_risks[:2]:
            if score > 0.6:
                suggestions.extend(suggestion_map.get(name, [])[:2])

        if risk_level == '高风险':
            suggestions.insert(0, '整体风险较高，建议立即进行全面风险评估并制定应对方案')
        elif risk_level == '中风险':
            suggestions.insert(0, '整体风险中等，建议关注主要风险点并制定改进计划')
        else:
            suggestions.insert(0, '整体风险较低，建议继续保持并定期监测')

        return suggestions[:5]

    def batch_assess(self, companies: List[Dict[str, float]]) -> List[RiskAssessmentResult]:
        return [self.assess(company) for company in companies]

    def get_model_info(self) -> Dict:
        return {
            'model_type': 'Logistic Regression + Expert Weights',
            'input_dimensions': len(self.RISK_DIMENSIONS),
            'risk_dimensions': self.RISK_DIMENSION_NAMES,
            'training_samples': 1000,
            'version': '1.0.0'
        }


def demo():
    print("=" * 60)
    print("Cloak - Risk Assessment Demo")
    print("=" * 60)
    print()

    model = RiskAssessmentModel()
    print("模型加载成功")
    print(f"   模型类型: {model.get_model_info()['model_type']}")
    print(f"   风险维度: {len(model.RISK_DIMENSIONS)}个")
    print()

    print("-" * 60)
    print("示例1：高风险企业评估")
    print("-" * 60)
    high_risk_company = {
        'data_compliance': 0.8,
        'patent_risk': 0.7,
        'algorithm_security': 0.6,
        'rd_failure': 0.8,
        'geopolitical': 0.7,
        'tech_ethics': 0.5
    }
    result = model.assess(high_risk_company)
    print(f"   综合风险等级: {result.overall_risk_level}")
    print(f"   综合风险分数: {result.overall_risk_score:.1%}")
    print(f"   模型置信度: {result.confidence:.1%}")
    print()
    print("   各维度风险:")
    for name, score in result.risk_breakdown.items():
        bar = "" * int(score * 20)
        print(f"     {name}: {bar} {score:.1%}")
    print()
    print("   主要风险因素:")
    for factor in result.risk_factors:
        print(f"     • {factor}")
    print()
    print("   改进建议:")
    for suggestion in result.suggestions:
        print(f"     • {suggestion}")
    print()

    print("-" * 60)
    print("示例2：中等风险企业评估")
    print("-" * 60)
    medium_risk_company = {
        'data_compliance': 0.5,
        'patent_risk': 0.4,
        'algorithm_security': 0.5,
        'rd_failure': 0.6,
        'geopolitical': 0.4,
        'tech_ethics': 0.5
    }
    result = model.assess(medium_risk_company)
    print(f"   综合风险等级: {result.overall_risk_level}")
    print(f"   综合风险分数: {result.overall_risk_score:.1%}")
    print(f"   模型置信度: {result.confidence:.1%}")
    print()
    print("   各维度风险:")
    for name, score in result.risk_breakdown.items():
        bar = "" * int(score * 20)
        print(f"     {name}: {bar} {score:.1%}")
    print()
    print("   改进建议:")
    for suggestion in result.suggestions:
        print(f"     • {suggestion}")
    print()

    print("-" * 60)
    print("示例3：低风险企业评估")
    print("-" * 60)
    low_risk_company = {
        'data_compliance': 0.2,
        'patent_risk': 0.3,
        'algorithm_security': 0.2,
        'rd_failure': 0.3,
        'geopolitical': 0.2,
        'tech_ethics': 0.3
    }
    result = model.assess(low_risk_company)
    print(f"   综合风险等级: {result.overall_risk_level}")
    print(f"   综合风险分数: {result.overall_risk_score:.1%}")
    print(f"   模型置信度: {result.confidence:.1%}")
    print()
    print("   各维度风险:")
    for name, score in result.risk_breakdown.items():
        bar = "█" * int(score * 20)
        print(f"     {name}: {bar} {score:.1%}")
    print()
    print("   改进建议:")
    for suggestion in result.suggestions:
        print(f"     • {suggestion}")
    print()

    print("=" * 60)
    print("演示完成！")
    print("=" * 60)


if __name__ == '__main__':
    demo()
