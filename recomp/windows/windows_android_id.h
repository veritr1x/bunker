#pragma once
#include <functional>
#include <optional>
#include <string>
namespace bunker::windows {
// Read only HKCU64 Software\Bunker\Apps\<package>\SecureSettings\android_id.
// Missing key/value is nullopt. Every other failure is explicit. This never
// creates, derives, migrates or manufactures an Android/device identifier.
std::function<std::optional<std::u16string>()> MakeWindowsAndroidIdReader(std::u16string package);
}
