#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace bunker::jni::string_codec_detail {
// Deliberately bounded Android-era standard-charset profile. This is ordinary
// UTF-8, not JNI modified UTF-8. Malformed replacement follows the JDK profile.
enum class Charset { Utf8, Utf16, Utf16BE, Utf16LE, Ascii, Latin1 };
inline std::optional<Charset> Find(const std::u16string &name) {
  std::string key;
  for (char16_t c : name) {
    if (c > 127) return {};
    key.push_back(static_cast<char>(c >= u'A' && c <= u'Z' ? c + 32 : c));
  }
  if (key == "utf-8" || key == "utf8") return Charset::Utf8;
  if (key == "utf-16" || key == "utf16" || key == "unicode" || key == "unicodebig") return Charset::Utf16;
  if (key == "utf-16be" || key == "unicodebigunmarked") return Charset::Utf16BE;
  if (key == "utf-16le" || key == "unicodelittleunmarked") return Charset::Utf16LE;
  if (key == "us-ascii" || key == "ascii") return Charset::Ascii;
  if (key == "iso-8859-1" || key == "iso8859_1" || key == "iso_8859_1" || key == "latin1") return Charset::Latin1;
  return {};
}
inline bool LegalName(const std::u16string &name) {
  if (name.empty()) return false;
  for (size_t i = 0; i < name.size(); ++i) {
    const auto c = name[i];
    if ((c >= u'a' && c <= u'z') || (c >= u'A' && c <= u'Z') || (c >= u'0' && c <= u'9')) continue;
    if (i && (c == u'-' || c == u'+' || c == u'.' || c == u':' || c == u'_')) continue;
    return false;
  }
  return true;
}
inline bool High(uint32_t c) { return c >= 0xd800 && c <= 0xdbff; }
inline bool Low(uint32_t c) { return c >= 0xdc00 && c <= 0xdfff; }
inline std::u16string Decode(const std::vector<uint8_t> &bytes, Charset charset) {
  std::u16string out;
  if (charset == Charset::Ascii || charset == Charset::Latin1) {
    for (auto c : bytes) out.push_back(charset == Charset::Ascii && c >= 128 ? char16_t{0xfffd} : static_cast<char16_t>(c));
    return out;
  }
  if (charset != Charset::Utf8) {
    bool little = charset == Charset::Utf16LE;
    size_t i = 0;
    if (charset == Charset::Utf16 && bytes.size() >= 2) {
      if (bytes[0] == 0xfe && bytes[1] == 0xff) i = 2;
      else if (bytes[0] == 0xff && bytes[1] == 0xfe) { little = true; i = 2; }
    }
    auto word = [&](size_t at) -> uint16_t { return little ? static_cast<uint16_t>(bytes[at] | (bytes[at + 1] << 8)) : static_cast<uint16_t>((bytes[at] << 8) | bytes[at + 1]); };
    while (i + 1 < bytes.size()) {
      auto c = word(i); i += 2;
      if (High(c)) {
        if (i + 1 < bytes.size() && Low(word(i))) { out.push_back(static_cast<char16_t>(c)); out.push_back(static_cast<char16_t>(word(i))); i += 2; }
        else { out.push_back(char16_t{0xfffd}); i += (bytes.size() - i >= 2 ? 2 : bytes.size() - i); }
      } else out.push_back(Low(c) ? char16_t{0xfffd} : static_cast<char16_t>(c));
    }
    if (i < bytes.size()) out.push_back(char16_t{0xfffd});
    return out;
  }
  size_t i = 0;
  while (i < bytes.size()) {
    const auto b = bytes[i];
    if (b < 128) { out.push_back(static_cast<char16_t>(b)); ++i; continue; }
    const unsigned n = b >= 0xc2 && b <= 0xdf ? 2 : b >= 0xe0 && b <= 0xef ? 3 : b >= 0xf0 && b <= 0xf4 ? 4 : 0;
    if (!n) { out.push_back(char16_t{0xfffd}); ++i; continue; }
    unsigned used = 1;
    uint32_t c = b & (n == 2 ? 31u : n == 3 ? 15u : 7u);
    while (used < n && i + used < bytes.size()) {
      const auto next = bytes[i + used];
      if ((next & 0xc0) != 0x80 || (used == 1 && ((b == 0xe0 && next < 0xa0) || (b == 0xf0 && next < 0x90) || (b == 0xf4 && next > 0x8f)))) break;
      c = (c << 6) | (next & 63u); ++used;
    }
    i += used;
    if (used != n || High(c) || Low(c)) { out.push_back(char16_t{0xfffd}); continue; }
    if (c <= 0xffff) out.push_back(static_cast<char16_t>(c));
    else { c -= 0x10000; out.push_back(static_cast<char16_t>(0xd800 + (c >> 10))); out.push_back(static_cast<char16_t>(0xdc00 + (c & 1023))); }
  }
  return out;
}
inline std::vector<uint8_t> Encode(const std::u16string &text, Charset charset) {
  std::vector<uint8_t> out;
  if (charset == Charset::Utf16 && !text.empty()) { out.push_back(0xfe); out.push_back(0xff); }
  auto word = [&](uint16_t c) {
    if (charset == Charset::Utf16LE) { out.push_back(static_cast<uint8_t>(c)); out.push_back(static_cast<uint8_t>(c >> 8)); }
    else { out.push_back(static_cast<uint8_t>(c >> 8)); out.push_back(static_cast<uint8_t>(c)); }
  };
  for (size_t i = 0; i < text.size(); ++i) {
    uint32_t c = text[i];
    bool malformed = false;
    if (High(c)) {
      if (i + 1 < text.size() && Low(text[i + 1])) { c = 0x10000 + ((c - 0xd800) << 10) + (text[++i] - 0xdc00); }
      else malformed = true;
    } else if (Low(c)) malformed = true;
    if (charset == Charset::Ascii || charset == Charset::Latin1) {
      out.push_back(!malformed && c <= (charset == Charset::Ascii ? 127u : 255u) ? static_cast<uint8_t>(c) : uint8_t{'?'});
    } else if (charset != Charset::Utf8) {
      if (malformed) word(0xfffd);
      else if (c <= 0xffff) word(static_cast<uint16_t>(c));
      else { c -= 0x10000; word(static_cast<uint16_t>(0xd800 + (c >> 10))); word(static_cast<uint16_t>(0xdc00 + (c & 1023))); }
    } else if (malformed) out.push_back('?');
    else if (c < 128) out.push_back(static_cast<uint8_t>(c));
    else if (c < 0x800) { out.push_back(static_cast<uint8_t>(0xc0 | (c >> 6))); out.push_back(static_cast<uint8_t>(0x80 | (c & 63))); }
    else if (c < 0x10000) { out.push_back(static_cast<uint8_t>(0xe0 | (c >> 12))); out.push_back(static_cast<uint8_t>(0x80 | ((c >> 6) & 63))); out.push_back(static_cast<uint8_t>(0x80 | (c & 63))); }
    else { out.push_back(static_cast<uint8_t>(0xf0 | (c >> 18))); out.push_back(static_cast<uint8_t>(0x80 | ((c >> 12) & 63))); out.push_back(static_cast<uint8_t>(0x80 | ((c >> 6) & 63))); out.push_back(static_cast<uint8_t>(0x80 | (c & 63))); }
  }
  return out;
}
}  // namespace bunker::jni::string_codec_detail
