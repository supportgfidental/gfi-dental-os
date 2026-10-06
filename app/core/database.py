from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./gfi_dental.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_multitenant_schema():
    """Create the clinics table and backfill existing records into one clinic."""
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE IF NOT EXISTS clinics ("
            "id INTEGER PRIMARY KEY, "
            "name VARCHAR NOT NULL, "
            "registered_mobile VARCHAR, "
            "license_number VARCHAR, "
            "issuing_council VARCHAR, "
            "verification_status VARCHAR NOT NULL DEFAULT 'PENDING', "
            "subscription_status VARCHAR NOT NULL DEFAULT 'active', "
            "created_at DATETIME)"
        ))
        clinic_columns = {
            column["name"] for column in inspect(connection).get_columns("clinics")
        }
        if "registered_mobile" not in clinic_columns:
            connection.execute(text("ALTER TABLE clinics ADD COLUMN registered_mobile VARCHAR"))
        if "operating_hours" not in clinic_columns:
            connection.execute(text("ALTER TABLE clinics ADD COLUMN operating_hours TEXT"))
        if "scheduling_context" not in clinic_columns:
            connection.execute(text("ALTER TABLE clinics ADD COLUMN scheduling_context TEXT"))
        if "license_number" not in clinic_columns:
            connection.execute(text("ALTER TABLE clinics ADD COLUMN license_number VARCHAR"))
        if "issuing_council" not in clinic_columns:
            connection.execute(text("ALTER TABLE clinics ADD COLUMN issuing_council VARCHAR"))
        if "verification_status" not in clinic_columns:
            connection.execute(text(
                "ALTER TABLE clinics ADD COLUMN verification_status VARCHAR "
                "NOT NULL DEFAULT 'PENDING'"
            ))
        connection.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_clinics_registered_mobile "
            "ON clinics (registered_mobile)"
        ))
        clinic_id = connection.execute(
            text("SELECT id FROM clinics ORDER BY id LIMIT 1")
        ).scalar()
        if clinic_id is None:
            connection.execute(
                text(
                    "INSERT INTO clinics (name, subscription_status, created_at) "
                    "VALUES (:name, 'active', CURRENT_TIMESTAMP)"
                ),
                {"name": "GFI Dental OS Clinic"},
            )
            clinic_id = connection.execute(
                text("SELECT id FROM clinics ORDER BY id LIMIT 1")
            ).scalar()

        inspector = inspect(connection)
        existing_tables = set(inspector.get_table_names())
        if "users" in existing_tables:
            user_columns = {column["name"] for column in inspector.get_columns("users")}
            user_additions = {
                "license_number": "VARCHAR",
                "issuing_council": "VARCHAR",
                "verification_status": "VARCHAR NOT NULL DEFAULT 'PENDING'",
                "license_certificate_path": "VARCHAR",
            }
            for column_name, column_type in user_additions.items():
                if column_name not in user_columns:
                    connection.execute(text(
                        f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"
                    ))
        connection.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_clinics_license_number "
            "ON clinics (license_number)"
        ))
        if "users" in existing_tables:
            connection.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_license_number "
                "ON users (license_number)"
            ))
        for table_name in ("users", "patients", "appointments", "treatment_plans"):
            if table_name not in existing_tables:
                continue
            columns = {column["name"] for column in inspector.get_columns(table_name)}
            if "clinic_id" not in columns:
                connection.execute(text(
                    f"ALTER TABLE {table_name} "
                    "ADD COLUMN clinic_id INTEGER REFERENCES clinics(id)"
                ))
            connection.execute(
                text(f"UPDATE {table_name} SET clinic_id = :clinic_id WHERE clinic_id IS NULL"),
                {"clinic_id": clinic_id},
            )
        timestamp_inspector = inspect(connection)
        for table_name in ("appointments", "treatment_plans"):
            if table_name not in existing_tables:
                continue
            columns = {column["name"] for column in timestamp_inspector.get_columns(table_name)}
            if "updated_at" not in columns:
                connection.execute(text(
                    f"ALTER TABLE {table_name} ADD COLUMN updated_at DATETIME"
                ))
                connection.execute(text(
                    f"UPDATE {table_name} SET updated_at = CURRENT_TIMESTAMP "
                    "WHERE updated_at IS NULL"
                ))


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()