"""Compatibility re-export — detectors now live in ``detection.slide_window``.

Kept so older pickled ``saved_fits`` (module path ``frontend.slide_window``) still load.
"""

from detection.slide_window import *  # noqa: F403
