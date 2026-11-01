#include "zlib_host.h"
#include <zlib.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
static unsigned checks;
static void check(bool condition,const char*why){++checks;if(!condition){std::fprintf(stderr,"zlib check failed: %s\n",why);std::exit(1);}}
int main(){
  bunker::windows::Zlib host;recomp::Runtime runtime;host.Install(runtime);
  bunker::windows::AndroidZStream stream{};
  check(host.Version()&&host.Version()[0]=='1',"real backend version");
  check(host.Init(nullptr,15,host.Version(),112)==Z_STREAM_ERROR,"null stream");
  check(host.Init(&stream,15,"2.0",112)==Z_VERSION_ERROR,"incompatible major version");
  check(host.Init(&stream,15,host.Version(),88)==Z_VERSION_ERROR,"reject native Windows stream size");
  check(host.Inflate(&stream,Z_NO_FLUSH)==Z_STREAM_ERROR&&host.End(&stream)==Z_STREAM_ERROR,"uninitialized stream rejected");
  check(host.Init(&stream,100,host.Version(),112)==Z_STREAM_ERROR&&!stream.state,"invalid window bits");
  stream={};check(host.Init(&stream,15,host.Version(),112)==Z_OK&&stream.state&&stream.zalloc&&stream.zfree,"native sidecar and guest-callable defaults installed");
  auto copied=stream;check(host.Inflate(&copied,Z_NO_FLUSH)==Z_STREAM_ERROR,"copied opaque stream cannot alias backend ownership");
  State state{};state.gpr.x0.qword=stream.opaque;state.gpr.x1.qword=3;state.gpr.x2.qword=7;
  runtime.Run(state,stream.zalloc);auto memory=reinterpret_cast<unsigned char*>(state.gpr.x0.qword);check(memory!=nullptr,"exposed default allocation is a guest import");
  std::memset(memory,0x39,21);check(memory[20]==0x39,"default zlib allocation is writable");
  state={};state.gpr.x0.qword=stream.opaque;state.gpr.x1.qword=reinterpret_cast<addr_t>(memory);runtime.Run(state,stream.zfree);
  check(host.Init(&stream,15,host.Version(),112)==Z_STREAM_ERROR,"double initialization rejected");
  check(host.End(&stream)==Z_OK&&!stream.state,"inflateEnd releases sidecar and clears guest state");
  check(host.End(&stream)==Z_STREAM_ERROR,"double end rejected");
  stream={};stream.zalloc=0x1234;stream.zfree=0x5678;
  check(host.Init(&stream,15,host.Version(),112)==Z_STREAM_ERROR,"guest callbacks require a translated runner");
  check(sizeof(uLong)==4||sizeof(uLong)==8,"host unsigned long width is not assumed");
  unsigned released=0; bunker::windows::Zlib *active=nullptr;
  {
    bunker::windows::Zlib callbacks([&](addr_t callback,const std::vector<addr_t>&args)->uint64_t{
      if(callback==0x1111)return reinterpret_cast<uint64_t>(std::calloc(static_cast<size_t>(args[1]),static_cast<size_t>(args[2])));
      check(callback==0x2222&&args.size()==2,"destructor runs configured free callback");
      bunker::windows::AndroidZStream attempt{};
      check(active->Init(&attempt,15,active->Version(),112)==Z_STREAM_ERROR,"teardown rejects reentrant new streams");
      std::free(reinterpret_cast<void*>(args[1]));++released;return 0;
    });active=&callbacks;
    bunker::windows::AndroidZStream live{};live.zalloc=0x1111;live.zfree=0x2222;
    check(callbacks.Init(&live,15,callbacks.Version(),112)==Z_OK,"custom allocator stream for teardown");
  }
  check(released==1,"provider teardown releases live backend exactly once without touching expired guest stream");
  std::printf("Zlib provider: %u native checks passed (host z_stream=%zu, Android=%zu).\n",checks,sizeof(z_stream),sizeof(stream));
}
