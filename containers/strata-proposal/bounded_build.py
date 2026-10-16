"""Unexecuted build proposal: one explicit compiler job, no retry or model setup."""
import json
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    root = Path('/opt/strata')
    sys.path.insert(0, str(root))
    import setup  # Only in a separately approved future builder, never in host tests.
    if setup.source_version() != '0.1.44.1':
        raise RuntimeError('Unexpected Strata source version')
    if setup.LLAMA_CPP_COMMIT != '3cf03257f219afbe7334045ff7c6a06ac68c627d':
        raise RuntimeError('Unexpected llama.cpp source identity')
    llama = setup.get_llama_cpp()
    nvcc, _ = setup.find_nvcc()
    cmake, ninja = setup.find_tool('cmake'), setup.find_tool('ninja')
    if not all((cmake, ninja, nvcc)):
        raise RuntimeError('Missing pinned build tools')
    build = root / 'build'
    subprocess.run([cmake, '-G', 'Ninja', f'-DCMAKE_MAKE_PROGRAM={ninja}',
                    '-S', str(root), '-B', str(build), '-DCMAKE_BUILD_TYPE=Release',
                    '-DSTRATA_ENABLE_CUDA=ON', '-DSTRATA_BUILD_TESTS=OFF',
                    '-DCMAKE_CUDA_ARCHITECTURES=86', f'-DCMAKE_CUDA_COMPILER={nvcc}',
                    f'-DSTRATA_GGML_DIR={llama}'], check=True)
    # Do not call setup.cmake_build: it explicitly supplies more than one job and retries.
    subprocess.run([cmake, '--build', str(build), '--target', 'strata', '--parallel', '1'], check=True)
    engine = root / 'engine'
    engine.mkdir(exist_ok=True)
    shutil.copy2(build / setup.EXE, engine / setup.EXE)
    if (build / setup.KQ_LIB).exists():
        shutil.copy2(build / setup.KQ_LIB, engine / setup.KQ_LIB)
    metadata = {'source': 'local', 'version': setup.source_version(), 'archs': [86], 'vision': 'none',
                'src': setup.source_hash(setup.ENGINE_SOURCES), 'vision_src': None,
                'cuda_dirs': [str(Path(nvcc).parent), '/usr/local/cuda/lib64']}
    (engine / 'BUILD.json').write_text(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    main()
