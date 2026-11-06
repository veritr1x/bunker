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
  using FrameVector=std::vector<Frame>;
#ifdef _WIN32
  static void DestroyFrames(void *value) noexcept {
    // Scalar bookkeeping only: no Forget, jumps, guest callback or owner access.
    delete static_cast<FrameVector*>(value);
  }
  static FrameVector &Frames(){
    static const pthread_key_t key=[] {
      pthread_key_t result{};const int error=pthread_key_create(&result,DestroyFrames);
      if(error)throw std::runtime_error("automatic frames storage key creation failed: "+std::to_string(error));
      return result;
    }();
    auto *value=static_cast<FrameVector*>(pthread_getspecific(key));
    if(!value){
      auto next=std::make_unique<FrameVector>();const int error=pthread_setspecific(key,next.get());
      if(error)throw std::runtime_error("automatic frames storage publication failed: "+std::to_string(error));
      value=next.release();
    }
    return *value;
  }
#else
  static FrameVector &Frames(){static thread_local FrameVector frames;return frames;}
#endif
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
// Original Unity FreeType cmap validation owns a different automatic buffer.
// A whole guest-stack reservation is not a C automatic-object lifetime.
struct GameFontCmapEnvironments {
  struct Frame {const GameFontCmapEnvironments *owner;uint64_t token,thread_generation,generation;addr_t entry_sp,return_pc,environment=0;};
  using FrameVector=std::vector<Frame>;
  bunker::windows::NonlocalJumps *jumps=nullptr;
  recomp::Entry original=nullptr;
  std::function<bunker::windows::NonlocalJumps::Thread()> current;
  std::atomic<uint64_t> next_generation{1};
#ifdef _WIN32
  static void DestroyFrames(void *value) noexcept {delete static_cast<FrameVector*>(value);}
  static FrameVector &Frames(){
    static const pthread_key_t key=[] {
      pthread_key_t result{};const int error=pthread_key_create(&result,DestroyFrames);
      if(error)throw std::runtime_error("font cmap frames storage key creation failed: "+std::to_string(error));
      return result;
    }();
    auto *value=static_cast<FrameVector*>(pthread_getspecific(key));
    if(!value){
      auto next=std::make_unique<FrameVector>();const int error=pthread_setspecific(key,next.get());
      if(error)throw std::runtime_error("font cmap frames storage publication failed: "+std::to_string(error));
      value=next.release();
    }
    return *value;
  }
#else
  static FrameVector &Frames(){static thread_local FrameVector frames;return frames;}
#endif
  void BeforeSetjmp(State &s,uint64_t token){
    if(s.gpr.x30.qword!=0x708d9240)return;
    Require(bool(current),"font cmap owner has no current-thread source");const auto thread=current();
    auto &frames=Frames();Require(!frames.empty()&&frames.back().owner==this&&thread.token==token&&frames.back().token==token&&frames.back().thread_generation==thread.generation,"font cmap setjmp has no live original invocation");
    auto &frame=frames.back();
    Require(frame.entry_sp>=0x1a0&&s.gpr.sp.qword==frame.entry_sp-0x1a0&&s.gpr.x0.qword==s.gpr.sp.qword+0x10,"original font cmap environment/frame shape differs");
    Require(!frame.environment||frame.environment==s.gpr.x0.qword,"font cmap invocation changed its automatic environment");
    // Each cmap record may save the SAME automatic buffer again. Save replaces
    // its wire context while its invocation generation stays live.
    frame.environment=s.gpr.x0.qword;
  }
  std::optional<bunker::windows::NonlocalJumps::Region> Find(addr_t env,size_t size,uint64_t token){
    if(size!=256||!current)return {};
    const auto thread=current();if(thread.token!=token||!thread.generation)return {};
    for(auto i=Frames().rbegin();i!=Frames().rend();++i)
      if(i->owner==this&&i->token==token&&i->thread_generation==thread.generation&&i->environment==env)
        return bunker::windows::NonlocalJumps::Region{env,env+256,i->generation};
    return {};
  }
  Memory *Run(State &s,addr_t pc,Memory *memory){
    Require(jumps&&original&&bool(current),"font cmap automatic owner is not configured");
    const auto thread=current();
    Require(pc==0x708d905c&&thread.token&&thread.generation&&thread.stack_low&&thread.stack_high>thread.stack_low&&!(s.gpr.sp.qword&15)&&s.gpr.sp.qword>=thread.stack_low&&s.gpr.sp.qword-thread.stack_low>=0x1a0&&s.gpr.sp.qword<=thread.stack_high,"original font cmap entry has no complete owned stack frame");
    const auto generation=next_generation.fetch_add(1);Require(generation&&generation!=UINT64_MAX,"font cmap automatic generation exhausted");
    Frames().push_back({this,thread.token,thread.generation,generation,s.gpr.sp.qword,s.gpr.x30.qword,0});
    auto retire=[&]{
      auto &frames=Frames();Require(!frames.empty()&&frames.back().owner==this&&frames.back().generation==generation&&frames.back().token==thread.token,"font cmap invocation nesting differs at retirement");
      const auto env=frames.back().environment;if(env)jumps->Forget(env);frames.pop_back();
    };
    Memory *result=nullptr;
    try{
      result=original(s,pc,memory);Require(!Frames().empty(),"font cmap invocation disappeared before return");const auto frame=Frames().back();
      Require(frame.owner==this&&frame.generation==generation&&frame.token==thread.token&&frame.thread_generation==thread.generation&&s.gpr.sp.qword==frame.entry_sp&&s.gpr.pc.qword==frame.return_pc,"original font cmap helper did not return within its invocation");
      // Empty/invalid/unknown-format cmap tables legitimately return before
      // setjmp. Revoke only a buffer that was actually saved.
    }catch(...){retire();throw;}
    retire();return result;
  }
};
GameFontCmapEnvironments *game_font_environments=nullptr;
Memory *GameOriginalFontCmapHelper(State &s,addr_t pc,Memory *memory){try{
  Require(game_font_environments,"font cmap owner is unavailable");
  return game_font_environments->Run(s,pc,memory);
 }catch(const std::exception &error){std::fprintf(stderr,"Game bootstrap: original font cmap owner failed:%s\n",error.what());std::abort();}}
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
struct GameWorkerObservation {
  struct NativeEnvironment {
    DWORD last_error=GetLastError();int native_errno=errno;fenv_t environment{};
    NativeEnvironment(){std::fegetenv(&environment);}
    ~NativeEnvironment(){std::fesetenv(&environment);errno=native_errno;SetLastError(last_error);}
  };
  // Scalar only: no destructor or provider access at native TLS retirement.
  static uint64_t &Token(){static thread_local uint64_t token=0;return token;}
  static void Lifecycle(const char *phase,const bunker::windows::Pthreads::WorkerInfo &info){
    NativeEnvironment preserve;
    std::fprintf(stderr,"Game bootstrap: worker lifecycle phase=%s token=%#llx parent=%#llx native_tid=%u stack_low=%#llx stack_high=%#llx tls=%#llx; observation only\n",phase,(unsigned long long)info.token,(unsigned long long)info.parent_token,info.native_tid,(unsigned long long)info.stack_low,(unsigned long long)info.stack_high,(unsigned long long)info.tls_address);
  }
  static void Enter(const bunker::windows::Pthreads::WorkerInfo &info){NativeEnvironment preserve;Token()=info.token;Lifecycle("enter",info);}
  static void Retire(const bunker::windows::Pthreads::WorkerInfo &info,bunker::windows::Pthreads::WorkerRetirement reason){
    NativeEnvironment preserve;Lifecycle(reason==bunker::windows::Pthreads::WorkerRetirement::normal?"retire_normal":"retire_cancelled",info);
    if(Token()==info.token)Token()=0;
  }
  static uint64_t Wait(const char *phase,const char *name,const State &s){
    NativeEnvironment preserve;const auto token=Token();if(!token)return 0;
    std::fprintf(stderr,"Game bootstrap: worker wait phase=%s import=%s token=%#llx native_tid=%lu PC=%#llx SP=%#llx FP=%#llx LR=%#llx x0=%#llx x1=%#llx x2=%#llx; call observation, not blocked-state proof\n",phase,name,(unsigned long long)token,GetCurrentThreadId(),(unsigned long long)s.gpr.pc.qword,(unsigned long long)s.gpr.sp.qword,(unsigned long long)s.gpr.x29.qword,(unsigned long long)s.gpr.x30.qword,(unsigned long long)s.gpr.x0.qword,(unsigned long long)s.gpr.x1.qword,(unsigned long long)s.gpr.x2.qword);
    return token;
  }
  static void BeforeCreate(const State &s){
    NativeEnvironment preserve;
    if(s.gpr.x30.qword!=0x82556a64||s.gpr.x2.qword!=0x82556a94||!s.gpr.x3.qword)return;
    const auto record=s.gpr.x3.qword;Require(record<=UINT64_MAX-0x20,"observed thread record prefix overflow");
    // Only initialized fields in the binary-proved 0x68-byte allocation. Read
    // before Create: the child may immediately free the nested 0x18 payload.
    const auto callback=Read<addr_t>(record+0x10),payload=Read<addr_t>(record+0x18);
    std::fprintf(stderr,"Game bootstrap: original worker create witness LR=%#llx entry=%#llx record=%#llx callback=%#llx payload=%#llx; before child start\n",(unsigned long long)s.gpr.x30.qword,(unsigned long long)s.gpr.x2.qword,(unsigned long long)record,(unsigned long long)callback,(unsigned long long)payload);
    if(callback==0x82557c80&&payload){
      Require(payload<=UINT64_MAX-0x18,"observed thread payload overflow");
      const auto owner=Read<addr_t>(payload),function=Read<addr_t>(payload+8),argument=Read<addr_t>(payload+16);
      std::fprintf(stderr,"Game bootstrap: original worker payload owner=%#llx function=%#llx argument=%#llx bytes=24; before child start, no post-create read\n",(unsigned long long)owner,(unsigned long long)function,(unsigned long long)argument);
    }
  }
};
struct GameTlsAudit {
  addr_t free_callback=0;
  std::function<void(State&,const std::function<void(State&)> &)> create_boundary;
  std::mutex mutex;std::map<int32_t,addr_t> destructors;
  addr_t Marker(const std::string &name)const{
    if(name=="pthread_key_create")return 0x7ffc60000000ULL;
    if(name=="pthread_key_delete")return 0x7ffc60000008ULL;
    if(name=="pthread_setspecific")return 0x7ffc60000010ULL;
    if(name=="pthread_create")return 0x7ffc60000018ULL;
    const char *waits[]={"pthread_cond_wait","pthread_cond_timedwait","pthread_mutex_lock","pthread_rwlock_rdlock","pthread_rwlock_wrlock","pthread_once","pthread_join","sem_wait","sem_timedwait","sigsuspend"};
    for(size_t i=0;i<std::size(waits);++i)if(name==waits[i])return 0x7ffc60000020ULL+i*8;
    return 0;
  }
  void Install(recomp::Runtime &runtime,bunker::windows::Pthreads &threads){
    runtime.AddImport(Marker("pthread_key_create"),recomp::MakeBridge<int32_t(int32_t*,addr_t)>([&threads,this](auto out,auto dtor){
      if(dtor&&!Translated(dtor)&&dtor!=free_callback){std::fprintf(stderr,"Game bootstrap: reached unregistered real pthread TLS destructor=%#llx\n",(unsigned long long)dtor);std::abort();}
      auto result=threads.KeyCreate(out,dtor);if(!result){auto key=Read<int32_t>(reinterpret_cast<addr_t>(out));std::lock_guard lock(mutex);destructors[key]=dtor;}return result;
    }));
    runtime.AddImport(Marker("pthread_key_delete"),recomp::MakeBridge<int32_t(int32_t)>([&threads,this](auto key){auto result=threads.KeyDelete(key);if(!result){std::lock_guard lock(mutex);destructors.erase(key);}return result;}));
    runtime.AddImport(Marker("pthread_setspecific"),recomp::MakeBridge<int32_t(int32_t,uint64_t)>([&threads](auto key,auto value){return threads.SetSpecific(key,value);}));
    auto create=recomp::MakeBridge<int32_t(uint64_t*,const bunker::windows::AndroidThreadAttr*,addr_t,addr_t)>([&threads](auto out,auto attr,auto entry,auto arg){
      if(entry&&!Translated(entry)){std::fprintf(stderr,"Game bootstrap: reached unregistered real pthread start=%#llx\n",(unsigned long long)entry);std::abort();}
      auto result=threads.Create(out,attr,entry,arg);if(!result)std::fprintf(stderr,"Game bootstrap: actual guest worker created token=%#llx entry=%#llx; no synthetic SignalHost binding\n",(unsigned long long)Read<uint64_t>(reinterpret_cast<addr_t>(out)),(unsigned long long)entry);return result;
    });
    runtime.AddImport(Marker("pthread_create"),[this,create](State &s){try{if(create_boundary)create_boundary(s,create);else{GameWorkerObservation::BeforeCreate(s);create(s);}}catch(const std::exception &error){std::fprintf(stderr,"Game bootstrap: worker creation observer/provider failed:%s\n",error.what());std::abort();}catch(...){std::fprintf(stderr,"Game bootstrap: worker creation observer/provider failed:unknown host exception\n");std::abort();}});
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
