"""Contract: every key reporting_service reads from `evaluation` must be a key that
TradingBrain.evaluate_opportunity actually returns. A mismatch silently stores NULL
(this hid technical/pattern/market/ml scores for every saved scan result)."""
import ast
import os

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _tree(rel):
    return ast.parse(open(os.path.join(ROOT, rel)).read())


def _func(tree, name):
    return next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == name)


def _returned_keys():
    fn = _func(_tree("core/trading_brain.py"), "evaluate_opportunity")
    dicts = [r.value for r in ast.walk(fn)
             if isinstance(r, ast.Return) and isinstance(r.value, ast.Dict)]
    assert dicts, "evaluate_opportunity has no dict return"
    return {k.value for d in dicts for k in d.keys if isinstance(k, ast.Constant)}


def _keys_read_by_saver():
    fn = _func(_tree("services/reporting_service.py"), "save_scan_result")
    keys = set()
    for n in ast.walk(fn):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "get" and isinstance(n.func.value, ast.Name)
                and n.func.value.id == "evaluation" and n.args
                and isinstance(n.args[0], ast.Constant)):
            keys.add(n.args[0].value)
    return keys


def test_saver_only_reads_keys_the_brain_returns():
    missing = _keys_read_by_saver() - _returned_keys()
    assert not missing, f"save_scan_result reads keys never returned: {sorted(missing)}"
