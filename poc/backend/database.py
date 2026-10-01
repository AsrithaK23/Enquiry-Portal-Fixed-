from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()
        # create_all() does not add columns to an existing SQLite database.
        connection = db.engine.connect()
        try:
            for table, column in (
                ("enquiries", "thread_key"),
                ("conversation_threads", "thread_key"),
                ("email_logs", "message_id"),
            ):
                columns = {row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({table})")}
                if column not in columns:
                    connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} VARCHAR(255)")
            connection.commit()
        finally:
            connection.close()
        print("[Database] Database tables initialized.")
