#include "jni_host.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <functional>
#include <iterator>
#include <stdexcept>
#include <thread>
#include <utility>
namespace {
std::atomic<unsigned>checks{0},calls{0};
void Check(bool value,const char*why){++checks;if(!value)throw std::runtime_error(why);}
struct Fixture{
 elf_image image{};recomp::Runtime runtime;bunker::jni::Host host{[](addr_t){return false;}};
 Fixture(){static_assert(sizeof(State)==1200&&alignof(State)==16);Check(!elf_load(BYTE_ARRAY_IMAGE,0x76000000,nullptr,&image),"actualNDKbytearrayfixturemapping");host.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));}
 addr_t Run(const char*name,std::initializer_list<addr_t>args){alignas(16)std::array<unsigned char,65536>stack{};State s{};Reg GPR::*reg[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5};size_t i=0;for(auto v:args)(s.gpr.*reg[i++]).qword=v;
  s.gpr.x19.qword=0xf123456789abcdefULL;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;std::array<unsigned char,16>upper;upper.fill(0xd3);std::memcpy(&s.simd.v[31],upper.data(),16);reinterpret_cast<unsigned char*>(&s)[1199]=0x6d;
  auto target=reinterpret_cast<addr_t>(elf_symbol(&image,name));Check(target!=0,"actualNDKexportexists");auto*token=reinterpret_cast<Memory*>(0xfedcba9876543210ULL);Check(runtime.Run(s,target,token)==token,"full64opaqueMemorytoken");++calls;
  Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size())&&s.gpr.x19.qword==0xf123456789abcdefULL,"originalcallerPCSPcalleeSaved64");Check(!std::memcmp(&s.simd.v[31],upper.data(),16)&&reinterpret_cast<unsigned char*>(&s)[1199]==0x6d,"State1200SIMD128andhighcellpreserved");return s.gpr.x0.qword;
 }
 addr_t Call(unsigned op,addr_t a=0,addr_t b=0,addr_t c=0,addr_t d=0){return Run("byte_dispatch",{host.EnvAddress(),op,a,b,c,d});}
 addr_t Find(const char*s){return Call(6,reinterpret_cast<addr_t>(s));}
 addr_t New(int32_t n){return Call(0,uint32_t(n));}
 addr_t Elements(addr_t a,uint8_t*copy=nullptr){return Call(2,a,reinterpret_cast<addr_t>(copy));}
 void Release(addr_t a,addr_t p,int mode){Call(3,a,p,uint32_t(mode));}
 void Get(addr_t a,int32_t start,int32_t n,void*p){Call(4,a,uint32_t(start),uint32_t(n),reinterpret_cast<addr_t>(p));}
 void Set(addr_t a,int32_t start,int32_t n,const void*p){Call(5,a,uint32_t(start),uint32_t(n),reinterpret_cast<addr_t>(p));}
 bool Same(addr_t a,addr_t b){return Call(13,a,b)!=0;}
 void Error(const char*category){Check(host.PendingException().find(category)!=std::string::npos,"exacthostexceptioncategory");host.ClearException();}
 addr_t Exception(){State s{};s.gpr.x0.qword=host.EnvAddress();host.InvokeEnv(15,s);return s.gpr.x0.qword;}
};
}
int main(){try{
 Fixture f;auto object=f.Find("java/lang/Object"),byteclass=f.Find("[B"),objects=f.Find("[Ljava/lang/Object;");Check(byteclass&&f.host.PendingException().empty(),"byteclassmetadata");
 auto a=f.New(256),empty=f.New(0);Check(a&&empty&&f.Call(1,a)==256&&f.Call(1,empty)==0,"newzeroand256length");Check(f.Run("byte_shape",{f.host.EnvAddress(),a})==31,"primitivebyteclassObjectCloneableSerializablebutnotObjectArray");
 std::array<unsigned char,256>pattern;for(unsigned i=0;i<256;++i)pattern[i]=static_cast<unsigned char>(i);std::array<unsigned char,272>out;out.fill(0x9b);f.Get(a,0,256,out.data()+8);Check(std::all_of(out.begin()+8,out.begin()+264,[](auto x){return x==0;}),"newarrayzeroed");
 f.Set(a,0,256,pattern.data());f.Get(a,0,256,out.data()+8);Check(!std::memcmp(out.data()+8,pattern.data(),256)&&std::all_of(out.begin(),out.begin()+8,[](auto x){return x==0x9b;})&&std::all_of(out.end()-8,out.end(),[](auto x){return x==0x9b;}),"all256signedbytebitpatterns/exactregioncanaries");
 unsigned char one=0x71;f.Get(empty,0,0,&one);f.Set(empty,0,0,&one);Check(one==0x71&&f.host.PendingException().empty(),"nonNULLzero-regionnoaccess");uint8_t zero_copy=0;auto zero=f.Elements(empty,&zero_copy);Check(zero&&zero_copy==1,"zerolenownedcopy");f.Release(empty,zero,2);
 Check(!f.New(-1),"negativearrayhostpolicy");f.Error("NegativeArraySizeException");
 for(auto bounds:std::array<std::pair<int32_t,int32_t>,5>{{{-1,1},{0,-1},{255,2},{INT32_MAX,1},{1,INT32_MAX}}}){out.fill(0x9b);const auto old=out;f.Get(a,bounds.first,bounds.second,out.data()+8);f.Error("ArrayIndexOutOfBoundsException");Check(out==old,"badgetregionstagednooutput");f.Set(a,bounds.first,bounds.second,pattern.data());f.Error("ArrayIndexOutOfBoundsException");}
 f.Get(a,0,256,out.data()+8);Check(!std::memcmp(out.data()+8,pattern.data(),256),"failedsetregionpreservesarray");
 for(int mode:{0,1,2}){struct{uint8_t before,copy,after;}flag{0x71,0,0x72};auto p=f.Elements(a,&flag.copy);Check(p&&flag.copy==1&&flag.before==0x71&&flag.after==0x72,"GetByteArrayElementsexactonebytecopyflag");auto before=pattern;std::memcpy(reinterpret_cast<void*>(p),pattern.data(),256);reinterpret_cast<unsigned char*>(p)[7]=unsigned(100+mode);f.Release(a,p,mode);f.Get(a,0,256,out.data()+8);if(mode==2)Check(!std::memcmp(out.data()+8,before.data(),256),"ABORTdiscards");else{pattern[7]=unsigned(100+mode);Check(!std::memcmp(out.data()+8,pattern.data(),256),"mode0orCOMMITpublishes");}if(mode==1){reinterpret_cast<unsigned char*>(p)[8]=0x55;f.Release(a,p,2);f.Get(a,0,256,out.data()+8);Check(!std::memcmp(out.data()+8,pattern.data(),256),"COMMITretainscopythenABORTdoesnotrepublish");}f.Release(a,p,2);f.Error("IllegalArgumentException");}
 uint8_t c1=0,c2=0;auto p1=f.Elements(a,&c1),p2=f.Elements(a,&c2);Check(p1&&p2&&p1!=p2&&c1==1&&c2==1,"independentconcurrentcopyleases");f.Get(a,0,32,reinterpret_cast<void*>(p1+16));Check(!std::memcmp(reinterpret_cast<void*>(p1+16),pattern.data(),32),"regiongetaliasintoindependentlease");f.Set(a,32,32,reinterpret_cast<void*>(p1+16));std::memcpy(pattern.data()+32,pattern.data(),32);f.Release(a,p1,2);f.Release(a,p2,2);f.Get(a,0,256,out.data()+8);Check(!std::memcmp(out.data()+8,pattern.data(),256),"setregionstagesleaseinput");
 auto b=f.New(256),p=f.Elements(a);f.Release(b,p,2);f.Error("IllegalArgumentException");f.Release(a,p,3);f.Error("IllegalArgumentException");f.Release(a,p,2);
 auto string=f.host.NewString(u"not bytes");Check(!f.Elements(string),"wrongtypeelements");f.Error("IllegalArgumentException");f.Release(a,reinterpret_cast<addr_t>(pattern.data()),0);f.Error("IllegalArgumentException");
 // Release cleanup is legal while an exception is pending; do not treat
 // invalid New/Get/region calls while pending as an ART runtime oracle.
 for(int mode:{0,1,2}){auto lease=f.Elements(a);f.host.ThrowException("java/lang/IllegalStateException",u"pending cleanup");const auto pending=f.host.PendingException();auto exception=f.Exception();f.Release(a,lease,mode);auto after=f.Exception();Check(f.host.PendingException()==pending,"releasepreservespendingexception");f.host.ClearException();Check(exception&&after&&f.Same(exception,after),"releasepreservesexistingThrowableidentity");if(mode==1)f.Release(a,lease,2);f.Call(10,exception);f.Call(10,after);}
 auto global=f.Call(7,a),weak=f.Call(11,a);Check(global&&weak&&f.Call(14,global)==2&&f.Call(14,weak)==3,"actualglobalweakreferencekinds");std::exception_ptr worker_error;
 const auto main_env=f.host.EnvAddress();auto owner_lease=f.Elements(global);std::thread worker([&]{try{addr_t e=0;State vm{};vm.gpr.x0.qword=f.host.VmAddress();vm.gpr.x1.qword=reinterpret_cast<addr_t>(&e);f.host.InvokeVm(4,vm);Check(e!=0,"actualJNIworkerattach");State wrong{};wrong.gpr.x0.qword=main_env;wrong.gpr.x1.qword=global;bool rejected=false;try{f.host.InvokeEnv(184,wrong);}catch(const std::exception&){rejected=true;}Check(rejected,"foreignJNIEnvdefensivehostboundaryguard");Check(!f.Elements(a),"foreignthreadlocalreferenceguard");f.Error("IllegalArgumentException");f.Release(global,owner_lease,2);Check(f.host.PendingException().empty(),"ordinaryelementscopycanbereleasedwithglobalrefandotherattachedEnv");auto worker_lease=f.Elements(global);Check(worker_lease!=0,"attachedworkergetsitscopy");f.Release(global,worker_lease,2);vm={};vm.gpr.x0.qword=f.host.VmAddress();f.host.InvokeVm(5,vm);Check(vm.gpr.x0.dword==0,"actualJNIworkerdetach");}catch(...){worker_error=std::current_exception();}});worker.join();if(worker_error)std::rethrow_exception(worker_error);f.Release(global,owner_lease,2);f.Error("IllegalArgumentException");
 f.Call(23,8);auto framed=f.New(4),frameweak=f.Call(11,framed),framelease=f.Elements(framed);f.Call(24,0);Check(!f.Same(frameweak,0),"leasekeepsframearrayalive");auto promoted=f.Call(9,frameweak);f.Release(promoted,framelease,2);f.Call(10,promoted);Check(f.Same(frameweak,0),"leasefreeandlastlocalreleasesarray");f.Call(12,frameweak);
 f.host.DefineClass("ByteFixture");f.host.DefineObjectMethod("ByteFixture","echo","([B)[B",[](addr_t,const bunker::jni::Host::MethodArguments&args){return args[0];});f.host.DefineField("ByteFixture","bytes","[B");f.host.MarkClassInitialized("ByteFixture");auto clazz=f.Find("ByteFixture"),receiver=f.host.NewInstance("ByteFixture");const char method[]="echo",sig[]="([B)[B",field[]="bytes",type[]="[B";auto methodid=f.Call(18,clazz,reinterpret_cast<addr_t>(method),reinterpret_cast<addr_t>(sig));auto echoed=f.Call(19,receiver,methodid,a);Check(echoed&&f.Same(echoed,a),"typedbyteargumentandreturngenuineNDKAcall");f.Call(19,receiver,methodid,string);f.Error("IllegalArgumentException");auto fieldid=f.Call(20,clazz,reinterpret_cast<addr_t>(field),reinterpret_cast<addr_t>(type));f.Call(21,receiver,fieldid,a);auto value=f.Call(22,receiver,fieldid);Check(value&&f.Same(value,a),"typedbytefieldactualNDKreadwrite");f.Call(21,receiver,fieldid,string);f.Error("IllegalArgumentException");
 auto nested=f.Call(15,1,byteclass,a),nestedclass=f.Find("[[B"),object_nested=f.Find("[[Ljava/lang/Object;");Check(nested&&nestedclass&&f.Call(25,nested,nestedclass)&&f.Call(25,nested,objects)&&!f.Call(25,nested,object_nested),"nestedbytearraysareObjectarraybutnotObjectarrayarray");auto element=f.Call(16,nested,0);Check(element&&f.Same(element,a),"nestedbytearrayidentity");f.Call(17,nested,0,string);f.Error("ArrayStoreException");auto old=f.Call(15,1,object,string);Check(old&&f.Same(f.Call(16,old,0),string),"existingreferencearraybehaviorpreserved");
 f.host.DefineClass("B");f.host.MarkClassInitialized("B");auto ordinary_class=f.Find("B"),ordinary=f.host.NewInstance("B"),ordinary_array=f.Call(15,1,ordinary_class,ordinary),ordinary_array_class=f.Find("[LB;");Check(ordinary_array&&ordinary_array_class&&!f.Call(25,a,ordinary_array_class)&&!f.Call(25,ordinary_array,byteclass),"primitiveBdescriptorcannotaliasordinaryclassnameBarray");Check(!f.Find("[L[B;"),"malformedLcomponentrejected");f.Error("NoClassDefFoundError");
 const char loader_name[]="getClassLoader",loader_sig[]="()Ljava/lang/ClassLoader;";auto class_type=f.Find("java/lang/Class"),loader_method=f.Call(18,class_type,reinterpret_cast<addr_t>(loader_name),reinterpret_cast<addr_t>(loader_sig));auto ordinary_loader=f.Call(19,ordinary_class,loader_method),array_loader=f.Call(19,ordinary_array_class,loader_method),byte_loader=f.Call(19,byteclass,loader_method);Check(f.Same(ordinary_loader,array_loader)&&!f.Same(ordinary_loader,byte_loader),"ordinaryBarraycomponentloaderdiffersfrombootstrapbytearrayloader");
 auto stale=f.New(1);f.Call(10,stale);Check(!f.Elements(stale),"retiredarrayreferenceguard");f.Error("IllegalArgumentException");f.Call(8,global);f.Call(12,weak);Check(f.host.PendingException().empty(),"nohiddenexceptions");
 std::printf("JNI-BYTE-ARRAY-PASS checks=%u NDK_calls=%u slots=6 State=1200 align=16 Memory64=1\n",checks.load(),calls.load());return 0;
}catch(const std::exception&e){std::fprintf(stderr,"JNI byte arrays: %s\n",e.what());return 1;}}
