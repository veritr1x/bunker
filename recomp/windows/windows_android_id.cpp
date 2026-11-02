#include "windows_android_id.h"
#include <algorithm>
#include <stdexcept>
#include <system_error>
#include <vector>
#ifdef _WIN32
#include <windows.h>
#endif
namespace bunker::windows {
std::function<std::optional<std::u16string>()> MakeWindowsAndroidIdReader(std::u16string package){
  if(package.empty()||package.front()==u'.'||package.back()==u'.'||package.find(u"..")!=std::u16string::npos||
     !std::all_of(package.begin(),package.end(),[](char16_t c){return(c>=u'a'&&c<=u'z')||(c>=u'A'&&c<=u'Z')||(c>=u'0'&&c<=u'9')||c==u'_'||c==u'.';}))
    throw std::invalid_argument("Android ID registry backing requires an exact bounded package namespace");
  if(package.size()>255)throw std::invalid_argument("Android ID package namespace is too long");
#ifdef _WIN32
  static_assert(sizeof(wchar_t)==sizeof(char16_t));
  std::wstring path=L"Software\\Bunker\\Apps\\";path.append(package.begin(),package.end());path+=L"\\SecureSettings";
  return [path=std::move(path)]()->std::optional<std::u16string>{
    struct Key {HKEY value=nullptr;~Key(){if(value)RegCloseKey(value);}} key;
    auto status=RegOpenKeyExW(HKEY_CURRENT_USER,path.c_str(),0,KEY_QUERY_VALUE|KEY_WOW64_64KEY,&key.value);
    if(status==ERROR_FILE_NOT_FOUND)return {};
    if(status!=ERROR_SUCCESS)throw std::system_error(status,std::system_category(),"Settings.Secure android_id registry open");
    DWORD type=0,bytes=0;
    status=RegQueryValueExW(key.value,L"android_id",nullptr,&type,nullptr,&bytes);
    if(status==ERROR_FILE_NOT_FOUND)return {};
    if(status!=ERROR_SUCCESS)throw std::system_error(status,std::system_category(),"Settings.Secure android_id registry size");
    if(type!=REG_SZ||bytes<sizeof(wchar_t)||bytes%sizeof(wchar_t)||bytes>65536)
      throw std::runtime_error("Settings.Secure android_id registry value has unsupported type/size");
    std::vector<wchar_t> data(bytes/sizeof(wchar_t));DWORD actual=bytes;
    status=RegQueryValueExW(key.value,L"android_id",nullptr,&type,reinterpret_cast<BYTE*>(data.data()),&actual);
    if(status==ERROR_FILE_NOT_FOUND)return {};
    if(status!=ERROR_SUCCESS)throw std::system_error(status,std::system_category(),"Settings.Secure android_id registry read");
    if(type!=REG_SZ||actual<sizeof(wchar_t)||actual%sizeof(wchar_t)||actual>bytes)
      throw std::runtime_error("Settings.Secure android_id registry value changed type/size during read");
    const size_t length=actual/sizeof(wchar_t);
    if(data[length-1]||std::find(data.begin(),data.begin()+length-1,L'\0')!=data.begin()+length-1)
      throw std::runtime_error("Settings.Secure android_id registry value is not one terminated String");
    return std::u16string(data.begin(),data.begin()+length-1);
  };
#else
  return []()->std::optional<std::u16string>{throw std::runtime_error("Windows Android ID registry backing is unavailable on this host");};
#endif
}
}
