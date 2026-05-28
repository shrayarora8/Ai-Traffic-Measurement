import argparse
import json
import os
import platform
import re
import socket
import ssl
import subprocess
import time
from datetime import datetime, timezone

import config

def resolve_dns(domain):
    """
    Resolve a domain name to its IP addresses using the CLI 'dig' utility.
    """
    result = {"domain": domain, "ips": [], "error": None}
    try:
        proc = subprocess.run(
            ["dig", "+short", "+time=5", "+tries=2", domain],
            capture_output=True,
            text=True,
            timeout=15,
        )
        lines = proc.stdout.strip().split("\n")
        ips = []
        for line in lines:
            line = line.strip().rstrip(".")
            if not line:
                continue
            if re.match(r"^[\d.]+$", line) or ":" in line:
                ips.append(line)
        result["ips"] = ips
    except subprocess.TimeoutExpired:
        result["error"] = "DNS lookup timed out"
    except FileNotFoundError:
        result["error"] = "'dig' command not found"
    except Exception as e:
        result["error"] = str(e)
    return result

def run_traceroute(domain, max_hops=None, timeout=None):
    """
    Run traceroute and parse output to extract hops, IPs, and RTTs.
    """
    max_hops = max_hops or config.TRACEROUTE_MAX_HOPS
    timeout = timeout or config.TRACEROUTE_TIMEOUT

    result = {
        "domain": domain,
        "hops": [],
        "reached_destination": False,
        "error": None,
    }

    try:
        # Send 1 probe per hop (-q 1) to speed up execution
        cmd = ["traceroute", "-m", str(max_hops), "-w", str(timeout), "-q", "1", domain]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max_hops * timeout + 30,
        )
        
        output = proc.stdout
        hops = []

        for line in output.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("traceroute to"):
                continue

            parts = line.split()
            if not parts:
                continue

            try:
                hop_num = int(parts[0])
            except ValueError:
                continue

            hop = {"hop_num": hop_num, "ip": None, "hostname": None, "rtt_ms": None}

            # Check if hop timed out (* * *)
            if "*" in parts[1:] and all(p == "*" for p in parts[1:]):
                hops.append(hop)
                continue

            # Parse IP and hostname
            ip_match = re.search(r"\((\d+\.\d+\.\d+\.\d+)\)", line)
            if ip_match:
                hop["ip"] = ip_match.group(1)
                hostname_match = re.search(r"(\S+)\s+\(" + re.escape(hop["ip"]) + r"\)", line)
                if hostname_match:
                    hostname = hostname_match.group(1)
                    hop["hostname"] = hostname if hostname != hop["ip"] else None
            else:
                for part in parts[1:]:
                    if re.match(r"^\d+\.\d+\.\d+\.\d+$", part):
                        hop["ip"] = part
                        break

            # Parse RTT
            rtt_match = re.search(r"([\d.]+)\s*ms", line)
            if rtt_match:
                hop["rtt_ms"] = float(rtt_match.group(1))

            hops.append(hop)

        result["hops"] = hops

        # Check if the final hop IP matches target resolution
        if hops:
            try:
                dest_ip = socket.gethostbyname(domain)
                last_hop_ip = next(
                    (h["ip"] for h in reversed(hops) if h["ip"] is not None), None
                )
                if last_hop_ip == dest_ip:
                    result["reached_destination"] = True
            except socket.gaierror:
                pass

    except subprocess.TimeoutExpired:
        result["error"] = "Traceroute timed out"
    except FileNotFoundError:
        result["error"] = "'traceroute' command not found"
    except Exception as e:
        result["error"] = str(e)

    return result

