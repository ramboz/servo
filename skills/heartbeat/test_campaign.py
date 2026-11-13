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
        # A non-`passed` advisory claim needs no oracle re-check (042-03 re-checks
        # only claimed passes), so this still exercises the 042-01 tier →
        # self_reported mapping without a `--worktree`. (An advisory `passed`
        # now requires the re-check — see RecordAdvisoryRecheck* in 042-03.)
        self.assertEqual(
            self._record("advisory", _usd_outcome(
                result="plateau", reason="oracle_plateau")).returncode, 0)
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


# =========================================================================== #
# Slice 042-02 — servo-driven serial dispatch (`campaign next`)
#
# Dispatch is exercised against a REAL git repo (a fresh `git init` target with a
# committed oracle.sh, so `git worktree add` runs the real nested-worktree path),
# with `loop.py` replaced by a deterministic stand-in injected as the subprocess
# RUNNER via `SERVO_CAMPAIGN_RUNNER_PY` (distinct from `SERVO_CAMPAIGN_LOOP_PY`,
# which overrides the in-process loop-module import for the validator + the 040
# outcome renderer — left on the real loop.py here). The stub writes the run's
# `state.json` and the
# `--outcome-line` record and prints a terminal summary — so the dispatch
# contract (worktree provisioned, loop launched with the item's budget/models,
# the loop's own typed line recorded, cost sourced from state.json) is exercised
# end to end with no live `claude -p` call. Known heartbeat-dispatch gotcha: a
# `git log` mock is NOT enough — worktree creation needs a real repo.
# =========================================================================== #

import tempfile as _tempfile  # noqa: E402  (module-level, after the 042-01 body)

_DISPATCH_ORACLE = (
    "#!/usr/bin/env bash\n"
    'echo "oracle: composite=1.0 threshold=0.5"\n'
    "exit 0\n"
)


def _git_cmd(target: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(target), *args],
                          capture_output=True, text=True)


def _dispatch_repo(target: Path) -> Path:
    """A real git repo target with a committed oracle + untracked `.servo/` manifest.

    `.servo/` is git-ignored (as in a real scaffolded install), so the worktree
    checkout does not inherit the manifest and `_provision_oracle` has real work
    to do.
    """
    target.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", str(target)], capture_output=True, text=True)
    _git_cmd(target, "config", "user.email", "test@servo.test")
    _git_cmd(target, "config", "user.name", "servo test")
    _git_cmd(target, "config", "commit.gpgsign", "false")
    (target / ".gitignore").write_text(".servo/\n")
    (target / "src.py").write_text("print('hello')\n")
    oracle = target / "oracle.sh"
    oracle.write_text(_DISPATCH_ORACLE)
    mode = oracle.stat().st_mode
    oracle.chmod(mode | 0o111)
    servo = target / ".servo"
    servo.mkdir(parents=True, exist_ok=True)
    (servo / "install.json").write_text(
        json.dumps({"installed_tier": "tier-0", "components": []}))
    _git_cmd(target, "add", "-A")
    _git_cmd(target, "commit", "-qm", "init")
    return target


def _write_stub_loop(path: Path, *, default: Optional[dict] = None,
                     by_item: Optional[dict] = None,
                     log_path: Optional[Path] = None) -> Path:
    """A deterministic stand-in `loop.py` for `campaign next`.

    It parses `--outcome-line <path>`, writes the run's `state.json` at
    `<worktree>/.servo/runs/<run_id>/state.json`, writes the spec-040 outcome
    record to the `--outcome-line` file, prints a terminal summary line, and logs
    its argv. Behaviour is keyed by the worktree basename (= item id). Knobs:
    `result`, `status` (final_oracle_status), `cost` (the state.json cost — the
    authoritative figure), `line_cost` (a DIFFERENT cost written into the outcome
    line, to prove servo reads state.json), `run_id`, `composite`, `threshold`,
    `rung`, `rungs`, `reason`, `iterations`, `host` (copilot → credit unit),
    `skip_outcome_line`, `no_summary`, `skip_state`, `exit_code`.
    """
    cfg = {
        "default": default if default is not None
        else {"result": "passed", "status": "pass", "cost": 0.42},
        "by_item": by_item or {},
        "log_path": str(log_path) if log_path is not None else "",
    }
    cfg_path = path.with_name(path.name + ".cfg.json")
    cfg_path.write_text(json.dumps(cfg))
    src = (
        "import sys, json, pathlib\n"
        f"CFG = json.loads(pathlib.Path({json.dumps(str(cfg_path))}).read_text())\n"
        "args = sys.argv[1:]\n"
        "worktree = pathlib.Path(args[0])\n"
        "item = worktree.name\n"
        "def _opt(name):\n"
        "    return args[args.index(name) + 1] if name in args else None\n"
        "if CFG['log_path']:\n"
        "    with open(CFG['log_path'], 'a') as _f:\n"
        "        _f.write(json.dumps({'argv': args, 'item': item}) + '\\n')\n"
        "beh = CFG['by_item'].get(item, CFG['default'])\n"
        "run_id = beh.get('run_id', 'crun-' + item)\n"
        "cost = beh.get('cost', 0.42)\n"
        "copilot = beh.get('host') == 'copilot'\n"
        "if not beh.get('skip_state'):\n"
        "    runs = worktree / '.servo' / 'runs' / run_id\n"
        "    runs.mkdir(parents=True, exist_ok=True)\n"
        "    state = {'run_id': run_id, 'state_schema_version': 1,\n"
        "             'backend': 'copilot' if copilot else 'claude',\n"
        "             'cumulative_cost_usd': None if copilot else cost}\n"
        "    if copilot:\n"
        "        state['cumulative_credits_nano'] = beh.get('credits_nano', 1000000000)\n"
        "    (runs / 'state.json').write_text(json.dumps(state))\n"
        "rec = {'servo_outcome': 1, 'result': beh.get('result', 'passed'),\n"
        "       'rung': beh.get('rung', 0), 'rungs': beh.get('rungs', 1),\n"
        "       'iterations': beh.get('iterations', 1),\n"
        "       'cost_usd': None if copilot else beh.get('line_cost', cost),\n"
        "       'composite': beh.get('composite', 0.9),\n"
        "       'threshold': beh.get('threshold', 0.5), 'run_id': run_id,\n"
        "       'reason': beh.get('reason', 'oracle_passed')}\n"
        "ol = _opt('--outcome-line')\n"
        "if ol and ol != '-' and not beh.get('skip_outcome_line'):\n"
        "    pathlib.Path(ol).write_text(json.dumps(rec) + '\\n')\n"
        "if not beh.get('no_summary'):\n"
        "    summary = {'schema_version': 1,\n"
        "               'final_oracle_status': beh.get('status', 'pass'),\n"
        "               'run_id': run_id,\n"
        "               'cumulative_cost_usd': None if copilot else cost,\n"
        "               'terminal_reason': beh.get('reason', 'oracle_passed'),\n"
        "               'iterations_completed': beh.get('iterations', 1),\n"
        "               'oracle_score_history': [{'iteration': 1,\n"
        "                   'composite': beh.get('composite', 0.9),\n"
        "                   'threshold': beh.get('threshold', 0.5)}]}\n"
        "    if copilot:\n"
        "        summary['cumulative_credits'] = beh.get('credits', 5.0)\n"
        "    print(json.dumps(summary))\n"
        "sys.exit(beh.get('exit_code', 0))\n"
    )
    path.write_text(src)
    return path


