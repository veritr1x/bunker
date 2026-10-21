import ast
import unittest

import build_site


class SiteFilesTest(unittest.TestCase):
    def test_every_local_import_is_published(self):
        published = {path for path in build_site.PYTHON if path.endswith(".py")}
        missing = []
        for path in sorted(published):
            folder = (build_site.ROOT / path).parent
            for node in ast.walk(ast.parse((build_site.ROOT / path).read_text())):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    module = folder / (name.split(".")[0] + ".py")
                    if module.exists():
                        relative = module.relative_to(build_site.ROOT).as_posix()
                        if relative not in published:
                            missing.append(f"{path} imports {relative}")
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
