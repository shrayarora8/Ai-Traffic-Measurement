import argparse
import json
import math
import os
import time
from datetime import datetime, timezone

import collector
import config


def utc_timestamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def region_codes():
    return list(config.REGIONS.keys()) if isinstance(config.REGIONS, dict) else list(config.REGIONS)


def region_name(region):
    return config.REGIONS.get(region, region) if isinstance(config.REGIONS, dict) else region


def provider_codes(include_no_vpn=False):
    providers = sorted(config.VPN_PROVIDERS.keys())
    if include_no_vpn:
        return [config.NO_VPN_PROVIDER] + providers
    return providers


def target_map(target_names):
    if not target_names:
        return config.TARGETS

    targets = {}
    for name in target_names:
        if name not in config.TARGETS:
            valid = ", ".join(sorted(config.TARGETS))
            raise ValueError(f"Unknown target '{name}'. Valid targets: {valid}")
        targets[name] = config.TARGETS[name]
    return targets


def default_rounds(hours, interval_minutes):
    return max(1, math.ceil((hours * 60) / interval_minutes))


def append_event(campaign_id, event):
    os.makedirs(config.CAMPAIGN_DATA_DIR, exist_ok=True)
    manifest_path = os.path.join(config.CAMPAIGN_DATA_DIR, f"{campaign_id}.jsonl")
    event = {"event_timestamp": datetime.now(timezone.utc).isoformat(), **event}
    with open(manifest_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, default=str) + "\n")
    return manifest_path


def print_plan(campaign_id, vpn_provider, vpn_region, targets, rounds, interval_minutes):
    manifest_path = os.path.join(config.CAMPAIGN_DATA_DIR, f"{campaign_id}.jsonl")
    print("Campaign plan")
    print(f"  campaign_id: {campaign_id}")
    print(f"  manifest: {manifest_path}")
    print(f"  vpn_provider: {vpn_provider}")
    print(f"  vpn_region: {vpn_region}")
    print(f"  targets: {', '.join(targets)}")
    print(f"  rounds: {rounds}")
    print(f"  interval_minutes: {interval_minutes}")


def run_round(campaign_id, round_number, vpn_provider, vpn_region, targets, notes=None):
    round_id = f"{campaign_id}-round-{round_number:04d}"
    saved_paths = []

    append_event(
        campaign_id,
        {
            "event": "round_started",
            "round_id": round_id,
            "round_number": round_number,
            "vpn_provider": vpn_provider,
            "vpn_region": vpn_region,
        },
    )

    for label, domain in targets.items():
        measurement = collector.run_measurement(
            domain,
            label=label,
            vpn_provider=vpn_provider,
            vpn_region=vpn_region,
            origin_type="vpn" if vpn_provider != config.NO_VPN_PROVIDER else "local",
            campaign_id=campaign_id,
            round_id=round_id,
            notes=notes,
        )
        output_path = collector.save_measurement(measurement)
        saved_paths.append(output_path)
        append_event(
            campaign_id,
            {
                "event": "measurement_saved",
                "round_id": round_id,
                "target_label": label,
                "target_domain": domain,
                "output_path": output_path,
            },
        )

    append_event(
        campaign_id,
        {
            "event": "round_completed",
            "round_id": round_id,
            "round_number": round_number,
            "saved_paths": saved_paths,
        },
    )
    return saved_paths


def run_campaign(args, vpn_provider, vpn_region):
    targets = target_map(args.targets)
    rounds = args.rounds or default_rounds(args.hours, args.interval_minutes)
    campaign_id = args.campaign_id or f"{utc_timestamp()}_{vpn_region}_{vpn_provider}"

    print_plan(campaign_id, vpn_provider, vpn_region, targets, rounds, args.interval_minutes)
    if args.dry_run:
        print("Dry run only; no files written and no measurements collected.")
        return campaign_id

    append_event(
        campaign_id,
        {
            "event": "campaign_started",
            "campaign_id": campaign_id,
            "vpn_provider": vpn_provider,
            "vpn_region": vpn_region,
            "vpn_region_name": region_name(vpn_region),
            "targets": targets,
            "interval_minutes": args.interval_minutes,
            "hours": args.hours,
            "rounds": rounds,
            "notes": args.notes,
        },
    )

    interval_seconds = args.interval_minutes * 60
    for round_number in range(1, rounds + 1):
        round_start = time.monotonic()
        run_round(campaign_id, round_number, vpn_provider, vpn_region, targets, notes=args.notes)

        if round_number == rounds:
            break

        sleep_seconds = max(interval_seconds - (time.monotonic() - round_start), 0)
        print(f"Sleeping {sleep_seconds:.1f} seconds before next round.")
        time.sleep(sleep_seconds)

    append_event(campaign_id, {"event": "campaign_completed", "campaign_id": campaign_id})
    return campaign_id


