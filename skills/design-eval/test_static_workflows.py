"""Opt-in public non-card workflows. ALL approvals are SYNTHETIC TEST ONLY.

Run with an explicit SERVO_STATIC_PRODUCER directory and the selected isolated
Python/Bash/PLAYWRIGHT_BROWSERS_PATH. No package, approval, install, source check
or runtime-closure seam is mocked. Only preserved-reader controls forbid work.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import static_contract as app

SHAPES = {
    "audio-routing": {
        "count": 7,
        "vendor_engine": False,
        "root": "#mix",
        "witnesses": ["#mix > aside", "#mix > button"],
        "roles": {"rack": ".bus", "meter": "output", "transport": "button"},
        "entry": "mix.html",
        "files": {
            "mix.html": '<!doctype html><meta charset="utf-8"><title>TEST ONLY mixer</title>'
                        '<link rel="stylesheet" href="mix.css"><main id="mix">'
                        '<aside class="bus">AUX 3</aside><output>-12 dB</output>'
                        '<button>Pause</button></main>',
            "mix.css": "body{margin:16px;font-family:sans-serif}"
                       "#mix{display:grid;grid-template-columns:240px 1fr;gap:25px}"
                       ".bus{box-sizing:border-box;width:240px;height:180px;background:#edf3fd}"
                       "output{font-size:20px}",
        },
        "fail": ("mix.html", "Pause", "Resume", "audio-transport-text"),
        "unknown": ("mix.css", "output{font-size:20px}",
                    "output{font-size:20px;filter:blur(1px)}", "audio-meter-text"),
    },
    "document-reader": {
        "count": 9,
        "vendor_engine": True,
        "root": "#document",
        "witnesses": ["#document > aside", "#document > div > h1"],
        "roles": {"chapters": "aside", "chapter-title": "h1", "folio": ".page",
                  "bookmark": "b"},
        "entry": "document.html",
        "files": {
            "document.html": '<!doctype html><meta charset="utf-8"><title>TEST ONLY reader</title>'
                             '<link rel="stylesheet" href="document.css">'
                             '<section id="document"><aside>Sommaire</aside><div>'
                             '<h1>Lire ensemble</h1><footer><span class="page"></span>'
                             '<b></b></footer></div></section>'
                             '<script src="page.js"></script>',
            "document.css": "body{margin:12px;background:#101820;color:#eee;"
                            "font-family:monospace}"
                            "#document{display:flex;flex-direction:column;gap:12px}"
                            "aside{height:48px;background:#234}"
                            "h1{font:700 24px monospace;color:#eee}"
                            "b{display:inline-block;width:6px;height:10px;background:#9ab}",
            "page.js": "fetch('/page.json').then(r=>r.json()).then(d=>"
                       "document.querySelector('.page').textContent=d.folio)",
            "page.json": '{"folio":"12 / 48"}',
        },
        "fail": ("document.html", "Lire ensemble", "Un autre titre", "reader-chapter-text"),
        "unknown": ("document.css", "font:700 24px monospace;",
                    "filter:blur(1px);font:700 24px monospace;", "reader-chapter-text"),
    },
}
MIMES = {".html": "text/html", ".css": "text/css", ".js": "text/javascript",
         ".json": "application/json"}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(
    os.environ.get("SERVO_STATIC_WORKFLOW_TESTS") == "1",
    "explicit clean producer and frozen runtime required",
)
class PublicWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get("SERVO_STATIC_PRODUCER"):
            raise AssertionError(
                "SERVO_STATIC_PRODUCER must explicitly select the clean dependency",
            )
        cls.producer = Path(os.environ["SERVO_STATIC_PRODUCER"]).resolve()
        cls.source_cut = os.environ.get("SERVO_STATIC_SOURCE_CUT")
        prefix = subprocess.run(
            ["git", "-C", str(cls.producer), "rev-parse", "--show-prefix"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        for name, expected in app.PRODUCER_PINS.items():
            text = (cls.producer / name).read_text()
            if any(retired in text for retired in ("import approved_card", "import capture_card")):
                raise AssertionError("producer closure contains a retired component import")
            actual = app.bundle.file_hash(cls.producer / name)
            if actual != expected:
                raise AssertionError(f"unsealed/different producer {name}: {actual} != {expected}")
            if cls.source_cut:
                committed = subprocess.run(
                    ["git", "-C", str(cls.producer), "show", cls.source_cut + ":" + prefix + name],
                    capture_output=True, check=True,
                ).stdout
                if app.bundle.raw(committed) != expected:
                    raise AssertionError("producer differs from explicit committed cut: " + name)
        if not (sys.flags.isolated and sys.dont_write_bytecode):
            raise AssertionError("run the selected isolated Python with -I -B")
        cls.consumer = load_module(
            "static_workflow_consumer", ROOT / "skills/quality-gate/gate_consumer.py",
        )

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name).resolve()
        self.env = dict(os.environ)
        self.env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + self.env["PATH"]
        self.env["XDG_STATE_HOME"] = str(self.work / "state")

    def cli(self, script, *args, expected=0, env=None):
        result = subprocess.run(
            [sys.executable, "-I", "-B", str(script), *map(str, args)],
            cwd=self.work, env=self.env if env is None else env,
            capture_output=True, text=True, timeout=300,
        )
        self.assertEqual(result.returncode, expected, result.stderr[-6000:])
        return result

    def source_cli(self, *args, expected=0, producer=None):
        # Source CLI's real module entrypoint; isolated bootstrap, no shim module.
        result = subprocess.run([
            sys.executable, "-I", "-B", "-c",
            "import sys;sys.path.insert(0,sys.argv[1]);import confirmed_source;"
            "raise SystemExit(confirmed_source.main(sys.argv[2:]))",
            str(self.producer if producer is None else producer), *map(str, args),
        ], cwd=self.work, env={
            **self.env, "SERVO_GATE_RUN_ID": str(uuid.uuid4()),
        }, capture_output=True, text=True, timeout=180)
        self.assertEqual(result.returncode, expected, result.stderr[-6000:])
        return result

    def overlay(self, operation, *args):
        if self.shape["vendor_engine"] and operation in ("generate", "install"):
            args = (*args, "--vendor-engine")
        return self.cli(
            ROOT / "skills/spec-oracle/oracle_overlay.py", operation,
            self.target, self.target / "spec", "static", *args,
        )

    def prepare_shape(self, label):
        shape = SHAPES[label]
        fixture = self.producer / "tests/fixtures/confirmed-source" / label
        self.original = self.work / "live-original"
        # NON-Git isolated original: later dependency commits cannot stale it.
        shutil.copytree(fixture / "source", self.original)
        self.assertFalse((self.original / ".git").exists())
        draft, package = self.work / "draft", self.work / "approved-source"
        self.source_cli("preview", "--source-root", self.original, "--manifest",
                        fixture / "manifest.json", "--out", draft)
        document = app.bundle.load(draft / "input.json")
        self.assertEqual(len(document["core"]["inventory"]), shape["count"])
        approval = app.bundle.load(draft / "approval-template.json")
        approval.update(
            reviewer="SYNTHETIC TEST ONLY independent source reviewer",
            independent=True, decision="approve",
            reason="SYNTHETIC TEST ONLY fixture, never application approval",
        )
        review = self.work / "TEST-ONLY-source-approval.json"
        app.bundle.publish(review, approval)
        self.source_cli("finalize", "--draft", draft, "--approval", review, "--out", package)
        self.source_cli("verify", "--package", package)
        self.source_cli("consumer-check", "--package", package, "--result-root",
                        "source-check/{run_id}/input")
        self.target = self.work / "target"
        self.target.mkdir()
        self.cli(ROOT / "skills/scaffold-init/scaffold.py", self.target)
        oracle = self.target / "oracle.sh"
        text = oracle.read_text().replace(
            "COMPONENTS=(\n", 'COMPONENTS=(\n  "quality:1"\n',
        ).replace(
            'weighted_sum="0"',
            "# SEED:start quality\nscore_quality() { echo 1.0; }\n# SEED:end quality\n"
            'weighted_sum="0"',
        )
        oracle.write_text(text)
        bindings = self.work / "bindings.json"
        app.bundle.publish(bindings, {
            "root": shape["root"], "document_witnesses": shape["witnesses"],
            "elements": shape["roles"],
        })
        prepare = (
            HERE / "static_contract.py", "prepare", "--target", self.target,
            "--package", package, "--producer-root", self.producer,
            "--bindings", bindings, "--browser-root", self.env["PLAYWRIGHT_BROWSERS_PATH"],
        )
        existing = self.target / "spec/static.md"
        existing.parent.mkdir(parents=True)
        existing.write_bytes(b"SYNTHETIC TEST ONLY existing project specification\n")
        refused = self.cli(*prepare, expected=2)
        self.assertIn("destination", refused.stderr)
        self.assertEqual(
            existing.read_bytes(), b"SYNTHETIC TEST ONLY existing project specification\n",
        )
        for path in ("spec/oracle/static", "tools/static", "design-input"):
            self.assertFalse((self.target / path).exists())
        existing.unlink()
        prepared = self.cli(*prepare)
        self.policy_path = self.target / "spec/oracle/static/app-policy.json"
        self.policy = app.bundle.load(self.policy_path)
        self.assertEqual(json.loads(prepared.stdout)["status"],
                         "pending-independent-review-not-installed")
        self.assertEqual(set(self.policy["runtime"]["module_origins"]),
                         {"playwright", "greenlet", "pyee", "typing_extensions"})
        self.assertEqual(
            {row["path"].removeprefix(str(self.target / "tools/static") + "/")
             for row in self.policy["evaluator_files"]},
            {*app.HELPERS, *("producer/" + name for name in app.PRODUCER_PINS),
             "runtime-files.json", "browser-membership.json"},
        )
        policy_review = self.work / "TEST-ONLY-policy-review.json"
        app.bundle.publish(policy_review, {
            "verdict": "pass", "author": "SYNTHETIC TEST ONLY policy author",
            "reviewer": "SYNTHETIC TEST ONLY independent policy reviewer",
            "policy_hash": app.policy_hash(self.policy),
            "claim": "SYNTHETIC TEST ONLY; no application approval or success claim",
        })
        self.cli(self.helper, "approve", "--policy", self.policy_path, "--review", policy_review)
        for operation in ("generate", "approve"):
            self.overlay(operation)
        self.overlay("install", "--enable-required", "--weight", "0")
        # Final driver seal through ordinary regeneration/reapproval/install.
        plan_path = self.policy_path.with_name("checks.json")
        plan = app.bundle.load(plan_path)
        for check in plan["checks"]:
            check["evaluator_artifacts"].append("oracle.sh")
        plan_path.write_bytes(app.bundle.canonical(plan) + b"\n")
        driver = oracle.read_bytes()
        for operation in ("generate", "approve"):
            self.overlay(operation)
        self.overlay("install", "--enable-required", "--weight", "0")
        self.assertEqual(oracle.read_bytes(), driver)
        if self.shape["vendor_engine"]:
            self.assertTrue((self.policy_path.parent / "checks.py").is_file())
            self.assertTrue((self.policy_path.parent / "required_runtime.py").is_file())
        self.assertFalse((self.target / ".servo/gate-runs").exists())
        self.select_snapshot(shape["files"])
        return document

    @property
    def helper(self):
        return self.target / "tools/static/static_contract.py"

    def select_snapshot(self, files):
        name = "candidate-" + str(uuid.uuid4())
        source, build = self.target / name, self.target / (name + "-build")
        source.mkdir()
        for filename, body in files.items():
            (source / filename).write_text(body)
        shape = self.shape
        app.bundle.publish(source / "candidate.json", {
            "schema_version": 1, "kind": "static_snapshot_candidate",
            "entry": "/" + shape["entry"], "metadata": [],
            "resources": [{"url": "/" + filename, "path": filename,
                           "content_type": MIMES[Path(filename).suffix]}
                          for filename in sorted(files)],
        })
        self.cli(self.target / "tools/static/static_snapshot.py",
                 "build", "--source", source, "--out", build)
        delivery = self.target / (name + "-delivery")
        shutil.copytree(build / "output", delivery)
        (self.target / "candidate-selection.json").write_bytes(app.bundle.canonical({
            "build": build.name, "delivery": delivery.name,
        }) + b"\n")
        self.cli(self.target / "tools/static/static_snapshot.py",
                 "verify", "--build", build, "--delivery", delivery)
        self.delivery = delivery

    def gate(self, expected):
        run, environment = self.consumer.request(self.target)
        result = self.cli(
            ROOT / "skills/quality-gate/gate.py", self.target, "--json",
            expected=expected, env={**self.env, **environment, "THRESHOLD": "0"},
        )
        payload = self.consumer.parse(result.stdout)
        accepted = self.consumer.accept(self.target, payload, expected, run)
        self.assertNotIn("consumer_error", accepted)
        self.assertEqual(accepted["exit_code"], expected)
        self.assertEqual(accepted["oracle"], payload)
        return accepted

    def pure_read(self, record):
        forbidden = AssertionError("preserved reader attempted execution/acquisition/comparison")
        with (
            patch("subprocess.run", side_effect=forbidden),
            patch("subprocess.Popen", side_effect=forbidden),
            patch.object(app, "acquire", side_effect=forbidden),
            patch.object(app, "compare", side_effect=forbidden),
        ):
            return self.consumer.read(self.target, record)

    def check_shape(self, label):
        self.shape = SHAPES[label]
        document = self.prepare_shape(label)
        if label == "audio-routing":
            self.changed_source_epoch_cannot_be_installed(label)
        baseline = self.gate(0)
        self.assertEqual(baseline["required"]["status"], "pass")
        self.assertEqual(self.pure_read(baseline), baseline)
        self.assertEqual(self.pure_read(baseline), baseline)
        envelope = (self.target / "spec/oracle/static/runs" / baseline["run_id"]
                    / "observed/evidence.json")
        self.cli(self.helper, "verify-current", "--policy", self.policy_path,
                 "--envelope", envelope)
        # Independent CURRENT delivery drift, without changing candidate/build.
        entry = self.delivery / self.shape["entry"]
        saved = entry.read_bytes()
        entry.write_bytes(saved + b"\n<!-- independent delivery drift -->")
        self.cli(self.helper, "verify-current", "--policy", self.policy_path,
                 "--envelope", envelope, expected=2)
        self.gate(2)
        entry.write_bytes(saved)
        # LIVE original-source drift is separate from delivery selection.
        original = self.original / document["core"]["manifest"]["source"]["entry"]
        saved = original.read_bytes()
        original.write_bytes(saved + b"\n<!-- live original drift -->")
        self.source_cli("verify", "--package", self.target / "design-input", expected=2)
        self.cli(self.helper, "verify-current", "--policy", self.policy_path,
                 "--envelope", envelope, expected=2)
        self.gate(2)
        original.write_bytes(saved)
        # New source-tool bytes invalidate the old source approval epoch.
        tools = self.target / "tools/static/producer"
        tool = tools / "design_input.py"
        saved = tool.read_bytes()
        tool.write_bytes(saved + b"\n# SYNTHETIC TEST ONLY tooling drift\n")
        refused = self.source_cli(
            "verify", "--package", self.target / "design-input", expected=2, producer=tools,
        )
        self.assertIn("runtime-identity", refused.stderr)
        refused_epoch = self.work / "refused-tooling-epoch"
        self.source_cli(
            "finalize", "--draft", self.work / "draft",
            "--approval", self.work / "TEST-ONLY-source-approval.json",
            "--out", refused_epoch, expected=2, producer=tools,
        )
        self.assertFalse(refused_epoch.exists())
        self.gate(2)
        tool.write_bytes(saved)
        # Output tamper refuses pure native read without replacing the original.
        capture = envelope.with_name("app.png")
        saved = capture.read_bytes()
        capture.write_bytes(saved + b"tamper")
        refused = self.pure_read(baseline)
        self.assertEqual(refused["exit_code"], 2)
        self.assertEqual(refused["oracle"], baseline["oracle"])
        self.assertEqual(refused["gate_ref"], baseline["gate_ref"])
        self.assertIn("consumer_error", refused)
        capture.write_bytes(saved)
        self.assertEqual(self.pure_read(baseline), baseline)
        for variant, code in (("fail", 1), ("unknown", 2)):
            filename, before, after, identity = self.shape[variant]
            files = dict(self.shape["files"])
            self.assertIn(before, files[filename])
            files[filename] = files[filename].replace(before, after)
            self.select_snapshot(files)
            verdict = self.gate(code)
            quality = next(row for row in verdict["components"] if row["component"] == "quality")
            self.assertEqual(quality["score"], 1.0)
            if code == 1:
                self.assertEqual(verdict["composite"], 1.0)
            self.assertEqual(verdict["threshold"], 0.0)
            self.assertIn(identity, verdict["required"]["failed" if code == 1 else "unknown"])
            self.assertEqual(self.pure_read(verdict), verdict)
        if os.environ.get("SERVO_STATIC_WORKFLOW_OUTPUT"):
            self.retain_clean_epoch(label)

    def changed_source_epoch_cannot_be_installed(self, label):
        # A genuine separately approved packet from different tooling must not
        # become installable merely because the new inspector can read it.
        tools = self.work / "alternate-source-tools"
        tools.mkdir()
        for name in app.PRODUCER_PINS:
            shutil.copyfile(self.producer / name, tools / name)
        module = tools / "design_input.py"
        module.write_bytes(
            module.read_bytes() + b"\n# SYNTHETIC TEST ONLY different writer epoch\n",
        )
        draft, package = self.work / "alternate-draft", self.work / "alternate-package"
        self.source_cli(
            "preview", "--source-root", self.original, "--manifest",
            self.producer / "tests/fixtures/confirmed-source" / label / "manifest.json",
            "--out", draft, producer=tools,
        )
        approval = app.bundle.load(draft / "approval-template.json")
        approval.update(
            reviewer="SYNTHETIC TEST ONLY alternate-epoch reviewer", independent=True,
            decision="approve", reason="SYNTHETIC TEST ONLY; not application approval",
        )
        review = self.work / "TEST-ONLY-alternate-source-approval.json"
        app.bundle.publish(review, approval)
        self.source_cli(
            "finalize", "--draft", draft, "--approval", review, "--out", package, producer=tools,
        )
        self.source_cli("verify", "--package", package, producer=tools)
        target = self.work / "alternate-epoch-target"
        target.mkdir()
        self.cli(ROOT / "skills/scaffold-init/scaffold.py", target)
        result = self.cli(
            HERE / "static_contract.py", "prepare", "--target", target,
            "--package", package, "--producer-root", self.producer,
            "--bindings", self.work / "bindings.json",
            "--browser-root", self.env["PLAYWRIGHT_BROWSERS_PATH"], expected=2,
        )
        self.assertIn("source tooling approval epoch", result.stderr)
        self.assertFalse((target / "spec/oracle/static/app-policy.json").exists())
        self.assertFalse((target / ".servo/required-policy.json").exists())

    def retain_clean_epoch(self, label):
        # Negative controls above are disposable. This is a distinct fresh
        # source approval/policy/install/run; never mutate its positive target.
        output = Path(os.environ["SERVO_STATIC_WORKFLOW_OUTPUT"]).resolve()
        output.mkdir(parents=True, exist_ok=True)
        self.work = output / (label + "-TESTONLY-" + str(uuid.uuid4()))
        self.work.mkdir()
        self.env["XDG_STATE_HOME"] = str(self.work / "state")
        self.prepare_shape(label)
        request, environment = self.consumer.request(self.target)
        command = [
            sys.executable, "-I", "-B", str(ROOT / "skills/quality-gate/gate.py"),
            str(self.target), "--json",
        ]
        app.bundle.publish(self.work / "consumer-request.json", {
            "run_id": request, "environment": environment, "command": command,
            "claim": "PROVISIONAL SYNTHETIC TEST ONLY; not application approval",
        })
        result = self.cli(
            ROOT / "skills/quality-gate/gate.py", self.target, "--json",
            env={**self.env, **environment, "THRESHOLD": "0"},
        )
        payload = self.consumer.parse(result.stdout)
        accepted = self.consumer.accept(self.target, payload, result.returncode, request)
        self.assertEqual(accepted["exit_code"], 0)
        self.assertNotIn("consumer_error", accepted)
        readback = self.pure_read(accepted)
        self.assertEqual(readback, accepted)
        app.bundle.publish(self.work / "native-gate-stdout.json", payload)
        app.bundle.publish(self.work / "consumer-accepted.json", accepted)
        app.bundle.publish(self.work / "consumer-read.json", readback)
        code_paths = [
            ROOT / ".claude-plugin/install-contract.json", ROOT / "README.md",
            *(path for directory in ("skills", "templates", "agents", "scripts")
              for path in sorted((ROOT / directory).rglob("*"))
              if path.is_file() and "__pycache__" not in path.parts
              and not path.name.endswith(".pyc")),
        ]
        code = [{"path": path.relative_to(ROOT).as_posix(),
                 "hash": app.bundle.file_hash(path)} for path in code_paths]
        servo_head = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        source_head = subprocess.run(
            ["git", "-C", str(self.producer), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        envelope = self.target / "spec/oracle/static/runs" / request / "observed/evidence.json"
        app.bundle.publish(self.work / "handoff.json", {
            "claim": "SYNTHETIC TEST ONLY; no application approval; Servo code uncommitted",
            "source_helper_root": str(self.producer),
            "source_cut_verified": self.source_cut,
            "source_head_observed": source_head,
            "source_helper_hashes": app.PRODUCER_PINS,
            "servo_head": servo_head,
            "servo_working_tree_code": code,
            "servo_working_tree_digest": app.bundle.identity("servo-test-code-v1", code),
            "target": str(self.target), "policy": str(self.policy_path),
            "live_original_root": str(self.original),
            "approved_source": str(self.target / "design-input"),
            "gate_ref": accepted["gate_ref"],
            "envelope": {"path": str(envelope), "hash": app.bundle.file_hash(envelope)},
            "artifacts": [
                {"path": str(path), "hash": app.bundle.file_hash(path)}
                for path in sorted(self.work.rglob("*"))
                if path.is_file() and "__pycache__" not in path.parts
            ],
        })
        print(f"TESTONLY retained handoff: {self.work / 'handoff.json'}")

    def test_audio_routing_public_workflow(self):
        self.check_shape("audio-routing")

    def test_document_reader_public_workflow(self):
        self.check_shape("document-reader")


@unittest.skipUnless(
    os.environ.get("SERVO_STATIC_READER_TARGET"),
    "explicit retained clean TESTONLY target required",
)
class CurrentReaderTests(unittest.TestCase):
    def test_current_reader_only_queries_fixed_metadata_without_evaluation(self):
        target = Path(os.environ["SERVO_STATIC_READER_TARGET"]).resolve()
        record = app.bundle.load(target.parent / "consumer-accepted.json")
        envelope = (target / "spec/oracle/static/runs" / record["run_id"]
                    / "observed/evidence.json")
        code = """
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.pycache_prefix = os.path.join(tempfile.gettempdir(), "servo-read-" + str(os.getpid()))
sys.path.insert(0, sys.argv[1])
import static_contract as app

