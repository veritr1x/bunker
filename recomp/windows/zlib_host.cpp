#include "zlib_host.h"
#include "../whole/bridge.h"
#include "provider_memory.h"
#include <zlib.h>
#include <cstdio>
#include <cstdlib>
#include <map>
#include <mutex>
#include <stdexcept>

namespace bunker::windows {
namespace pm=provider_memory;
namespace {
const char *const names[]={"inflate","inflateEnd","inflateInit2_","inflateInit_","zlibVersion"};
void *Allocate(uint32_t items,uint32_t size)noexcept{
  const uint64_t bytes=uint64_t(items)*size;
  return bytes>SIZE_MAX?nullptr:pm::Allocate(static_cast<size_t>(bytes));
}
[[noreturn]]void CallbackFailure()noexcept{std::fputs("Bunker zlib guest allocator callback failed\n",stderr);std::abort();}
}
struct Zlib::Impl {
  struct Stream {
    Impl *owner;
    z_stream native{};
    addr_t allocate,free,opaque;
    std::recursive_mutex lock;
    bool busy=false,live=false;
    struct Mirror{void *guest;size_t size;};
    std::map<void*,Mirror> mirrors;
    Stream(Impl *p,addr_t a,addr_t f,addr_t o):owner(p),allocate(a),free(f),opaque(o){}
    ~Stream(){if(live)::inflateEnd(&native);recomp::InvalidateGuestMemory(pm::Address(this),sizeof(*this));}
    void PublishAllocations(){
      for(const auto &entry:mirrors)recomp::WriteGuestMemory(pm::Address(entry.second.guest),entry.first,entry.second.size);
    }
    void ReleaseGuest(void *p,size_t size){
      recomp::InvalidateGuestMemory(pm::Address(p),size);
      if(free==owner->DefaultFree())pm::Free(p);
      else owner->runner(free,{opaque,pm::Address(p)});
    }
  };
  Runner runner;
  addr_t base;
  bool installed=false,stopping=false;
  std::mutex registry;
  std::map<AndroidZStream*,std::shared_ptr<Stream>> streams;
  Impl(Runner r,addr_t b):runner(std::move(r)),base(b){}
  addr_t DefaultAlloc()const{return base+5*8;}
  addr_t DefaultFree()const{return base+6*8;}
  static voidpf Alloc(voidpf opaque,uInt items,uInt size)noexcept{
    auto &s=*static_cast<Stream*>(opaque);
    if(s.allocate==s.owner->DefaultAlloc()&&s.free==s.owner->DefaultFree())return std::malloc(size_t(items)*size);
    void *guest=nullptr,*native=nullptr;
    const size_t bytes=size_t(items)*size;
    try{
      s.PublishAllocations();
      guest=s.allocate==s.owner->DefaultAlloc()?Allocate(items,size):reinterpret_cast<void*>(s.owner->runner(s.allocate,{s.opaque,items,size}));
      if(!guest)return nullptr;
      recomp::InvalidateGuestMemory(pm::Address(guest),bytes);
      native=std::malloc(bytes?bytes:1);
      if(!native){s.ReleaseGuest(guest,bytes);return nullptr;}
      recomp::ReadGuestMemory(native,pm::Address(guest),bytes);
      s.mirrors.emplace(native,Stream::Mirror{guest,bytes});return native;
    }catch(const std::bad_alloc&){std::free(native);if(guest)try{s.ReleaseGuest(guest,bytes);}catch(...){CallbackFailure();}return nullptr;
    }catch(...){CallbackFailure();}
  }
  static void Free(voidpf opaque,voidpf address)noexcept{
    auto &s=*static_cast<Stream*>(opaque);
    if(s.allocate==s.owner->DefaultAlloc()&&s.free==s.owner->DefaultFree()){std::free(address);return;}
    try{
      s.PublishAllocations();auto found=s.mirrors.find(address);
      if(found==s.mirrors.end())CallbackFailure();auto original=found->second;s.mirrors.erase(found);
      s.ReleaseGuest(original.guest,original.size);std::free(address);
    }catch(...){CallbackFailure();}
  }
  std::shared_ptr<Stream> Find(AndroidZStream *guest){
    std::lock_guard<std::mutex> guard(registry);auto i=streams.find(guest);
    return i==streams.end()?nullptr:i->second;
  }
  static void Status(AndroidZStream *g,const Stream &s){
    pm::Write(&g->message,pm::Address(s.native.msg));pm::Write(&g->data_type,int32_t(s.native.data_type));pm::Write(&g->adler,uint64_t(s.native.adler));
  }
};
Zlib::Zlib(Runner runner,addr_t base):impl_(std::make_unique<Impl>(std::move(runner),base)){
  if((base&7)||base>UINT64_MAX-7*8)throw std::invalid_argument("invalid zlib marker base");
}
Zlib::~Zlib(){
  // Free callbacks can reenter the provider. Keep the registry and runner alive
  // while cleanup runs, but reject new streams during shutdown.
  std::map<AndroidZStream*,std::shared_ptr<Impl::Stream>> pending;
  {std::lock_guard<std::mutex> guard(impl_->registry);impl_->stopping=true;pending.swap(impl_->streams);}
  pending.clear();
}
const char *Zlib::Version()const{return ::zlibVersion();}
addr_t Zlib::Marker(const std::string &name)const{
  for(size_t i=0;i<sizeof(names)/sizeof(*names);++i)if(name==names[i])return impl_->base+i*8;
  throw std::invalid_argument("unsupported zlib import: "+name);
}
int Zlib::Init(AndroidZStream *g,int bits,const char *version,int size)noexcept{
  try{
    if(!version||pm::String(version,1)!=std::string(1,ZLIB_VERSION[0])||size!=sizeof(AndroidZStream))return Z_VERSION_ERROR;
    if(!g)return Z_STREAM_ERROR;
    auto wire=pm::Read(g);
    {std::lock_guard<std::mutex> guard(impl_->registry);
      if(impl_->stopping||impl_->streams.count(g))return Z_STREAM_ERROR;
    }
    pm::Write(&g->message,addr_t(0));
    if(!wire.zalloc){wire.zalloc=impl_->DefaultAlloc();wire.opaque=0;pm::Write(&g->zalloc,wire.zalloc);pm::Write(&g->opaque,wire.opaque);}
    if(!wire.zfree){wire.zfree=impl_->DefaultFree();pm::Write(&g->zfree,wire.zfree);}
    if((wire.zalloc!=impl_->DefaultAlloc()||wire.zfree!=impl_->DefaultFree())&&!impl_->runner)return Z_STREAM_ERROR;
    auto stream=std::make_shared<Impl::Stream>(impl_.get(),wire.zalloc,wire.zfree,wire.opaque);
    recomp::InvalidateGuestMemory(pm::Address(stream.get()),sizeof(*stream));
    stream->native.zalloc=Impl::Alloc;stream->native.zfree=Impl::Free;stream->native.opaque=stream.get();
    int result=::inflateInit2_(&stream->native,bits,ZLIB_VERSION,sizeof(z_stream));
    stream->PublishAllocations();Impl::Status(g,*stream);
    if(result!=Z_OK){pm::Write(&g->state,addr_t(0));return result;}
    stream->live=true;
    {std::lock_guard<std::mutex> guard(impl_->registry);
      if(impl_->stopping||!impl_->streams.emplace(g,stream).second)return Z_STREAM_ERROR;
    }
    pm::Write(&g->state,pm::Address(stream.get()));pm::Write(&g->total_in,uint64_t(0));pm::Write(&g->total_out,uint64_t(0));return result;
  }catch(const std::bad_alloc&){return Z_MEM_ERROR;}catch(...){return Z_STREAM_ERROR;}
}
int Zlib::Inflate(AndroidZStream *g,int flush)noexcept{
  if(!g)return Z_STREAM_ERROR;
  try{
    auto s=impl_->Find(g);if(!s)return Z_STREAM_ERROR;
    std::lock_guard<std::recursive_mutex> guard(s->lock);
    auto wire=pm::Read(g);
    if(!s->live||s->busy||wire.state!=pm::Address(s.get()))return Z_STREAM_ERROR;
    if(!wire.next_out||(!wire.next_in&&wire.avail_in))return Z_STREAM_ERROR;
    struct Scope{bool &busy;Scope(bool&b):busy(b){busy=true;}~Scope(){busy=false;}} scope(s->busy);
    auto input=pm::Bytes(reinterpret_cast<void*>(wire.next_in),wire.avail_in);
    std::vector<Bytef> output(std::max<uint32_t>(wire.avail_out,1));
    s->native.next_in=input.data();s->native.avail_in=wire.avail_in;
    s->native.next_out=output.data();s->native.avail_out=wire.avail_out;
    const uLong total_in=s->native.total_in,total_out=s->native.total_out;
    int result=::inflate(&s->native,flush);
    const uint32_t consumed=wire.avail_in-s->native.avail_in,produced=wire.avail_out-s->native.avail_out;
    s->PublishAllocations();
    recomp::WriteGuestMemory(wire.next_out,output.data(),produced);
    pm::Write(&g->next_in,wire.next_in+consumed);pm::Write(&g->avail_in,uint32_t(s->native.avail_in));
    pm::Write(&g->next_out,wire.next_out+produced);pm::Write(&g->avail_out,uint32_t(s->native.avail_out));
    // Native totals, not pointer deltas: Z_NEED_DICT consumes its header but
    // returns before zlib updates total_in. Unsigned subtraction also handles
    // Windows' 32-bit uLong wrapping while guest counters remain LP64.
    pm::Write(&g->total_in,wire.total_in+uint64_t(uLong(s->native.total_in-total_in)));
    pm::Write(&g->total_out,wire.total_out+uint64_t(uLong(s->native.total_out-total_out)));
    Impl::Status(g,*s);return result;
  }catch(const std::bad_alloc&){return Z_MEM_ERROR;}catch(...){return Z_STREAM_ERROR;}
}
int Zlib::End(AndroidZStream *g)noexcept{
  if(!g)return Z_STREAM_ERROR;
  try{
    auto s=impl_->Find(g);if(!s)return Z_STREAM_ERROR;
    std::lock_guard<std::recursive_mutex> guard(s->lock);
    if(!s->live||s->busy||pm::Read(&g->state)!=pm::Address(s.get()))return Z_STREAM_ERROR;
    s->busy=true;int result=::inflateEnd(&s->native);s->busy=false;
    if(result==Z_OK){s->live=false;pm::Write(&g->state,addr_t(0));std::lock_guard<std::mutex> registry(impl_->registry);impl_->streams.erase(g);}
    return result;
  }catch(...){return Z_STREAM_ERROR;}
}
void Zlib::Install(recomp::Runtime &runtime){
  if(impl_->installed)throw std::logic_error("zlib imports already installed");
  runtime.AddImport(Marker("inflate"),recomp::MakeBridge<int32_t(AndroidZStream*,int32_t)>([this](auto s,auto f){return Inflate(s,f);}));
  runtime.AddImport(Marker("inflateEnd"),recomp::MakeBridge<int32_t(AndroidZStream*)>([this](auto s){return End(s);}));
  runtime.AddImport(Marker("inflateInit2_"),recomp::MakeBridge<int32_t(AndroidZStream*,int32_t,const char*,int32_t)>([this](auto s,auto b,auto v,auto n){return Init(s,b,v,n);}));
  runtime.AddImport(Marker("inflateInit_"),recomp::MakeBridge<int32_t(AndroidZStream*,const char*,int32_t)>([this](auto s,auto v,auto n){return Init(s,15,v,n);}));
  runtime.AddImport(Marker("zlibVersion"),recomp::MakeBridge<const char*()>([this]{return Version();}));
  runtime.AddImport(impl_->DefaultAlloc(),recomp::MakeBridge<void*(void*,uint32_t,uint32_t)>([](auto,auto n,auto size){return Allocate(n,size);}));
  runtime.AddImport(impl_->DefaultFree(),recomp::MakeBridge<void(void*,void*)>([](auto,auto p){pm::Free(p);}));
  impl_->installed=true;
}
}  // namespace bunker::windows
