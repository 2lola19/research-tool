import sys

from workers.review_worker.main import run

run(
    run_once="--once" in sys.argv[1:],
    recover_expired="--recover-expired" in sys.argv[1:],
)
