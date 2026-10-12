"""Backfill `jobs.language` for postings stored before language detection existed.

Only rows where `language` is NULL are touched, so a language already detected is never
overwritten. A posting with too little text stays NULL ("Not detected" in the feed) and is
simply looked at again on the next run. Run the dry pass first and read the counts.

    python -m backend.scripts.backfill_job_language            # dry run
    python -m backend.scripts.backfill_job_language --commit   # write
"""
import argparse
import collections
import logging
import sys

from backend.analyzer.language import detect_job_language
from backend.models.db import Job, SessionLocal

logger = logging.getLogger("jobnavigator.backfill.language")

BATCH = 500


def run(commit: bool = False, limit: int | None = None) -> dict:
    """Detect the language of every job that has none. Returns the tally per language."""
    db = SessionLocal()
    tally: collections.Counter = collections.Counter()
    try:
        query = db.query(Job.id).filter(Job.language.is_(None)).order_by(Job.discovered_at)
        if limit:
            query = query.limit(limit)

        # ids first, rows per batch: a commit inside a server-side cursor loop
        # invalidates the cursor on Postgres ("named cursor isn't valid anymore")
        ids = [row[0] for row in query.all()]
        for start in range(0, len(ids), BATCH):
            chunk = ids[start:start + BATCH]
            for job in db.query(Job).filter(Job.id.in_(chunk)).all():
                tally["scanned"] += 1
                language = detect_job_language(job.title, job.description)
                if language is None:
                    tally["undetected"] += 1
                    continue
                tally[language] += 1
                if commit:
                    job.language = language
            if commit:
                db.commit()
            else:
                db.expunge_all()
    finally:
        db.close()

    return dict(tally)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", action="store_true",
                        help="write the results; without it nothing is saved")
    parser.add_argument("--limit", type=int, default=None,
                        help="stop after this many jobs")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    tally = run(commit=args.commit, limit=args.limit)

    logger.info("COMMIT" if args.commit else "DRY RUN — nothing written")
    logger.info("scanned    %d", tally.pop("scanned", 0))
    logger.info("undetected %d  -> left NULL", tally.pop("undetected", 0))
    for language, count in sorted(tally.items(), key=lambda kv: -kv[1]):
        logger.info("  %-9s %d", language, count)
    return 0


if __name__ == "__main__":
    sys.exit(main())
