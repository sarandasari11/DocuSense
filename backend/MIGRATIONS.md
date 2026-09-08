# Database migrations

Production deployments use Alembic for schema changes. Run commands from the `backend` directory with the target `DATABASE_URL` available in the environment.

```powershell
python -m alembic upgrade head
```

Create a new migration after changing the SQLModel schema:

```powershell
python -m alembic revision --autogenerate -m "describe the schema change"
```

Development and test environments may still use `init_db()` to create tables automatically. Production startup does not call `create_all()`, so migrations must run before the application starts.
