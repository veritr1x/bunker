#include "android_obb_storage.h"
#include "filesystem.h"
#include "unicode.h"
#include <map>
namespace bunker::windows {
std::function<int32_t(const std::u16string&)> MakeObbDirectoryPreparer(
    FileSystem &files,const std::vector<ExternalObbVolume> &volumes,const std::u16string &package){
  std::map<std::u16string,std::u16string> roots;
  for(const auto &volume:volumes){auto path=ObbDirectoryPath(volume.root,package);if(volume.available&&!roots.emplace(path,volume.root).second)throw std::invalid_argument("duplicate OBB volume root");}
  return [&files,roots=std::move(roots)](const std::u16string &path)->int32_t{
    const auto found=roots.find(path);if(found==roots.end())return 22;
    auto failure=[&]{const auto error=files.Error();return error>0?error:5;};
    auto directory=[&](const std::u16string &p)->int32_t{AndroidStat stat{};const auto name=Utf8(p);if(files.Stat(name.c_str(),&stat))return failure();return (stat.mode&0170000)==0040000?0:20;};
    if(auto error=directory(found->second))return error;
    if(files.Access(Utf8(found->second).c_str(),2))return failure();
    // Create only the three fixed descendants, never a volume root or any
    // arbitrary caller path. Every existing object is rechecked as a directory.
    for(const auto &child:{found->second+u"/Android",found->second+u"/Android/obb",path}){
      const auto name=Utf8(child);if(files.Mkdir(name.c_str(),0700)&&files.Error()!=17)return failure();
      if(auto error=directory(child))return error;
    }
    if(files.Access(Utf8(path).c_str(),2))return failure();return 0;
  };
}
}