def _next(tmp: Path, loop_stub: Path, *, campaign_id: str = "camp-1",
          extra_env: Optional[dict] = None) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    # Inject the stub as the subprocess RUNNER only; the in-process loop-module
    # import (validator + the spec-040 outcome renderer) stays bound to the real
    # loop.py, so the fallback-renderer path exercises loop.py's own contract.
    env["SERVO_CAMPAIGN_RUNNER_PY"] = str(loop_stub)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(CAMPAIGN), "next", campaign_id, "--target", str(tmp)],
        capture_output=True, text=True, env=env,
    )


def _outcome_entries(tmp: Path, campaign_id: str = "camp-1") -> list:
    return [e for e in _ledger_lines(tmp, campaign_id) if "outcome" in e]


def _decision_entries(tmp: Path, campaign_id: str = "camp-1") -> list:
    return [e for e in _ledger_lines(tmp, campaign_id)
            if e.get("kind") == "coordinator_decision"]


def _reservations_dir(tmp: Path, campaign_id: str = "camp-1") -> Path:
    return _campaign_dir(tmp, campaign_id) / "reservations"


def _seed_reservation(tmp: Path, item: str, *, pid: int, campaign_id: str = "camp-1",
                      base_sha: str = "0" * 40,
                      started_at: str = "2020-01-01T00:00:00Z") -> Path:
    rdir = _reservations_dir(tmp, campaign_id)
    rdir.mkdir(parents=True, exist_ok=True)
    worktree = _campaign_dir(tmp, campaign_id) / "worktrees" / item
    path = rdir / (item + ".json")
    path.write_text(json.dumps({
        "item": item, "pid": pid, "base_sha": base_sha,
        "worktree": str(worktree), "branch": "servo/campaign/" + item,
        "started_at": started_at,
    }))
    return path


def _dead_pid() -> int:
    """A PID that is not alive (raises ProcessLookupError on signal 0)."""
    for pid in range(999999, 2, -1):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return pid
        except PermissionError:
            continue
    return 999999


def _item(item_id: str, *, oracle_ref: str = "oracle.sh", unit: str = "usd",
          scope: Optional[str] = None) -> dict:
    it = _valid_item(item_id, unit=unit)
    it["oracle_ref"] = oracle_ref
    if scope is not None:
        it["escalation_scope"] = scope
    return it


# --------------------------------------------------------------------------- #
# AC1 — dispatch at most one ready item; nothing ready → exit 0
# --------------------------------------------------------------------------- #

class NextDispatchOneReadyItemTests(unittest.TestCase):
    def setUp(self):
        self._td = _tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name) / "repo"
        _dispatch_repo(self.tmp)
        self.loop = Path(self._td.name) / "stub_loop.py"
        self.log = Path(self._td.name) / "loop.log"
        self.addCleanup(self._td.cleanup)

    def test_dispatches_first_ready_in_plan_order_and_records_servo_tier(self):
        plan = _valid_plan(_item("item-a"), _item("item-b"))
        _init(self.tmp, plan)
        _write_stub_loop(self.loop, log_path=self.log,
                         default={"result": "passed", "status": "pass", "cost": 0.5})
        proc = _next(self.tmp, self.loop)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # Exactly one loop launched — the FIRST plan item.
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual([c["item"] for c in calls], ["item-a"])
        # Its outcome is recorded with tier=servo (never self_reported).
        outs = _outcome_entries(self.tmp)
        self.assertEqual(len(outs), 1)
        self.assertEqual(outs[0]["item"], "item-a")
        self.assertEqual(outs[0]["tier"], "servo")
        self.assertFalse(outs[0]["self_reported"])
        self.assertEqual(outs[0]["outcome"]["result"], "passed")

    def test_loop_launched_with_item_budget_and_models(self):
        plan = _valid_plan(_item("item-a"))
        _init(self.tmp, plan)
        _write_stub_loop(self.loop, log_path=self.log)
        _next(self.tmp, self.loop)
        argv = [json.loads(line) for line in self.log.read_text().splitlines()][0]["argv"]
        self.assertIn("--outcome-line", argv)
        self.assertIn("--prompt", argv)
        # USD budget → --cost-ceiling carrying the item's ceiling (5.0 → "5").
        self.assertEqual(argv[argv.index("--cost-ceiling") + 1], "5")
        self.assertNotIn("--host", argv)  # claude host, not copilot
        # the item's models block is forwarded verbatim
        self.assertEqual(
            json.loads(argv[argv.index("--models") + 1]),
            {"runner": {"model": "claude-sonnet-5-5", "effort": "high"}})

    def test_nothing_ready_exits_zero_records_no_outcome(self):
        plan = _valid_plan(_item("item-a"))
        _init(self.tmp, plan)
        # Pre-record a terminal outcome so the only item is not ready.
        _run(["record", "camp-1", "item-a", "--outcome", json.dumps(_usd_outcome()),
              "--target", str(self.tmp)])
        _write_stub_loop(self.loop, log_path=self.log)
        before = len(_outcome_entries(self.tmp))
        proc = _next(self.tmp, self.loop)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("nothing to dispatch", (proc.stdout + proc.stderr).lower())
        self.assertFalse(self.log.exists(),
                         "no loop should be launched when nothing is ready")
        self.assertEqual(len(_outcome_entries(self.tmp)), before)


# --------------------------------------------------------------------------- #
# AC2 — record the loop's own typed line; cost from state.json, not re-derived
# --------------------------------------------------------------------------- #

