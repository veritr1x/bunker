#pragma once
#include <cstdint>
#include <functional>
#include <string>
namespace bunker::windows {
class FileSystem;
// FileSystem must outlive the callback and every Context retaining it. Supports
// only this mounted root's exact files/cache children; parents are not created.
std::function<int32_t(const std::u16string&)> MakeInternalDirectoryPreparer(FileSystem&,const std::u16string &data_dir);
}
