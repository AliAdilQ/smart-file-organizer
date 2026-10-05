"""Additive upgrade for the existing v1 schedule table.

Only these known columns are migrated; no existing data is replaced. A general
migration tool is still recommended for future schema changes.
"""
from sqlalchemy import inspect, text
from app.extensions import db


def initialize_database():
    db.create_all()
    columns = {column['name'] for column in inspect(db.engine).get_columns('scheduled_task')}
    additions = {
        'name': "VARCHAR(120) NOT NULL DEFAULT 'Organization routine'",
        'is_demo': 'BOOLEAN NOT NULL DEFAULT false',
    }
    with db.engine.begin() as connection:
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(text(f'ALTER TABLE scheduled_task ADD COLUMN {name} {definition}'))
