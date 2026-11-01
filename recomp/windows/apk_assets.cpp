#include "apk_assets.h"
#include <algorithm>
#include <fstream>
#include <limits>
#include <zlib.h>

namespace bunker::windows {
namespace {
uint16_t U16(const uint8_t *p) { return uint16_t(p[0]) | uint16_t(p[1]) << 8; }
uint32_t U32(const uint8_t *p) { return uint32_t(U16(p)) | uint32_t(U16(p + 2)) << 16; }
[[noreturn]] void Invalid(const char *message) { throw AssetError(AssetError::InvalidArchive, message); }
bool AssetName(const std::string &name) {
  if (name.empty() || name.front() == '/' || name.back() == '/' || name.find('\\') != std::string::npos || name.find('\0') != std::string::npos) return false;
  size_t start = 0;
  while (start < name.size()) {
    const size_t end = name.find('/', start);
    const auto part = name.substr(start, end == std::string::npos ? end : end - start);
    if (part.empty() || part == "." || part == "..") return false;
    if (end == std::string::npos) break;
    start = end + 1;
  }
  return true;
}
}  // namespace

std::vector<uint8_t> ApkAssets::Bytes(uint64_t offset, uint64_t count) const {
  if (offset > file_size_ || count > file_size_ - offset ||
      offset > static_cast<uint64_t>(std::numeric_limits<std::streamoff>::max()) ||
      count > static_cast<uint64_t>(std::numeric_limits<std::streamsize>::max())) Invalid("ZIP range exceeds APK");
  std::ifstream file(apk_, std::ios::binary);
  if (!file) throw AssetError(AssetError::IO, "cannot open APK");
  std::vector<uint8_t> result(static_cast<size_t>(count));
  file.seekg(static_cast<std::streamoff>(offset));
  if (count && !file.read(reinterpret_cast<char *>(result.data()), static_cast<std::streamsize>(count))) throw AssetError(AssetError::IO, "short APK read");
  return result;
}

ApkAssets::ApkAssets(std::filesystem::path apk) : apk_(std::move(apk)) {
  std::error_code error;
  file_size_ = std::filesystem::file_size(apk_, error);
  if (error) throw AssetError(AssetError::IO, "cannot determine APK size");
  if (file_size_ < 22) Invalid("APK lacks ZIP directory");
  const uint64_t tail_offset = file_size_ > 65557 ? file_size_ - 65557 : 0;
  const auto tail = Bytes(tail_offset, file_size_ - tail_offset);
  size_t end = tail.size();
  for (size_t i = tail.size() - 22;; --i) {
    const auto p = tail.data() + i;
    if (U32(p) == 0x06054b50 && i + 22 + U16(p + 20) == tail.size()) {
      const uint32_t span = U32(p + 12), start = U32(p + 16);
      // Do not mistake an EOCD-looking sequence inside a ZIP comment for the
      // actual directory. ZIP64 is diagnosed separately below.
      if (span == 0xffffffff || start == 0xffffffff ||
          (start <= tail_offset + i && span == tail_offset + i - start)) { end = i; break; }
    }
    if (!i) break;
  }
  if (end == tail.size()) Invalid("ZIP end record is absent or truncated");
  const auto e = tail.data() + end;
  if (U16(e + 4) || U16(e + 6) || U16(e + 8) != U16(e + 10)) throw AssetError(AssetError::Unsupported, "split ZIP archives are unsupported");
  const uint16_t count = U16(e + 10);
  const uint32_t length = U32(e + 12);
  directory_ = U32(e + 16);
  if (count == 0xffff || length == 0xffffffff || directory_ == 0xffffffff) throw AssetError(AssetError::Unsupported, "ZIP64 directory is unsupported");
  if (directory_ > tail_offset + end || length != tail_offset + end - directory_) Invalid("invalid ZIP directory span");
  const auto directory = Bytes(directory_, length);
  size_t position = 0;
  for (uint32_t index = 0; index < count; ++index) {
    if (directory.size() - position < 46 || U32(directory.data() + position) != 0x02014b50) Invalid("invalid ZIP directory entry");
    const auto p = directory.data() + position;
    const size_t name_size = U16(p + 28), extra = U16(p + 30), comment = U16(p + 32);
    const size_t record = 46 + name_size + extra + comment;
    if (record > directory.size() - position || U16(p + 34)) Invalid("invalid ZIP directory lengths or disk");
    const std::string name(reinterpret_cast<const char *>(p + 46), name_size);
    if (name.compare(0, 7, "assets/") == 0 && name.back() != '/') {
      const auto relative = name.substr(7);
      if (!AssetName(relative)) Invalid("invalid APK asset path");
      Entry entry{U32(p + 42), U32(p + 20), U32(p + 24), U32(p + 16), U16(p + 10), U16(p + 8), name};
      if (entry.offset == 0xffffffff || entry.compressed == 0xffffffff || entry.size == 0xffffffff) throw AssetError(AssetError::Unsupported, "ZIP64 asset is unsupported");
      if (!entries_.emplace(relative, std::move(entry)).second) Invalid("duplicate APK asset path");
    }
    position += record;
  }
  if (position != directory.size()) Invalid("ZIP directory count does not match its bytes");
}

std::vector<uint8_t> ApkAssets::Read(const std::string &name) const {
  if (!AssetName(name)) throw AssetError(AssetError::NotFound, "invalid relative asset name");
  const auto found = entries_.find(name);
  if (found == entries_.end()) throw AssetError(AssetError::NotFound, "APK asset not found: " + name);
  const auto &entry = found->second;
  if ((entry.flags & ~uint16_t(0x080e)) || (entry.method != 0 && entry.method != 8) ||
      (entry.method == 0 && (entry.flags & 6))) throw AssetError(AssetError::Unsupported, "unsupported APK asset flags/compression");
  const auto header = Bytes(entry.offset, 30);
  if (U32(header.data()) != 0x04034b50 || U16(header.data() + 6) != entry.flags || U16(header.data() + 8) != entry.method) Invalid("ZIP local/directory headers disagree");
  const uint16_t local_name = U16(header.data() + 26), extra = U16(header.data() + 28);
  const auto local = Bytes(uint64_t(entry.offset) + 30, local_name);
  if (std::string(local.begin(), local.end()) != entry.zip_name) Invalid("ZIP local asset name disagrees");
  if (!(entry.flags & 8) && (U32(header.data() + 14) != entry.crc || U32(header.data() + 18) != entry.compressed || U32(header.data() + 22) != entry.size)) Invalid("ZIP local asset sizes/CRC disagree");
  const uint64_t data_offset = uint64_t(entry.offset) + 30 + local_name + extra;
  if (data_offset > directory_ || entry.compressed > directory_ - data_offset) Invalid("ZIP asset overlaps its directory");
  const auto compressed = Bytes(data_offset, entry.compressed);
  if (entry.flags & 8) {
    const auto descriptor_offset = data_offset + entry.compressed;
    const auto descriptor = Bytes(descriptor_offset, std::min<uint64_t>(16, directory_ - descriptor_offset));
    const auto matches = [&](size_t start) {
      return descriptor.size() >= start + 12 && U32(descriptor.data() + start) == entry.crc &&
          U32(descriptor.data() + start + 4) == entry.compressed && U32(descriptor.data() + start + 8) == entry.size;
    };
    if (!matches(0) && !(descriptor.size() >= 16 && U32(descriptor.data()) == 0x08074b50 && matches(4))) Invalid("ZIP asset data descriptor disagrees");
  }
  std::vector<uint8_t> result;
  if (entry.method == 0) {
    if (entry.compressed != entry.size) Invalid("stored ZIP asset size disagrees");
    result = compressed;
  } else {
    result.resize(std::max<uint32_t>(entry.size, 1));
    z_stream stream{};
    if (inflateInit2(&stream, -MAX_WBITS) != Z_OK) throw AssetError(AssetError::IO, "cannot initialize ZIP inflater");
    struct End { z_stream &value; ~End() { inflateEnd(&value); } } end{stream};
    stream.next_in = const_cast<Bytef *>(compressed.data()); stream.avail_in = entry.compressed;
    stream.next_out = result.data(); stream.avail_out = static_cast<uInt>(result.size());
    const int status = inflate(&stream, Z_FINISH);
    if (status != Z_STREAM_END || stream.total_out != entry.size || stream.avail_in) throw AssetError(AssetError::Integrity, "ZIP asset deflate size/data mismatch");
    result.resize(entry.size);
  }
  const auto crc = static_cast<uint32_t>(crc32(0, result.data(), static_cast<uInt>(result.size())));
  if (crc != entry.crc) throw AssetError(AssetError::Integrity, "ZIP asset CRC mismatch");
  return result;
}
}  // namespace bunker::windows