class NextCostFromStateJsonTests(unittest.TestCase):
    def setUp(self):
        self._td = _tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name) / "repo"
        _dispatch_repo(self.tmp)
        self.loop = Path(self._td.name) / "stub_loop.py"
        self.addCleanup(self._td.cleanup)

    def test_recorded_cost_comes_from_state_json_not_outcome_line(self):
        _init(self.tmp, _valid_plan(_item("item-a")))
        # state.json cost = 0.42 (authoritative); outcome-line cost = 99.0 (wrong).
        _write_stub_loop(self.loop, default={
            "result": "passed", "status": "pass", "cost": 0.42, "line_cost": 99.0})
        proc = _next(self.tmp, self.loop)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        outs = _outcome_entries(self.tmp)
        self.assertEqual(len(outs), 1)
        self.assertEqual(outs[0]["outcome"]["cost_usd"], 0.42)

    def test_records_the_loops_typed_result_and_run_id(self):
        _init(self.tmp, _valid_plan(_item("item-a")))
        _write_stub_loop(self.loop, default={
            "result": "plateau", "status": "below_threshold", "cost": 1.25,
            "run_id": "the-run", "reason": "oracle_plateau", "rung": 2, "rungs": 2})
        _next(self.tmp, self.loop)
        outcome = _outcome_entries(self.tmp)[0]["outcome"]
        self.assertEqual(outcome["result"], "plateau")
        self.assertEqual(outcome["run_id"], "the-run")
        self.assertEqual(outcome["cost_usd"], 1.25)


# --------------------------------------------------------------------------- #
# AC3 — each `next` records its own coordinator decision
# --------------------------------------------------------------------------- #

class NextCoordinatorDecisionTests(unittest.TestCase):
    def setUp(self):
        self._td = _tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name) / "repo"
        _dispatch_repo(self.tmp)
        self.loop = Path(self._td.name) / "stub_loop.py"
        self.addCleanup(self._td.cleanup)

    def test_dispatch_records_a_coordinator_decision(self):
        _init(self.tmp, _valid_plan(_item("item-a"), _item("item-b")))
        _write_stub_loop(self.loop)
        _next(self.tmp, self.loop)
        decisions = _decision_entries(self.tmp)
        self.assertEqual(len(decisions), 1)
        d = decisions[0]
        self.assertEqual(d["max_parallel"], 1)
        self.assertEqual(d["dispatched"]["item"], "item-a")
        self.assertEqual(d["dispatched"]["result"], "passed")
        self.assertIn("item-a", d["read"]["ready"])

    def test_nothing_ready_still_records_a_decision(self):
        _init(self.tmp, _valid_plan(_item("item-a")))
        _run(["record", "camp-1", "item-a", "--outcome", json.dumps(_usd_outcome()),
              "--target", str(self.tmp)])
        _write_stub_loop(self.loop)
        _next(self.tmp, self.loop)
        decisions = _decision_entries(self.tmp)
        self.assertEqual(len(decisions), 1)
        self.assertIsNone(decisions[0]["dispatched"])


# --------------------------------------------------------------------------- #
# AC4 — reservation reconciliation on wake
# --------------------------------------------------------------------------- #

class NextReservationReconcileTests(unittest.TestCase):
    def setUp(self):
        self._td = _tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name) / "repo"
        _dispatch_repo(self.tmp)
        self.loop = Path(self._td.name) / "stub_loop.py"
        self.addCleanup(self._td.cleanup)

    def test_killed_reservation_is_released_and_item_requeued(self):
        _init(self.tmp, _valid_plan(_item("item-a")))
        _seed_reservation(self.tmp, "item-a", pid=_dead_pid(), base_sha="f" * 40)
        _write_stub_loop(self.loop)
        proc = _next(self.tmp, self.loop)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # The stale reservation was released and re-queued at its base sha.
        d = _decision_entries(self.tmp)[0]
        rec = [r for r in d["reconciled"] if r["item"] == "item-a"]
        self.assertEqual(len(rec), 1)
        self.assertEqual(rec[0]["action"], "released_requeued")
        self.assertEqual(rec[0]["base_sha"], "f" * 40)
        # Budget recovered: the item is re-dispatched (a fresh outcome recorded).
        self.assertEqual(len(_outcome_entries(self.tmp)), 1)
        # The reservation is not left dangling after the run halts.
        self.assertFalse((_reservations_dir(self.tmp) / "item-a.json").exists())

    def test_live_reservation_is_held_not_released(self):
        _init(self.tmp, _valid_plan(_item("item-a")))
        # os.getpid() (the test process) is alive → the run is "live".
        _seed_reservation(self.tmp, "item-a", pid=os.getpid())
        _write_stub_loop(self.loop, log_path=Path(self._td.name) / "l.log")
        proc = _next(self.tmp, self.loop)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        # Held: not reconciled away, not dispatched (item is reserved-live).
        self.assertTrue((_reservations_dir(self.tmp) / "item-a.json").exists())
        self.assertEqual(_outcome_entries(self.tmp), [])
        self.assertIsNone(_decision_entries(self.tmp)[0]["dispatched"])

    def test_recorded_reservation_is_cleaned_without_requeue(self):
        _init(self.tmp, _valid_plan(_item("item-a")))
        _run(["record", "camp-1", "item-a", "--outcome", json.dumps(_usd_outcome()),
              "--target", str(self.tmp)])
        _seed_reservation(self.tmp, "item-a", pid=_dead_pid())
        _write_stub_loop(self.loop, log_path=Path(self._td.name) / "l.log")
        _next(self.tmp, self.loop)
        d = _decision_entries(self.tmp)[0]
        rec = [r for r in d["reconciled"] if r["item"] == "item-a"]
        self.assertEqual(rec[0]["action"], "cleaned_recorded")
        # Not re-dispatched (it has a terminal outcome already).
        self.assertEqual(len(_outcome_entries(self.tmp)), 1)
        self.assertFalse((_reservations_dir(self.tmp) / "item-a.json").exists())

    def test_reservation_released_after_a_normal_dispatch(self):
        _init(self.tmp, _valid_plan(_item("item-a")))
        _write_stub_loop(self.loop)
        _next(self.tmp, self.loop)
        # A reservation is held only while the run is live → gone at halt.
        self.assertFalse((_reservations_dir(self.tmp) / "item-a.json").exists())


# --------------------------------------------------------------------------- #
# AC5 — escalations batched by scope
# --------------------------------------------------------------------------- #

