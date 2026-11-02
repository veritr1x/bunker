#include "windows_shared_preferences.h"
#include <algorithm>
#include <stdexcept>
#include <system_error>
#ifdef _WIN32
#include <windows.h>
#endif
namespace bunker::windows {
namespace {
constexpr size_t kMaxBytes=4*1024*1024,kMaxEntries=16384,kMaxUnits=262144,kMaxSet=16384;
constexpr uint8_t kMagic[8]={'B','N','K','P','R','E','F',1};
void Bad(){throw std::runtime_error("SharedPreferences snapshot format/size is unsupported or corrupt");}
struct Writer {
  std::vector<uint8_t> data;
  void n(uint64_t v,size_t bytes){if(data.size()>kMaxBytes-bytes)Bad();for(size_t i=0;i<bytes;++i)data.push_back(uint8_t(v>>(8*i)));}
  void text(const std::u16string&s){if(s.size()>kMaxUnits)Bad();n(s.size(),4);for(auto c:s)n(c,2);}
};
struct Reader {
  const std::vector<uint8_t>&data;size_t at=0;
  uint64_t n(size_t bytes){if(at>data.size()||bytes>data.size()-at)Bad();uint64_t v=0;for(size_t i=0;i<bytes;++i)v|=uint64_t(data[at++])<<(i*8);return v;}
  std::u16string text(){auto count=n(4);if(count>kMaxUnits||count>(data.size()-at)/2)Bad();std::u16string s;for(size_t i=0;i<count;++i)s.push_back(char16_t(n(2)));return s;}
};
void Package(const std::u16string&p){if(std::any_of(p.begin(),p.end(),[](char16_t c){return c>=u'A'&&c<=u'Z';}))throw std::runtime_error("SharedPreferences unsupported noncanonical package namespace; lowercase profile required");if(p.empty()||p.size()>255||p.front()==u'.'||p.back()==u'.'||p.find(u"..")!=p.npos||!std::all_of(p.begin(),p.end(),[](char16_t c){return(c>=u'a'&&c<=u'z')||(c>=u'0'&&c<=u'9')||c==u'_'||c==u'.';}))throw std::invalid_argument("SharedPreferences requires an exact bounded package namespace");}
}
std::vector<uint8_t> EncodeSharedPreferencesSnapshot(const SharedPreferencesSnapshot&map){
  if(map.size()>kMaxEntries)Bad();Writer w;for(auto c:kMagic)w.n(c,1);w.n(map.size(),4);
  for(auto &[key,value]:map){w.text(key);w.n(value.kind,1);switch(value.kind){
    case SharedPreferenceValue::String:w.text(value.text);break;
    case SharedPreferenceValue::Integer:case SharedPreferenceValue::Float:if(value.bits>>32)Bad();w.n(value.bits,4);break;
    case SharedPreferenceValue::Boolean:if(value.bits>1)Bad();w.n(value.bits,1);break;
    case SharedPreferenceValue::Long:w.n(value.bits,8);break;
    case SharedPreferenceValue::StringSet:if(value.strings.size()>kMaxSet)Bad();w.n(value.strings.size(),4);for(auto&s:value.strings)w.text(s);break;
    default:Bad();
  }}return std::move(w.data);
}
SharedPreferencesSnapshot DecodeSharedPreferencesSnapshot(const std::vector<uint8_t>&data){
  if(data.size()>kMaxBytes)Bad();Reader r{data};for(auto c:kMagic)if(r.n(1)!=c)Bad();auto count=r.n(4);if(count>kMaxEntries)Bad();SharedPreferencesSnapshot map;
  for(size_t i=0;i<count;++i){auto key=r.text();SharedPreferenceValue value;value.kind=static_cast<SharedPreferenceValue::Kind>(r.n(1));switch(value.kind){
    case SharedPreferenceValue::String:value.text=r.text();break;
    case SharedPreferenceValue::Integer:case SharedPreferenceValue::Float:value.bits=r.n(4);break;
    case SharedPreferenceValue::Boolean:value.bits=r.n(1);if(value.bits>1)Bad();break;
    case SharedPreferenceValue::Long:value.bits=r.n(8);break;
    case SharedPreferenceValue::StringSet:{auto n=r.n(4);if(n>kMaxSet)Bad();for(size_t k=0;k<n;++k)if(!value.strings.insert(r.text()).second)Bad();break;}
    default:Bad();
  }if(!map.emplace(std::move(key),std::move(value)).second)Bad();}if(r.at!=data.size())Bad();return map;
}
SharedPreferencesBackend MakeWindowsSharedPreferencesBackend(std::u16string package){
  Package(package);
#ifdef _WIN32
  static_assert(sizeof(wchar_t)==2);std::wstring path=L"Software\\Bunker\\Apps\\";path.append(package.begin(),package.end());path+=L"\\SharedPreferences";
  const auto legacy=package,modern=package+u".v2.playerprefs";
  auto name=[legacy,modern](const std::u16string&store){if(store!=legacy&&store!=modern)throw std::runtime_error("SharedPreferences unsupported store name");return std::wstring(store.begin(),store.end());};
  struct Key {HKEY key=nullptr;~Key(){if(key)RegCloseKey(key);}};
  SharedPreferencesBackend backend;
  backend.read=[path,name](const std::u16string&store)->std::optional<SharedPreferencesSnapshot>{
    const auto value=name(store);Key key;auto status=RegOpenKeyExW(HKEY_CURRENT_USER,path.c_str(),0,KEY_QUERY_VALUE|KEY_WOW64_64KEY,&key.key);
    if(status==ERROR_FILE_NOT_FOUND)return {};if(status)throw std::system_error(status,std::system_category(),"SharedPreferences registry open");
    DWORD type=0,size=0;status=RegQueryValueExW(key.key,value.c_str(),nullptr,&type,nullptr,&size);if(status==ERROR_FILE_NOT_FOUND)return {};if(status)throw std::system_error(status,std::system_category(),"SharedPreferences registry size");
    if(type!=REG_BINARY||size>kMaxBytes)Bad();std::vector<uint8_t> data(size);DWORD actual=size;status=RegQueryValueExW(key.key,value.c_str(),nullptr,&type,data.data(),&actual);
    // Deletion/type/size races are errors once a store was observed, never a
    // manufactured empty store. No retry can silently replace prior contents.
    if(status)throw std::system_error(status,std::system_category(),"SharedPreferences registry snapshot read");if(type!=REG_BINARY||actual!=size)Bad();return DecodeSharedPreferencesSnapshot(data);
  };
  backend.write=[path,name](const std::u16string&store,const SharedPreferencesSnapshot&snapshot)->uint32_t{
    const auto value=name(store);const auto data=EncodeSharedPreferencesSnapshot(snapshot);Key key;auto status=RegCreateKeyExW(HKEY_CURRENT_USER,path.c_str(),0,nullptr,0,KEY_SET_VALUE|KEY_QUERY_VALUE|KEY_WOW64_64KEY,nullptr,&key.key,nullptr);if(status)return status;
    status=RegSetValueExW(key.key,value.c_str(),0,REG_BINARY,data.data(),static_cast<DWORD>(data.size()));if(status)return status;
    return RegFlushKey(key.key); // This bounded synchronous apply does real I/O.
  };return backend;
#else
  return {[](const std::u16string&)->std::optional<SharedPreferencesSnapshot>{throw std::runtime_error("Windows SharedPreferences backend unavailable on this host");},[](const std::u16string&,const SharedPreferencesSnapshot&)->uint32_t{throw std::runtime_error("Windows SharedPreferences backend unavailable on this host");}};
#endif
}
}
