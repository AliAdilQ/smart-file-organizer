"""Category defaults and validated destination names."""
import re
from pathlib import PurePosixPath
from app.extensions import db
from app.models import OrganizationRule

DEFAULTS = {
    'Images': '.jpg .jpeg .png .gif .webp .svg .bmp .tiff',
    'Documents': '.pdf .doc .docx .txt .rtf .odt',
    'Spreadsheets': '.xls .xlsx .csv',
    'Presentations': '.ppt .pptx',
    'Videos': '.mp4 .mkv .avi .mov .wmv .webm',
    'Audio': '.mp3 .wav .flac .aac .ogg .m4a',
    'Archives': '.zip .rar .7z .tar .gz',
    'Applications': '.exe .msi .apk .dmg .deb',
    'Code': '.py .js .html .css .java .cpp .c .php .json .xml .sql',
    'Ebooks': '.epub .mobi',
    'Other': '',
}
MODES = {'type': 'File type', 'extension': 'Extension', 'year': 'Year',
         'month': 'Year & month', 'size': 'File size'}


def validate_destination(value):
    value = value.strip().replace('\\', '/')
    parts = PurePosixPath(value).parts
    reserved = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)),
                *(f'lpt{i}' for i in range(1, 10))}
    if (not value or len(value) > 240 or value.startswith('/') or
            any(p in ('..', '.') or not re.fullmatch(r'[\w -]+', p) or
                p.endswith(' ') or p.split('.')[0].lower() in reserved for p in parts)):
        raise ValueError('Destination must be a relative folder name, e.g. University/Notes.')
    return '/'.join(parts)


def normalize_extensions(value):
    parts = value.lower().replace(',', ' ').split()
    normalized = sorted(set(p if p.startswith('.') else '.' + p for p in parts))
    if not normalized or any(not re.fullmatch(r'\.[a-z0-9]{1,16}', p) for p in normalized):
        raise ValueError('Enter extensions such as .pdf, .docx. At least one is required.')
    if len(' '.join(normalized)) > 512:
        raise ValueError('Too many extensions.')
    return ' '.join(normalized)


def seed_defaults():
    for name, extensions in DEFAULTS.items():
        if not OrganizationRule.query.filter_by(user_id=None, name=name).first():
            db.session.add(OrganizationRule(name=name, extensions=extensions, destination=name, priority=1000))
    db.session.commit()


def available_rules(user_id):
    return OrganizationRule.query.filter(
        (OrganizationRule.user_id == user_id) | (OrganizationRule.user_id.is_(None)),
        OrganizationRule.is_active.is_(True)
    ).order_by(OrganizationRule.priority, OrganizationRule.user_id.desc(), OrganizationRule.id).all()


def classify(path, rules, mode, stat):
    from datetime import datetime
    category, destination = 'Other', 'Other'
    for rule in rules:
        if path.suffix.lower() in rule.extensions.split():
            category, destination = rule.name, validate_destination(rule.destination)
            break
    date = datetime.fromtimestamp(stat.st_mtime)
    if mode == 'extension':
        extension = path.suffix.lower().lstrip('.')
        destination = extension if re.fullmatch(r'[a-z0-9]{1,16}', extension) else 'No extension'
    elif mode == 'year':
        destination += '/' + str(date.year)
    elif mode == 'month':
        destination += '/' + str(date.year) + '/' + date.strftime('%B')
    elif mode == 'size':
        size = stat.st_size
        destination = next(label for limit, label in ((1024**2, 'Tiny'), (10*1024**2, 'Small'),
                           (100*1024**2, 'Medium'), (1024**3, 'Large'), (float('inf'), 'Very Large')) if size < limit)
    return category, destination
