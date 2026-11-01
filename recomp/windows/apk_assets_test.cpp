#include "apk_assets.h"
#include <cstdio>
#include <string>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
int main(int argc, char **argv) {
  if (argc != 3) return 2;
#ifdef _WIN32
  _setmode(_fileno(stdout), _O_BINARY);
#endif
  try {
    bunker::windows::ApkAssets archive(std::filesystem::u8path(argv[1]));
    std::string name = argv[2];
    if (name == "#unicode") name = u8"nested/日本語.bin";
    if (name == "#nul") name = std::string("a\0b", 3);
    const auto data = archive.Read(name);
    if (!data.empty() && std::fwrite(data.data(), 1, data.size(), stdout) != data.size()) return 3;
    return 0;
  } catch (const bunker::windows::AssetError &error) {
    std::fprintf(stderr, "asset error %d: %s\n", error.kind, error.what());
    return 10 + error.kind;
  } catch (const std::exception &error) {
    std::fprintf(stderr, "asset reader: %s\n", error.what());
    return 20;
  }
}
