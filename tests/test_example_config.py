"""The example configuration stays in step with the library: it must compile, and every name
it imports from macmage must exist. Importing it outright would register live hotkeys (and
collide with a running agent), so this checks the contract without the side effects."""
import ast
from pathlib import Path

import macmage

CFG = Path(__file__).parent.parent/'examples'/'config.py'


def test_example_config_compiles_and_imports_resolve():
    "Syntax holds, and every `from macmage import ...` name is real"
    tree = ast.parse(CFG.read_text(), str(CFG))
    names = [a.name for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module == 'macmage' for a in n.names]
    assert names, 'the example config no longer imports from macmage?'
    missing = [o for o in names if not hasattr(macmage, o)]
    assert not missing, f'example config imports names macmage does not export: {missing}'
