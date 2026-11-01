#include "android_internal_storage.h"
#include "filesystem.h"
#include "unicode.h"
#include <stdexcept>
namespace bunker::windows {
std::function<int32_t(const std::u16string&)> MakeInternalDirectoryPreparer(FileSystem &files,const std::u16string &data_dir){
  auto base=data_dir;while(base.size()>1&&base.back()==u'/')base.pop_back();
  if(base.empty()||base.front()!=u'/'||base.find(u'\0')!=std::u16string::npos||base.find(u'\\')!=std::u16string::npos)throw std::invalid_argument("internal storage needs an absolute Android mount root");
  for(size_t at=1;at<base.size();){auto end=base.find(u'/',at);if(end==std::u16string::npos)end=base.size();auto part=base.substr(at,end-at);if(part.empty()||part==u"."||part==u"..")throw std::invalid_argument("noncanonical internal storage root");at=end+1;}
  auto root=Utf8(base);const auto prefix=base+(base.back()==u'/'?u"":u"/");const auto files_path=prefix+u"files",cache_path=prefix+u"cache";
  return [&files,root,files_path,cache_path](const std::u16string &path)->int32_t{
    if(path!=files_path&&path!=cache_path)return 22;
    auto failure=[&]{auto error=files.Error();return error>0?error:5;};AndroidStat stat{};
    if(files.Stat(root.c_str(),&stat))return failure();if((stat.mode&0170000)!=0040000)return 20;
    const auto target=Utf8(path);
    // Existing objects are accepted only after rooted Stat proves directory.
    // Mkdir's owner-private Windows DACL policy is explicit, not Android chmod.
    if(files.Mkdir(target.c_str(),0700)&&files.Error()!=17)return failure();
    if(files.Stat(target.c_str(),&stat))return failure();return (stat.mode&0170000)==0040000?0:20;
  };
}
}
