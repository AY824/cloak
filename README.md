# Cloak

Cloak is built on Nostr with federated learning for On-chain private risk data exchange.

---

Data stays local. Value flows freely.

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

## Protocol

NIP-304 custom event kinds:

| Kind | Type    |
|------|---------|
| 30401| Asset   |
| 30402| Demand  |
| 30403| Compute |
| 30404| Receipt |
| 30405| Rating  |

---

## License

MIT
