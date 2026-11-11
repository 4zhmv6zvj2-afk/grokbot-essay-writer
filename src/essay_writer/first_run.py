"""First-run glue for an uploaded copy: the public facade.

The stage-3 split keeps the behaviour and the importable entry points here
while the implementation lives in four modules along the existing seams:

- ``first_run_install``: unpack an uploaded zip, verify its optional checksum,
  run the hash-pinned install, and install the consent-gated Cursor CLI.
- ``first_run_host``: write and enable the Cursor/Grok Build MCP config.
- ``first_run_mac``: the friend's Mac handoff folder and deliverable copies.
- ``first_run_cli``: argument parsing, usage text, and ``main``.

This module re-exports the names production code and tests import from
``essay_writer.first_run``. It is a facade, not a second implementation: every
name below is the real function or constant from its owning module.
"""

from __future__ import annotations

from essay_writer.first_run_cli import main
from essay_writer.first_run_common import first_run_prompt, package_root
from essay_writer.first_run_host import (
    attach_build_mcp,
    attach_custom_mcp,
    enable_build_mcp,
    enable_mcp_server,
    expose_writer_on_path,
    grok_config_home,
    mcp_launch_command,
    mcp_template,
    render_server_table,
    repo_bot_share,
    resolve_build_config,
    resolve_user_config,
    write_bot_share,
)
from essay_writer.first_run_install import (
    CURSOR_AGENT_INSTALL_URL,
    CURSOR_AGENT_MANUAL_INSTALL,
    CURSOR_INSTALL_HASH_MISMATCH,
    CURSOR_INSTALL_NEEDS_CONSENT,
    CURSOR_INSTALL_NEEDS_HASH,
    CURSOR_INSTALL_SHA256_ENV,
    cursor_install_consent,
    ensure_cursor_agent,
    install_self_check,
    install_uploaded_copy,
)
from essay_writer.first_run_mac import (
    DELIVERABLE_SUFFIXES,
    MAC_DELIVERABLES_NAME,
    MAC_FOUR_WAY_CARD,
    MAC_FOUR_WAY_FRIEND_SPEECH,
    UPGRADE_REREAD_MARKER,
    UPGRADE_REREAD_SPEECH,
    attach_friend_upgrade_fo_card,
    choose_mac_handoff,
    copy_deliverable_to_mac,
    ensure_sequence_mac_folder,
    friend_mac_home,
    mac_deliverables_dir,
    mac_deliverables_record,
    module_mac_deliverables_dir,
    module_shared_mac_deliverables_dir,
    read_mac_handoff_dir,
    recommended_mac_handoff_dir,
    remember_mac_handoff_dir,
    sequence_mac_candidates,
    sequence_mac_deliverables_dir,
    sequence_mac_handoff_place,
    upgrade_reread_tip_sha,
    visible_canonical_mac_handoff_dir,
)

__all__ = [
    # CLI and install entry points.
    "main",
    "install_uploaded_copy",
    "install_self_check",
    "ensure_cursor_agent",
    "cursor_install_consent",
    "CURSOR_AGENT_INSTALL_URL",
    "CURSOR_AGENT_MANUAL_INSTALL",
    "CURSOR_INSTALL_HASH_MISMATCH",
    "CURSOR_INSTALL_NEEDS_CONSENT",
    "CURSOR_INSTALL_NEEDS_HASH",
    "CURSOR_INSTALL_SHA256_ENV",
    # Host config and attach.
    "attach_build_mcp",
    "attach_custom_mcp",
    "enable_build_mcp",
    "enable_mcp_server",
    "expose_writer_on_path",
    "grok_config_home",
    "mcp_launch_command",
    "mcp_template",
    "render_server_table",
    "repo_bot_share",
    "resolve_build_config",
    "resolve_user_config",
    "write_bot_share",
    # Mac handoff helpers and their stable constants.
    "DELIVERABLE_SUFFIXES",
    "MAC_DELIVERABLES_NAME",
    "MAC_FOUR_WAY_CARD",
    "MAC_FOUR_WAY_FRIEND_SPEECH",
    "UPGRADE_REREAD_MARKER",
    "UPGRADE_REREAD_SPEECH",
    "attach_friend_upgrade_fo_card",
    "choose_mac_handoff",
    "copy_deliverable_to_mac",
    "ensure_sequence_mac_folder",
    "friend_mac_home",
    "mac_deliverables_dir",
    "mac_deliverables_record",
    "module_mac_deliverables_dir",
    "module_shared_mac_deliverables_dir",
    "read_mac_handoff_dir",
    "recommended_mac_handoff_dir",
    "remember_mac_handoff_dir",
    "sequence_mac_candidates",
    "sequence_mac_deliverables_dir",
    "sequence_mac_handoff_place",
    "upgrade_reread_tip_sha",
    "visible_canonical_mac_handoff_dir",
    # Shared path and prompt helpers.
    "first_run_prompt",
    "package_root",
]


if __name__ == "__main__":
    raise SystemExit(main())
