
import numpy as np
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import json


@dataclass
class PricingResult:
    suggested_price: float
    price_range: tuple
    confidence: float
    price_breakdown: Dict[str, float]
    factors: List[str]
    suggestions: List[str]

    def to_dict(self):
        return {
            'suggested_price': self.suggested_price,
            'price_range': list(self.price_range),
            'confidence': self.confidence,
            'price_breakdown': self.price_breakdown,
            'factors': self.factors,
            'suggestions': self.suggestions
        }

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


class DataPricingModel:

    RISK_TYPE_BASE_PRICE = {
        'data_compliance': 1.2,
        'patent_infringement': 1.0,
        'algorithm_security': 1.1,
        'rd_failure': 0.9,
        'geopolitical': 1.3,
        'tech_ethics': 0.8
    }

    RISK_TYPE_NAMES = {
        'data_compliance': '数据合规风险',
        'patent_infringement': '专利侵权风险',
        'algorithm_security': '算法安全风险',
        'rd_failure': '研发失败风险',
        'geopolitical': '地缘管制风险',
        'tech_ethics': '科技伦理风险'
    }

    DP_LEVEL_FACTOR = {
        'weak': 1.0,
        'medium': 0.85,
        'strong': 0.7
    }

    def __init__(self):
        self.weights = {
            'sample_count': 0.25,
            'data_quality': 0.20,
            'risk_level': 0.20,
            'market_demand': 0.20,
            'dp_level': 0.15
        }

        self.base_price_per_1000 = 50.0

    def estimate_price(self, data_features: Dict) -> PricingResult:
        risk_type = data_features.get('risk_type', 'data_compliance')
        sample_count = data_features.get('sample_count', 1000)
        data_quality = data_features.get('data_quality', 0.7)
        risk_level = data_features.get('risk_level', 0.5)
        market_demand = data_features.get('market_demand', 0.5)
        dp_level = data_features.get('dp_level', 'medium')

        sample_score = min(1.0, np.log10(sample_count + 1) / 4)

        quality_score = data_quality

        risk_score = risk_level

        demand_score = market_demand

        dp_factor = self.DP_LEVEL_FACTOR.get(dp_level, 0.85)

        value_coefficient = (
            sample_score * self.weights['sample_count'] +
            quality_score * self.weights['data_quality'] +
            risk_score * self.weights['risk_level'] +
            demand_score * self.weights['market_demand']
        ) * dp_factor

        risk_type_factor = self.RISK_TYPE_BASE_PRICE.get(risk_type, 1.0)

        base_price = self.base_price_per_1000 * (sample_count / 1000)
        suggested_price = base_price * value_coefficient * risk_type_factor

        price_low = suggested_price * 0.8
        price_high = suggested_price * 1.2

        confidence = 0.6 + 0.3 * min(1.0, sample_count / 5000) + 0.1 * data_quality
        confidence = min(0.98, confidence)

        price_breakdown = {
            '基础价值': round(base_price * 0.3, 2),
            '样本量贡献': round(base_price * sample_score * self.weights['sample_count'] * risk_type_factor, 2),
            '数据质量贡献': round(base_price * quality_score * self.weights['data_quality'] * risk_type_factor, 2),
            '风险等级贡献': round(base_price * risk_score * self.weights['risk_level'] * risk_type_factor, 2),
            '市场需求贡献': round(base_price * demand_score * self.weights['market_demand'] * risk_type_factor, 2),
            '隐私保护调整': round(base_price * value_coefficient * (dp_factor - 1) * risk_type_factor, 2)
        }

        factors = []
        factor_scores = [
            ('样本量', sample_score),
            ('数据质量', quality_score),
            ('风险等级', risk_score),
            ('市场需求', demand_score)
        ]
        factor_scores.sort(key=lambda x: x[1], reverse=True)

        for name, score in factor_scores[:3]:
            if score > 0.7:
                factors.append(f"{name}较高（{score:.0%}），对价格有正向贡献")
            elif score < 0.3:
                factors.append(f"{name}较低（{score:.0%}），限制了数据价值")

        suggestions = self._generate_suggestions(
            sample_count, data_quality, risk_level, market_demand, dp_level
        )

        return PricingResult(
            suggested_price=round(suggested_price, 2),
            price_range=(round(price_low, 2), round(price_high, 2)),
            confidence=round(confidence, 3),
            price_breakdown=price_breakdown,
            factors=factors,
            suggestions=suggestions
        )

    def _generate_suggestions(self, sample_count, data_quality, risk_level, market_demand, dp_level):
        suggestions = []

        if sample_count < 500:
            suggestions.append("建议增加数据样本量，样本量是影响数据价值的关键因素")
        elif sample_count < 2000:
            suggestions.append("当前样本量中等，扩充样本可显著提升价值")

        if data_quality < 0.5:
            suggestions.append("建议提升数据质量，包括数据清洗、去重、标注等")
        elif data_quality < 0.8:
            suggestions.append("数据质量良好，可通过数据标注进一步增值")

        if market_demand < 0.4:
            suggestions.append("当前市场需求较低，建议关注热门风险类型数据")

        if dp_level == 'strong':
            suggestions.append("当前隐私保护等级较高，可根据场景适当调整以提升数据效用")
        elif dp_level == 'weak':
            suggestions.append("当前隐私保护较弱，建议加强隐私保护以提升数据可信度")

        suggestions.append("可结合联邦学习联合建模，进一步提升数据价值")
        suggestions.append("提供详细的数据说明文档，增加买家信任")

        return suggestions[:5]

    def batch_estimate(self, data_list: List[Dict]) -> List[PricingResult]:
        return [self.estimate_price(data) for data in data_list]

    def get_model_info(self) -> Dict:
        return {
            'model_type': 'Multi-Factor Pricing Model',
            'factors': list(self.weights.keys()),
            'risk_types': list(self.RISK_TYPE_NAMES.keys()),
            'dp_levels': list(self.DP_LEVEL_FACTOR.keys()),
            'version': '1.0.0'
        }