class NextEscalationBatchTests(unittest.TestCase):
    def setUp(self):
        self._td = _tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name) / "repo"
        _dispatch_repo(self.tmp)
        self.loop = Path(self._td.name) / "stub_loop.py"
        self.addCleanup(self._td.cleanup)

    def test_ceiling_plateau_items_batched_by_explicit_scope(self):
        plan = _valid_plan(
            _item("item-a", scope="area-x"),
            _item("item-b", scope="area-x"),
            _item("item-c", scope="area-y"),
            _item("item-d", scope="area-z"),
        )
        _init(self.tmp, plan)
        plateau = json.dumps(_usd_outcome(result="plateau", reason="oracle_plateau",
                                          rung=2, rungs=2))
        for it in ("item-a", "item-b", "item-c"):
            _run(["record", "camp-1", it, "--outcome", plateau, "--target", str(self.tmp)])
        # item-d passed — must NOT be escalated.
        _run(["record", "camp-1", "item-d", "--outcome", json.dumps(_usd_outcome()),
              "--target", str(self.tmp)])
        _write_stub_loop(self.loop)
        proc = _next(self.tmp, self.loop)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        d = _decision_entries(self.tmp)[0]
        esc = {e["scope"]: sorted(e["items"]) for e in d["escalations"]}
        # One batch per scope (not one message per item); passed item excluded.
        self.assertEqual(esc, {"area-x": ["item-a", "item-b"], "area-y": ["item-c"]})
        self.assertIn("area-x", proc.stdout)

    def test_unscoped_plateau_items_batch_into_one_message(self):
        # Independent items with DISTINCT oracle_refs and NO escalation_scope must
        # still batch into ONE escalation — not one message per item (the AC5
        # anti-goal). oracle_ref is the gate, not the escalation scope.
        plan = _valid_plan(
            _item("item-a", oracle_ref="oracle-a.sh"),
            _item("item-b", oracle_ref="oracle-b.sh"),
            _item("item-c", oracle_ref="oracle-c.sh"),
        )
        _init(self.tmp, plan)
        plateau = json.dumps(_usd_outcome(result="plateau", reason="oracle_plateau",
                                          rung=2, rungs=2))
        for it in ("item-a", "item-b", "item-c"):
            _run(["record", "camp-1", it, "--outcome", plateau, "--target", str(self.tmp)])
        _write_stub_loop(self.loop)
        proc = _next(self.tmp, self.loop)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        d = _decision_entries(self.tmp)[0]
        self.assertEqual(len(d["escalations"]), 1)  # exactly one batch
        self.assertEqual(sorted(d["escalations"][0]["items"]),
                         ["item-a", "item-b", "item-c"])
        # one human escalation line, not one per item
        self.assertEqual(proc.stdout.count("plateaued at the ladder ceiling"), 1)


# --------------------------------------------------------------------------- #
# AC6 — servo never merges and the runner does no git operations
# --------------------------------------------------------------------------- #

class NextNoGitOpsTests(unittest.TestCase):
    def setUp(self):
        self._td = _tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name) / "repo"
        _dispatch_repo(self.tmp)
        self.loop = Path(self._td.name) / "stub_loop.py"
        self.addCleanup(self._td.cleanup)

    def test_next_does_not_commit_or_move_head(self):
        _init(self.tmp, _valid_plan(_item("item-a")))
        head_before = _git_cmd(self.tmp, "rev-parse", "HEAD").stdout.strip()
        count_before = _git_cmd(self.tmp, "rev-list", "--count", "HEAD").stdout.strip()
        _write_stub_loop(self.loop)
        _next(self.tmp, self.loop)
        head_after = _git_cmd(self.tmp, "rev-parse", "HEAD").stdout.strip()
        count_after = _git_cmd(self.tmp, "rev-list", "--count", "HEAD").stdout.strip()
        self.assertEqual(head_before, head_after)   # no merge / no commit
        self.assertEqual(count_before, count_after)


def _seed_orphan_outcome(tmp: Path, item: str, *, run_id: str = "orphan-run",
                         state_cost: float = 0.33, line_cost: float = 0.33,
                         campaign_id: str = "camp-1") -> None:
    """Simulate a worker that FINISHED (wrote its --outcome-line + state.json) but
    whose parent `campaign next` died before recording it: an orphaned sink file
    plus the run's state.json under the item's worktree."""
    cdir = _campaign_dir(tmp, campaign_id)
    wdir = cdir / "worktrees"
    wdir.mkdir(parents=True, exist_ok=True)
    rec = _usd_outcome(run_id=run_id, cost_usd=line_cost, result="passed",
                       reason="oracle_passed")
    (wdir / (item + ".outcome.json")).write_text(json.dumps(rec) + "\n")
    runs = wdir / item / ".servo" / "runs" / run_id
    runs.mkdir(parents=True, exist_ok=True)
    (runs / "state.json").write_text(
        json.dumps({"run_id": run_id, "cumulative_cost_usd": state_cost}))


# --------------------------------------------------------------------------- #
# AC1 — plan order skips terminal items
# --------------------------------------------------------------------------- #

class NextPlanOrderTests(unittest.TestCase):
    def setUp(self):
        self._td = _tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name) / "repo"
        _dispatch_repo(self.tmp)
        self.loop = Path(self._td.name) / "stub_loop.py"
        self.log = Path(self._td.name) / "loop.log"
        self.addCleanup(self._td.cleanup)

    def test_dispatches_next_ready_when_earlier_item_terminal(self):
        _init(self.tmp, _valid_plan(_item("item-a"), _item("item-b")))
        # item-a already plateaued (terminal, not ready); item-b is the next ready.
        _run(["record", "camp-1", "item-a", "--outcome",
              json.dumps(_usd_outcome(result="plateau", reason="oracle_plateau")),
              "--target", str(self.tmp)])
        _write_stub_loop(self.loop, log_path=self.log)
        _next(self.tmp, self.loop)
        calls = [json.loads(line) for line in self.log.read_text().splitlines()]
        self.assertEqual([c["item"] for c in calls], ["item-b"])
        self.assertIn("item-b", {e["item"] for e in _outcome_entries(self.tmp)})


# --------------------------------------------------------------------------- #
# AC2 — fail-open / fallback paths + credit dispatch
# --------------------------------------------------------------------------- #

class NextFallbackEnvErrorCreditTests(unittest.TestCase):
    def setUp(self):
        self._td = _tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name) / "repo"
        _dispatch_repo(self.tmp)
        self.loop = Path(self._td.name) / "stub_loop.py"
        self.log = Path(self._td.name) / "loop.log"
        self.addCleanup(self._td.cleanup)

    def test_fallback_renderer_used_when_outcome_line_missing(self):
        _init(self.tmp, _valid_plan(_item("item-a")))
        # no --outcome-line file, but a terminal summary on stdout → the ledger
        # stores loop.py's OWN _outcome_record rendering of that summary.
        _write_stub_loop(self.loop, default={
            "result": "passed", "status": "pass", "cost": 0.7,
            "skip_outcome_line": True})
        proc = _next(self.tmp, self.loop)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        outs = _outcome_entries(self.tmp)
        self.assertEqual(len(outs), 1)
        self.assertEqual(outs[0]["tier"], "servo")
        self.assertEqual(outs[0]["outcome"]["result"], "passed")
        self.assertEqual(outs[0]["outcome"]["cost_usd"], 0.7)

    def test_no_outcome_and_no_summary_leaves_item_open_with_dispatch_error(self):
        _init(self.tmp, _valid_plan(_item("item-a")))
        _write_stub_loop(self.loop, default={"skip_outcome_line": True,
                                             "no_summary": True})
        proc = _next(self.tmp, self.loop)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(_outcome_entries(self.tmp), [])  # nothing recorded; item open
        d = _decision_entries(self.tmp)[0]
        self.assertIsNone(d["dispatched"])
        self.assertEqual(d["dispatch_error"]["item"], "item-a")
        self.assertIn("no outcome line or summary", d["dispatch_error"]["reason"])
        self.assertFalse((_reservations_dir(self.tmp) / "item-a.json").exists())

    def test_cost_falls_back_to_outcome_line_when_state_json_absent(self):
        _init(self.tmp, _valid_plan(_item("item-a")))
        # state.json absent → cost is taken from the loop's own --outcome-line.
        _write_stub_loop(self.loop, default={
            "result": "passed", "status": "pass", "line_cost": 0.55,
            "skip_state": True})
        proc = _next(self.tmp, self.loop)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(_outcome_entries(self.tmp)[0]["outcome"]["cost_usd"], 0.55)

    def test_credit_item_dispatches_copilot_and_records_null_cost(self):
        _init(self.tmp, _valid_plan(_item("item-a", unit="credit")))
        _write_stub_loop(self.loop, log_path=self.log, default={
            "result": "passed", "status": "pass", "host": "copilot", "credits": 42.0})
        proc = _next(self.tmp, self.loop)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        argv = [json.loads(line) for line in self.log.read_text().splitlines()][0]["argv"]
        self.assertEqual(argv[argv.index("--host") + 1], "copilot")
        self.assertIn("--credit-ceiling", argv)
        self.assertNotIn("--cost-ceiling", argv)
        self.assertEqual(argv[argv.index("--max-iterations") + 1], "5")
        # a credit/Copilot run records cost_usd null (042-01 rule; credits in 042-04)
        self.assertIsNone(_outcome_entries(self.tmp)[0]["outcome"]["cost_usd"])


