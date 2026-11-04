#pragma once
#include <cfenv>
#include <cerrno>
#include <cstdint>
#include <cstring>
#include <limits>
#include <iterator>
#include <new>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
#include "../whole/runtime.h"
#include "unicode.h"
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <sys/utsname.h>
#include <sys/uio.h>
#include <sys/syscall.h>
#include <unistd.h>
#endif

namespace bunker::windows::libc_detail {
// Android/Bionic UAPI: six independent 65-byte arrays, no host struct cast.
struct Utsname {
  char sysname[65],nodename[65],release[65],version[65],machine[65],domainname[65];
};
static_assert(sizeof(Utsname)==390 && alignof(Utsname)==1);
static_assert(offsetof(Utsname,release)==130 && offsetof(Utsname,domainname)==325);
struct UnameFacts {
  std::string sysname,nodename,release,version,machine,domainname;
};

// Stage and validate every field before publishing any output. The bound is
// encoded UTF-8 BYTES, rather than UTF-16 code units or Unicode character count.
inline int EncodeUname(const UnameFacts &facts,Utsname &output) noexcept {
  try {
    Utsname staged{};
    const std::string *inputs[]={&facts.sysname,&facts.nodename,&facts.release,&facts.version,&facts.machine,&facts.domainname};
    char *fields[]={staged.sysname,staged.nodename,staged.release,staged.version,staged.machine,staged.domainname};
    for(unsigned i=0;i<6;++i){
      const auto &value=*inputs[i];
      if(i!=5 && value.empty())return 5;
      if(value.size()>64)return 75;
      if(value.find('\0')!=std::string::npos)return 84;
      (void)Utf16(value);  // Strict validation; malformed UTF-8 is not replaced.
      std::memcpy(fields[i],value.data(),value.size());
    }
    output=staged;return 0;
  }catch(const std::bad_alloc &){return 12;}
  catch(const std::invalid_argument &){return 84;}
  catch(...){return 5;}
}

namespace uname_detail {
struct NativeEnvironment {
  int error=errno;
  fenv_t floating{};
#ifdef _WIN32
  DWORD last_error=GetLastError();
#endif
  NativeEnvironment(){std::fegetenv(&floating);}
  ~NativeEnvironment(){std::fesetenv(&floating);errno=error;
#ifdef _WIN32
    SetLastError(last_error);
#endif
  }
};
#ifdef _WIN32
inline int WindowsError(DWORD error) noexcept {
  switch(error){
    case ERROR_ACCESS_DENIED:return 13;
    case ERROR_NOT_ENOUGH_MEMORY:case ERROR_OUTOFMEMORY:return 12;
    case ERROR_INVALID_PARAMETER:return 22;
    case ERROR_CALL_NOT_IMPLEMENTED:case ERROR_PROC_NOT_FOUND:case ERROR_MOD_NOT_FOUND:return 38;
    case ERROR_NOT_SUPPORTED:return 95;
    case ERROR_NO_UNICODE_TRANSLATION:return 84;
    case ERROR_BUFFER_OVERFLOW:case ERROR_INSUFFICIENT_BUFFER:case ERROR_MORE_DATA:return 75;
    default:return 5;
  }
}
template<class F> F Procedure(HMODULE module,const char *name) noexcept {
  auto raw=GetProcAddress(module,name);F function=nullptr;
  static_assert(sizeof(function)==sizeof(raw));std::memcpy(&function,&raw,sizeof(function));return function;
}
inline std::string Wide(const wchar_t *text,size_t count){
  static_assert(sizeof(wchar_t)==2);
  std::u16string value;value.reserve(count);
  for(size_t i=0;i<count;++i)value.push_back(static_cast<char16_t>(text[i]));
  return Utf8(value);
}
inline int Name(COMPUTER_NAME_FORMAT format,std::string &output){
  std::vector<wchar_t> text(256);
  for(;;){
    DWORD count=static_cast<DWORD>(text.size());
    if(GetComputerNameExW(format,text.data(),&count)){
      if(count>=text.size()||text[count]!=L'\0')return 5;
      output=Wide(text.data(),count);return 0;
    }
    const auto error=GetLastError();
    if(error!=ERROR_MORE_DATA)return WindowsError(error);
    if(count<=text.size()||count>32768)return 75;
    text.assign(count,L'\0');
  }
}
inline bool Writable(addr_t address,size_t size) noexcept {
  if(!address||address>std::numeric_limits<addr_t>::max()-size)return false;
  const auto end=address+size;auto cursor=address;
  while(cursor<end){
    MEMORY_BASIC_INFORMATION info{};
    if(!VirtualQuery(reinterpret_cast<const void*>(cursor),&info,sizeof(info))||info.State!=MEM_COMMIT||(info.Protect&(PAGE_GUARD|PAGE_NOACCESS)))return false;
    const DWORD protection=info.Protect&0xff;
    if(protection!=PAGE_READWRITE&&protection!=PAGE_WRITECOPY&&protection!=PAGE_EXECUTE_READWRITE&&protection!=PAGE_EXECUTE_WRITECOPY)return false;
    const auto base=reinterpret_cast<addr_t>(info.BaseAddress);
    if(base>std::numeric_limits<addr_t>::max()-info.RegionSize)return false;
    const auto next=base+info.RegionSize;if(next<=cursor)return false;
    cursor=next;
  }
  return true;
}
#endif
inline int Publish(addr_t address,const Utsname &value) noexcept {
  if(!address||address>std::numeric_limits<addr_t>::max()-sizeof(value))return 14;
  bool copied=false;
  try {
    recomp::WithGuestMemoryWrite(address,sizeof(value),[&]{
#ifdef _WIN32
      // WPM can change protections for debugger writes. Reject RO/guard pages
      // explicitly first, while the provider memory-lifetime lock is held.
      if(!Writable(address,sizeof(value)))return;
      SIZE_T count=0;
      copied=WriteProcessMemory(GetCurrentProcess(),reinterpret_cast<void*>(address),&value,sizeof(value),&count)&&count==sizeof(value);
#else
      iovec local{const_cast<Utsname*>(&value),sizeof(value)};
      iovec remote{reinterpret_cast<void*>(address),sizeof(value)};
      const auto count=::syscall(SYS_process_vm_writev,::getpid(),&local,1,&remote,1,0);
      copied=count==static_cast<decltype(count)>(sizeof(value));
#endif
    });
  }catch(...){return 14;}
  return copied?0:14;
}
}  // namespace uname_detail

// Query actual host identity. Windows release is the real NT major.minor.build;
// architecture is the native OS machine reported by IsWow64Process2, not a
// claim about a physical CPU or this AArch64 guest. No Linux/Android disguise.
inline int QueryUnameFacts(UnameFacts &output) noexcept {
  uname_detail::NativeEnvironment preserve;
  try {
    UnameFacts facts;
#ifdef _WIN32
    const auto ntdll=GetModuleHandleW(L"ntdll.dll");
    const auto kernel=GetModuleHandleW(L"kernel32.dll");
    if(!ntdll||!kernel)return 38;
    using Version=LONG(WINAPI*)(OSVERSIONINFOW*);
    using Machines=BOOL(WINAPI*)(HANDLE,USHORT*,USHORT*);
    const auto version=uname_detail::Procedure<Version>(ntdll,"RtlGetVersion");
    const auto machines=uname_detail::Procedure<Machines>(kernel,"IsWow64Process2");
    if(!version||!machines)return 38;
    OSVERSIONINFOW native{};native.dwOSVersionInfoSize=sizeof(native);
    if(version(&native)!=0||native.dwPlatformId!=VER_PLATFORM_WIN32_NT)return 5;
    USHORT process_machine=0,native_machine=0;
    if(!machines(GetCurrentProcess(),&process_machine,&native_machine))return uname_detail::WindowsError(GetLastError());
    switch(native_machine){
      case 0x8664:facts.machine="x86_64";break;
      case 0x014c:facts.machine="x86";break;
      case 0xaa64:facts.machine="aarch64";break;
      case 0x01c4:facts.machine="arm";break;
      case 0x0200:facts.machine="ia64";break;
      default:return 95;
    }
    facts.sysname="Windows_NT";
    facts.release=std::to_string(native.dwMajorVersion)+"."+std::to_string(native.dwMinorVersion)+"."+std::to_string(native.dwBuildNumber);
    size_t csd=0;while(csd<std::size(native.szCSDVersion)&&native.szCSDVersion[csd])++csd;
    if(csd==std::size(native.szCSDVersion))return 5;
    facts.version=csd?uname_detail::Wide(native.szCSDVersion,csd):"Build "+std::to_string(native.dwBuildNumber);
    int error=uname_detail::Name(ComputerNameDnsHostname,facts.nodename);if(error)return error;
    error=uname_detail::Name(ComputerNameDnsDomain,facts.domainname);if(error)return error;
#else
    struct utsname native{};
    if(::uname(&native))return errno>0?errno:5;
    auto field=[](const char *text,size_t size){size_t length=0;while(length<size&&text[length])++length;if(length==size)throw std::invalid_argument("unterminated native uname field");return std::string(text,length);};
    facts.sysname=field(native.sysname,sizeof(native.sysname));facts.nodename=field(native.nodename,sizeof(native.nodename));facts.release=field(native.release,sizeof(native.release));facts.version=field(native.version,sizeof(native.version));facts.machine=field(native.machine,sizeof(native.machine));
#if defined(__USE_GNU)
    facts.domainname=field(native.domainname,sizeof(native.domainname));
#else
    facts.domainname=field(native.__domainname,sizeof(native.__domainname));
#endif
#endif
    output=std::move(facts);return 0;
  }catch(const std::bad_alloc &){return 12;}
  catch(const std::invalid_argument &){return 84;}
  catch(...){return 5;}
}

// Query injection is a local callable for focused tests, not mutable provider
// configuration. Production always passes QueryUnameFacts. Keep the native
// environment guard alive through error-sink publication as well as queries.
template<class ErrorSink,class Query>
inline int32_t UnameWithQuery(addr_t output,ErrorSink &&error_sink,Query &&query) {
  uname_detail::NativeEnvironment preserve;
  int error=0;
  if(!output||output>std::numeric_limits<addr_t>::max()-sizeof(Utsname))error=14;
  else {
    try {
      UnameFacts facts;error=query(facts);
      if(!error){
        Utsname value{};error=EncodeUname(facts,value);
        if(!error)error=uname_detail::Publish(output,value);
      }
    }catch(const std::bad_alloc &){error=12;}
    catch(const std::invalid_argument &){error=84;}
    catch(...){error=5;}
  }
  // Publish once outside the query catch block. A throwing error sink must
  // escape to the existing import fatal boundary after native state restores.
  if(error){error_sink(error>0?error:5);return -1;}
  return 0;
}
template<class ErrorSink>
inline int32_t Uname(addr_t output,ErrorSink &&error_sink) {
  return UnameWithQuery(output,std::forward<ErrorSink>(error_sink),QueryUnameFacts);
}
}  // namespace bunker::windows::libc_detail