def measure_tcp_rtt(host, port=443, attempts=3):
    """
    Measure TCP handshake RTT by connecting to the target port.
    """
    result = {
        "host": host,
        "port": port,
        "rtt_ms": None,
        "all_rtts_ms": [],
        "error": None,
    }
    rtts = []

    for i in range(attempts):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        try:
            start = time.perf_counter()
            sock.connect((host, port))
            end = time.perf_counter()
            rtt = (end - start) * 1000
            rtts.append(round(rtt, 3))
        except socket.timeout:
            rtts.append(None)
        except OSError as e:
            rtts.append(None)
            result["error"] = str(e)
        finally:
            sock.close()

        if i < attempts - 1:
            time.sleep(0.5)

    result["all_rtts_ms"] = rtts
    valid_rtts = [r for r in rtts if r is not None]
    if valid_rtts:
        result["rtt_ms"] = min(valid_rtts)
        result["error"] = None
    else:
        result["error"] = result.get("error") or "All attempts failed"

    return result

def extract_tls_cert(domain, port=443):
    """
    Fetch TLS certificate and extract Subject Alternative Names and Issuer metadata.
    """
    result = {
        "domain": domain,
        "subject": None,
        "issuer": None,
        "san": [],
        "not_before": None,
        "not_after": None,
        "tls_version": None,
        "cipher": None,
        "error": None,
    }

    try:
        context = ssl.create_default_context()
        with socket.create_connection((domain, port), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=domain) as tls_sock:
                cert = tls_sock.getpeercert()

                if cert.get("subject"):
                    subject_dict = {}
                    for field in cert["subject"]:
                        for key, value in field:
                            subject_dict[key] = value
                    result["subject"] = subject_dict

                if cert.get("issuer"):
                    issuer_dict = {}
                    for field in cert["issuer"]:
                        for key, value in field:
                            issuer_dict[key] = value
                    result["issuer"] = issuer_dict

                san_entries = cert.get("subjectAltName", ())
                result["san"] = [value for (type_, value) in san_entries]
                result["not_before"] = cert.get("notBefore")
                result["not_after"] = cert.get("notAfter")
                result["tls_version"] = tls_sock.version()
                
                cipher_info = tls_sock.cipher()
                if cipher_info:
                    result["cipher"] = cipher_info[0]

    except ssl.SSLError as e:
        result["error"] = f"TLS error: {e}"
    except socket.timeout:
        result["error"] = "Connection timed out"
    except Exception as e:
        result["error"] = str(e)

    return result

def run_measurement(domain, label=None):
    """
    Orchestrate all 4 network measurements for a single target domain.
    """
    label = label or domain
    print(f"\nMeasuring: {label} ({domain})")
    
    measurement = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "target_label": label,
        "target_domain": domain,
        "source_machine": platform.node(),
        "vpn_provider": None,
        "vpn_region": None,
    }

    # DNS
    measurement["dns"] = resolve_dns(domain)
    dns_ips = measurement["dns"]["ips"]

    # Traceroute
    measurement["traceroute"] = run_traceroute(domain)

    # TCP RTT
    rtt_target = dns_ips[0] if dns_ips else domain
    measurement["tcp_rtt"] = measure_tcp_rtt(rtt_target)

    # TLS Cert
    measurement["tls_cert"] = extract_tls_cert(domain)

    return measurement

def save_measurement(measurement, output_path=None):
    """
    Save measurement object to JSON file in data/raw directory.
    """
    if output_path is None:
        os.makedirs(config.RAW_DATA_DIR, exist_ok=True)
        ts = measurement["timestamp"].replace(":", "-")
        label = measurement["target_label"]
        vpn = measurement.get("vpn_provider") or "no-vpn"
        region = measurement.get("vpn_region") or "local"
        filename = f"{ts}_{region}_{vpn}_{label}.json"
        output_path = os.path.join(config.RAW_DATA_DIR, filename)

    with open(output_path, "w") as f:
        json.dump(measurement, f, indent=2, default=str)
    
    print(f"Saved: {output_path}")
    return output_path

def main():
    parser = argparse.ArgumentParser(description="AI service traffic measurement collector.")
    parser.add_argument("--target", help="Domain to measure")
    parser.add_argument("--output", help="Output JSON path")
    args = parser.parse_args()

    if args.target:
        result = run_measurement(args.target)
        save_measurement(result, args.output)
    else:
        for label, domain in config.TARGETS.items():
            result = run_measurement(domain, label=label)
            save_measurement(result, args.output)

if __name__ == "__main__":
    main()