# --------------------------------------------------------------------------- #
# AC4 — a finished-but-unrecorded run is promoted, not re-spent
# --------------------------------------------------------------------------- #

class NextOrphanPromotionTests(unittest.TestCase):
    def setUp(self):
        self._td = _tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name) / "repo"
        _dispatch_repo(self.tmp)
        self.loop = Path(self._td.name) / "stub_loop.py"
        self.log = Path(self._td.name) / "loop.log"
        self.addCleanup(self._td.cleanup)

    def test_finished_but_unrecorded_run_is_promoted_not_requeued(self):
        _init(self.tmp, _valid_plan(_item("item-a")))
        # a finished worker's orphaned line (line cost 99.0) + its state.json (0.33);
        # a dead-pid reservation stands in for the died-before-recording parent.
        _seed_orphan_outcome(self.tmp, "item-a", run_id="r-orphan",
                             state_cost=0.33, line_cost=99.0)
        _seed_reservation(self.tmp, "item-a", pid=_dead_pid())
        _write_stub_loop(self.loop, log_path=self.log)
        proc = _next(self.tmp, self.loop)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        d = _decision_entries(self.tmp)[0]
        rec = [r for r in d["reconciled"] if r["item"] == "item-a"]
        self.assertEqual(rec[0]["action"], "promoted_orphan")
        # the finished worker's result is recorded (NOT re-run), cost from state.json
        outs = _outcome_entries(self.tmp)
        self.assertEqual(len(outs), 1)
        self.assertEqual(outs[0]["tier"], "servo")
        self.assertEqual(outs[0]["outcome"]["cost_usd"], 0.33)
        self.assertFalse(self.log.exists(), "promoted item must not be re-dispatched")
        self.assertFalse((_reservations_dir(self.tmp) / "item-a.json").exists())


# --------------------------------------------------------------------------- #
# AC1/AC6 — a non-blocking coordinator lock serializes overlapping wakes
# --------------------------------------------------------------------------- #

class NextCoordinatorLockTests(unittest.TestCase):
    def test_contended_next_backs_off_without_dispatching(self):
        import fcntl
        with _tempfile.TemporaryDirectory() as d:
            tmp = Path(d) / "repo"
            _dispatch_repo(tmp)
            loop = Path(d) / "stub_loop.py"
            _write_stub_loop(loop)
            _init(tmp, _valid_plan(_item("item-a")))
            lock_path = _campaign_dir(tmp) / ".next.lock"
            fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                proc = _next(tmp, loop)
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
                os.close(fd)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("backing off", proc.stdout)
            self.assertEqual(_outcome_entries(tmp), [])  # nothing dispatched
            self.assertEqual(_decision_entries(tmp), [])  # no decision appended


# --------------------------------------------------------------------------- #
# Unit contracts: optional escalation_scope + the loop.py renderer drift guard
# --------------------------------------------------------------------------- #

class NextUnitContractTests(unittest.TestCase):
    def test_escalation_scope_is_optional_and_validated(self):
        with _tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            self.assertEqual(_init(tmp, _valid_plan(_item("item-a", scope="area-x")),
                                   "camp-ok").returncode, 0)
        with _tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            bad = _item("item-a")
            bad["escalation_scope"] = ""  # present but empty → rejected
            proc = _init(tmp, {"schema_version": 1, "items": [bad]}, "camp-bad")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("escalation_scope", proc.stderr)

    def test_default_escalation_scope_groups_unscoped_items(self):
        plan = _valid_plan(_item("a", oracle_ref="x.sh"), _item("b", oracle_ref="y.sh"))
        latest = {
            "a": {"outcome": {"result": "plateau"}},
            "b": {"outcome": {"result": "plateau"}},
        }
        groups = _cmp._compute_escalations(plan, latest)
        self.assertEqual(len(groups), 1)  # one shared default scope
        self.assertEqual(groups[0]["scope"], _cmp.DEFAULT_ESCALATION_SCOPE)
        self.assertEqual(sorted(groups[0]["items"]), ["a", "b"])

    def test_non_git_target_is_dispatch_env_error(self):
        # A non-git target cannot be isolated — the early guard fails cleanly and
        # the reason is recorded in the coordinator decision (no worker launched).
        with _tempfile.TemporaryDirectory() as d:
            tmp = Path(d)  # a plain dir, not a git repo
            loop = tmp / "stub_loop.py"
            _write_stub_loop(loop)
            _init(tmp, _valid_plan(_item("item-a")))
            proc = _next(tmp, loop)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(_outcome_entries(tmp), [])
            entry = _decision_entries(tmp)[0]
            self.assertIsNone(entry["dispatched"])
            self.assertEqual(entry["dispatch_error"]["item"], "item-a")
            self.assertIn("not a git work tree", entry["dispatch_error"]["reason"])

    def test_outcome_renderer_binds_to_loop_pys_own(self):
        # Drift guard for the dynamic `_outcome_record` binding (the twin of the
        # 042-01 validator/constant parity tests): if loop.py renames or reshapes
        # its 040 renderer, this fails loudly rather than silently mis-recording.
        renderer = _cmp._load_outcome_renderer()
        rec = renderer({
            "terminal_reason": "oracle_passed", "final_oracle_status": "pass",
            "iterations_completed": 2, "cumulative_cost_usd": 1.5,
            "oracle_score_history": [{"composite": 0.9, "threshold": 0.5}],
            "run_id": "r"})
        self.assertEqual(rec["servo_outcome"], _cmp.OUTCOME_SCHEMA_VERSION)
        self.assertEqual(rec["result"], "passed")
        self.assertEqual(rec["cost_usd"], 1.5)
        self.assertEqual(rec["run_id"], "r")


