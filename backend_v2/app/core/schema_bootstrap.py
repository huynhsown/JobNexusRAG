from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def bootstrap_schema(conn: AsyncConnection, logger: logging.Logger) -> None:
    """
    Apply idempotent schema upgrades for existing deployments.

    The project currently relies on `create_all()` and has no Alembic migrations,
    so existing tables need explicit `ALTER TABLE` statements during startup.
    """
    if conn.dialect.name != "postgresql":
        logger.warning(
            "Schema bootstrap only applies PostgreSQL-specific ALTER statements; "
            "skipping extra bootstrap for dialect=%s",
            conn.dialect.name,
        )
        return

    statements = [
        """
        ALTER TABLE candidates
        ADD COLUMN IF NOT EXISTS source_candidate_id BIGINT,
        ADD COLUMN IF NOT EXISTS open_to_work BOOLEAN
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_candidates_source_candidate_id
        ON candidates (source_candidate_id)
        WHERE source_candidate_id IS NOT NULL
        """,
        """
        ALTER TABLE candidate_cvs
        ADD COLUMN IF NOT EXISTS source_cv_id BIGINT,
        ADD COLUMN IF NOT EXISTS title VARCHAR(255),
        ADD COLUMN IF NOT EXISTS is_searchable BOOLEAN NOT NULL DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS content_hash VARCHAR(255)
        """,
        """
        ALTER TABLE candidate_cvs
        ALTER COLUMN filename DROP NOT NULL,
        ALTER COLUMN original_filename DROP NOT NULL,
        ALTER COLUMN file_type DROP NOT NULL,
        ALTER COLUMN file_size DROP NOT NULL
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_candidate_cvs_source_cv_id
        ON candidate_cvs (source_cv_id)
        WHERE source_cv_id IS NOT NULL
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_candidate_cvs_one_searchable_per_candidate
        ON candidate_cvs (candidate_id)
        WHERE is_searchable = TRUE
        """,
        """
        ALTER TABLE companies
        ADD COLUMN IF NOT EXISTS source_company_id BIGINT
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_companies_source_company_id
        ON companies (source_company_id)
        WHERE source_company_id IS NOT NULL
        """,
        """
        ALTER TABLE job_postings
        ADD COLUMN IF NOT EXISTS source_job_id BIGINT
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_job_postings_source_job_id
        ON job_postings (source_job_id)
        WHERE source_job_id IS NOT NULL
        """,
        """
        ALTER TABLE job_applications
        ADD COLUMN IF NOT EXISTS source_application_id BIGINT,
        ADD COLUMN IF NOT EXISTS candidate_cv_id INTEGER,
        ADD COLUMN IF NOT EXISTS cv_resolution_status VARCHAR(50)
        """,
        """
        UPDATE job_applications
        SET cv_resolution_status = 'pending_cv_resolution'
        WHERE cv_resolution_status IS NULL
        """,
        """
        ALTER TABLE job_applications
        ALTER COLUMN cv_resolution_status SET DEFAULT 'pending_cv_resolution',
        ALTER COLUMN cv_resolution_status SET NOT NULL
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_job_applications_source_application_id
        ON job_applications (source_application_id)
        WHERE source_application_id IS NOT NULL
        """,
        """
        ALTER TABLE match_results
        ADD COLUMN IF NOT EXISTS candidate_cv_id INTEGER,
        ADD COLUMN IF NOT EXISTS application_id INTEGER,
        ADD COLUMN IF NOT EXISTS mode VARCHAR(50),
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE
        """,
        """
        UPDATE match_results
        SET mode = 'candidate_find_jobs'
        WHERE mode IS NULL
        """,
        """
        UPDATE match_results
        SET updated_at = created_at
        WHERE updated_at IS NULL
        """,
        """
        ALTER TABLE match_results
        ALTER COLUMN mode SET DEFAULT 'candidate_find_jobs',
        ALTER COLUMN mode SET NOT NULL,
        ALTER COLUMN updated_at SET DEFAULT NOW(),
        ALTER COLUMN updated_at SET NOT NULL
        """,
    ]

    for statement in statements:
        await conn.execute(text(statement))

    constraint_blocks = [
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_job_applications_candidate_cv_id'
            ) THEN
                ALTER TABLE job_applications
                ADD CONSTRAINT fk_job_applications_candidate_cv_id
                FOREIGN KEY (candidate_cv_id)
                REFERENCES candidate_cvs(id)
                ON DELETE SET NULL;
            END IF;
        END $$;
        """,
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_match_results_candidate_cv_id'
            ) THEN
                ALTER TABLE match_results
                ADD CONSTRAINT fk_match_results_candidate_cv_id
                FOREIGN KEY (candidate_cv_id)
                REFERENCES candidate_cvs(id)
                ON DELETE SET NULL;
            END IF;
        END $$;
        """,
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_match_results_application_id'
            ) THEN
                ALTER TABLE match_results
                ADD CONSTRAINT fk_match_results_application_id
                FOREIGN KEY (application_id)
                REFERENCES job_applications(id)
                ON DELETE SET NULL;
            END IF;
        END $$;
        """,
    ]

    for statement in constraint_blocks:
        await conn.execute(text(statement))

    logger.info("Schema bootstrap completed")
