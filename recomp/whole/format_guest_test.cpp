#include "../windows/logging.h"
#include "elfload.h"
#include "traces.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
static bunker::windows::Logging logging;
static void *resolve(const char *name) {
  try { return reinterpret_cast<void *>(logging.Marker(name)); } catch (...) { return nullptr; }
}
int main() {
#ifdef _WIN32
  _setmode(_fileno(stdout),_O_BINARY);
#endif
  elf_image image;
  if(elf_load(FORMAT_LIBRARY,0x40000000,resolve,&image))return 1;
  recomp::Runtime runtime;runtime.AddTraces(kTraces,sizeof(kTraces)/sizeof(*kTraces));logging.Install(runtime);
  unsigned char captured[512];
  auto capture=[&](std::string_view text) { if(text.size()>=sizeof(captured))return false;std::memcpy(captured,text.data(),text.size());return true; };
  logging.SetOutput(capture);
  logging.SetLog([&](int priority,std::string_view tag,std::string_view text) { if(tag!="bunker"||(priority!=4&&priority!=5))return false;return capture(text); });
  alignas(16) unsigned char stack[1<<18];
  auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,"format_case"));
  for(unsigned n=0;n<16;++n) {
    unsigned char out[512];std::memset(out,0xa5,sizeof(out));std::memset(captured,0,sizeof(captured));
    State s{};s.gpr.x0.qword=n;s.gpr.x1.qword=reinterpret_cast<addr_t>(out);
    s.gpr.sp.qword=reinterpret_cast<addr_t>(stack+sizeof(stack));s.gpr.x30.qword=0xfeedffff;
    runtime.Run(s,entry);
    if(s.gpr.pc.qword!=0xfeedffff||s.gpr.sp.qword!=reinterpret_cast<addr_t>(stack+sizeof(stack)))std::abort();
    int32_t result=static_cast<int32_t>(s.gpr.x0.qword);
    std::fwrite(&result,4,1,stdout);std::fwrite(out,1,512,stdout);std::fwrite(captured,1,512,stdout);
  }
}