# =========================================================================== #
# Spec 042-03 — host-driven advisory: `campaign brief`, the advisory oracle
# re-check in `record`, and the runaway-limit disclosure.
#
# The oracle re-check reuses heartbeat's canonical `_run_gate_json`, so the gate
# is stubbed via `SERVO_HEARTBEAT_GATE_PY` (the env that runner resolves). A bare
# worktree dir has no installed policy, so `gate_consumer.accept`'s legacy
# no-policy adapter returns the stub's verdict as-is; `_unpriced_oracle_error`
# returns None without a `.servo/install.json`. Brief base-sha tests use a REAL
# git repo (`_dispatch_repo`), and one integration test runs the REAL gate.py.
# =========================================================================== #


def _write_stub_gate(path: Path, *, exit_code: int = 0, status: str = "pass",
                     composite: float = 1.0, threshold: float = 0.5,
                     marker: Optional[Path] = None) -> Path:
    """A deterministic stand-in `gate.py` for the advisory re-check.

    Emits one JSON verdict line (no `schema_version`/`kind`/`required`, so the
    no-policy legacy adapter in `gate_consumer.accept` returns it verbatim) and
    exits with a code that MATCHES the line's `exit_code` (the adapter requires
    it). An optional `marker` file is touched on invocation, to prove whether the
    re-check ran at all (AC5)."""
    verdict = {"exit_code": exit_code, "status": status,
               "composite": composite, "threshold": threshold, "reason": "stub"}
    lines = ["import sys"]
    if marker is not None:
        lines.append(f"open({json.dumps(str(marker))}, 'w').close()")
    lines.append(f"print({json.dumps(json.dumps(verdict))})")
    lines.append(f"sys.exit({exit_code})")
    path.write_text("\n".join(lines) + "\n")
    return path


def _worktree_dir(root: Path, name: str = "wt") -> Path:
    """A plain directory standing in for the host's worker worktree (the stubbed
    gate makes a real repo/oracle unnecessary; it only needs to be writable so
    `gate_consumer.request` can resolve its run dir)."""
    wt = root / name
    wt.mkdir(parents=True, exist_ok=True)
    return wt


def _record_adv(tmp: Path, item: str, outcome: dict, *,
                worktree: Optional[Path] = None, gate_stub: Optional[Path] = None,
                tier: str = "advisory", campaign_id: str = "camp-1",
                extra_env: Optional[dict] = None) -> subprocess.CompletedProcess:
    args = ["record", campaign_id, item, "--outcome", json.dumps(outcome),
            "--tier", tier, "--target", str(tmp)]
    if worktree is not None:
        args += ["--worktree", str(worktree)]
    env = dict(os.environ)
    if gate_stub is not None:
        env["SERVO_HEARTBEAT_GATE_PY"] = str(gate_stub)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(CAMPAIGN), *args], capture_output=True, text=True, env=env)


def _brief(tmp: Path, *item: str, campaign_id: str = "camp-1") -> subprocess.CompletedProcess:
    return _run(["brief", campaign_id, *item, "--target", str(tmp)])


# --------------------------------------------------------------------------- #
# AC1 — `campaign brief` emits a per-item kickoff brief (data-not-instructions)
# --------------------------------------------------------------------------- #

class BriefEmitsKickoffTests(unittest.TestCase):
    def setUp(self):
        self._td = _tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        _dispatch_repo(self.tmp)  # real git repo → a resolvable base sha
        self.item = _item("item-a", oracle_ref="oracle.sh")
        self.assertEqual(_init(self.tmp, _valid_plan(self.item)).returncode, 0)

    def tearDown(self):
        self._td.cleanup()

    def test_brief_carries_item_fields_as_data(self):
        res = _brief(self.tmp, "item-a")
        self.assertEqual(res.returncode, 0, res.stderr)
        out = res.stdout
        # the authored fields appear inside the delimited UNTRUSTED DATA block
        self.assertIn(_cmp._ITEM_BEGIN, out)
        self.assertIn(_cmp._ITEM_END, out)
        self.assertIn("oracle.sh", out)                  # oracle_ref
        self.assertIn('"unit": "usd"', out)              # budget block, as data
        self.assertIn("models", out)                     # models block, as data
        self.assertIn(self.item["prompt"], out)          # the authored prompt

    def test_brief_states_base_sha(self):
        head = subprocess.run(["git", "-C", str(self.tmp), "rev-parse", "HEAD"],
                              capture_output=True, text=True).stdout.strip()
        res = _brief(self.tmp, "item-a")
        self.assertIn(head, res.stdout)

    def test_brief_instructs_record_before_commit(self):
        out = _brief(self.tmp, "item-a").stdout
        self.assertIn("campaign record", out)
        self.assertIn("--tier advisory", out)
        self.assertIn("--worktree", out)
        self.assertIn("before", out.lower())             # record-before-commit
        self.assertIn("commit", out.lower())

    def test_brief_states_item_text_is_data(self):
        out = _brief(self.tmp, "item-a").stdout
        self.assertIn("UNTRUSTED", out)
        self.assertIn("not instructions", out.lower().replace("not an instruction",
                                                               "not instructions"))

    def test_brief_discloses_runaway_limit(self):
        out = _brief(self.tmp, "item-a").stdout
        self.assertIn(_cmp.ADVISORY_RUNAWAY_NOTE, out)

    def test_brief_unknown_item_refused(self):
        res = _brief(self.tmp, "no-such-item")
        self.assertEqual(res.returncode, 2)
        self.assertEqual(_ledger_lines(self.tmp), [])    # writes nothing


class BriefAllItemsTests(unittest.TestCase):
    def test_no_item_emits_one_brief_per_item_in_plan_order(self):
        with _tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            _dispatch_repo(tmp)
            _init(tmp, _valid_plan(_item("alpha"), _item("beta"), _item("gamma")))
            out = _brief(tmp).stdout
            self.assertEqual(out.count(_cmp._ITEM_BEGIN), 3)
            # plan order preserved
            self.assertLess(out.index("alpha"), out.index("beta"))
            self.assertLess(out.index("beta"), out.index("gamma"))

    def test_brief_writes_nothing_to_the_ledger(self):
        with _tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            _dispatch_repo(tmp)
            _init(tmp, _valid_plan(_item("alpha")))
            _brief(tmp)
            self.assertEqual(_ledger_lines(tmp), [])

    def test_non_git_target_base_sha_degrades_gracefully(self):
        # AC1 graceful degradation: a target with no resolvable git HEAD (here a
        # plain, non-git dir) still emits a brief, exit 0, with the base sha marked
        # unavailable rather than failing.
        with _tempfile.TemporaryDirectory() as d:
            tmp = Path(d)  # NOT a git repo
            _init(tmp, _valid_plan(_item("alpha")))
            res = _brief(tmp, "alpha")
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("base sha: unavailable", res.stdout)
            self.assertIn(_cmp._ITEM_BEGIN, res.stdout)  # the brief still renders


