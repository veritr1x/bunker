#pragma once
#include <cstdint>
#include <stdexcept>
#include <string>
namespace bunker::windows {
// Standard UTF-8 for APK names/text, separate from JNI's modified UTF-8.
inline std::u16string Utf16(const std::string &input){
  std::u16string out;
  for(size_t at=0;at<input.size();){
    uint32_t c=static_cast<uint8_t>(input[at++]),minimum=0;unsigned extra=0;
    if(c<0x80){}
    else if(c>=0xc2&&c<=0xdf){c&=31;minimum=0x80;extra=1;}
    else if(c>=0xe0&&c<=0xef){c&=15;minimum=0x800;extra=2;}
    else if(c>=0xf0&&c<=0xf4){c&=7;minimum=0x10000;extra=3;}
    else throw std::invalid_argument("invalid UTF-8 leading byte");
    while(extra--){if(at==input.size()||(static_cast<uint8_t>(input[at])&0xc0)!=0x80)throw std::invalid_argument("invalid UTF-8 continuation");c=(c<<6)|(static_cast<uint8_t>(input[at++])&63);}
    if(c<minimum||c>0x10ffff||(c>=0xd800&&c<=0xdfff))throw std::invalid_argument("invalid UTF-8 scalar value");
    if(c<0x10000)out.push_back(static_cast<char16_t>(c));else{c-=0x10000;out.push_back(static_cast<char16_t>(0xd800+(c>>10)));out.push_back(static_cast<char16_t>(0xdc00+(c&1023)));}
  }
  return out;
}
inline std::string Utf8(const std::u16string &input){
  std::string out;
  for(size_t at=0;at<input.size();++at){
    uint32_t c=input[at];
    if(c>=0xd800&&c<=0xdbff){if(at+1==input.size()||input[at+1]<0xdc00||input[at+1]>0xdfff)throw std::invalid_argument("unpaired UTF-16 surrogate");c=0x10000+((c-0xd800)<<10)+(input[++at]-0xdc00);}
    else if(c>=0xdc00&&c<=0xdfff)throw std::invalid_argument("unpaired UTF-16 surrogate");
    if(c<0x80)out.push_back(static_cast<char>(c));
    else if(c<0x800){out.push_back(static_cast<char>(0xc0|(c>>6)));out.push_back(static_cast<char>(0x80|(c&63)));}
    else if(c<0x10000){out.push_back(static_cast<char>(0xe0|(c>>12)));out.push_back(static_cast<char>(0x80|((c>>6)&63)));out.push_back(static_cast<char>(0x80|(c&63)));}
    else{out.push_back(static_cast<char>(0xf0|(c>>18)));out.push_back(static_cast<char>(0x80|((c>>12)&63)));out.push_back(static_cast<char>(0x80|((c>>6)&63)));out.push_back(static_cast<char>(0x80|(c&63)));}
  }
  return out;
}
}
