from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from test_helpers import ROOT_DIR, TestFailure, docker_compose, log, main_guard, wait_for_ready


RESULTS_ROOT = ROOT_DIR / "artifacts" / "load_benchmarks"
AGGREGATED_ROW_PATTERN = re.compile(
    r"^\s*Aggregated\s+"
    r"(?P<requests>\d+)\s+"
    r"(?P<failures>\d+)\((?P<failure_pct>[0-9.]+)%\)\s+\|\s+"
    r"(?P<avg>\d+)\s+"
    r"(?P<min>\d+)\s+"
    r"(?P<max>\d+)\s+"
    r"(?P<med>\d+)\s+\|\s+"
    r"(?P<req_s>[0-9.]+)\s+"
    r"(?P<fail_s>[0-9.]+)\s*$"
)


@dataclass(frozen=True)
class BenchmarkCase:
    name: str
    users: int
    spawn_rate: int
    duration: str
    user_class: str
    description: str

    def locust_command(self) -> list[str]:
        return [
            "--profile",
            "loadtest",
            "run",
            "--rm",
            "locust",
            "--headless",
            "-u",
            str(self.users),
            "-r",
            str(self.spawn_rate),
            "-t",
            self.duration,
            "--only-summary",
            "--exit-code-on-error",
            "1",
            self.user_class,
        ]


FULL_SUITE = [
    BenchmarkCase(
        name="warm_search_25u",
        users=25,
        spawn_rate=5,
        duration="45s",
        user_class="WarmSearchUser",
        description="Steady-state warm search baseline",
    ),
    BenchmarkCase(
        name="warm_search_50u",
        users=50,
        spawn_rate=10,
        duration="45s",
        user_class="WarmSearchUser",
        description="Steady-state warm search saturation check",
    ),
    BenchmarkCase(
        name="warm_search_75u",
        users=75,
        spawn_rate=15,
        duration="45s",
        user_class="WarmSearchUser",
        description="Steady-state warm search high-stress run",
    ),
    BenchmarkCase(
        name="search_ingest_80u",
        users=80,
        spawn_rate=15,
        duration="45s",
        user_class="SearchOnlyUser",
        description="Ingestion-heavy search breakpoint check",
    ),
    BenchmarkCase(
        name="auth_20u",
        users=20,
        spawn_rate=5,
        duration="45s",
        user_class="AuthOnlyUser",
        description="Authentication throughput baseline",
    ),
    BenchmarkCase(
        name="auth_50u",
        users=50,
        spawn_rate=10,
        duration="45s",
        user_class="AuthOnlyUser",
        description="Authentication saturation check",
    ),
]

QUICK_SUITE = [
    BenchmarkCase(
        name="warm_search_25u",
        users=25,
        spawn_rate=5,
        duration="30s",
        user_class="WarmSearchUser",
        description="Quick steady-state warm search baseline",
    ),
    BenchmarkCase(
        name="search_ingest_40u",
        users=40,
        spawn_rate=8,
        duration="30s",
        user_class="SearchOnlyUser",
        description="Quick ingestion-heavy search check",
    ),
    BenchmarkCase(
        name="auth_20u",
        users=20,
        spawn_rate=5,
        duration="30s",
        user_class="AuthOnlyUser",
        description="Quick authentication baseline",
    ),
]


def parse_aggregated_metrics(output: str) -> dict[str, int | float]:
    for line in output.splitlines():
        match = AGGREGATED_ROW_PATTERN.match(line)
        if match:
            return {
                "requests": int(match.group("requests")),
                "failures": int(match.group("failures")),
                "failure_pct": float(match.group("failure_pct")),
                "avg_ms": int(match.group("avg")),
                "min_ms": int(match.group("min")),
                "max_ms": int(match.group("max")),
                "median_ms": int(match.group("med")),
                "requests_per_second": float(match.group("req_s")),
                "failures_per_second": float(match.group("fail_s")),
            }
    raise TestFailure("Unable to parse aggregated Locust metrics from benchmark output")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def format_summary(results: list[dict]) -> str:
    lines = [
        "# Load Benchmark Summary",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "| Case | Class | Users | Spawn | Duration | Exit | Requests | Failures | Failure % | Median ms | Avg ms | Max ms | Req/s |",
        "| --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for result in results:
        metrics = result["metrics"]
        lines.append(
            "| "
            f"{result['name']} | "
            f"{result['user_class']} | "
            f"{result['users']} | "
            f"{result['spawn_rate']} | "
            f"{result['duration']} | "
            f"{result['exit_code']} | "
            f"{metrics['requests']} | "
            f"{metrics['failures']} | "
            f"{metrics['failure_pct']:.2f} | "
            f"{metrics['median_ms']} | "
            f"{metrics['avg_ms']} | "
            f"{metrics['max_ms']} | "
            f"{metrics['requests_per_second']:.2f} |"
        )
    return "\n".join(lines) + "\n"


def run_case(case: BenchmarkCase, output_dir: Path) -> dict:
    log(f"INFO: starting benchmark {case.name}")
    wait_for_ready()

    result = docker_compose(case.locust_command(), check=False)
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    combined_output = "\n".join(part for part in (stdout, stderr) if part)
    metrics = parse_aggregated_metrics(combined_output)

    raw_path = output_dir / f"{case.name}.log"
    write_text(
        raw_path,
        (stdout if stdout else "")
        + ("\n\nSTDERR\n" if stdout and stderr else "")
        + (stderr if stderr else "")
        + "\n",
    )

    benchmark_result = {
        "name": case.name,
        "description": case.description,
        "user_class": case.user_class,
        "users": case.users,
        "spawn_rate": case.spawn_rate,
        "duration": case.duration,
        "exit_code": result.returncode,
        "metrics": metrics,
        "raw_log": str(raw_path.relative_to(ROOT_DIR)).replace("\\", "/"),
    }

    if stderr:
        benchmark_result["stderr"] = stderr

    log(
        "INFO: completed "
        f"{case.name} exit={result.returncode} "
        f"failures={metrics['failures']} "
        f"median_ms={metrics['median_ms']} "
        f"req_s={metrics['requests_per_second']:.2f}"
    )
    return benchmark_result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run repeatable Locust load benchmark sweeps and save timestamped results."
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run a shorter subset of the benchmark suite for validation.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    suite = QUICK_SUITE if args.quick else FULL_SUITE

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = RESULTS_ROOT / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for case in suite:
        results.append(run_case(case, output_dir))

    summary_path = output_dir / "summary.json"
    summary_md_path = output_dir / "summary.md"
    write_text(summary_path, json.dumps(results, indent=2) + "\n")
    write_text(summary_md_path, format_summary(results))

    latest_path = RESULTS_ROOT / "latest.json"
    write_text(latest_path, json.dumps(results, indent=2) + "\n")

    log(f"INFO: benchmark results written to {output_dir}")
    log(f"INFO: markdown summary written to {summary_md_path}")


if __name__ == "__main__":
    main_guard(main)
