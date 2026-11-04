"""Four specialists. A stage calls one of these. It does not keep a second copy.

Grok Bot speaks to the client. Writer drafts and writes Word. Researcher
gathers and annotates. EQR reviews. The spine decides which one a stage calls.
"""

from __future__ import annotations

ROLES = ("grok_bot", "writer", "researcher", "eqr")
