"""coach/ is the domain (lessons, practice, analysis); server/ is the web layer on top. coach never depends on it."""

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB_LAYER = ("server", "fastapi", "starlette", "uvicorn", "pydantic")


def test_coach_does_not_import_the_web_layer():
    for path in sorted((ROOT / "coach").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                assert name.split(".")[0] not in WEB_LAYER, f"{path.name} imports {name}"


def test_coach_loads_without_the_web_layer():
    code = ("import sys; sys.path.insert(0, r'%s'); import coach.run, coach.capture, coach.analyze, coach.vocab, "
            "coach.lessons, coach.insights, coach.db, coach.importer, coach.accounts, coach.__main__; "
            "print(','.join(m for m in %r if m in sys.modules))") % (ROOT, WEB_LAYER)
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == ""
