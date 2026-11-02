#pragma once
// Included in the new harness's anonymous namespace after Require/Read.
struct GameModuleLedger {
  std::string name;std::vector<addr_t> constructors,finalizers;
  size_t constructed=0,finalized=0;
  bool Owns(addr_t pc)const{return std::find(constructors.begin(),constructors.end(),pc)!=constructors.end()||std::find(finalizers.begin(),finalizers.end(),pc)!=finalizers.end();}
  void Run(addr_t pc,bunker::windows::Pthreads &threads){
    const bool ctor=std::find(constructors.begin(),constructors.end(),pc)!=constructors.end();
    if(ctor){Require(!finalized&&constructed<constructors.size()&&pc==constructors[constructed],"module constructor owner/order differs");}
    else Require(constructed==constructors.size()&&finalized<finalizers.size()&&pc==finalizers[finalizers.size()-1-finalized],"module finalizer owner/order differs");
    std::fprintf(stderr,"Game bootstrap: %s %s %zu/%zu entry=%#llx\n",name.c_str(),ctor?"constructor":"finalizer",(ctor?constructed:finalized)+1,ctor?constructors.size():finalizers.size(),(unsigned long long)pc);
    threads.Run(pc);if(ctor)++constructed;else ++finalized;
  }
};
struct GameAutomaticEnvironments {
  struct Frame {uint64_t token,generation;addr_t entry_sp,return_pc,environment=0;};
  bunker::windows::NonlocalJumps *jumps=nullptr;recomp::Entry original=nullptr;
  std::function<bunker::windows::NonlocalJumps::Thread()> current;
  std::atomic<uint64_t> next_generation{1};
  static std::vector<Frame> &Frames(){static thread_local std::vector<Frame> frames;return frames;}
  void BeforeSetjmp(State &s,uint64_t token){
    if(s.gpr.x30.qword!=0x825b0580)return;
    auto &frames=Frames();Require(!frames.empty()&&frames.back().token==token,"IL2CPP automatic setjmp has no live original helper invocation");
    auto &f=frames.back();Require(f.entry_sp>=0x140&&s.gpr.sp.qword==f.entry_sp-0x140&&s.gpr.x0.qword==s.gpr.sp.qword+8,"original IL2CPP automatic environment/frame shape differs");
    Require(!f.environment,"original automatic environment saved twice in one invocation");f.environment=s.gpr.x0.qword;
  }
  std::optional<bunker::windows::NonlocalJumps::Region> Find(addr_t env,size_t size,uint64_t token){
    if(size!=256)return {};
    for(auto i=Frames().rbegin();i!=Frames().rend();++i)if(i->token==token&&i->environment==env)return bunker::windows::NonlocalJumps::Region{env,env+256,i->generation};
    return {};
  }
};
GameAutomaticEnvironments *game_environments=nullptr;
Memory *GameOriginalSaveHelper(State &s,addr_t pc,Memory *memory){try{
  auto &owners=*game_environments;auto generation=owners.next_generation.fetch_add(1);Require(generation!=0,"automatic environment generation exhausted");
  // No reference into this vector survives a nested original guest call.
  const auto current=owners.jumps;Require(current,"nonlocal owner not configured");
  Require(bool(owners.current),"automatic owner has no truthful current-thread source");auto thread=owners.current();auto token=thread.token;
  Require(!(s.gpr.sp.qword&15)&&s.gpr.sp.qword>=thread.stack_low&&s.gpr.sp.qword-thread.stack_low>=0x140&&s.gpr.sp.qword<=thread.stack_high,"original automatic helper entry has no complete owned stack frame");
  owners.Frames().push_back({token,generation,s.gpr.sp.qword,s.gpr.x30.qword,0});
  auto result=owners.original(s,pc,memory);auto frame=owners.Frames().back();
  Require(frame.generation==generation&&frame.token==token&&frame.environment&&s.gpr.sp.qword==frame.entry_sp&&s.gpr.pc.qword==frame.return_pc,"original automatic helper did not return within its real invocation");
  owners.jumps->Forget(frame.environment);owners.Frames().pop_back();
  // Return only after the automatic object has been revoked. The original
  // trailing raw global is left untouched; no collector callback is replaced.
  return result;
 }catch(const std::exception &e){std::fprintf(stderr,"Game bootstrap: original automatic-context owner failed:%s\n",e.what());std::abort();}}
struct GameTlsAudit {
  addr_t free_callback=0;
  std::mutex mutex;std::map<int32_t,addr_t> destructors;
  addr_t Marker(const std::string &name)const{
    if(name=="pthread_key_create")return 0x7ffc60000000ULL;
    if(name=="pthread_key_delete")return 0x7ffc60000008ULL;
    if(name=="pthread_setspecific")return 0x7ffc60000010ULL;
    if(name=="pthread_create")return 0x7ffc60000018ULL;
    return 0;
  }
  void Install(recomp::Runtime &runtime,bunker::windows::Pthreads &threads){
    runtime.AddImport(Marker("pthread_key_create"),recomp::MakeBridge<int32_t(int32_t*,addr_t)>([&threads,this](auto out,auto dtor){
      if(dtor&&!Translated(dtor)&&dtor!=free_callback){std::fprintf(stderr,"Game bootstrap: reached unregistered real pthread TLS destructor=%#llx\n",(unsigned long long)dtor);std::abort();}
      auto result=threads.KeyCreate(out,dtor);if(!result){auto key=Read<int32_t>(reinterpret_cast<addr_t>(out));std::lock_guard lock(mutex);destructors[key]=dtor;}return result;
    }));
    runtime.AddImport(Marker("pthread_key_delete"),recomp::MakeBridge<int32_t(int32_t)>([&threads,this](auto key){auto result=threads.KeyDelete(key);if(!result){std::lock_guard lock(mutex);destructors.erase(key);}return result;}));
    runtime.AddImport(Marker("pthread_setspecific"),recomp::MakeBridge<int32_t(int32_t,uint64_t)>([&threads](auto key,auto value){return threads.SetSpecific(key,value);}));
    runtime.AddImport(Marker("pthread_create"),recomp::MakeBridge<int32_t(uint64_t*,const bunker::windows::AndroidThreadAttr*,addr_t,addr_t)>([&threads](auto out,auto attr,auto entry,auto arg){
      if(entry&&!Translated(entry)){std::fprintf(stderr,"Game bootstrap: reached unregistered real pthread start=%#llx\n",(unsigned long long)entry);std::abort();}
      auto result=threads.Create(out,attr,entry,arg);if(!result)std::fprintf(stderr,"Game bootstrap: actual guest worker created token=%#llx entry=%#llx; no synthetic SignalHost binding\n",(unsigned long long)Read<uint64_t>(reinterpret_cast<addr_t>(out)),(unsigned long long)entry);return result;
    }));
  }
  size_t PendingModuleCallbacks(bunker::windows::Pthreads &threads){
    std::vector<std::pair<int32_t,addr_t>> keys;{std::lock_guard lock(mutex);for(auto entry:destructors)if(entry.second)keys.push_back(entry);}
    size_t pending=0;for(auto [key,dtor]:keys)if(auto value=threads.GetSpecific(key)){
      const bool provider_owned=free_callback&&dtor==free_callback;
      if(!provider_owned)++pending;
      std::fprintf(stderr,"Game bootstrap: actual UI TLS %s destructor remains key=%d callback=%#llx value=%#llx\n",provider_owned?"provider-free":"module-owned",key,(unsigned long long)dtor,(unsigned long long)value);
    }return pending;
  }
};
