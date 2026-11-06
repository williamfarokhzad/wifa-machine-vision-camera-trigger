import random
import subprocess
import sys
import unittest

from trigger_replay import Request, load_requests, replay


class ReplayTests(unittest.TestCase):
    def test_spaced(self):
        self.assertEqual([True, True, True], [x.accepted for x in replay(
            load_requests("examples/spaced.csv"), 10000)])

    def test_drop_is_not_queued_and_does_not_extend_busy(self):
        events = replay(load_requests("examples/busy.csv"), 15000)
        self.assertEqual([True, False, True], [x.accepted for x in events])
        self.assertEqual([15000, 15000, 30000], [x.ready_after_us for x in events])

    def test_half_open_boundary_and_tie_order(self):
        events = replay(load_requests("examples/boundary.csv"), 12000)
        self.assertEqual(["P1", "P4"], [x.request.part for x in events if x.accepted])
        self.assertEqual(12000, events[-1].ready_before_us)

    def test_translation_invariance(self):
        original = load_requests("examples/busy.csv")
        shifted = [Request(r.part, r.time_us + 170_005) for r in original]
        self.assertEqual([x.accepted for x in replay(original, 15000)],
                         [x.accepted for x in replay(shifted, 15000)])

    def test_no_phantom_frames_and_independent_tick_oracle(self):
        rng = random.Random(399)
        for _ in range(120):
            times = sorted(rng.randrange(70) for _ in range(30))
            span = rng.randrange(1, 12)
            requests = [Request(f"P{i}", t) for i, t in enumerate(times)]
            blocked_ticks = set()
            expected = []
            for request in requests:
                if request.time_us not in blocked_ticks:
                    expected.append(request.part)
                    blocked_ticks.update(range(request.time_us, request.time_us + span))
            self.assertEqual(expected, [x.request.part for x in replay(requests, span) if x.accepted])

    def test_rejects_invalid_duration_and_traces(self):
        for bad in (0, -1, 2.5, True):
            with self.subTest(duration=bad), self.assertRaises(ValueError):
                replay([], bad)
        for rows in ([Request("P1", -1)], [Request("P1", 0.5)],
                     [Request(" ", 0)], [Request("P1", 0), Request("P1", 5)],
                     load_requests("examples/out-of-order.csv")):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                replay(rows, 5)

    def test_cli_rejects_out_of_order_without_partial_data(self):
        result = subprocess.run(
            [sys.executable, "trigger_replay.py", "examples/out-of-order.csv", "--busy-us", "15000"],
            capture_output=True, text=True)
        self.assertEqual(2, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertIn("nondecreasing", result.stderr)

    def test_cli_exact_output(self):
        result = subprocess.run(
            [sys.executable, "trigger_replay.py", "examples/busy.csv", "--busy-us", "15000"],
            capture_output=True, text=True, check=True)
        self.assertEqual(
            "part,time_us,decision,ready_before_us,ready_after_us\n"
            "P1,0,accepted,0,15000\nP2,12000,missed,15000,15000\n"
            "P3,15000,accepted,15000,30000\n", result.stdout)
        self.assertEqual("summary: accepted=2 missed=1\n", result.stderr)


if __name__ == "__main__":
    unittest.main()
