import re

from app.config import REPO_ROOT

CONFIG = (REPO_ROOT / "backend" / "app" / "config.py").read_text()


def env_names(path):
    if not path.exists():
        return None
    return set(re.findall(r"^([A-Z][A-Z0-9_]*)=", path.read_text(), re.MULTILINE))


def test_env_example_lists_every_setting_config_reads():
    read = set(re.findall(r'os\.getenv\("([A-Z0-9_]+)"', CONFIG))
    assert read <= env_names(REPO_ROOT / ".env.example"), "add the missing setting to .env.example"


def test_local_env_has_the_same_settings_as_the_example():
    local = env_names(REPO_ROOT / ".env")
    if local is None:  # .env is gitignored, so absent on CI
        return
    assert local == env_names(REPO_ROOT / ".env.example")
