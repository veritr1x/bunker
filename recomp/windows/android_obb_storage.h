#pragma once
#include <cstdint>
#include <functional>
#include <stdexcept>
#include <string>
#include <vector>

namespace bunker::windows {
struct ExternalObbVolume {
  std::u16string root;
  bool available=true;
};
// A configured virtual volume root, not an inferred Android device volume.
inline std::u16string ObbDirectoryPath(const std::u16string &root,const std::u16string &package){
  if(root.size()<2||root.front()!=u'/'||root.back()==u'/'||root.find(u'\0')!=std::u16string::npos||root.find(u'\\')!=std::u16string::npos)
    throw std::invalid_argument("OBB volume needs a canonical absolute Android root");
  for(size_t at=1;at<root.size();){auto end=root.find(u'/',at);if(end==std::u16string::npos)end=root.size();auto part=root.substr(at,end-at);if(part.empty()||part==u"."||part==u"..")throw std::invalid_argument("noncanonical OBB volume root");at=end+1;}
  if(package.empty()||package==u"."||package==u".."||package.find(u'\0')!=std::u16string::npos||package.find(u'/')!=std::u16string::npos||package.find(u'\\')!=std::u16string::npos)
    throw std::invalid_argument("OBB directory needs a single actual package component");
  return root+u"/Android/obb/"+package;
}
class FileSystem;
// The FileSystem and its explicit volume mounts must outlive this callback.
// Only available catalog roots' exact Android/obb/package children are prepared.
std::function<int32_t(const std::u16string&)> MakeObbDirectoryPreparer(
    FileSystem&,const std::vector<ExternalObbVolume>&,const std::u16string &package);
}
