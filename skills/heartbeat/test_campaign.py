"""
AC verification tests for `/servo:heartbeat`'s campaign CLI (`campaign.py`),
spec slice 042-01 (plan and ledger).

Run from the repo root:
    python3 -m pytest skills/heartbeat/test_campaign.py -q
or directly:
    python3 skills/heartbeat/test_campaign.py

Slice 042-01 acceptance criteria:
    AC1 (init validates + writes plan.json/ledger.jsonl, fail-closed) →
        InitWritesContractTests + InitFailClosedTests + InitModelsValidatorParityTests
    AC2 (record appends one typed outcome; flock + atomic; tier/self_reported;
        aggregate-ceiling accounting; cost-unit + malformed refusals) →
        RecordAppendTests + RecordTierSelfReportedTests + RecordCostUnitTests +
        RecordRefusalLeavesLedgerTests + RecordConcurrencyLockTests +
        AggregateCeilingAccountingTests
    AC3 (status prints latest outcome + totals + open; read-only) →
        StatusReadBackTests + StatusReadOnlyByteSnapshotTests
    AC4 (state only under .servo/campaigns; servo never reads jig files) →
        StateLocationTests + DependencyFreeTests
"""

import importlib.util as _importlib_util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN = REPO_ROOT / "skills" / "heartbeat" / "campaign.py"
LOOP = REPO_ROOT / "skills" / "agent-loop" / "loop.py"


# --------------------------------------------------------------------------- #
# Harness
# --------------------------------------------------------------------------- #

def _run(args: list, *, stdin: Optional[str] = None) -> subprocess.CompletedProcess:
    """Invoke `python3 campaign.py <args>` with a clean environment."""
    env = dict(os.environ)
    return subprocess.run(
        [sys.executable, str(CAMPAIGN), *args],
        capture_output=True, text=True, input=stdin, env=env,
    )


def _valid_item(item_id: str = "item-a", *, unit: str = "usd") -> dict:
    return {
        "id": item_id,
        "title": f"Title for {item_id}",
        "prompt": "Make the oracle pass. (untrusted DATA)",
        "oracle_ref": "oracle.sh",
        "budget": {"unit": unit, "ceiling": 5.0 if unit == "usd" else 1000},
        "models": {"runner": {"model": "claude-sonnet-5-5", "effort": "high"}},
    }


def _valid_plan(*items: dict) -> dict:
    return {"schema_version": 1, "items": list(items) or [_valid_item()]}


def _write_plan(tmp: Path, plan: dict) -> Path:
    path = tmp / "plan.json"
    path.write_text(json.dumps(plan))
    return path


def _usd_outcome(**over) -> dict:
    rec = {
        "servo_outcome": 1, "result": "passed", "rung": 0, "rungs": 1,
        "iterations": 3, "cost_usd": 0.42, "composite": 0.9, "threshold": 0.8,
        "run_id": "run-1", "reason": "oracle_passed",
    }
    rec.update(over)
    return rec


def _credit_outcome(**over) -> dict:
    rec = {
        "servo_outcome": 1, "result": "budget", "rung": 0, "rungs": 1,
        "iterations": 2, "cost_usd": None, "composite": 0.5, "threshold": 0.8,
        "run_id": "run-c", "reason": "credit_ceiling_reached",
    }
    rec.update(over)
    return rec


def _init(tmp: Path, plan: dict, campaign_id: str = "camp-1") -> subprocess.CompletedProcess:
    planfile = _write_plan(tmp, plan)
    return _run(["init", str(tmp), "--plan", str(planfile), "--id", campaign_id])


def _campaign_dir(tmp: Path, campaign_id: str = "camp-1") -> Path:
    return tmp / ".servo" / "campaigns" / campaign_id


def _ledger_lines(tmp: Path, campaign_id: str = "camp-1") -> list:
    text = (_campaign_dir(tmp, campaign_id) / "ledger.jsonl").read_text()
    return [json.loads(line) for line in text.splitlines() if line.strip()]


