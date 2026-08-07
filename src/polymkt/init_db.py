"""Create the schema on the dev database.

The pytest fixtures create tables against the ``polymkt_test`` database
automatically, but nothing does this for the main ``polymkt`` dev database
that ``python -m polymkt.run`` writes to. Run this once (or any time the
schema changes) before starting the scheduler:

    python -m polymkt.init_db
"""

import logging

from polymkt.db.models import Base
from polymkt.db.session import engine

logger = logging.getLogger(__name__)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    Base.metadata.create_all(engine)
    logger.info("Schema created (or already present) on %s", engine.url)


if __name__ == "__main__":
    main()
