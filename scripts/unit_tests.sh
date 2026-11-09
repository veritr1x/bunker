#!/usr/bin/env bash
# The release's unit tests, in one place: release.yml and pages.yml run them in CI and
# scripts/release.py before it tags. Needs scripts/requirements-notices.txt and, for the
# Deck Builder page in a browser, scripts/requirements-web-tests.txt with Playwright's
# Chromium (those tests skip without it). PYTHON picks the interpreter (default python3).
set -euo pipefail
cd "$(dirname "$0")/.."
py=${PYTHON:-python3}
(cd scripts && "$py" -m unittest test_version test_release test_release_assets test_notices test_sync_notice_prices test_history_runs test_tower_floors test_audit_notices test_audit_summon_links test_build_remaining_summon_notices test_build_summon_notice_repair_pack test_native_notice_costume_bonus test_notice_event_bonuses test_notice_fidelity test_notice_icons test_notice_templates test_rich_notice_content)
(cd android/tools && "$py" -m unittest test_privacy test_update_apk test_build_info test_notice_pack test_master_patch test_assemble_stream test_client_days test_bunker_button test_game_regions test_deck_builder_page)
(cd ios/tools && "$py" -m unittest test_ipa_stream test_sign_ipa test_release_updater)
(cd web && "$py" -m unittest test_build_site)
# The release notes: CHANGELOG.md has a section for VERSION.
"$py" -c "import sys; sys.path.insert(0, 'scripts'); import release_assets; release_assets.changelog_section(open('CHANGELOG.md').read(), open('VERSION').read().strip())"