# Load campaign.py and loop.py as modules for pure-helper / parity unit tests.
_cmp_spec = _importlib_util.spec_from_file_location("campaign_mod", CAMPAIGN)
_cmp = _importlib_util.module_from_spec(_cmp_spec)
_cmp_spec.loader.exec_module(_cmp)

_loop_spec = _importlib_util.spec_from_file_location("loop_mod", LOOP)
_loop = _importlib_util.module_from_spec(_loop_spec)
_loop_spec.loader.exec_module(_loop)


# --------------------------------------------------------------------------- #
# AC1 — init
# --------------------------------------------------------------------------- #

class InitWritesContractTests(unittest.TestCase):
    def test_valid_init_writes_plan_and_empty_ledger(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            res = _init(tmp, _valid_plan(_valid_item("item-a"), _valid_item("item-b")))
            self.assertEqual(res.returncode, 0, res.stderr)
            cdir = _campaign_dir(tmp)
            self.assertTrue((cdir / "plan.json").is_file())
            self.assertTrue((cdir / "ledger.jsonl").is_file())
            # ledger starts empty.
            self.assertEqual((cdir / "ledger.jsonl").read_text(), "")
            # plan round-trips the items.
            stored = json.loads((cdir / "plan.json").read_text())
            self.assertEqual(stored["schema_version"], 1)
            self.assertEqual([i["id"] for i in stored["items"]], ["item-a", "item-b"])

    def test_init_prints_campaign_id(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            res = _init(tmp, _valid_plan(), "my-campaign")
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("my-campaign", res.stdout)

    def test_generated_id_when_omitted(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            planfile = _write_plan(tmp, _valid_plan())
            res = _run(["init", str(tmp), "--plan", str(planfile)])
            self.assertEqual(res.returncode, 0, res.stderr)
            campaigns = tmp / ".servo" / "campaigns"
            created = [p.name for p in campaigns.iterdir()]
            self.assertEqual(len(created), 1)
            # the generated id matches the item-id regex family.
            self.assertRegex(created[0], r"^[a-z0-9][a-z0-9-]*$")

    def test_credit_denominated_budget_is_valid(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            res = _init(tmp, _valid_plan(_valid_item("c", unit="credit")))
            self.assertEqual(res.returncode, 0, res.stderr)


class InitFailClosedTests(unittest.TestCase):
    """Every rejection: rc=2, a single reason on stderr, and NOTHING written."""

    def _reject(self, plan: dict, *, needle: Optional[str] = None):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            res = _init(tmp, plan, "camp-x")
            self.assertEqual(res.returncode, 2, f"expected rc=2; stdout={res.stdout}")
            # No partial campaign directory left behind.
            self.assertFalse(
                _campaign_dir(tmp, "camp-x").exists(),
                "fail-closed init must write nothing (no partial files)",
            )
            if needle is not None:
                self.assertIn(needle, res.stderr)
            return res

    def test_unknown_top_level_key(self):
        plan = _valid_plan()
        plan["extra"] = True
        self._reject(plan)

    def test_schema_version_not_one(self):
        plan = _valid_plan()
        plan["schema_version"] = 2
        self._reject(plan)

    def test_missing_schema_version(self):
        plan = {"items": [_valid_item()]}
        self._reject(plan)

    def test_empty_items(self):
        self._reject({"schema_version": 1, "items": []})

    def test_items_not_a_list(self):
        self._reject({"schema_version": 1, "items": {"id": "a"}})

    def test_duplicate_item_id(self):
        self._reject(_valid_plan(_valid_item("dup"), _valid_item("dup")))

    def test_bad_item_id_regex(self):
        self._reject(_valid_plan(_valid_item("Bad_ID")))

    def test_item_id_leading_hyphen(self):
        self._reject(_valid_plan(_valid_item("-x")))

    def test_missing_required_item_field(self):
        for field in ("id", "title", "prompt", "oracle_ref", "budget", "models"):
            item = _valid_item()
            del item[field]
            with self.subTest(field=field):
                self._reject({"schema_version": 1, "items": [item]})

    def test_unknown_item_key(self):
        item = _valid_item()
        item["surprise"] = 1
        self._reject({"schema_version": 1, "items": [item]})

    def test_empty_oracle_ref(self):
        item = _valid_item()
        item["oracle_ref"] = ""
        self._reject({"schema_version": 1, "items": [item]})

    def test_budget_missing_unit(self):
        item = _valid_item()
        item["budget"] = {"ceiling": 5.0}
        self._reject({"schema_version": 1, "items": [item]})

    def test_budget_missing_ceiling(self):
        item = _valid_item()
        item["budget"] = {"unit": "usd"}
        self._reject({"schema_version": 1, "items": [item]})

    def test_budget_bad_unit(self):
        item = _valid_item()
        item["budget"] = {"unit": "euros", "ceiling": 5.0}
        self._reject({"schema_version": 1, "items": [item]})

    def test_budget_nonpositive_ceiling(self):
        for bad in (0, -1, -0.5):
            item = _valid_item()
            item["budget"] = {"unit": "usd", "ceiling": bad}
            with self.subTest(ceiling=bad):
                self._reject({"schema_version": 1, "items": [item]})

    def test_budget_unknown_key(self):
        item = _valid_item()
        item["budget"] = {"unit": "usd", "ceiling": 5.0, "extra": 1}
        self._reject({"schema_version": 1, "items": [item]})

    def test_models_invalid(self):
        item = _valid_item()
        item["models"] = {"runner": {"bogus": "x"}}
        self._reject({"schema_version": 1, "items": [item]})

    def test_plan_not_an_object(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            planfile = tmp / "plan.json"
            planfile.write_text("[1, 2, 3]")
            res = _run(["init", str(tmp), "--plan", str(planfile), "--id", "camp-x"])
            self.assertEqual(res.returncode, 2)
            self.assertFalse(_campaign_dir(tmp, "camp-x").exists())

    def test_plan_malformed_json(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            planfile = tmp / "plan.json"
            planfile.write_text("{not json")
            res = _run(["init", str(tmp), "--plan", str(planfile), "--id", "camp-x"])
            self.assertEqual(res.returncode, 2)
            self.assertFalse(_campaign_dir(tmp, "camp-x").exists())

    def test_plan_file_missing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            res = _run(["init", str(tmp), "--plan", str(tmp / "nope.json"), "--id", "camp-x"])
            self.assertEqual(res.returncode, 2)
            self.assertFalse(_campaign_dir(tmp, "camp-x").exists())

    def test_existing_id_dir_refused_no_clobber(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self.assertEqual(_init(tmp, _valid_plan(), "camp-x").returncode, 0)
            # Record something so the dir has state, then re-init onto it.
            marker = _campaign_dir(tmp, "camp-x") / "ledger.jsonl"
            marker.write_text('{"sentinel": true}\n')
            res = _init(tmp, _valid_plan(), "camp-x")
            self.assertEqual(res.returncode, 2)
            # Existing state is NOT clobbered.
            self.assertIn("sentinel", marker.read_text())

    def test_target_missing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            planfile = _write_plan(tmp, _valid_plan())
            res = _run(["init", str(tmp / "no-such-target"), "--plan", str(planfile),
                        "--id", "camp-x"])
            self.assertEqual(res.returncode, 2)


class InitModelsValidatorParityTests(unittest.TestCase):
    """AC1: the models block is validated with loop.py's 038 validator, and
    rejected with the SAME message."""

    def test_campaign_validator_behaves_like_loop_validator(self):
        # campaign.py loads loop.py's validator dynamically; prove behavioral
        # parity (same normalized output AND same error) over representative
        # blocks — "the same validator, rejected with the same messages" (AC1).
        campaign_validate = _cmp._load_models_validator()
        blocks = [
            {"runner": {"model": "claude-sonnet-5-5", "effort": "high"}},
            {"runner": {}, "judge": {}, "mystery": 1},
            {"runner": {"effort": "turbo"}},
            {"runner": {"model": "x"}, "escalation": [{"effort": "high"}]},
            {"runner": {"model": "x"}, "escalation": [{}]},
            "not-an-object",
        ]
        for block in blocks:
            with self.subTest(block=block):
                self.assertEqual(
                    campaign_validate(block, allow_escalation=True),
                    _loop._validate_models(block, allow_escalation=True),
                )

    def test_same_message_for_unknown_models_key(self):
        bad = {"runner": {}, "judge": {}, "mystery": 1}
        _, loop_err = _loop._validate_models(bad, allow_escalation=True)
        self.assertIsNotNone(loop_err)
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            item = _valid_item()
            item["models"] = bad
            res = _init(tmp, {"schema_version": 1, "items": [item]}, "camp-x")
            self.assertEqual(res.returncode, 2)
            self.assertIn(loop_err, res.stderr)

    def test_escalation_ladder_allowed(self):
        # allow_escalation=True — a ladder is a valid 038-03 models block.
        item = _valid_item()
        item["models"] = {
            "runner": {"model": "claude-sonnet-5-5"},
            "escalation": [{"effort": "high"}, {"model": "claude-opus-4-8"}],
        }
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            res = _init(tmp, {"schema_version": 1, "items": [item]}, "camp-x")
            self.assertEqual(res.returncode, 0, res.stderr)

    def test_outcome_constants_track_loop(self):
        # The 040 outcome schema version + result set are mirrored from loop.py
        # (not dynamically loaded on the hot record path); this guard fails if
        # loop.py's 040 contract drifts from campaign.py's copy.
        self.assertEqual(_cmp.OUTCOME_SCHEMA_VERSION, _loop.OUTCOME_SCHEMA_VERSION)
        self.assertEqual(set(_cmp.OUTCOME_RESULTS), {
            _loop.OUTCOME_RESULT_PASSED, _loop.OUTCOME_RESULT_PLATEAU,
            _loop.OUTCOME_RESULT_BUDGET, _loop.OUTCOME_RESULT_BLOCKED,
            _loop.OUTCOME_RESULT_ERROR,
        })


# --------------------------------------------------------------------------- #
# AC2 — record
# --------------------------------------------------------------------------- #

class RecordAppendTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.assertEqual(
            _init(self.tmp, _valid_plan(_valid_item("item-a"), _valid_item("item-b"))).returncode,
            0,
        )

    def tearDown(self):
        self._td.cleanup()

    def _record(self, item, outcome, *, tier=None):
        args = ["record", "camp-1", item, "--outcome", json.dumps(outcome),
                "--target", str(self.tmp)]
        if tier is not None:
            args += ["--tier", tier]
        return _run(args)

    def test_append_one_typed_outcome(self):
        res = self._record("item-a", _usd_outcome())
        self.assertEqual(res.returncode, 0, res.stderr)
        entries = _ledger_lines(self.tmp)
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["item"], "item-a")
        self.assertEqual(e["tier"], "servo")
        self.assertFalse(e["self_reported"])
        self.assertIn("recorded_at", e)
        self.assertEqual(e["outcome"]["result"], "passed")
        self.assertEqual(e["outcome"]["cost_usd"], 0.42)
        self.assertEqual(e["outcome"]["reason"], "oracle_passed")

    def test_appends_accumulate(self):
        self.assertEqual(self._record("item-a", _usd_outcome()).returncode, 0)
        self.assertEqual(self._record("item-a", _usd_outcome(result="plateau",
                         reason="oracle_plateau")).returncode, 0)
        self.assertEqual(self._record("item-b", _usd_outcome()).returncode, 0)
        self.assertEqual(len(_ledger_lines(self.tmp)), 3)

    def test_ledger_is_jsonl_one_object_per_line(self):
        self._record("item-a", _usd_outcome())
        self._record("item-b", _usd_outcome())
        raw = (_campaign_dir(self.tmp) / "ledger.jsonl").read_text()
        lines = raw.splitlines()
        self.assertEqual(len(lines), 2)
        for line in lines:
            json.loads(line)  # each line parses on its own


class RecordTierSelfReportedTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        _init(self.tmp, _valid_plan(_valid_item("item-a")))

    def tearDown(self):
        self._td.cleanup()

    def _record(self, tier, outcome=None):
        return _run(["record", "camp-1", "item-a", "--outcome",
                     json.dumps(outcome or _usd_outcome()), "--tier", tier,
                     "--target", str(self.tmp)])

    def test_servo_not_self_reported(self):
        self.assertEqual(self._record("servo").returncode, 0)
        self.assertFalse(_ledger_lines(self.tmp)[-1]["self_reported"])

    def test_wrapped_tier_not_accepted_by_cli(self):
        # wrapped is "verified, not declared" (ADR-0049): 042-01's CLI does not
        # accept it (it is earned by 042-04's verifier). The ledger schema +
        # accounting still handle wrapped — see AggregateCeilingAccountingTests.
        self.assertNotEqual(self._record("wrapped").returncode, 0)

    def test_advisory_is_self_reported(self):
        self.assertEqual(self._record("advisory").returncode, 0)
        entry = _ledger_lines(self.tmp)[-1]
        self.assertEqual(entry["tier"], "advisory")
        self.assertTrue(entry["self_reported"])

    def test_unknown_tier_refused(self):
        res = self._record("gremlin")
        self.assertNotEqual(res.returncode, 0)


class RecordCostUnitTests(unittest.TestCase):
    """AC2: a cost in the wrong unit is refused rc=2, ledger unchanged."""

    def setUp(self):
        import tempfile
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        _init(self.tmp, _valid_plan(
            _valid_item("usd-item", unit="usd"),
            _valid_item("credit-item", unit="credit"),
        ))

    def tearDown(self):
        self._td.cleanup()

    def _record(self, item, outcome):
        return _run(["record", "camp-1", item, "--outcome", json.dumps(outcome),
                     "--target", str(self.tmp)])

    def test_usd_item_accepts_numeric_cost(self):
        self.assertEqual(self._record("usd-item", _usd_outcome(cost_usd=0.0)).returncode, 0)
        self.assertEqual(self._record("usd-item", _usd_outcome(cost_usd=1.5)).returncode, 0)

    def test_usd_item_rejects_null_cost(self):
        res = self._record("usd-item", _credit_outcome())
        self.assertEqual(res.returncode, 2)
        self.assertEqual(_ledger_lines(self.tmp), [])

    def test_credit_item_accepts_null_cost(self):
        self.assertEqual(self._record("credit-item", _credit_outcome()).returncode, 0)

    def test_credit_item_rejects_positive_usd_cost(self):
        res = self._record("credit-item", _usd_outcome())  # cost_usd 0.42 > 0
        self.assertEqual(res.returncode, 2)
        self.assertEqual(_ledger_lines(self.tmp), [])

    def test_credit_item_accepts_zero_cost_refusal(self):
        # A credit/Copilot run that halts at a refusal/preflight helper emits
        # cost_usd: 0.0 (loop.py hardcodes 0.0 there regardless of host). That is
        # a REAL outcome the ledger must keep — not a wrong-unit drop.
        refusal = {
            "servo_outcome": 1, "result": "error", "rung": 0, "rungs": 1,
            "iterations": 0, "cost_usd": 0.0, "composite": None,
            "threshold": None, "run_id": "run-x",
            "reason": "unpriced_oracle_components",
        }
        self.assertEqual(self._record("credit-item", refusal).returncode, 0)
        self.assertEqual(_ledger_lines(self.tmp)[-1]["outcome"]["reason"],
                         "unpriced_oracle_components")


class RecordRefusalLeavesLedgerTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        _init(self.tmp, _valid_plan(_valid_item("item-a")))
        # Seed one good entry; every refusal below must leave it untouched.
        _run(["record", "camp-1", "item-a", "--outcome", json.dumps(_usd_outcome()),
              "--target", str(self.tmp)])
        self.before = (_campaign_dir(self.tmp) / "ledger.jsonl").read_text()

    def tearDown(self):
        self._td.cleanup()

    def _unchanged(self, res):
        self.assertEqual(res.returncode, 2)
        self.assertEqual((_campaign_dir(self.tmp) / "ledger.jsonl").read_text(), self.before)

    def test_unknown_item_id(self):
        self._unchanged(_run(["record", "camp-1", "ghost", "--outcome",
                              json.dumps(_usd_outcome()), "--target", str(self.tmp)]))

    def test_malformed_outcome_not_json(self):
        self._unchanged(_run(["record", "camp-1", "item-a", "--outcome", "{nope",
                              "--target", str(self.tmp)]))

    def test_malformed_outcome_not_object(self):
        self._unchanged(_run(["record", "camp-1", "item-a", "--outcome", "[1,2]",
                              "--target", str(self.tmp)]))

    def test_malformed_outcome_wrong_schema_version(self):
        self._unchanged(_run(["record", "camp-1", "item-a", "--outcome",
                              json.dumps(_usd_outcome(servo_outcome=2)),
                              "--target", str(self.tmp)]))

    def test_malformed_outcome_bad_result(self):
        self._unchanged(_run(["record", "camp-1", "item-a", "--outcome",
                              json.dumps(_usd_outcome(result="banana")),
                              "--target", str(self.tmp)]))

    def test_malformed_outcome_negative_cost(self):
        # A negative cost_usd is impossible input (a cost is a cumulative spend);
        # refuse it so it can't subtract from enforced spend.
        self._unchanged(_run(["record", "camp-1", "item-a", "--outcome",
                              json.dumps(_usd_outcome(cost_usd=-1.0)),
                              "--target", str(self.tmp)]))

    def test_missing_campaign(self):
        res = _run(["record", "no-camp", "item-a", "--outcome", json.dumps(_usd_outcome()),
                    "--target", str(self.tmp)])
        self.assertEqual(res.returncode, 2)


class RecordConcurrencyLockTests(unittest.TestCase):
    """AC2: the flock-guarded, atomic append loses no record under contention."""

    def test_concurrent_records_all_land(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            _init(tmp, _valid_plan(_valid_item("item-a")))
            n = 10
            procs = []
            for i in range(n):
                outcome = _usd_outcome(run_id=f"run-{i}", cost_usd=float(i))
                procs.append(subprocess.Popen(
                    [sys.executable, str(CAMPAIGN), "record", "camp-1", "item-a",
                     "--outcome", json.dumps(outcome), "--target", str(tmp)],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                ))
            rcs = [p.wait() for p in procs]
            self.assertTrue(all(rc == 0 for rc in rcs), rcs)
            entries = _ledger_lines(tmp)
            self.assertEqual(len(entries), n)
            run_ids = {e["outcome"]["run_id"] for e in entries}
            self.assertEqual(run_ids, {f"run-{i}" for i in range(n)})


class AggregateCeilingAccountingTests(unittest.TestCase):
    """AC2: the aggregate ceiling counts cost only from servo + wrapped; a
    self_reported (advisory) cost is never counted as enforced spend."""

    def test_enforced_cost_excludes_self_reported(self):
        entries = [
            _cmp._ledger_entry("a", "servo", _usd_outcome(cost_usd=1.00), "t"),
            _cmp._ledger_entry("b", "wrapped", _usd_outcome(cost_usd=2.00), "t"),
            _cmp._ledger_entry("c", "advisory", _usd_outcome(cost_usd=4.00), "t"),
        ]
        plan = _valid_plan(_valid_item("a"), _valid_item("b"), _valid_item("c"))
        summary = _cmp._status_summary(plan, entries)
        self.assertAlmostEqual(summary["totals"]["enforced_cost_usd"], 3.00)
        self.assertAlmostEqual(summary["totals"]["self_reported_cost_usd"], 4.00)

    def test_credit_null_cost_not_counted(self):
        entries = [
            _cmp._ledger_entry("a", "servo", _usd_outcome(cost_usd=1.50), "t"),
            _cmp._ledger_entry("c", "servo", _credit_outcome(), "t"),
        ]
        plan = _valid_plan(_valid_item("a"), _valid_item("c", unit="credit"))
        summary = _cmp._status_summary(plan, entries)
        self.assertAlmostEqual(summary["totals"]["enforced_cost_usd"], 1.50)

    def test_cost_unit_helper_matches_spec(self):
        # usd: null (credit/Copilot) rejected; any number incl. 0.0 accepted.
        self.assertIsNone(_cmp._cost_unit_error("usd", 0.0))
        self.assertIsNone(_cmp._cost_unit_error("usd", 5.0))
        self.assertIsNotNone(_cmp._cost_unit_error("usd", None))
        # credit: positive USD spend rejected; null (Copilot) and 0.0 (Copilot
        # refusal / no-spend) both accepted — neither drops a real outcome.
        self.assertIsNone(_cmp._cost_unit_error("credit", None))
        self.assertIsNone(_cmp._cost_unit_error("credit", 0.0))
        self.assertIsNotNone(_cmp._cost_unit_error("credit", 0.01))
        self.assertIsNotNone(_cmp._cost_unit_error("credit", 1.0))

    def test_wrapped_in_schema_not_in_cli(self):
        # wrapped is a valid LEDGER tier (schema + accounting handle it, ready
        # for 042-04) but the 042-01 CLI will not record it.
        self.assertIn("wrapped", _cmp.TIERS)
        self.assertNotIn("wrapped", _cmp.CLI_TIERS)
        entry = _cmp._ledger_entry("x", "wrapped", _usd_outcome(), "t")
        self.assertFalse(entry["self_reported"])


# --------------------------------------------------------------------------- #
# AC3 — status
# --------------------------------------------------------------------------- #

class StatusReadBackTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        _init(self.tmp, _valid_plan(
            _valid_item("item-a"), _valid_item("item-b"), _valid_item("item-c")))
        # item-a passed, item-b plateau, item-c never recorded (open).
        _run(["record", "camp-1", "item-a", "--outcome", json.dumps(_usd_outcome(cost_usd=1.0)),
              "--target", str(self.tmp)])
        _run(["record", "camp-1", "item-b", "--outcome",
              json.dumps(_usd_outcome(result="plateau", reason="oracle_plateau", cost_usd=2.0)),
              "--target", str(self.tmp)])

    def tearDown(self):
        self._td.cleanup()

    def test_status_json_shape(self):
        res = _run(["status", "camp-1", "--json", "--target", str(self.tmp)])
        self.assertEqual(res.returncode, 0, res.stderr)
        summary = json.loads(res.stdout)
        self.assertEqual(summary["schema_version"], 1)
        totals = summary["totals"]
        self.assertAlmostEqual(totals["enforced_cost_usd"], 3.0)
        self.assertEqual(totals["passed"], 1)
        self.assertEqual(totals["plateau"], 1)
        self.assertEqual(set(summary["open_items"]), {"item-b", "item-c"})

    def test_status_latest_outcome_wins(self):
        # Re-record item-a as blocked; latest should win.
        _run(["record", "camp-1", "item-a", "--outcome",
              json.dumps(_usd_outcome(result="blocked", reason="dirty_tree", cost_usd=0.1)),
              "--target", str(self.tmp)])
        summary = json.loads(
            _run(["status", "camp-1", "--json", "--target", str(self.tmp)]).stdout)
        by_id = {i["id"]: i for i in summary["items"]}
        self.assertEqual(by_id["item-a"]["latest_result"], "blocked")
        self.assertEqual(summary["totals"]["blocked"], 1)
        self.assertEqual(summary["totals"]["passed"], 0)

    def test_status_human_mentions_items_and_totals(self):
        res = _run(["status", "camp-1", "--target", str(self.tmp)])
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("item-a", res.stdout)
        self.assertIn("item-c", res.stdout)  # the open item is shown

    def test_status_missing_campaign_rc2(self):
        res = _run(["status", "ghost", "--target", str(self.tmp)])
        self.assertEqual(res.returncode, 2)

    def test_status_malformed_ledger_line_fails_closed(self):
        # A corrupt/tampered ledger line → read-only status fails closed rc=2
        # with a single reason, not an unhandled traceback.
        ledger = _campaign_dir(self.tmp) / "ledger.jsonl"
        ledger.write_text(ledger.read_text() + "{not json\n")
        res = _run(["status", "camp-1", "--json", "--target", str(self.tmp)])
        self.assertEqual(res.returncode, 2)
        self.assertIn("malformed", res.stderr)

    def test_status_marks_credit_items(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            _init(tmp, _valid_plan(_valid_item("c", unit="credit")))
            summary = json.loads(
                _run(["status", "camp-1", "--json", "--target", str(tmp)]).stdout)
            self.assertEqual(summary["totals"]["credit_items"], 1)
            human = _run(["status", "camp-1", "--target", str(tmp)]).stdout
            self.assertIn("credit", human.lower())


class StatusReadOnlyByteSnapshotTests(unittest.TestCase):
    def test_status_writes_nothing(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            _init(tmp, _valid_plan(_valid_item("item-a")))
            _run(["record", "camp-1", "item-a", "--outcome", json.dumps(_usd_outcome()),
                  "--target", str(tmp)])
            cdir = _campaign_dir(tmp)
            before = {p: p.read_bytes() for p in cdir.rglob("*") if p.is_file()}
            for _ in range(2):
                self.assertEqual(
                    _run(["status", "camp-1", "--json", "--target", str(tmp)]).returncode, 0)
                self.assertEqual(_run(["status", "camp-1", "--target", str(tmp)]).returncode, 0)
            after = {p: p.read_bytes() for p in cdir.rglob("*") if p.is_file()}
            self.assertEqual(before, after)


# --------------------------------------------------------------------------- #
# AC4 — state location / dependency-free
# --------------------------------------------------------------------------- #

class StateLocationTests(unittest.TestCase):
    def test_all_state_under_servo_campaigns(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            _init(tmp, _valid_plan(_valid_item("item-a")))
            _run(["record", "camp-1", "item-a", "--outcome", json.dumps(_usd_outcome()),
                  "--target", str(tmp)])
            _run(["status", "camp-1", "--target", str(tmp)])
            written = [p for p in tmp.rglob("*") if p.is_file()]
            servo_root = tmp / ".servo" / "campaigns"
            for p in written:
                self.assertTrue(
                    str(p).startswith(str(servo_root)) or p.name == "plan.json"
                    and p.parent == tmp,
                    f"unexpected write outside .servo/campaigns: {p}",
                )
            # The campaign's own state is all under .servo/campaigns/camp-1/.
            self.assertTrue((servo_root / "camp-1" / "plan.json").is_file())
            self.assertTrue((servo_root / "camp-1" / "ledger.jsonl").is_file())


class DependencyFreeTests(unittest.TestCase):
    """AC4 + the skill invariant: campaign.py never statically imports a sibling
    skill module, and never references jig files. Scans CODE (via `ast`), not
    docstring prose, so the module may still explain the boundary in words."""

    def _tree(self):
        import ast
        return ast.parse(CAMPAIGN.read_text())

    def _docstring_node_ids(self, tree):
        import ast
        ids = set()
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if not isinstance(body, list) or not body:
                continue
            first = body[0]
            if (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)
                    and isinstance(first.value.value, str)):
                ids.add(id(first.value))
        return ids

    def test_no_static_cross_skill_import(self):
        import ast
        forbidden = {"loop", "heartbeat", "gate", "gate_consumer"}
        for node in ast.walk(self._tree()):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(alias.name.split(".")[0], forbidden,
                                     f"must not statically import {alias.name!r}")
            elif isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                self.assertNotIn(root, forbidden,
                                 f"must not statically import from {node.module!r}")

    def test_no_jig_path_literals(self):
        import ast
        tree = self._tree()
        skip = self._docstring_node_ids(tree)
        offending = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and id(node) not in skip):
                low = node.value.lower()
                if any(tok in low for tok in ("jig", "docs/specs", "docs/decisions",
                                              "reframe")):
                    offending.append(node.value)
        self.assertEqual(offending, [], f"jig/spec refs in code strings: {offending}")

    def test_models_validator_loaded_dynamically_not_imported(self):
        # Positive: the 038 validator is reached via importlib, not a static import.
        src = CAMPAIGN.read_text()
        self.assertIn("spec_from_file_location", src)
        self.assertIn("agent-loop", src)


if __name__ == "__main__":
    unittest.main()
