#pragma once
// Include after the three collector profiles, with socket_transport.h already
// included at global scope. Epochs, records and delivery stay in those original
// persistent lifetime owners, including late requests across provider phases.
class GameSocketWaitCollector {
  using Transport=bunker::windows::SocketTransport;
  bunker::windows::Pthreads&threads_;
  GameCollectorDelivery&ordinary_;GameUnityMainCollector&main_;GameUnityWorkerCollector&workers_;
  GameSocketWaitContext::SitePolicy policy_;
  static bool WaitImport(const std::string&name){return name=="read"||name=="write"||name=="connect"||name=="accept"||name=="send"||name=="recv"||name=="sendto"||name=="recvfrom"||name=="sendmsg"||name=="recvmsg"||name=="poll"||name=="select";}
  static GameSocketWaitContext::Operation Operation(Transport::WaitOperation value){
    using S=Transport::WaitOperation;using D=GameSocketWaitContext::Operation;
    switch(value){case S::Read:return D::Read;case S::Write:return D::Write;case S::Connect:return D::Connect;case S::Accept:return D::Accept;case S::Poll:return D::Poll;case S::Select:return D::Select;case S::PipeRead:return D::PipeRead;case S::PipeWrite:return D::PipeWrite;}
    throw std::runtime_error("socket collector: unknown transport operation");
  }
  static GameSocketWaitContext::Phase Phase(Transport::WaitPhase value){
    using S=Transport::WaitPhase;using D=GameSocketWaitContext::Phase;
    switch(value){case S::Copied:return D::Copied;case S::BeforeNativeWait:return D::BeforeNativeWait;case S::AfterNativeWait:return D::AfterNativeWait;case S::Returned:return D::Returned;}
    throw std::runtime_error("socket collector: unknown transport observation phase");
  }
 public:
  GameSocketWaitCollector(bunker::windows::Pthreads&threads,GameCollectorDelivery&ordinary,GameUnityMainCollector&main,GameUnityWorkerCollector&workers,GameSocketWaitContext::SitePolicy policy={})
    :threads_(threads),ordinary_(ordinary),main_(main),workers_(workers),policy_(std::move(policy)){}
  void WithSocketWait(const std::string&name,State&state,const std::function<void()>&invoke){
    GameSocketWaitContext::NativeEnvironment preserve;
    const auto token=threads_.Self();
    const bool main=main_.Owns(token),worker=!main&&workers_.Owns(token),ordinary=!main&&!worker&&ordinary_.Owns(token);
    {
      static thread_local std::map<std::pair<uint64_t,std::string>,uint64_t> counts;
      auto&count=counts[{token,name}];if(count!=UINT64_MAX)++count;
      if(count<=64||count%4096==0)std::fprintf(stderr,"Game socket import: name=%s token=%#llx native_tid=%lu PC=%#llx LR=%#llx lifetime=%s site=%s calls=%llu; first64 then every4096, GC record not inferred\n",name.c_str(),(unsigned long long)token,GetCurrentThreadId(),(unsigned long long)state.gpr.pc.qword,(unsigned long long)state.gpr.x30.qword,main?"attached_main":worker?"prepared_Unity_worker":ordinary?"prepared_worker":"unknown",(policy_?policy_(name,state):GameSocketWaitContext::OriginalSite(name,state))?"listed":"unlisted",(unsigned long long)count);
    }
    if(!WaitImport(name)){invoke();return;}
    if(main){main_.WithSocketWait(name,state,invoke,policy_);return;}
    if(worker){workers_.WithSocketWait(name,state,invoke,policy_);return;}
    if(ordinary){ordinary_.WithSocketWait(name,state,invoke,policy_);return;}
    // No lifecycle, record or signal context is fabricated for a foreign role.
    invoke();
  }
  Transport::WaitDecision Observe(const Transport::WaitObservation&source){
    GameSocketWaitContext::NativeEnvironment preserve;
    const GameSocketWaitContext::Observation observation{source.state,source.descriptor,Operation(source.operation),Phase(source.phase),source.request_identity,source.retained_request,source.finite,source.deadline_nanoseconds};
    const auto token=threads_.Self();GameSocketWaitContext::Decision decision;
    if(main_.Owns(token))decision=main_.ObserveSocketWait(observation);
    else if(workers_.Owns(token))decision=workers_.ObserveSocketWait(observation);
    else if(ordinary_.Owns(token))decision=ordinary_.ObserveSocketWait(observation);
    return {decision.handled,decision.restart};
  }
};
