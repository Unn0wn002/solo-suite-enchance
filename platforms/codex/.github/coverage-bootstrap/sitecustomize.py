"""Start coverage in child Python processes only when CI opts in."""

try:
    import coverage
except ImportError:
    # The bootstrap is on PYTHONPATH while the hash-locked dependencies are
    # being installed.  It must be inert until coverage itself is available.
    pass
else:
    coverage.process_startup()
