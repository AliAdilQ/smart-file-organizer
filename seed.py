from app import create_app
from app.demo import seed_demo

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        summary = seed_demo()
    print('Development demo data ready. See README.md for credentials.')
    print('Dataset:', ', '.join(f'{value} {name}' for name, value in summary.items()))
