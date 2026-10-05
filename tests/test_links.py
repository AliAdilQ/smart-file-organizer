from html.parser import HTMLParser
from urllib.parse import urlsplit


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = set()

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for key, value in attrs:
                if key == 'href' and value and value.startswith('/'):
                    self.links.add(urlsplit(value).path)


def test_rendered_internal_links(client, login):
    login('admin')
    pending = {'/', '/dashboard', '/history', '/rules', '/schedules', '/statistics',
               '/profile', '/settings', '/organize/', '/admin/', '/admin/users',
               '/admin/rules', '/admin/logs', '/auth/forgot-password'}
    visited = set()
    while pending:
        path = pending.pop()
        if path in visited:
            continue
        visited.add(path)
        response = client.get(path, follow_redirects=True)
        assert response.status_code == 200, path
        parser = LinkParser()
        parser.feed(response.get_data(as_text=True))
        pending.update(parser.links - visited)