# --------------------------------------------------------------------------- #
# AC2 — advisory `record` re-runs the oracle before accepting a claimed pass
# --------------------------------------------------------------------------- #

class RecordAdvisoryRecheckTests(unittest.TestCase):
    def setUp(self):
        self._td = _tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        _init(self.tmp, _valid_plan(_item("item-a", oracle_ref="oracle.sh")))
        self.wt = _worktree_dir(self.tmp, "wt-a")

    def tearDown(self):
        self._td.cleanup()

    def test_confirmed_pass_records_passed(self):
        gate = _write_stub_gate(self.tmp / "gate_pass.py", exit_code=0, status="pass")
        res = _record_adv(self.tmp, "item-a", _usd_outcome(result="passed"),
                          worktree=self.wt, gate_stub=gate)
        self.assertEqual(res.returncode, 0, res.stderr)
        entry = _ledger_lines(self.tmp)[-1]
        self.assertEqual(entry["outcome"]["result"], "passed")
        self.assertTrue(entry["self_reported"])          # cost/rung/reason still self-reported
        rc = entry["oracle_recheck"]
        self.assertTrue(rc["confirmed"])
        self.assertEqual(rc["claimed_result"], "passed")
        self.assertEqual(rc["recorded_result"], "passed")

    def test_unconfirmed_pass_downgraded_to_blocked(self):
        # oracle ran and did NOT pass (below threshold, exit 1) → never 'passed'.
        gate = _write_stub_gate(self.tmp / "gate_below.py", exit_code=1,
                                status="below_threshold", composite=0.3)
        res = _record_adv(self.tmp, "item-a", _usd_outcome(result="passed"),
                          worktree=self.wt, gate_stub=gate)
        self.assertEqual(res.returncode, 0, res.stderr)
        entry = _ledger_lines(self.tmp)[-1]
        self.assertEqual(entry["outcome"]["result"], "blocked")   # AC2: never passed
        self.assertEqual(entry["oracle_recheck"]["claimed_result"], "passed")
        self.assertFalse(entry["oracle_recheck"]["confirmed"])

    def test_oracle_env_error_records_error(self):
        # oracle ran on a real worktree but env-errored (exit 2) → cannot confirm.
        gate = _write_stub_gate(self.tmp / "gate_env.py", exit_code=2,
                                status="env_error")
        res = _record_adv(self.tmp, "item-a", _usd_outcome(result="passed"),
                          worktree=self.wt, gate_stub=gate)
        self.assertEqual(res.returncode, 0, res.stderr)
        entry = _ledger_lines(self.tmp)[-1]
        self.assertEqual(entry["outcome"]["result"], "error")
        self.assertFalse(entry["oracle_recheck"]["confirmed"])

    def test_uninvocable_gate_refuses_and_records_nothing(self):
        # gate.py cannot run at all (no parseable verdict) → rc=2, ledger unchanged
        # (a servo-side env problem the operator fixes & retries, not an item error).
        missing = self.tmp / "no_such_gate.py"
        res = _record_adv(self.tmp, "item-a", _usd_outcome(result="passed"),
                          worktree=self.wt, gate_stub=missing)
        self.assertEqual(res.returncode, 2)
        self.assertEqual(_ledger_lines(self.tmp), [])

    def test_passed_without_worktree_refused(self):
        res = _record_adv(self.tmp, "item-a", _usd_outcome(result="passed"))
        self.assertEqual(res.returncode, 2)
        self.assertIn("worktree", res.stderr.lower())
        self.assertEqual(_ledger_lines(self.tmp), [])

    def test_passed_worktree_absent_refused(self):
        gate = _write_stub_gate(self.tmp / "gate_pass.py")
        res = _record_adv(self.tmp, "item-a", _usd_outcome(result="passed"),
                          worktree=self.tmp / "does-not-exist", gate_stub=gate)
        self.assertEqual(res.returncode, 2)
        self.assertEqual(_ledger_lines(self.tmp), [])

    def test_non_pass_claim_skips_recheck(self):
        # A claimed plateau needs no re-check: recorded as-is, self_reported, and
        # the gate is never invoked (marker absent).
        marker = self.tmp / "gate_ran"
        gate = _write_stub_gate(self.tmp / "gate_pass.py", marker=marker)
        res = _record_adv(self.tmp, "item-a",
                          _usd_outcome(result="plateau", reason="oracle_plateau"),
                          worktree=self.wt, gate_stub=gate)
        self.assertEqual(res.returncode, 0, res.stderr)
        entry = _ledger_lines(self.tmp)[-1]
        self.assertEqual(entry["outcome"]["result"], "plateau")
        self.assertTrue(entry["self_reported"])
        self.assertNotIn("oracle_recheck", entry)
        self.assertFalse(marker.exists())                 # no re-check ran

    def test_servo_tier_pass_not_rechecked(self):
        # servo-tier outcomes come from servo's own loop run (042-02), already
        # oracle-gated; the advisory re-check is advisory-only.
        marker = self.tmp / "gate_ran"
        gate = _write_stub_gate(self.tmp / "gate_pass.py", marker=marker)
        res = _record_adv(self.tmp, "item-a", _usd_outcome(result="passed"),
                          worktree=self.wt, gate_stub=gate, tier="servo")
        self.assertEqual(res.returncode, 0, res.stderr)
        entry = _ledger_lines(self.tmp)[-1]
        self.assertEqual(entry["outcome"]["result"], "passed")
        self.assertFalse(entry["self_reported"])
        self.assertNotIn("oracle_recheck", entry)
        self.assertFalse(marker.exists())


