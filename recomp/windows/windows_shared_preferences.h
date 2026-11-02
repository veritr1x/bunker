#pragma once
#include "android_shared_preferences.h"
#include <vector>
namespace bunker::windows {
// Explicit per-user/package namespace, independent of the game's CLI DataRoot:
// HKCU64 Software\Bunker\Apps\<package>\SharedPreferences, value per store.
// Construction does not open/create a key or read/write a value.
// Only canonical lowercase package spellings are supported, so Windows' case-
// insensitive registry cannot alias two accepted Android package identities.
SharedPreferencesBackend MakeWindowsSharedPreferencesBackend(std::u16string package);
// Versioned bounded wire format, exposed to allow independent malformed-input
// and persistent-backend tests without a second serializer implementation.
std::vector<uint8_t> EncodeSharedPreferencesSnapshot(const SharedPreferencesSnapshot&);
SharedPreferencesSnapshot DecodeSharedPreferencesSnapshot(const std::vector<uint8_t>&);
}