def demo():
    print("=" * 60)
    print("Cloak - Pricing Engine Demo")
    print("=" * 60)
    print()

    model = DataPricingModel()
    print("定价模型加载成功")
    print(f"   模型类型: {model.get_model_info()['model_type']}")
    print(f"   定价因子: {len(model.get_model_info()['factors'])}个")
    print()

    print("-" * 60)
    print("示例1：高质量大规模数据定价")
    print("-" * 60)
    high_quality_data = {
        'risk_type': 'data_compliance',
        'sample_count': 5000,
        'data_quality': 0.9,
        'risk_level': 0.8,
        'market_demand': 0.7,
        'dp_level': 'medium'
    }
    result = model.estimate_price(high_quality_data)
    print(f"   风险类型: {model.RISK_TYPE_NAMES[high_quality_data['risk_type']]}")
    print(f"   样本数量: {high_quality_data['sample_count']:,} 条")
    print(f"   数据质量: {high_quality_data['data_quality']:.0%}")
    print(f"   风险等级: {high_quality_data['risk_level']:.0%}")
    print(f"   市场需求: {high_quality_data['market_demand']:.0%}")
    print(f"   隐私等级: {high_quality_data['dp_level']}")
    print()
    print(f"   建议价格: {result.suggested_price} USDT")
    print(f"   价格区间: {result.price_range[0]} - {result.price_range[1]} USDT")
    print(f"   定价置信度: {result.confidence:.1%}")
    print()
    print("   价格构成:")
    for name, value in result.price_breakdown.items():
        print(f"     • {name}: {value} USDT")
    print()
    print("   影响因素:")
    for factor in result.factors:
        print(f"     • {factor}")
    print()
    print("   增值建议:")
    for suggestion in result.suggestions:
        print(f"     • {suggestion}")
    print()

    print("-" * 60)
    print("示例2：中等规模数据定价")
    print("-" * 60)
    medium_data = {
        'risk_type': 'patent_infringement',
        'sample_count': 1000,
        'data_quality': 0.7,
        'risk_level': 0.6,
        'market_demand': 0.5,
        'dp_level': 'medium'
    }
    result = model.estimate_price(medium_data)
    print(f"   风险类型: {model.RISK_TYPE_NAMES[medium_data['risk_type']]}")
    print(f"   样本数量: {medium_data['sample_count']:,} 条")
    print(f"   建议价格: {result.suggested_price} USDT")
    print(f"   价格区间: {result.price_range[0]} - {result.price_range[1]} USDT")
    print(f"   定价置信度: {result.confidence:.1%}")
    print()

    print("-" * 60)
    print("示例3：稀缺高价值数据（地缘管制）")
    print("-" * 60)
    rare_data = {
        'risk_type': 'geopolitical',
        'sample_count': 500,
        'data_quality': 0.85,
        'risk_level': 0.9,
        'market_demand': 0.9,
        'dp_level': 'strong'
    }
    result = model.estimate_price(rare_data)
    print(f"   风险类型: {model.RISK_TYPE_NAMES[rare_data['risk_type']]}")
    print(f"   样本数量: {rare_data['sample_count']:,} 条")
    print(f"   建议价格: {result.suggested_price} USDT")
    print(f"   价格区间: {result.price_range[0]} - {result.price_range[1]} USDT")
    print(f"   定价置信度: {result.confidence:.1%}")
    print()
    print("   增值建议:")
    for suggestion in result.suggestions:
        print(f"     • {suggestion}")
    print()

    print("=" * 60)
    print("演示完成！")
    print("=" * 60)


if __name__ == '__main__':
    demo()