def run_matrix(args):
    targets = target_map(args.targets)
    rounds = args.rounds or 1
    campaign_id = args.campaign_id or f"{utc_timestamp()}_manual_matrix"

    print("Manual matrix plan")
    print(f"  campaign_id: {campaign_id}")
    print(f"  providers: {', '.join(provider_codes())}")
    print(f"  regions: {', '.join(region_codes())}")
    print(f"  targets: {', '.join(targets)}")
    print(f"  rounds_per_context: {rounds}")

    if args.dry_run:
        print("Dry run only; no files written and no measurements collected.")
        return campaign_id

    append_event(
        campaign_id,
        {
            "event": "matrix_started",
            "campaign_id": campaign_id,
            "vpn_providers": provider_codes(),
            "vpn_regions": region_codes(),
            "targets": targets,
            "rounds_per_context": rounds,
            "notes": args.notes,
        },
    )

    print("For each prompt, connect the requested VPN exit first, then press Enter.")
    for vpn_provider in provider_codes():
        for vpn_region in region_codes():
            prompt = (
                f"\nConnect {vpn_provider} to {vpn_region} ({region_name(vpn_region)}), "
                "verify it is active, then press Enter to collect all targets..."
            )
            if args.no_prompt:
                print(prompt)
            else:
                input(prompt)

            for round_number in range(1, rounds + 1):
                run_round(campaign_id, round_number, vpn_provider, vpn_region, targets, notes=args.notes)
                if round_number < rounds:
                    print(f"Sleeping {args.interval_minutes} minutes before next matrix round...")
                    time.sleep(args.interval_minutes * 60)

    append_event(campaign_id, {"event": "matrix_completed", "campaign_id": campaign_id})
    return campaign_id


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run repeated AI traffic measurements for a manually selected VPN context."
    )
    parser.add_argument(
        "--vpn-provider",
        choices=provider_codes(include_no_vpn=True),
        help="Active VPN provider label. Use no-vpn with --vpn-region local.",
    )
    parser.add_argument(
        "--vpn-region",
        choices=["local"] + region_codes(),
        help="Active VPN exit region. Use local only with --vpn-provider no-vpn.",
    )
    parser.add_argument("--campaign-id", help="Optional campaign ID; defaults to timestamp_region_provider")
    parser.add_argument("--hours", type=float, default=config.CAMPAIGN_HOURS, help="Campaign duration in hours")
    parser.add_argument(
        "--interval-minutes",
        type=float,
        default=config.INTERVAL_MINUTES,
        help="Minutes between measurement rounds",
    )
    parser.add_argument("--rounds", type=int, help="Override number of rounds, useful for short tests")
    parser.add_argument(
        "--target",
        action="append",
        dest="targets",
        help="Target label to include. Repeat for multiple labels. Defaults to all targets.",
    )
    parser.add_argument("--notes", help="Notes stored in campaign manifest and measurement JSON")
    parser.add_argument("--dry-run", action="store_true", help="Print campaign plan without collecting data")
    parser.add_argument(
        "--matrix",
        action="store_true",
        help="Prompt through every configured VPN provider and region; defaults to one round per context",
    )
    parser.add_argument("--no-prompt", action="store_true", help="Do not wait for Enter in --matrix mode")
    return parser


def main():
    args = build_parser().parse_args()

    if args.matrix:
        run_matrix(args)
        return

    if not args.vpn_provider or not args.vpn_region:
        raise SystemExit("--vpn-provider and --vpn-region are required unless --matrix is used")
    if args.vpn_provider == config.NO_VPN_PROVIDER and args.vpn_region != "local":
        raise SystemExit("Use --vpn-region local when --vpn-provider no-vpn")
    if args.vpn_provider != config.NO_VPN_PROVIDER and args.vpn_region == "local":
        raise SystemExit("Use a real region when measuring a VPN provider")

    run_campaign(args, args.vpn_provider, args.vpn_region)


if __name__ == "__main__":
    main()
