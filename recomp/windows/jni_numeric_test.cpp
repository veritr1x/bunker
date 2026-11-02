#include "package_test_session.h"
#include "numeric_expected.h"
#include <algorithm>
#include <atomic>
#include <cstring>
#include <functional>
#include <map>
struct NumericPayload {std::function<void()> retired;~NumericPayload(){retired();}};
int main(){try{
 unsigned checks=0;auto check=[&](bool value,const char *why){if(!value)throw std::runtime_error(why);++checks;};
 elf_image image{};check(!elf_load(PACKAGE_IMAGE,0x74000000,nullptr,&image),"actual Android NDK numeric callers load");Session h(image);
 // Transparent observation of the actual production-installed JNI dispatch.
 // Arguments/results are never repacked and exceptions stay inside its fence.
 recomp::Runtime observed;observed.AddTraces(kTraces,std::size(kTraces));
 struct VaList {addr_t stack,gr_top,vr_top;int32_t gr_offs,vr_offs;};
 unsigned va_calls=0,float_returns=0,int_returns=0;bool observing=true;
 for(size_t slot=4;slot<bunker::jni::kEnvSlots;++slot)observed.AddImport(h.host.EnvMarker(slot),[&,slot](State &s){
   const bool via_v=slot==29||slot==35||slot==50||slot==56||slot==115||slot==130||slot==136;
   auto pointer=s.gpr.x3.qword;std::vector<std::pair<addr_t,std::vector<uint8_t>>> snapshots;
   auto keep=[&](addr_t p,size_t n){std::vector<uint8_t> bytes(n);recomp::ReadGuestMemory(bytes.data(),p,n);snapshots.emplace_back(p,std::move(bytes));};
   if(observing&&via_v&&pointer){VaList list{};recomp::ReadGuestMemory(&list,pointer,sizeof(list));keep(pointer,sizeof(list));if(list.gr_offs<0)keep(list.gr_top+list.gr_offs,-list.gr_offs);if(list.vr_offs<0)keep(list.vr_top+list.vr_offs,-list.vr_offs);++va_calls;}
   h.runtime.Dispatch(s,h.host.EnvMarker(slot),nullptr);
   for(const auto &[p,bytes]:snapshots){std::vector<uint8_t> after(bytes.size());recomp::ReadGuestMemory(after.data(),p,after.size());check(after==bytes,"actual passed va_list and GP/VR save areas are immutable");}
   if(slot==49||slot==50||slot==51||slot==129||slot==130||slot==131){check(!(s.gpr.x0.qword>>32),"actual jint JNI result is W0 with upper X0 zero");++int_returns;}
   if(slot==55||slot==56||slot==57||slot==135||slot==136||slot==137){std::array<uint8_t,16> raw{};std::memcpy(raw.data(),&s.simd.v[0],16);check(std::all_of(raw.begin()+4,raw.end(),[](auto b){return b==0;}),"actual float JNI result uses S0 and deterministic zero SIMD upper bits");++float_returns;}
 });
 auto run=[&](const char *symbol,std::initializer_list<addr_t> values){alignas(16)std::array<uint8_t,65536> stack{};State s{};Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6,&GPR::x7};size_t i=0;for(auto v:values)(s.gpr.*regs[i++]).qword=v;auto top=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.sp.qword=top;s.gpr.x30.qword=0xfeedffff;s.gpr.x20.qword=0x123456789abcdef0ULL;observed.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,symbol)));check(s.gpr.sp.qword==top&&s.gpr.pc.qword==0xfeedffff&&s.gpr.x20.qword==0x123456789abcdef0ULL,"NDK numeric call preserves PC/SP/callee-saved canary");return s.gpr.x0.qword;};
 h.host.DefineClass("NumericProbe");h.host.DefineClass("NumericCtor");h.host.DefineClass("NumericPayload");auto receiver=h.host.NewInstance("NumericProbe"),owner=h.find("NumericProbe"),ref=h.host.NewString(u"numeric ref");
 uint32_t expected0=0,expected1=0,out_bits=0;int32_t expected_i=INT32_MIN,out_i=INT32_MIN;const uint64_t wide=0xfedcba9876543210ULL;bool pair=false,throw_java=false;unsigned callbacks=0,retirements=0;std::vector<addr_t> temporaries;
 auto arguments=[&](addr_t r,const bunker::jni::Host::MethodArguments &args){++callbacks;check(h.call(232,r)==1,"numeric callback owns borrowed receiver local");if(pair)check(args[0]==expected0&&args[1]==wide&&args[2]==expected1,"independent FP/GP cursors preserve F/J/F exact bits");else{check(args[0]!=ref&&h.call(24,args[0],ref)&&h.call(232,args[0])==1,"mixed reference argument is a fresh borrowed local");check(args[1]==expected0&&static_cast<int32_t>(args[2])==expected_i,"mixed F/I slots retain exact binary32 and signed int values");}
   auto temporary=h.host.NewString(u"numeric temporary");temporaries.push_back(h.call(226,temporary));check(!h.call(19,8),"numeric callback may leave nested user frame");auto payload=std::make_shared<NumericPayload>();payload->retired=[&]{++retirements;auto local=h.host.NewString(u"retirement local");h.host.DeleteLocalReference(local);};h.host.NewHostInstance("NumericPayload",std::move(payload));if(throw_java)h.host.ThrowException("java/lang/IllegalStateException",u"numeric callback failure");};
 for(bool stat:{false,true})for(bool p:{false,true}){auto name=std::string(stat?"static_":"")+(p?"pair":"mixed");auto sig=p?"(FJF)":"(Ljava/lang/Object;FI)";
   auto integer=[&,p](addr_t r,const bunker::jni::Host::MethodArguments &a){check(pair==p,"selected exact numeric shape");arguments(r,a);return out_i;};auto floating=[&,p](addr_t r,const bunker::jni::Host::MethodArguments &a){check(pair==p,"selected exact float shape");arguments(r,a);return out_bits;};
   if(stat){h.host.DefineStaticIntMethod("NumericProbe",name+"I",std::string(sig)+"I",integer);h.host.DefineStaticFloatBitsMethod("NumericProbe",name+"F",std::string(sig)+"F",floating);}else{h.host.DefineIntMethod("NumericProbe",name+"I",std::string(sig)+"I",integer);h.host.DefineFloatBitsMethod("NumericProbe",name+"F",std::string(sig)+"F",floating);}
 }
 auto method=[&](const std::string &name,const std::string &sig,bool stat=false){auto id=h.call(stat?113:33,owner,reinterpret_cast<addr_t>(name.c_str()),reinterpret_cast<addr_t>(sig.c_str()));check(id&&!h.host.PendingException().size(),"exact typed numeric method resolves");return id;};
 auto invoke=[&](addr_t object,addr_t id,int mode,uint32_t f0,uint32_t f1=0){struct {uint64_t before=0x1122334455667788ULL,guard=0,after=0x8877665544332211ULL;} data;
   auto result=pair?run("numeric_pair",{h.host.EnvAddress(),object,id,uint64_t(f0)|(uint64_t(f1)<<32),wide,static_cast<addr_t>(mode),reinterpret_cast<addr_t>(&data.guard)}):run("numeric_mixed",{h.host.EnvAddress(),object,id,ref,uint64_t(f0)|(uint64_t(static_cast<uint32_t>(expected_i))<<32),static_cast<addr_t>(mode),reinterpret_cast<addr_t>(&data.guard)});
   check(data.before==0x1122334455667788ULL&&data.after==0x8877665544332211ULL&&data.guard==0x123456789abcdef0ULL,"jvalue padding/arguments and external output canaries survive direct/V/A/stackV");return result;};
 auto clean=[&]{for(auto weak:temporaries){check(h.call(24,weak,0),"numeric callback temporary dies after owned frame/reentrant retirement");h.call(227,weak);}temporaries.clear();check(h.call(232,ref)==1,"numeric callback never consumes caller ref");};
 std::vector<bunker::jni::MethodDeclaration> abstract_methods{{"dispatchI","(FJF)I"},{"dispatchF","(FJF)F"},{"dispatchO","(Ljava/lang/Object;FI)Ljava/lang/Object;"}};
 h.host.DefineClass("NumericBase",abstract_methods);h.host.DefineInterface("NumericInterface",abstract_methods);h.host.DefineClass("NumericDerived",{},"NumericBase",false,{"NumericInterface"});auto derived=h.host.NewInstance("NumericDerived");
 h.host.DefineIntMethod("NumericDerived","dispatchI","(FJF)I",[&](addr_t r,const bunker::jni::Host::MethodArguments &a){arguments(r,a);return out_i;});
 h.host.DefineFloatBitsMethod("NumericDerived","dispatchF","(FJF)F",[&](addr_t r,const bunker::jni::Host::MethodArguments &a){arguments(r,a);return out_bits;});
 h.host.DefineObjectMethod("NumericDerived","dispatchO","(Ljava/lang/Object;FI)Ljava/lang/Object;",[&](addr_t r,const bunker::jni::Host::MethodArguments &a){arguments(r,a);return a[0];});
 for(const char *declaring:{"NumericBase","NumericInterface"}){
   auto ii=h.method(declaring,"dispatchI","(FJF)I"),fi=h.method(declaring,"dispatchF","(FJF)F"),oi=h.method(declaring,"dispatchO","(Ljava/lang/Object;FI)Ljava/lang/Object;");check(ii&&fi&&oi&&h.host.PendingException().empty(),"plain base/interface declaration IDs resolve before actual override selection");
   for(int form=0;form<6;++form){const auto &row=kNumericExpected[15];expected0=expected1=form==2?row.raw:row.promoted;out_i=INT32_MIN;out_bits=row.raw;pair=true;
     check(invoke(derived,ii,form,row.raw,row.raw)==static_cast<uint32_t>(out_i),"Base/interface ID selects real I override before F/J/F decoding");clean();check(invoke(derived,fi,form+32,row.raw,row.raw)==out_bits,"Base/interface ID selects real F override before F/J/F decoding");clean();pair=false;
     auto value=invoke(derived,oi,form+64,row.raw);check(value&&h.call(24,value,ref)&&h.call(232,value)==1,"Base/interface object-F call decodes actual implementation and promotes identity");h.host.DeleteLocalReference(value);clean();
   }
 }
 for(bool stat:{false,true})for(pair=false;;pair=true){auto name=std::string(stat?"static_":"")+(pair?"pair":"mixed");auto sig=pair?"(FJF)":"(Ljava/lang/Object;FI)";auto ii=method(name+"I",std::string(sig)+"I",stat),fi=method(name+"F",std::string(sig)+"F",stat);
   for(const auto &row:kNumericExpected)for(int form=0;form<6;++form){expected0=form==2?row.raw:row.promoted;expected1=expected0;out_bits=row.raw;out_i=(form&1)?INT32_MAX:INT32_MIN;
     auto base=form+(stat?16:0);check(invoke(stat?owner:receiver,ii,base,row.raw,row.raw)==static_cast<uint32_t>(out_i)&&h.host.PendingException().empty(),"actual JNI int family returns signed extrema through all argument forms");clean();check(invoke(stat?owner:receiver,fi,base+32,row.raw,row.raw)==out_bits&&h.host.PendingException().empty(),"float result copies exact raw S0 bits including NaN/sign/subnormal");clean();}
   throw_java=true;expected0=kNumericExpected[6].promoted;expected1=expected0;check(!invoke(stat?owner:receiver,ii,(stat?16:0)+1,kNumericExpected[6].raw,kNumericExpected[6].raw)&&h.host.PendingException().find("numeric callback failure")!=std::string::npos,"numeric Java exception survives cleanup instead of becoming valid zero");h.host.ClearException();throw_java=false;clean();if(pair)break;
 }
 pair=false;expected0=kNumericExpected[6].promoted;h.host.DefineObjectMethod("NumericProbe","editor","(Ljava/lang/Object;FI)Ljava/lang/Object;",[&](addr_t r,const bunker::jni::Host::MethodArguments&a){arguments(r,a);return a[0];});auto editor=method("editor","(Ljava/lang/Object;FI)Ljava/lang/Object;");
 for(int form=0;form<6;++form){expected0=form==2?kNumericExpected[6].raw:kNumericExpected[6].promoted;auto value=invoke(receiver,editor,form+64,kNumericExpected[6].raw);check(value&&value!=ref&&h.call(24,value,ref)&&h.call(232,value)==1,"object result with F arguments retains exact guarded owned-frame promotion");h.host.DeleteLocalReference(value);clean();}
 h.host.DefineConstructor("NumericCtor","(Ljava/lang/Object;FI)V",[&](const bunker::jni::Host::MethodArguments&a){check(a[1]==expected0&&static_cast<int32_t>(a[2])==expected_i,"constructor F argument uses same numeric decoding");return h.host.NewInstance("NumericCtor");});auto ctor_owner=h.find("NumericCtor"),ctor=h.method("NumericCtor","<init>","(Ljava/lang/Object;FI)V");for(int form=0;form<6;++form){auto value=invoke(ctor_owner,ctor,form+96,kNumericExpected[6].raw);check(value&&h.call(232,value)==1,"F constructor still requires real exact-owner result");h.host.DeleteLocalReference(value);}
 h.host.DefineIntMethod("NumericProbe","zeroI","()I",[&](addr_t,const bunker::jni::Host::MethodArguments&){return out_i;});h.host.DefineFloatBitsMethod("NumericProbe","zeroF","()F",[&](addr_t,const bunker::jni::Host::MethodArguments&){return out_bits;});
 for(int form=0;form<3;++form)for(auto i:{0,-1,INT32_MIN,INT32_MAX}){out_i=i;uint64_t guard=0;check(run("numeric_zero",{h.host.EnvAddress(),receiver,method("zeroI","()I"),static_cast<addr_t>(form),reinterpret_cast<addr_t>(&guard)})==static_cast<uint32_t>(i)&&guard==0x123456789abcdef0ULL,"Integer.intValue-shaped zero-argument direct/V/A signed result");}
 for(int form=0;form<3;++form)for(const auto &row:kNumericExpected){out_bits=row.raw;uint64_t guard=0;check(run("numeric_zero",{h.host.EnvAddress(),receiver,method("zeroF","()F"),static_cast<addr_t>(form+32),reinterpret_cast<addr_t>(&guard)})==row.raw&&guard==0x123456789abcdef0ULL,"Float.floatValue-shaped zero-argument S0 payload");}
 auto error=[&]{check(h.host.PendingException().find("IllegalArgumentException")!=std::string::npos,"invalid numeric shape raises real JNI argument error");h.host.ClearException();};
 for(auto slot:{49,50,51,55,56,57}){State s{};s.gpr.x0.qword=h.host.EnvAddress();s.gpr.x1.qword=receiver;s.gpr.x2.qword=method(slot<55?"zeroF":"zeroI",slot<55?"()F":"()I");h.host.InvokeEnv(slot,s);error();}
 for(auto signature:{"(D)I","([F)I","(IIII)I","()J","()D","()Ljava/lang/Object;"}){bool rejected=false;try{h.host.DefineIntMethod("NumericProbe","bad",signature,[](addr_t,const bunker::jni::Host::MethodArguments&){return 0;});}catch(const std::invalid_argument&){rejected=true;}check(rejected,"numeric declarations reject D/primitive arrays/argument widening/wrong result");}
 const auto mixed=method("mixedI","(Ljava/lang/Object;FI)I");auto bad_v=[&](VaList list){State s{};s.gpr.x0.qword=h.host.EnvAddress();s.gpr.x1.qword=receiver;s.gpr.x2.qword=mixed;s.gpr.x3.qword=reinterpret_cast<addr_t>(&list);h.host.InvokeEnv(50,s);error();};
 alignas(16)std::array<uint64_t,32> bank{};bank[0]=ref;bank[2]=static_cast<uint32_t>(expected_i);auto base=reinterpret_cast<addr_t>(bank.data());
 bad_v({base,base,base,-65,-128});bad_v({base,base+8,base+8,-8,-16});bad_v({base,0,base,-8,-16});bad_v({UINT64_MAX-7,base,base,0,0});
 h.host.DefineIntMethod("NumericProbe","onlyI","(I)I",[](addr_t,const bunker::jni::Host::MethodArguments &a){return static_cast<int32_t>(a[0]);});
 h.host.DefineFloatBitsMethod("NumericProbe","onlyF","(F)F",[](addr_t,const bunker::jni::Host::MethodArguments &a){return static_cast<uint32_t>(a[0]);});
 auto direct_v=[&](addr_t id,VaList list,bool fp){State s{};s.gpr.x0.qword=h.host.EnvAddress();s.gpr.x1.qword=receiver;s.gpr.x2.qword=id;s.gpr.x3.qword=reinterpret_cast<addr_t>(&list);h.host.InvokeEnv(fp?56:50,s);uint32_t bits=0;if(fp)std::memcpy(&bits,&s.simd.v[0],4);else bits=s.gpr.x0.dword;return bits;};
 bank[0]=static_cast<uint32_t>(INT32_MIN);check(direct_v(method("onlyI","(I)I"),{base,base+8,1,-8,INT32_MIN},false)==static_cast<uint32_t>(INT32_MIN)&&h.host.PendingException().empty(),"unused VR metadata is never validated or dereferenced");
 double one=1.0;std::memcpy(bank.data(),&one,8);check(direct_v(method("onlyF","(F)F"),{base,1,base+16,INT32_MIN,-16},true)==0x3f800000&&h.host.PendingException().empty(),"unused GR metadata is never validated or dereferenced");
 for(bool fp:{false,true})for(bool stat:{false,true}){State s{};s.gpr.x0.qword=h.host.EnvAddress();s.gpr.x1.qword=stat?receiver:owner;s.gpr.x2.qword=method(fp?"zeroF":"zeroI",fp?"()F":"()I");h.host.InvokeEnv(fp?(stat?135:55):(stat?129:49),s);error();}
 {State s{};s.gpr.x0.qword=h.host.EnvAddress();s.gpr.x1.qword=receiver;s.gpr.x2.qword=mixed;s.gpr.x3.qword=UINT64_MAX-15;h.host.InvokeEnv(51,s);error();}
 for(bool fp:{false,true}){bool rejected=false;try{if(fp)h.host.DefineFloatBitsMethod("NumericProbe","badFloat","()I",[](addr_t,const bunker::jni::Host::MethodArguments&){return uint32_t(0);});else h.host.DefineIntMethod("NumericProbe","zeroI","()I",[](addr_t,const bunker::jni::Host::MethodArguments&){return 0;});}catch(const std::invalid_argument&){rejected=true;}check(rejected,"exact float result and existing method duplicate guards remain enforced");}
 check(va_calls&&float_returns&&int_returns&&retirements==callbacks&&h.host.PendingException().empty(),"numeric frame/retirement/ABI monitoring completed without hidden exception");
 std::printf("JNI numeric: %u checks; actual NDK instance/static I/F direct,V,A,GP/VR/both-stackV; Base/interface overrides, ARM64 promotion reference, raw NaN/zero/subnormal bits, owned frames and cursor negatives\n",checks);
}catch(const std::exception &e){std::fprintf(stderr,"JNI numeric test: %s\n",e.what());return 1;}}