policy = app.bundle.load(sys.argv[2])
source = app.bundle.load(Path(policy["source"]["root"]) / "input.json")["core"]["origin"]["root"]
allowed = {
    ("uname", "-p"),
    ("file", "-b", platform._follow_symlinks(sys.executable)),
    ("git", "-C", source, "rev-parse", "HEAD"),
}
commands = []
run, popen = subprocess.run, subprocess.Popen

def guard(command, options):
    if options.get("shell", False) or tuple(command) not in allowed:
        raise AssertionError("non-metadata command: " + repr(command))
    commands.append(tuple(command))

def metadata_run(command, *args, **kwargs):
    guard(command, kwargs)
    return run(command, *args, **kwargs)

def metadata_popen(command, *args, **kwargs):
    guard(command, kwargs)
    return popen(command, *args, **kwargs)

platform.invalidate_caches()
forbidden = AssertionError("current reader acquired/evaluated/compared")
with (
    patch("subprocess.run", side_effect=metadata_run),
    patch("subprocess.Popen", side_effect=metadata_popen),
    patch.object(app, "acquire", side_effect=forbidden),
    patch.object(app, "evaluate", side_effect=forbidden),
    patch.object(app, "compare", side_effect=forbidden),
):
    app.validate_current(sys.argv[2], sys.argv[3])
    for invalid in (["uname", "-a"], ["git", "-C", source, "status"]):
        try:
            metadata_run(invalid)
        except AssertionError:
            pass
        else:
            raise AssertionError("arbitrary command accepted")
if set(commands) != allowed:
    raise AssertionError("expected uncached metadata queries: " + repr(commands))
"""
        result = subprocess.run([
            sys.executable, "-I", "-B", "-c", code, str(target / "tools/static"),
            str(target / "spec/oracle/static/app-policy.json"), str(envelope),
        ], capture_output=True, text=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr[-4000:])


if __name__ == "__main__":
    unittest.main()
