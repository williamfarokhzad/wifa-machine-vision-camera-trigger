"""Replay decoded part trigger requests against a simulated camera readiness gate."""
import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Request:
    part: str
    time_us: int


@dataclass(frozen=True)
class Result:
    request: Request
    accepted: bool
    ready_before_us: int
    ready_after_us: int


def replay(requests, busy_us):
    """Integer microseconds. Busy interval includes start but excludes end."""
    if type(busy_us) is not int or busy_us < 1:
        raise ValueError("busy time must be a positive integer in microseconds")
    ready, previous = 0, -1
    seen, results = set(), []
    for req in requests:
        if type(req.time_us) is not int or req.time_us < 0 or req.time_us < previous:
            raise ValueError("timestamps must be nonnegative integers in nondecreasing order")
        if not req.part.strip() or req.part in seen:
            raise ValueError("part identifiers must be nonempty and unique")
        seen.add(req.part)
        previous = req.time_us
        before = ready
        accepted = req.time_us >= before
        if accepted:
            ready = req.time_us + busy_us
        results.append(Result(req, accepted, before, ready))
    return results


def load_requests(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as stream:
        rows = csv.reader(stream, strict=True)
        if next(rows, None) != ["part", "time_us"]:
            raise ValueError("CSV header must be part,time_us")
        result = []
        for line, row in enumerate(rows, 2):
            if len(row) != 2:
                raise ValueError(f"expected exactly two columns on row {line}")
            try:
                result.append(Request(row[0].strip(), int(row[1])))
            except ValueError as exc:
                raise ValueError(f"invalid integer time_us on row {line}") from exc
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace", help="CSV with columns part,time_us")
    parser.add_argument("--busy-us", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        results = replay(load_requests(args.trace), args.busy_us)
    except (OSError, ValueError, csv.Error) as exc:
        parser.exit(2, f"error: {exc}\n")
    out = csv.writer(sys.stdout, lineterminator="\n")
    out.writerow(("part", "time_us", "decision", "ready_before_us", "ready_after_us"))
    for event in results:
        out.writerow((event.request.part, event.request.time_us,
                      "accepted" if event.accepted else "missed",
                      event.ready_before_us, event.ready_after_us))
    accepted = sum(item.accepted for item in results)
    print(f"summary: accepted={accepted} missed={len(results)-accepted}", file=sys.stderr)


if __name__ == "__main__":
    main()
