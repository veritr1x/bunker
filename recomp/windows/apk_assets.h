#pragma once
#include <cstdint>
#include <filesystem>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

namespace bunker::windows {
class AssetError : public std::runtime_error {
 public:
  enum Kind { NotFound, InvalidArchive, Unsupported, Integrity, IO };
  AssetError(Kind kind, const std::string &message) : std::runtime_error(message), kind(kind) {}
  Kind kind;
};

// Reads actual APK ZIP members; never extracts files or executes archive data.
// Names are relative to assets/, case sensitive, with no traversal components.
class ApkAssets {
 public:
  explicit ApkAssets(std::filesystem::path apk);
  std::vector<uint8_t> Read(const std::string &name) const;
 private:
  struct Entry {
    uint32_t offset, compressed, size, crc;
    uint16_t method, flags;
    std::string zip_name;
  };
  std::vector<uint8_t> Bytes(uint64_t offset, uint64_t count) const;
  std::filesystem::path apk_;
  uint64_t file_size_ = 0, directory_ = 0;
  std::map<std::string, Entry> entries_;
};
}  // namespace bunker::windows
