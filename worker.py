"""Run exactly one worker process; --once is suitable for an OS task scheduler."""
import argparse
import time
from app import create_app
from app.scheduler import run_due


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    app = create_app()
    try:
        while True:
            with app.app_context():
                run_due()
            if args.once:
                break
            time.sleep(30)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
