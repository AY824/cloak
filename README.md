# Cloak

Cloak is built on Nostr with federated learning for On-chain private risk data exchange.

Cloak是一个基于Nostr协议，融合联邦学习的区块链上风险数据资产隐私流通网络，旨在实现风险数据的合规资产化转化，可支撑保险精算、信贷风控等产业落地场景。

---

Data stays local. Value flows freely.

---

## Protocol

NIP-304

| Kind |       Type     |
|------|    ---------   |
| 30401| Asset   资产发布|
| 30402| Demand  需求发布|
| 30403| Compute 计算参数|
| 30404| Receipt 交易凭证|
| 30405| Rating  声誉评价|

---

## Contracts

RiskAssetNFT

TradeEscrow

RevenueSplit

---

# scikit-learn/Flower

# FedAvg/DP

---

## Build

```bash
git clone https://github.com/AY824/cloak.git
cd cloak
pip install -r requirements.txt
```

---

## Usage

```bash
# Run tests
python3 -m pytest tests/ -v

# Start node
python3 backend/main.py

# Web interface
cd frontend && python3 -m http.server 8080
```

---

## License

MIT