class RecordAdvisoryRecheckRealGateTests(unittest.TestCase):
    """Integration: the re-check wiring against the REAL gate.py (not a stub)."""

    def _worktree_with_oracle(self, root: Path, exit_code: int) -> Path:
        # A minimal real scaffold the REAL gate.py accepts: a committed oracle.sh
        # (the gate's deterministic driver) + the `.servo/install.json` manifest
        # gate.py requires (ADR-0002). No installed policy, so gate_consumer's
        # no-policy path grades the oracle's own exit/score.
        wt = _worktree_dir(root, f"wt-{exit_code}")
        oracle = wt / "oracle.sh"
        comp = "1.0" if exit_code == 0 else "0.1"
        oracle.write_text("#!/usr/bin/env bash\n"
                          f'echo "oracle: composite={comp} threshold=0.5"\n'
                          f"exit {exit_code}\n")
        oracle.chmod(oracle.stat().st_mode | 0o111)
        servo = wt / ".servo"
        servo.mkdir(parents=True, exist_ok=True)
        (servo / "install.json").write_text(
            json.dumps({"installed_tier": "tier-0", "components": []}))
        return wt

    def test_real_gate_confirms_passing_oracle(self):
        with _tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            _init(tmp, _valid_plan(_item("item-a")))
            wt = self._worktree_with_oracle(tmp, 0)
            res = _record_adv(tmp, "item-a", _usd_outcome(result="passed"), worktree=wt)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(_ledger_lines(tmp)[-1]["outcome"]["result"], "passed")

    def test_real_gate_downgrades_failing_oracle(self):
        with _tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            _init(tmp, _valid_plan(_item("item-a")))
            wt = self._worktree_with_oracle(tmp, 1)
            res = _record_adv(tmp, "item-a", _usd_outcome(result="passed"), worktree=wt)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertNotEqual(_ledger_lines(tmp)[-1]["outcome"]["result"], "passed")


# --------------------------------------------------------------------------- #
# AC3 — every field but the re-checked result is self_reported; self-reported
# cost is never enforced spend (even on a confirmed pass).
# --------------------------------------------------------------------------- #

class AdvisoryFieldsSelfReportedTests(unittest.TestCase):
    def test_confirmed_pass_cost_not_enforced(self):
        with _tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            _init(tmp, _valid_plan(_item("item-a")))
            wt = _worktree_dir(tmp)
            gate = _write_stub_gate(tmp / "gate_pass.py")
            _record_adv(tmp, "item-a", _usd_outcome(result="passed", cost_usd=9.99),
                        worktree=wt, gate_stub=gate)
            res = _run(["status", "camp-1", "--json", "--target", str(tmp)])
            summary = json.loads(res.stdout)
            # the verified pass counts as passed, but its cost is self-reported
            self.assertEqual(summary["totals"]["enforced_cost_usd"], 0.0)
            self.assertAlmostEqual(summary["totals"]["self_reported_cost_usd"], 9.99)
            self.assertEqual(summary["totals"]["passed"], 1)

    def test_recheck_result_is_servos_not_self_reported(self):
        with _tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            _init(tmp, _valid_plan(_item("item-a")))
            wt = _worktree_dir(tmp)
            gate = _write_stub_gate(tmp / "gate.py", exit_code=1,
                                    status="below_threshold")
            _record_adv(tmp, "item-a", _usd_outcome(result="passed"),
                        worktree=wt, gate_stub=gate)
            entry = _ledger_lines(tmp)[-1]
            # the host CLAIMED passed; servo's own re-check is the recorded result
            self.assertEqual(entry["oracle_recheck"]["claimed_result"], "passed")
            self.assertEqual(entry["outcome"]["result"], "blocked")


# --------------------------------------------------------------------------- #
# AC4 — the runaway limit is disclosed in the brief AND in status, not hidden.
# --------------------------------------------------------------------------- #

class RunawayDisclosureTests(unittest.TestCase):
    def test_status_discloses_limit_once_advisory_in_play(self):
        with _tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            _init(tmp, _valid_plan(_item("item-a")))
            wt = _worktree_dir(tmp)
            gate = _write_stub_gate(tmp / "gate.py")
            _record_adv(tmp, "item-a", _usd_outcome(result="passed"),
                        worktree=wt, gate_stub=gate)
            human = _run(["status", "camp-1", "--target", str(tmp)]).stdout
            self.assertIn(_cmp.ADVISORY_RUNAWAY_NOTE, human)
            js = json.loads(_run(["status", "camp-1", "--json",
                                  "--target", str(tmp)]).stdout)
            self.assertTrue(js["advisory_active"])

    def test_servo_only_status_stays_quiet(self):
        with _tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            _init(tmp, _valid_plan(_item("item-a")))
            _run(["record", "camp-1", "item-a", "--outcome",
                  json.dumps(_usd_outcome()), "--target", str(tmp)])  # servo tier
            human = _run(["status", "camp-1", "--target", str(tmp)]).stdout
            self.assertNotIn(_cmp.ADVISORY_RUNAWAY_NOTE, human)
            js = json.loads(_run(["status", "camp-1", "--json",
                                  "--target", str(tmp)]).stdout)
            self.assertFalse(js["advisory_active"])


# --------------------------------------------------------------------------- #
# AC5 — servo never spawns or messages a host session in the advisory path; it
# only writes briefs and reads worktrees (the oracle re-check is the only
# subprocess, and no worker/loop is launched).
# --------------------------------------------------------------------------- #

class AdvisoryNoSpawnTests(unittest.TestCase):
    def test_record_never_launches_a_worker(self):
        with _tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            _init(tmp, _valid_plan(_item("item-a")))
            wt = _worktree_dir(tmp)
            gate = _write_stub_gate(tmp / "gate.py")
            # The loop stub LOGS every invocation to `runner_log`: if the advisory
            # record path ever spawned a worker/loop (now or via a future
            # regression that read SERVO_CAMPAIGN_RUNNER_PY), the log would appear.
            # Non-vacuous: the stub creates the file only when actually invoked.
            runner_log = tmp / "runner.log"
            runner = _write_stub_loop(tmp / "stub_loop.py", log_path=runner_log)
            res = _record_adv(
                tmp, "item-a", _usd_outcome(result="passed"), worktree=wt,
                gate_stub=gate,
                extra_env={"SERVO_CAMPAIGN_RUNNER_PY": str(runner),
                           "SERVO_CAMPAIGN_LOOP_PY": str(runner)})
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertFalse(runner_log.exists())        # no worker/loop invoked
            # A spawned loop.py writes <worktree>/.servo/runs/<run_id>/state.json;
            # the advisory re-check (gate.py only) never creates runs/. Its absence
            # is the trace-based no-spawn proof.
            self.assertFalse((wt / ".servo" / "runs").exists())

    def test_brief_spawns_nothing(self):
        with _tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            _dispatch_repo(tmp)
            _init(tmp, _valid_plan(_item("item-a")))
            runner_log = tmp / "runner.log"
            runner = _write_stub_loop(tmp / "stub_loop.py", log_path=runner_log)
            res = subprocess.run(
                [sys.executable, str(CAMPAIGN), "brief", "camp-1",
                 "--target", str(tmp)],
                capture_output=True, text=True,
                env={**os.environ, "SERVO_CAMPAIGN_RUNNER_PY": str(runner),
                     "SERVO_CAMPAIGN_LOOP_PY": str(runner)})
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertFalse(runner_log.exists())        # brief invoked no worker/loop
            self.assertEqual(_outcome_entries(tmp), [])  # and wrote no outcome


if __name__ == "__main__":
    unittest.main()
