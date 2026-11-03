#include "package_test_session.h"
#include <algorithm>
#include <functional>
#include <limits>
#include <map>
#include <memory>
#include <vector>
struct LongPayload {std::function<void()> retired;~LongPayload(){retired();}};
int main(){try{
 unsigned checks=0;auto check=[&](bool value,const char *why){if(!value)throw std::runtime_error(why);++checks;};
 elf_image image{};check(!elf_load(PACKAGE_IMAGE,0x74000000,nullptr,&image),"NDK long fixture loads");Session h(image);
 auto run=[&](const char *symbol,std::initializer_list<addr_t> args){alignas(16)std::array<uint8_t,65536> stack{};State s{};Reg GPR::*registers[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};size_t n=0;for(auto a:args)(s.gpr.*registers[n++]).qword=a;auto top=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.sp.qword=top;s.gpr.x30.qword=0xfeedffff;s.gpr.x19.qword=0x9876543210abcdefULL;s.gpr.x20.qword=0x123456789abcdef0ULL;h.runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,symbol)));check(s.gpr.sp.qword==top&&s.gpr.pc.qword==0xfeedffff&&s.gpr.x19.qword==0x9876543210abcdefULL&&s.gpr.x20.qword==0x123456789abcdef0ULL,"actual NDK caller preserves SP/return/callee registers");return s.gpr.x0.qword;};
 h.host.DefineClass("LongProbe");h.host.DefineClass("LongPayload");h.host.DefineClass("LongWrong");
 auto receiver=h.host.NewInstance("LongProbe"),reference=h.host.NewString(u"long argument"),owner=h.find("LongProbe");
 int64_t expected=0,wide=0;int32_t integer=0;unsigned callbacks=0,retirements=0;int failure=0;bool mixed=false,nesting=false;addr_t zero_id=0;
 std::vector<addr_t> borrowed,weak;unsigned nested_calls=0;
 auto implementation=[&](addr_t r,const bunker::jni::Host::MethodArguments &a)->int64_t{
  ++callbacks;check(h.call(232,r)==1&&h.call(24,r,receiver),"jlong receiver is a borrowed callee local with actual identity");borrowed.push_back(r);
  if(mixed){check(a[0]!=reference&&h.call(24,a[0],reference)&&h.call(232,a[0])==1,"reference argument is separately borrowed");borrowed.push_back(a[0]);check(a[1]==static_cast<uint64_t>(wide)&&static_cast<int32_t>(a[2])==integer,"J argument keeps all64 bits and I argument low32 sign");}
  check(!h.call(19,4),"long callback can create user frame");auto temporary=h.host.NewString(u"owned long temporary");weak.push_back(h.call(226,temporary));
  auto payload=std::make_shared<LongPayload>();payload->retired=[&]{++retirements;auto local=h.host.NewString(u"retirement reentry");h.host.DeleteLocalReference(local);};h.host.NewHostInstance("LongPayload",std::move(payload));
  if(nesting){nesting=false;bool was=mixed;mixed=false;auto value=h.call(52,receiver,zero_id);mixed=was;check(value==static_cast<uint64_t>(expected),"same-thread reentrant long callback keeps outer owned frame");++nested_calls;}
  if(failure==1)h.host.ThrowException("java/lang/IllegalStateException",u"long method exception");
  if(failure==2)throw std::runtime_error("long C++ exception");
  return expected;
 };
 h.host.DefineLongMethod("LongProbe","zero","()J",implementation);h.host.DefineLongMethod("LongProbe","mixed","(Ljava/lang/Object;JI)J",implementation);
 zero_id=h.method("LongProbe","zero","()J");auto mixed_id=h.method("LongProbe","mixed","(Ljava/lang/Object;JI)J");check(zero_id&&mixed_id&&h.host.PendingException().empty(),"instance long metadata resolves exact descriptors");
 auto clean=[&]{for(auto v:borrowed)check(h.call(232,v)==0,"borrowed callback local expires after scalar return");borrowed.clear();for(auto v:weak){check(h.call(24,v,0),"callback temporary/extra user frame retired");h.call(227,v);}weak.clear();check(h.call(232,receiver)==1&&h.call(232,reference)==1&&h.host.PendingException().empty(),"caller locals survive callback cleanup");};
 auto invoke=[&](addr_t object,addr_t method,int form){struct{uint64_t before=0x1122334455667788ULL,out[2]={0,0},after=0x8877665544332211ULL;} memory;
  auto result=mixed?run("long_mixed",{h.host.EnvAddress(),object,method,reference,static_cast<uint64_t>(wide),static_cast<uint32_t>(integer),static_cast<addr_t>(form),reinterpret_cast<addr_t>(memory.out)}):run("long_zero",{h.host.EnvAddress(),object,method,static_cast<addr_t>(form),reinterpret_cast<addr_t>(memory.out)});
  check(memory.before==0x1122334455667788ULL&&memory.after==0x8877665544332211ULL&&memory.out[0]==0x123456789abcdef0ULL&&memory.out[1]==(result^0xfedcba9876543210ULL),"NDK direct/V/A leaves arguments unchanged and writes following result bits");return result;
 };
 const int64_t values[]={0,1,-1,INT64_MIN,INT64_MAX,INT64_C(0x100000000),-INT64_C(0x100000001),INT64_C(0x123456789abcdef),-INT64_C(0x123456789abcdef)};
 for(unsigned i=0;i<std::size(values);++i)for(int shape=0;shape<2;++shape)for(int form=0;form<3;++form){expected=values[i];wide=values[(i+3)%std::size(values)];integer=(i&1)?INT32_MIN:INT32_MAX;mixed=shape;
  auto result=invoke(receiver,mixed?mixed_id:zero_id,form);check(result==static_cast<uint64_t>(expected)&&h.host.PendingException().empty(),"exact signed64 return without truncation or object promotion");clean();std::printf("RECORD %u %d %d %016llx %016llx\n",i,shape,form,static_cast<unsigned long long>(result),static_cast<unsigned long long>(result^0xfedcba9876543210ULL));
 }
 // The real receiver's implementation is selected before mixed arguments are decoded.
 h.host.DefineClass("LongBase",{{"dispatch","(Ljava/lang/Object;JI)J"}});h.host.DefineInterface("LongInterface",{{"dispatch","(Ljava/lang/Object;JI)J"}});h.host.DefineClass("LongDerived",{},"LongBase",false,{"LongInterface"});auto derived=h.host.NewInstance("LongDerived");
 h.host.DefineLongMethod("LongDerived","dispatch","(Ljava/lang/Object;JI)J",[&](addr_t r,const bunker::jni::Host::MethodArguments&a){check(h.call(24,r,derived),"virtual long receiver matches derived identity");check(h.call(24,a[0],reference)&&a[1]==static_cast<uint64_t>(wide)&&static_cast<int32_t>(a[2])==integer,"base/interface ID uses selected long signature arguments");return expected;});
 mixed=true;wide=INT64_MIN;integer=INT32_MIN;expected=-INT64_C(0x100000001);
 for(auto name:{"LongBase","LongInterface"})for(int form=0;form<3;++form){check(invoke(derived,h.method(name,"dispatch","(Ljava/lang/Object;JI)J"),form)==static_cast<uint64_t>(expected),"Base/interface MethodID invokes concrete virtual long override");}
 mixed=false;nesting=true;expected=INT64_MAX;check(invoke(receiver,zero_id,1)==static_cast<uint64_t>(expected)&&nested_calls==1,"reentrant long callback completed");clean();
 for(int form=0;form<3;++form){failure=1;check(invoke(receiver,zero_id,form)==0&&h.host.PendingException().find("long method exception")!=std::string::npos,"Java exception survives owned-frame cleanup and makes zero exceptional");h.host.ClearException();failure=0;clean();}
 failure=2;bool caught=false;try{h.call(52,receiver,zero_id);}catch(const std::runtime_error&e){caught=std::string(e.what())=="long C++ exception";}failure=0;check(caught,"direct C++ entry rethrows after owned-frame cleanup");clean();
 auto java_error=[&](const char *type){check(h.host.PendingException().find(type)!=std::string::npos,"receiver/result validation produces typed Java exception");h.host.ClearException();};
 auto prior=callbacks;check(h.call(52,0,zero_id)==0,"null receiver returns exceptional zero");java_error("NullPointerException");check(h.call(52,h.host.NewInstance("LongWrong"),zero_id)==0,"wrong receiver returns exceptional zero");java_error("IllegalArgumentException");check(h.call(52,receiver,0x1234)==0,"invalid method ID returns exceptional zero");java_error("NoSuchMethodError");check(callbacks==prior,"invalid receiver/method never invokes callback");
 h.host.DefineIntMethod("LongProbe","integer","()I",[](addr_t,const bunker::jni::Host::MethodArguments&){return int32_t(-1);});auto int_id=h.method("LongProbe","integer","()I");
 for(size_t slot:{size_t(52),size_t(53),size_t(54)}){check(!h.call(slot,receiver,int_id),"long family rejects int descriptor");java_error("IllegalArgumentException");}
 for(size_t slot:{size_t(49),size_t(50),size_t(51)}){check(!h.call(slot,receiver,zero_id),"int family rejects long descriptor");java_error("IllegalArgumentException");}
 check(!h.call(113,owner,reinterpret_cast<addr_t>("zero"),reinterpret_cast<addr_t>("()J")),"instance long declaration cannot resolve as static");java_error("NoSuchMethodError");
 for(const char *sig:{"()I","()F","()D","()Ljava/lang/Object;","(D)J","(IIII)J","([I)J","(J)JJ"}){bool rejected=false;try{h.host.DefineLongMethod("LongProbe","bad",sig,implementation);}catch(const std::invalid_argument&){rejected=true;}check(rejected,"long binder validates exact J return and existing bounded descriptor grammar");}
 bool duplicate=false;try{h.host.DefineLongMethod("LongProbe","zero","()J",implementation);}catch(const std::invalid_argument&){duplicate=true;}check(duplicate,"duplicate long declaration remains rejected");
 bool missing=false;try{h.host.DefineLongMethod("LongProbe","missing","()J",{});}catch(const std::invalid_argument&){missing=true;}check(missing,"empty long handler rejected");
 // No static/nonvirtual feature is introduced by the instance-only adapter.
 for(size_t slot:{size_t(82),size_t(83),size_t(84),size_t(132),size_t(133),size_t(134)}){bool rejected=false;try{h.call(slot,receiver,zero_id);}catch(const std::runtime_error&e){rejected=std::string(e.what()).find("unsupported JNI")!=std::string::npos;}check(rejected,"nonvirtual/static long families keep their existing unsupported boundary");}
 check(retirements==callbacks&&h.host.PendingException().empty(),"every long callback root/temporary retired without native cleanup or hidden exception");
 std::printf("JNI long method: %u checks; actual NDK instance direct/V/A signed64, virtual overrides, exceptions and owned frames\n",checks);
}catch(const std::exception&e){std::fprintf(stderr,"JNI long method test: %s\n",e.what());return 1;}}
