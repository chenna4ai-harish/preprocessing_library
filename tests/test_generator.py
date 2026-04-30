from __future__ import annotations

import os
import unittest
from pathlib import Path

import preprocessing_library.generator as gen


class TestGenerator(unittest.TestCase):
    def test_list_templates_default_resolves(self) -> None:
        templates = gen.list_templates()
        self.assertIn("file_union", templates)
        self.assertIn("file_split_by_value", templates)

    def test_generate_preprocessor_default_dirs(self) -> None:
        module_dir = Path(gen.__file__).resolve().parent

        script_name = "__test_generated_preprocessor.py"
        out_path: Path | None = None

        # Avoid tempfile on some locked-down Windows environments (it may create
        # directories that are not accessible). Use a deterministic workspace dir.
        workspace_root = Path(__file__).resolve().parents[1]
        cwd_dir = workspace_root / "__test_cwd_dir__"
        cwd_dir.mkdir(parents=True, exist_ok=True)

        old_cwd = os.getcwd()
        os.chdir(cwd_dir)
        try:
            out_path = Path(
                gen.generate_preprocessor(
                    template_name="file_split_by_value",
                    parameters={
                        "SPLIT_COLUMN": "Status",
                        "OUTPUT_DIR": "./output",
                        "OUTPUT_FORMAT": "csv",
                        "FILENAME_TEMPLATE": "{split_column}_{value}.csv",
                        "INCLUDE_SPLIT_COLUMN": "True",
                    },
                    output_script_name=script_name,
                )
            )
        finally:
            os.chdir(old_cwd)
            # Best-effort cleanup: leave the folder if something else used it.
            try:
                cwd_dir.rmdir()
            except OSError:
                pass

        self.assertIsNotNone(out_path)
        assert out_path is not None
        self.assertTrue(out_path.is_file(), f"Expected file to exist: {out_path}")
        self.assertEqual(out_path.name, script_name)
        self.assertEqual(out_path.parent.resolve(), (module_dir / "generated_scripts").resolve())

        # Cleanup (generated scripts should be transient)
        out_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
