from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import bounded_build


class BoundedBuildTests(unittest.TestCase):
    def test_missing_sources_fail_before_any_upstream_code_or_command(self):
        with tempfile.TemporaryDirectory() as folder:
            setup = SimpleNamespace(source_version=Mock())
            with patch.dict(sys.modules, {'setup': setup}), patch.object(bounded_build.subprocess, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'will not fetch replacements'):
                    bounded_build.main(Path(folder))
                setup.source_version.assert_not_called()
                run.assert_not_called()

    def test_staged_source_uses_no_download_helper_and_one_compiler_job(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'third_party/llama.cpp/ggml').mkdir(parents=True)
            (root / 'third_party/llama.cpp/gguf-py').mkdir()
            (root / 'CMakeLists.txt').write_text('synthetic source')
            (root / 'third_party/llama.cpp/ggml/CMakeLists.txt').write_text('synthetic ggml')
            (root / 'build').mkdir()
            (root / 'build/strata').write_bytes(b'synthetic output, not executable')
            setup = SimpleNamespace(source_version=lambda: '0.1.44.1',
                LLAMA_CPP_COMMIT='3cf03257f219afbe7334045ff7c6a06ac68c627d',
                find_nvcc=lambda: ('/synthetic/cuda/nvcc', None), find_tool=lambda name: '/synthetic/' + name,
                EXE='strata', KQ_LIB='strata_kq.so', ENGINE_SOURCES=[], source_hash=lambda _: 'synthetic')
            # No get_llama_cpp method exists: an accidental download fallback fails.
            original_path = sys.path[:]
            try:
                with patch.dict(sys.modules, {'setup': setup}), patch.object(bounded_build.subprocess, 'run') as run:
                    bounded_build.main(root)
                    self.assertEqual(run.call_count, 2)
                    self.assertIn('-DSTRATA_GGML_DIR=' + str(root / 'third_party/llama.cpp'), run.call_args_list[0].args[0])
                    self.assertEqual(run.call_args_list[1].args[0][-2:], ['--parallel', '1'])
            finally:
                sys.path[:] = original_path


if __name__ == '__main__':
    unittest.main()
