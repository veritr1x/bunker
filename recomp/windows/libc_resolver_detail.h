#pragma once
// Include Winsock before windows.h (the other libc detail headers use it).
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#else
#include <arpa/inet.h>
#include <netdb.h>
#endif
#include "../whole/runtime.h"
#include <array>
#include <cerrno>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

namespace bunker::windows::libc_resolver {
// Bionic LP64 uses socklen_t (32 bits), and canon precedes addr. In particular
// this must not be a glibc addrinfo cast, or a Windows size_t addrlen copy.
struct AddrInfo {
  int32_t flags,family,type,protocol;
  uint32_t length,padding;
  addr_t canon,address,next;
};
static_assert(sizeof(AddrInfo)==48 && alignof(AddrInfo)==8);
static_assert(offsetof(AddrInfo,length)==16 && offsetof(AddrInfo,canon)==24 &&
              offsetof(AddrInfo,address)==32 && offsetof(AddrInfo,next)==40);
struct Node {
  int32_t family,type,protocol;
  std::vector<unsigned char> address;
  std::string canonical;
  bool has_canonical=false;
};
struct Service {
  bool numeric=false,sets_error=false;
  uint64_t value=0;
  int error=0;
};
// Android's str2number uses LP64 strtoul, clears errno for every nonempty
// string, and returns an int after a UINT_MAX check. Preserve those side
// effects and signed-result behavior before native service lookup.
inline Service ParseService(const std::string &text) {
  Service result;
  if(text.empty())return result;
  result.sets_error=true;
  size_t at=0;
  while(at<text.size() && (text[at]==' ' || (text[at]>='\t'&&text[at]<='\r')))++at;
  bool negative=false;
  if(at<text.size()&&(text[at]=='+'||text[at]=='-'))negative=text[at++]=='-';
  const auto start=at;
  bool overflow=false;
  uint64_t value=0;
  while(at<text.size()&&text[at]>='0'&&text[at]<='9'){
    const unsigned digit=static_cast<unsigned>(text[at++]-'0');
    if(value>(UINT64_MAX-digit)/10)overflow=true;
    else if(!overflow)value=value*10+digit;
  }
  if(overflow){result.error=34;return result;}
  if(start==at||at!=text.size())return result;
  if(negative)value=uint64_t{0}-value;
  if(value>INT32_MAX)return result;
  result.numeric=true;result.value=value;return result;
}
inline int Validate(const AddrInfo &h,bool has_service) {
  if(h.length||h.canon||h.address||h.next)return 12;
  // AI_ALL / AI_V4MAPPED constants exist in netdb.h, but Android 13's
  // implementation does not admit them in its actual AI_MASK.
  if(static_cast<uint32_t>(h.flags)&~uint32_t{0x40f})return 3;
  if(h.family!=0&&h.family!=2&&h.family!=10)return 5;
  if((h.type==1&&h.protocol&&h.protocol!=6)||
     (h.type==2&&h.protocol&&h.protocol!=17))return 12;
  if(has_service){
    if(h.type==3)return 9;
    if(h.type!=0&&h.type!=1&&h.type!=2)return 10;
  }
  return 0;
}
inline bool DecimalQuad(const std::string &text,std::string &canonical) {
  size_t at=0;
  for(unsigned octet=0;octet<4;++octet){
    const auto begin=at;unsigned value=0;
    while(at<text.size()&&text[at]>='0'&&text[at]<='9'){
      value=value*10+static_cast<unsigned>(text[at++]-'0');
      if(value>255)return false;
    }
    if(at==begin)return false;
    if(octet)canonical+='.';
    canonical+=std::to_string(value);
    if(octet==3)return at==text.size();
    if(at==text.size()||text[at++]!='.')return false;
  }
  return false;
}
inline std::string NormalizeAddress(const std::string &text) {
  const auto dot=text.find('.');
  if(dot==text.npos)return text;
  const auto colon=text.rfind(':',dot);
  const auto begin=colon==text.npos?size_t{0}:colon+1;
  if(colon!=text.npos&&dot-begin>4)return text;
  std::string tail;
  if(!DecimalQuad(text.substr(begin),tail))return text;
  return text.substr(0,begin)+tail;
}

class Native {
 public:
#ifdef _WIN32
  Native(){
    module_=LoadLibraryExW(L"ws2_32.dll",nullptr,LOAD_LIBRARY_SEARCH_SYSTEM32);
    if(!module_)throw std::runtime_error("resolver cannot load System32 ws2_32.dll");
    try{
      start_=Symbol<Start>("WSAStartup");cleanup_=Symbol<Cleanup>("WSACleanup");
      get_=Symbol<Get>("getaddrinfo");free_=Symbol<Free>("freeaddrinfo");
      pton_=Symbol<Pton>("inet_pton");
      WSADATA data{};const auto error=start_(MAKEWORD(2,2),&data);
      if(error)throw std::runtime_error("native Winsock resolver startup failed: "+std::to_string(error));
      started_=true;
      if(data.wVersion!=MAKEWORD(2,2))throw std::runtime_error("native Winsock 2.2 resolver unavailable");
    }catch(...){if(started_)cleanup_();FreeLibrary(module_);module_=nullptr;throw;}
  }
  ~Native(){if(started_)cleanup_();if(module_)FreeLibrary(module_);}
#else
  Native()=default;
#endif
  Native(const Native&)=delete;Native &operator=(const Native&)=delete;
  int PtonAddress(int family,const std::string &text,void *output)const {
#ifdef _WIN32
    return pton_(family==10?AF_INET6:AF_INET,text.c_str(),output);
#else
    return ::inet_pton(family==10?AF_INET6:AF_INET,text.c_str(),output);
#endif
  }
  int Query(const char *node,const char *service,int family,int type,int protocol,int flags,
            std::vector<Node> &output,int &system_error)const {
    addrinfo hints{};
    hints.ai_family=family==10?AF_INET6:family==2?AF_INET:AF_UNSPEC;
    hints.ai_socktype=type;hints.ai_protocol=protocol;
    if(flags&1)hints.ai_flags|=AI_PASSIVE;
    if(flags&2)hints.ai_flags|=AI_CANONNAME;
    if(flags&4)hints.ai_flags|=AI_NUMERICHOST;
    if(flags&0x400)hints.ai_flags|=AI_ADDRCONFIG;
    addrinfo *head=nullptr;
#ifdef _WIN32
    const int error=get_(node,service,&hints,&head);
#else
    const int error=::getaddrinfo(node,service,&hints,&head);
#endif
    const int saved_errno=errno;
    struct Release {const Native *owner;addrinfo *head;~Release(){owner->ReleaseList(head);}} release{this,head};
    if(error){const auto mapped=MapError(error);if(mapped==11)system_error=saved_errno;return mapped;}
    for(auto *p=head;p;p=p->ai_next){
      const int guest_family=p->ai_family==AF_INET?2:p->ai_family==AF_INET6?10:0;
      const size_t length=guest_family==2?16:guest_family==10?28:0;
      if(!length||!p->ai_addr||p->ai_addrlen<length)
        throw std::runtime_error("native resolver returned an invalid Internet address");
      Node result{guest_family,p->ai_socktype,p->ai_protocol,std::vector<unsigned char>(length,0),{},false};
      // Explicit sockaddr conversion: family is host-order and differs for
      // IPv6; port/address/flow/scope retain their own specified byte orders.
      const uint16_t af=static_cast<uint16_t>(guest_family);
      std::memcpy(result.address.data(),&af,2);
      std::memcpy(result.address.data()+2,reinterpret_cast<const unsigned char*>(p->ai_addr)+2,guest_family==2?6:26);
      if(p->ai_canonname){result.canonical=p->ai_canonname;result.has_canonical=true;}
      output.push_back(std::move(result));
    }
    return output.empty()?7:0;
  }
 private:
  void ReleaseList(addrinfo *head)const noexcept {
    if(!head)return;
#ifdef _WIN32
    free_(head);
#else
    ::freeaddrinfo(head);
#endif
  }
  static int MapError(int error) {
    if(error==EAI_AGAIN)return 2;
    if(error==EAI_BADFLAGS)return 3;
    if(error==EAI_FAIL)return 4;
    if(error==EAI_FAMILY)return 5;
    if(error==EAI_MEMORY)return 6;
#ifdef EAI_NODATA
    if(error==EAI_NODATA)return 7;
#endif
    if(error==EAI_NONAME)return 8;
    if(error==EAI_SERVICE)return 9;
    if(error==EAI_SOCKTYPE)return 10;
#ifdef EAI_SYSTEM
    if(error==EAI_SYSTEM)return 11;
#endif
#ifdef EAI_OVERFLOW
    if(error==EAI_OVERFLOW)return 14;
#endif
    return 4;
  }
#ifdef _WIN32
  using Start=int (WSAAPI*)(WORD,LPWSADATA);
  using Cleanup=int (WSAAPI*)();
  using Get=int (WSAAPI*)(const char*,const char*,const addrinfo*,addrinfo**);
  using Free=void (WSAAPI*)(addrinfo*);
  using Pton=int (WSAAPI*)(int,const char*,void*);
  template<typename T>T Symbol(const char *name){
    auto raw=GetProcAddress(module_,name);T value=nullptr;
    static_assert(sizeof(value)==sizeof(raw));std::memcpy(&value,&raw,sizeof(value));
    if(!value)throw std::runtime_error(std::string("native resolver API unavailable: ")+name);
    return value;
  }
  HMODULE module_=nullptr;bool started_=false;
  Start start_=nullptr;Cleanup cleanup_=nullptr;Get get_=nullptr;Free free_=nullptr;Pton pton_=nullptr;
#endif
};

inline const char *ErrorText(int code) {
  // These are the public Android EAI descriptions, not Windows WSA numbers.
  static const char *const messages[]={
    "Success","Address family for hostname not supported","Temporary failure in name resolution",
    "Invalid value for ai_flags","Non-recoverable failure in name resolution","ai_family not supported",
    "Memory allocation failure","No address associated with hostname","hostname nor servname provided, or not known",
    "servname not supported for ai_socktype","ai_socktype not supported","System error returned in errno",
    "Invalid value for hints","Resolved protocol is unknown","Argument buffer overflow","Unknown error"};
  return messages[code>=0&&code<15?code:15];
}
}  // namespace bunker::windows::libc_resolver
