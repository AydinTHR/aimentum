from app.db import get_engine


def test_engine_pings_before_handing_out_a_connection():
    """The pool must check a connection is alive before reusing it.

    Neon suspends an idle compute and Render sleeps the service, so pooled
    connections outlive the database that accepted them. This reads a private
    attribute on purpose: there is no public way to prove the flag reached the
    pool, and the alternative is trusting a keyword argument that would go
    unnoticed if it were deleted.
    """
    assert get_engine().pool._pre_ping is True
