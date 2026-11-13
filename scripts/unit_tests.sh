#!/usr/bin/env bash
# The release's unit tests, in one place: release.yml and pages.yml run them in CI and
# scripts/release.py before it tags. Needs scripts/requirements-notices.txt and, for the
# Deck Builder page in a browser, scripts/requirements-web-tests.txt with Playwright's
# Chromium (those tests skip without it). PYTHON picks the interpreter (default python3).
set -euo pipefail
cd "$(dirname "$0")/.."
py=${PYTHON:-python3}
(cd scripts && "$py" -m unittest test_version test_build_jdk test_release test_release_assets test_notices test_sync_notice_prices test_history_runs test_tower_floors test_audit_notices test_audit_summon_links test_build_remaining_summon_notices test_build_summon_notice_repair_pack test_native_notice_costume_bonus test_notice_event_bonuses test_notice_fidelity test_notice_icons test_notice_templates test_rich_notice_content test_game_text test_master_text test_export_translations test_language_packs test_check_translations test_make_noto_subsets)
(cd android/tools && "$py" -m unittest test_privacy test_update_apk test_build_info test_notice_pack test_master_patch test_assemble_stream test_client_days test_bunker_button test_game_regions test_deck_builder_page test_build_signing test_bunker_language test_game_fonts test_info_icon_size test_bunker_text test_bunker_catalogue test_bunker_pseudo test_player_pages test_deckbuilder_text test_launcher_status test_sign_off test_bunker_text_java test_launcher_text test_auto_deploy test_battle_mods test_arena_points)
(cd ios/tools && "$py" -m unittest test_ipa_stream test_sign_ipa test_release_updater test_lt_text test_framework_build test_auto_deploy)
(cd web && "$py" -m unittest test_build_site)
# The release notes: CHANGELOG.md has a section for VERSION.
"$py" -c "import sys; sys.path.insert(0, 'scripts'); import release_assets; release_assets.changelog_section(open('CHANGELOG.md').read(), open('VERSION').read().strip())"
