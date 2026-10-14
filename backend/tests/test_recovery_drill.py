import importlib.util
from pathlib import Path
import zipfile
import pytest

spec = importlib.util.spec_from_file_location('recovery_drill', Path(__file__).parents[1] / 'scripts/recovery_drill.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


def test_attachment_roundtrip_and_existing_target_refused(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'attachment.txt').write_text('Synthetic attachment', encoding='utf-8')
    archive = tmp_path / 'files.zip'
    recovery.archive_files(source, archive)
    target = tmp_path / 'restored'
    recovery.restore_files(archive, target)
    assert recovery.digest(source / 'attachment.txt') == recovery.digest(target / 'attachment.txt')
    with pytest.raises(ValueError, match='must not exist'):
        recovery.restore_files(archive, target)


@pytest.mark.parametrize('member', ['../escaped.txt', '/absolute.txt', 'C:/escaped.txt', 'a/../../escaped.txt'])
def test_restore_rejects_traversal_before_writing(tmp_path, member):
    archive = tmp_path / 'bad.zip'
    with zipfile.ZipFile(archive, 'w') as f:
        f.writestr(member, 'unsafe')
    with pytest.raises(ValueError, match='Unsafe'):
        recovery.restore_files(archive, tmp_path / 'restored')
    assert not (tmp_path / 'restored').exists()


def test_backup_cannot_write_inside_source(tmp_path):
    with pytest.raises(ValueError, match='outside source'):
        recovery.archive_files(tmp_path, tmp_path / 'files.zip')


def test_failed_recovery_validation_survives_optimized_python():
    import subprocess
    import sys
    script = str(Path(recovery.__file__).resolve())
    code = (
        'import runpy; '
        f'module = runpy.run_path({script!r}); '
        'module["require_equal"]("corrupt", "expected", "injected corruption")'
    )
    result = subprocess.run([sys.executable, '-O', '-c', code], capture_output=True, text=True)
    assert result.returncode != 0
    assert 'Recovery verification failed: injected corruption' in result.stderr


def test_successful_recovery_validation():
    recovery.require_equal('matching', 'matching', 'same value')
