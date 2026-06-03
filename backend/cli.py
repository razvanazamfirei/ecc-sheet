"""Flask CLI command registration."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import click
from flask import Flask

from backend.anesthesia_sync import AnesthesiaSyncError, sync_anesthesia_stop_times
from backend.errors import APIError
from backend.imports.residents_csv import import_residents_csv_file
from backend.security import get_current_user


def register_cli_commands(
    app: Flask,
    *,
    ensure_runtime_schema: Callable[[], None],
    init_db: Callable[[], None],
) -> None:
    """Register Flask CLI commands on the application."""

    @app.cli.command("sync-anesthesia-stop-times")
    @click.option(
        "--start-date",
        required=True,
        type=click.DateTime(formats=["%Y-%m-%d"]),
        help="Start work date in YYYY-MM-DD format.",
    )
    @click.option(
        "--end-date",
        required=True,
        type=click.DateTime(formats=["%Y-%m-%d"]),
        help="End work date in YYYY-MM-DD format.",
    )
    @click.option(
        "--overwrite-existing",
        is_flag=True,
        help="Replace existing anesthesia stop times instead of only filling blanks.",
    )
    @click.option(
        "--dry-run",
        is_flag=True,
        help="Preview matching updates without writing to the database.",
    )
    def sync_anesthesia_stop_times_command(
        start_date,
        end_date,
        overwrite_existing: bool,
        dry_run: bool,
    ) -> None:
        """Sync anesthesia stop times from MSSQL into time-entry records."""
        try:
            ensure_runtime_schema()
            result = sync_anesthesia_stop_times(
                start_date=start_date.date(),
                end_date=end_date.date(),
                overwrite_existing=overwrite_existing,
                dry_run=dry_run,
                user=get_current_user(),
            )
        except AnesthesiaSyncError as exc:
            raise click.ClickException(str(exc)) from exc

        click.echo(result.summary())

    @app.cli.command("import-residents-csv")
    @click.option(
        "--path",
        "csv_path",
        required=True,
        type=click.Path(exists=True, dir_okay=False, path_type=Path),
        help="Path to the residents CSV bootstrap file.",
    )
    @click.option(
        "--dry-run",
        is_flag=True,
        help="Validate and preview resident changes without writing to the database.",
    )
    def import_residents_csv_command(csv_path: Path, dry_run: bool) -> None:
        """Import residents from a managed CSV file."""
        ensure_runtime_schema()
        try:
            result = import_residents_csv_file(
                csv_path,
                user=get_current_user(),
                dry_run=dry_run,
            )
        except APIError as exc:
            raise click.ClickException(str(exc)) from exc

        click.echo(result.summary())

    @app.cli.command("bootstrap-application")
    @click.option(
        "--residents-csv",
        type=click.Path(exists=True, dir_okay=False, path_type=Path),
        help="Optional residents CSV file to import after schema/default bootstrap.",
    )
    def bootstrap_application_command(residents_csv: Path | None) -> None:
        """Bootstrap schema, defaults, and optionally residents from CSV."""
        init_db()
        click.echo("Schema and default data bootstrapped.")

        if residents_csv is None:
            return

        try:
            result = import_residents_csv_file(
                residents_csv,
                user=get_current_user(),
                dry_run=False,
            )
        except APIError as exc:
            raise click.ClickException(str(exc)) from exc

        click.echo(result.summary())
