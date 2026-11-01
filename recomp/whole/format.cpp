#include "format.h"
#include "guest_memory.h"
#include <cctype>
#include <cstdio>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <vector>

namespace recomp {
namespace {
template <typename T> T Read(uint64_t address) {
  if (!address) throw std::invalid_argument("null guest variadic argument address");
  T result;
  ReadGuestMemory(&result, address, sizeof(result));
  return result;
}
template <typename T> T Narrow(uint64_t bits) {
  T value;
  std::memcpy(&value, &bits, sizeof(value));
  return value;
}
template <typename T> std::string Render(const std::string &format, T value) {
  int size = std::snprintf(nullptr, 0, format.c_str(), value);
  if (size < 0) throw std::invalid_argument("host rejected guest format conversion");
  std::vector<char> buffer(static_cast<size_t>(size) + 1);
  if (std::snprintf(buffer.data(), buffer.size(), format.c_str(), value) != size)
    throw std::runtime_error("inconsistent formatted conversion length");
  return std::string(buffer.data(), static_cast<size_t>(size));
}
std::string Number(const char *&position) {
  const char *start = position;
  uint64_t value = 0;
  while (std::isdigit(static_cast<unsigned char>(*position))) {
    value = value * 10 + (*position++ - '0');
    if (value > static_cast<uint64_t>(std::numeric_limits<int>::max()))
      throw std::invalid_argument("guest format width or precision exceeds int");
  }
  return std::string(start, position);
}
std::string Pointer(uint64_t value, const std::string &flags,
                    const std::string &width, const std::string &precision) {
  // Bionic prefixes every pointer, including zero; host %p is platform-specific.
  size_t minimum = precision.empty() || precision == "." ? 0 : std::stoul(precision.substr(1));
  std::string digits = !value && !precision.empty() && !minimum ? "" :
      Render("%llx", static_cast<unsigned long long>(value));
  if (minimum > digits.size()) digits.insert(0, minimum - digits.size(), '0');
  std::string text = "0x" + digits;
  size_t field = width.empty() ? 0 : std::stoul(width);
  if (field > text.size()) {
    size_t pad = field - text.size();
    if (flags.find('-') != std::string::npos) text.append(pad, ' ');
    else if (precision.empty() && flags.find('0') != std::string::npos) text.insert(2, pad, '0');
    else text.insert(0, pad, ' ');
  }
  return text;
}
}  // namespace

VaArguments::VaArguments(const void *guest_list) {
  static_assert(sizeof(Layout) == 32);
  if (!guest_list) throw std::invalid_argument("null AAPCS64 va_list");
  ReadGuestMemory(&value_, reinterpret_cast<addr_t>(guest_list), sizeof(value_));
  if (value_.gr_offs > 0 || value_.gr_offs < -64 || value_.gr_offs % 8 ||
      value_.vr_offs > 0 || value_.vr_offs < -128 || value_.vr_offs % 16)
    throw std::invalid_argument("invalid AAPCS64 va_list register offsets");
  if ((value_.gr_offs < 0 && value_.gr_top < static_cast<uint64_t>(-value_.gr_offs)) ||
      (value_.vr_offs < 0 && value_.vr_top < static_cast<uint64_t>(-value_.vr_offs)))
    throw std::invalid_argument("invalid AAPCS64 va_list register save area");
}
uint64_t VaArguments::Stack() {
  if (!value_.stack || (value_.stack & 7) || value_.stack > UINT64_MAX - 8)
    throw std::invalid_argument("invalid AAPCS64 va_list stack pointer");
  auto result = value_.stack;
  value_.stack += 8;
  return result;
}
uint64_t VaArguments::Integer() {
  if (value_.gr_offs < 0) {
    auto address = value_.gr_top + static_cast<int64_t>(value_.gr_offs);
    value_.gr_offs += 8;
    return Read<uint64_t>(address);
  }
  return Read<uint64_t>(Stack());
}
double VaArguments::Floating() {
  if (value_.vr_offs < 0) {
    auto address = value_.vr_top + static_cast<int64_t>(value_.vr_offs);
    value_.vr_offs += 16;
    return Read<double>(address);
  }
  return Read<double>(Stack());
}

std::string Format(const char *format, FormatArguments args) {
  if (!format || !args.integer || !args.floating)
    throw std::invalid_argument("invalid guest format arguments");
  const auto format_snapshot = ReadGuestString(reinterpret_cast<addr_t>(format));
  std::string output;
  const char *position = format_snapshot.c_str();
  while (*position) {
    if (*position != '%') { output += *position++; continue; }
    ++position;
    if (*position == '%') { output += '%'; ++position; continue; }
    std::string flags;
    while (*position && std::strchr("-+ #0'", *position)) {
      if (*position != '\'') flags += *position;  // Bionic ignores grouping.
      ++position;
    }
    std::string width;
    if (*position == '*') {
      ++position;
      int64_t value = Narrow<int32_t>(args.integer());
      if (value < 0) { flags += '-'; value = -value; }
      if (value > std::numeric_limits<int>::max()) throw std::invalid_argument("invalid dynamic width");
      width = std::to_string(value);
    } else width = Number(position);
    if (*position == '$') throw std::invalid_argument("positional guest formats require an explicit adapter");
    std::string precision;
    if (*position == '.') {
      ++position;
      if (*position == '*') {
        ++position;
        auto value = Narrow<int32_t>(args.integer());
        if (value >= 0) precision = '.' + std::to_string(value);
      } else precision = '.' + Number(position);
    }
    std::string length;
    if (*position && std::strchr("hljztL", *position)) {
      length += *position++;
      if ((length == "h" || length == "l") && *position == length[0]) length += *position++;
    }
    const char conversion = *position;
    if (!conversion) throw std::invalid_argument("unterminated guest format conversion");
    ++position;
    const std::string prefix = '%' + flags + width + precision;
    if (conversion == 'd' || conversion == 'i') {
      auto bits = args.integer();
      int64_t value;
      if (length == "hh") value = Narrow<int8_t>(bits);
      else if (length == "h") value = Narrow<int16_t>(bits);
      else if (length.empty()) value = Narrow<int32_t>(bits);
      else if (length == "l" || length == "ll" || length == "j" || length == "z" || length == "t") value = Narrow<int64_t>(bits);
      else throw std::invalid_argument("unsupported guest integer format length");
      output += Render(prefix + "ll" + conversion, static_cast<long long>(value));
    } else if (conversion == 'u' || conversion == 'o' || conversion == 'x' || conversion == 'X') {
      auto value = args.integer();
      if (length == "hh") value = static_cast<uint8_t>(value);
      else if (length == "h") value = static_cast<uint16_t>(value);
      else if (length.empty()) value = static_cast<uint32_t>(value);
      else if (length != "l" && length != "ll" && length != "j" && length != "z" && length != "t")
        throw std::invalid_argument("unsupported guest unsigned format length");
      output += Render(prefix + "ll" + conversion, static_cast<unsigned long long>(value));
    } else if (std::strchr("aAeEfFgG", conversion)) {
      if (!length.empty() && length != "l") throw std::invalid_argument("guest long double formatting is not implemented");
      output += Render(prefix + conversion, args.floating());
    } else if (conversion == 's') {
      if (!length.empty()) throw std::invalid_argument("guest wide string formatting is not implemented");
      const char *text = reinterpret_cast<const char *>(args.integer());
      const size_t maximum = precision.empty() ? std::numeric_limits<size_t>::max() :
          precision.size() == 1 ? 0 : static_cast<size_t>(std::stoull(precision.substr(1)));
      const auto snapshot = text ? ReadGuestString(reinterpret_cast<addr_t>(text), maximum) : std::string("(null)");
      output += Render(prefix + 's', snapshot.c_str());
    } else if (conversion == 'c') {
      if (!length.empty()) throw std::invalid_argument("guest wide character formatting is not implemented");
      output += Render(prefix + 'c', static_cast<int>(Narrow<uint8_t>(args.integer())));
    } else if (conversion == 'p') {
      if (!length.empty()) throw std::invalid_argument("invalid guest pointer format length");
      output += Pointer(args.integer(), flags, width, precision);
    } else {
      throw std::invalid_argument(std::string("unsupported guest format conversion: ") + conversion);
    }
    if (output.size() > static_cast<size_t>(std::numeric_limits<int>::max()))
      throw std::length_error("guest formatted output exceeds int");
  }
  return output;
}
std::string Format(const char *format, bridge_detail::Arguments &args) {
  return Format(format, {[&] { return args.Read<uint64_t>(); }, [&] { return args.Read<double>(); }});
}
std::string Format(const char *format, VaArguments &args) {
  return Format(format, {[&] { return args.Integer(); }, [&] { return args.Floating(); }});
}
}  // namespace recomp
