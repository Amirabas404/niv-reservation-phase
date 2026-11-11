from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JobRun


async def claim_job(session: AsyncSession, run_key: str, job_name: str) -> bool:
    """True only for the first caller of this run_key. The claim commits or rolls back with the job,
    so a failed job is retried on the next tick instead of being silently skipped."""
    result = await session.execute(
        insert(JobRun).values(run_key=run_key, job_name=job_name)
        .on_conflict_do_nothing(index_elements=["run_key"])
        .returning(JobRun.id)
    )
    return result.scalar_one_or_none() is not None
