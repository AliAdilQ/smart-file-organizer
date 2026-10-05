"""Check that portfolio documentation references real local artifacts."""
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_local_links_and_screenshot_dimensions():
    content = (ROOT / 'README.md').read_text(encoding='utf-8')
    for target in re.findall(r'\]\(([^)]+)\)', content):
        if target.startswith(('https://', 'http://', '#')):
            continue
        assert (ROOT / target.split('#')[0]).is_file(), target
    screenshots = re.findall(r'!\[[^\]]*\]\((docs/screenshots/[^)]+\.png)\)', content)
    assert len(set(screenshots)) == 9
    for target in screenshots:
        data = (ROOT / target).read_bytes()
        assert data[:8] == b'\x89PNG\r\n\x1a\n'
        assert struct.unpack('>II', data[16:24]) == (1440, 900)
        assert len(data) > 20_000


def test_readme_identity_credentials_and_complete_tree():
    content = (ROOT / 'README.md').read_text(encoding='utf-8')
    assert 'git clone https://github.com/AliAdilQ/smart-file-organizer.git' in content
    assert 'https://github.com/AliAdilQ)' in content
    before, credentials = content.split('## Demo Credentials', 1)
    credentials, after = credentials.split('## Organization Rules', 1)
    passwords = re.findall(r'\| `([^`]+)` \|\s*$', credentials, re.MULTILINE)
    assert len(passwords) == 6
    for password in set(passwords):
        assert password not in before + after
        for path in ROOT.glob('**/*.py'):
            if any(part in {'.venv', 'venv', 'instance'} for part in path.parts):
                continue
            assert password not in path.read_text(encoding='utf-8'), str(path)
    tree = content.split('<!-- PROJECT_TREE_START -->', 1)[1].split('<!-- PROJECT_TREE_END -->', 1)[0]
    assert 'schema.py' in tree and 'test_readme.py' in tree
    for placeholder in ('YOUR_USERNAME', 'yourusername', 'your-repository', 'Lorem ipsum'):
        assert placeholder not in content
