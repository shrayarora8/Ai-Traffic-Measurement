# AI Service Traffic Measurement

**Authors:** Haochen Dong, Shray Arora, Mohammad Beigi

A network measurement study that traces the jurisdictional footprint of AI inference traffic. We measure the routing paths from four countries (US, Germany, Japan, Brazil) to three major AI providers (OpenAI, Google, Anthropic) through different VPN types to assess cross-border data exposure and VPN measurement bias.

## Quick Start

```bash
# 1. Clone and enter the project
git clone <your-repo-url>
cd ai-traffic-measurement

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run a single measurement (no VPN needed)
python collector.py

# 5. Check results
ls data/raw/
cat data/raw/*.json | python -m json.tool
```

## Project Structure

| File | Purpose |
|------|---------|
| `config.py` | All configuration (targets, regions, intervals) |
| `collector.py` | Core measurement script (DNS, traceroute, RTT, TLS) |
| `vpn_control.py` | VPN connection automation (TODO) |
| `run_campaign.py` | 72-hour measurement campaign loop (TODO) |
| `analyzer.py` | Post-collection analysis and visualization (TODO) |
| `concepts_guide.md` | Networking concepts reference |

## Measurements Collected

Each measurement round captures four types of network data per AI provider:

1. **DNS Resolution** — Which IP address does the provider's domain resolve to from this location?
2. **Traceroute** — What routers does the traffic pass through, and in which countries?
3. **TCP Handshake RTT** — How far away is the server (physically)?
4. **TLS Certificate** — What does the server's certificate reveal about the data center?

## Status

- [x] Project structure
- [x] Configuration
- [x] Collector (all 4 measurements)
- [ ] VPN controller
- [ ] Campaign runner (72-hour loop)
- [ ] Analyzer (geolocation + jurisdictional exposure)
