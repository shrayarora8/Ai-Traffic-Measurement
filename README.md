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

# 4. Run a single measurement and label the current network origin
python collector.py --vpn-provider no-vpn --vpn-region local

# 5. Run one prompted pass through all configured VPN provider/region pairs
python run_campaign.py --matrix

# 6. Check results
ls data/raw/
cat data/raw/*.json | python -m json.tool
```

## Manual VPN Campaign Collection

The project does not control the VPN client directly. Connect the VPN manually first, then start a campaign with the matching provider and region labels.

Run one smoke-test round after each VPN switch:

```bash
python run_campaign.py --vpn-provider expressvpn --vpn-region us --rounds 1
```

Run the full 72-hour campaign for the current VPN exit point:

```bash
python run_campaign.py --vpn-provider expressvpn --vpn-region us
```

Repeat the campaign for all planned network origins:

```bash
python run_campaign.py --vpn-provider expressvpn --vpn-region us
python run_campaign.py --vpn-provider expressvpn --vpn-region de
python run_campaign.py --vpn-provider expressvpn --vpn-region jp
python run_campaign.py --vpn-provider expressvpn --vpn-region br

python run_campaign.py --vpn-provider protonvpn --vpn-region us
python run_campaign.py --vpn-provider protonvpn --vpn-region de
python run_campaign.py --vpn-provider protonvpn --vpn-region jp
python run_campaign.py --vpn-provider protonvpn --vpn-region br
```

Or run a prompted matrix pass. The script will ask you to connect each
ExpressVPN/ProtonVPN exit in US, Germany, Japan, and Brazil, then it will
measure OpenAI, Google Gemini, and Anthropic for the active VPN context:

```bash
python run_campaign.py --matrix
```

Each round measures OpenAI, Google Gemini, and Anthropic, then writes one JSON file per provider to `data/raw/`. Campaign metadata is written to `data/campaigns/`.

## Project Structure

| File | Purpose |
|------|---------|
| `config.py` | All configuration (targets, regions, intervals) |
| `collector.py` | Core measurement script (DNS, traceroute, RTT, TLS) |
| `vpn_control.py` | VPN connection automation (TODO) |
| `run_campaign.py` | 72-hour measurement campaign loop for manually selected VPN origins |
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
- [x] Collector (all 4 measurements + VPN/region labels)
- [x] Manual matrix collection for four regions x two VPN types
- [ ] VPN controller
- [x] Campaign runner (72-hour loop)
- [ ] Analyzer (geolocation + jurisdictional exposure)
