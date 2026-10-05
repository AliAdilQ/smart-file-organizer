"""Generate text fixtures with representative extensions, never overwrite files."""
from pathlib import Path

FILES = ['assignment.pdf', 'resume.docx', 'budget.xlsx', 'presentation.pptx', 'vacation.jpg',
         'profile.png', 'tutorial.mp4', 'song.mp3', 'backup.zip', 'script.py', 'unknown.xyz']


def generate():
    folder = Path(__file__).resolve().parent / 'demo_files' / 'sample_downloads'
    folder.mkdir(parents=True, exist_ok=True)
    for filename in FILES:
        path = folder / filename
        try:
            with path.open('x', encoding='utf-8') as handle:
                handle.write('SFO TEST FILE. Dummy text, not a real document or media file.\n')
        except FileExistsError:
            pass
    return folder


if __name__ == '__main__':
    print(f'Safe dummy files generated in: {generate()}')
