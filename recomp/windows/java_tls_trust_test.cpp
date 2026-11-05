#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include "java_tls_trust.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <algorithm>
#include <array>
#include <atomic>
#include <cerrno>
#include <cfenv>
#include <cstdio>
#include <fstream>
#include <map>
#include <set>
#include <stdexcept>
#include <thread>
namespace {
using bunker::windows::JavaTlsTrust;
using Der=JavaTlsTrust::Der;
static_assert(sizeof(State)==1200&&alignof(State)==16);
unsigned checks=0,entries=0,forms[3]={};
std::map<std::string,unsigned> calls;
void Check(bool value,const char*message){++checks;if(!value)throw std::runtime_error(message);}
constexpr const char* factory_name="javax/net/ssl/TrustManagerFactory";
constexpr const char* trust_name="javax/net/ssl/TrustManager";
constexpr const char* xtrust_name="javax/net/ssl/X509TrustManager";
constexpr const char* cert_name="java/security/cert/Certificate";
void Dirty(){errno=ERANGE;SetLastError(0x99112233);std::fesetround(FE_UPWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_OVERFLOW);}
struct Session {
 recomp::Runtime runtime;
 bunker::jni::Host host{[](addr_t pc){return std::any_of(std::begin(kTraces),std::end(kTraces),[pc](auto&trace){return trace.address==pc;});}};
 elf_image&image;
 explicit Session(elf_image&i):image(i){host.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));}
 addr_t Run(const char*symbol,std::initializer_list<addr_t>args){
  ++entries;++calls[symbol];State s{};alignas(16)std::array<unsigned char,65536>stack{};
  Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6};size_t n=0;
  s.gpr.x0.qword=host.EnvAddress();n=1;for(auto a:args)(s.gpr.*r[n++]).qword=a;
  auto top=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.sp.qword=top;s.gpr.x30.qword=0xfeedffff;
  s.gpr.x19.qword=0xf123456789abcdefULL;s.gpr.x29.qword=0xe123456789abcdefULL;
  std::array<unsigned char,16>v;v.fill(0xd7);memcpy(&s.simd.v[31],v.data(),16);reinterpret_cast<unsigned char*>(&s)[1199]=0x79;
  auto*memory=reinterpret_cast<Memory*>(0xfedcba9876543210ULL);auto pc=reinterpret_cast<addr_t>(elf_symbol(&image,symbol));Check(pc!=0,"NDK caller export exists");
  Check(runtime.Run(s,pc,memory)==memory,"NDK opaque Memory64 identity");
  Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==top&&s.gpr.x19.qword==0xf123456789abcdefULL&&s.gpr.x29.qword==0xe123456789abcdefULL,"NDK PC/SP and high64 saved GPRs");
  Check(!memcmp(&s.simd.v[31],v.data(),16)&&reinterpret_cast<unsigned char*>(&s)[1199]==0x79,"NDK State1200 SIMD128 highcell");return s.gpr.x0.qword;
 }
 addr_t Find(const char*name){return Run("tls_find",{reinterpret_cast<addr_t>(name)});}
 addr_t Method(addr_t clazz,const char*name,const char*sig,bool stat=false){return Run("tls_method",{clazz,reinterpret_cast<addr_t>(name),reinterpret_cast<addr_t>(sig),stat});}
 addr_t Object(addr_t receiver,addr_t method,int form,addr_t argument=0,bool has=false,bool stat=false){++forms[form];return Run("tls_object",{receiver,method,argument,has,stat,static_cast<addr_t>(form)});}
 void Init(addr_t receiver,addr_t method,int form,addr_t key=0){++forms[form];Run("tls_void",{receiver,method,key,static_cast<addr_t>(form)});}
 addr_t Element(addr_t array,int index){return Run("tls_element",{array,static_cast<addr_t>(index)});}
 size_t Length(addr_t array){return Run("tls_length",{array});}
 bool Same(addr_t first,addr_t second){return Run("tls_same",{first,second});}
 void Delete(addr_t object){Run("tls_reference",{object,4});}
 void NoException(){Check(host.PendingException().empty(),"no unexpected Java exception");}
 void Exception(const char*type){
  Check(host.PendingException().find(type)!=std::string::npos,"expected Java exception type");auto first=Run("tls_exception",{}),second=Run("tls_exception",{});
  Check(first&&Same(first,second),"pending throwable retains actual object identity");Run("tls_clear",{});
  Check(Run("tls_shape",{first,Find(type)})&1,"actual throwable is instance of expected Java class");Delete(first);Delete(second);NoException();
 }
 Der Bytes(addr_t bytes){
  size_t size=Length(bytes);std::vector<uint8_t>buffer(size+16,0xa9);Run("tls_byte_region",{bytes,0,size,reinterpret_cast<addr_t>(buffer.data()+8)});
  Check(std::all_of(buffer.begin(),buffer.begin()+8,[](uint8_t b){return b==0xa9;})&&std::all_of(buffer.end()-8,buffer.end(),[](uint8_t b){return b==0xa9;}),"JNI byte region guards");
  unsigned char copy=0x7d;auto pointer=Run("tls_byte_elements",{bytes,reinterpret_cast<addr_t>(&copy)});
  Check(pointer&&copy<=1&&!memcmp(reinterpret_cast<void*>(pointer),buffer.data()+8,size),"original-style GetByteArrayElements returns entire real DER");Run("tls_release_bytes",{bytes,pointer,2});
  NoException();return {buffer.begin()+8,buffer.end()-8};
 }
};
struct Methods {
 addr_t factory,trust,xtrust,certificate,xcertificate,def,instance,init,managers,issuers,encoded;
 explicit Methods(Session&s){factory=s.Find(factory_name);trust=s.Find(trust_name);xtrust=s.Find(xtrust_name);certificate=s.Find(cert_name);xcertificate=s.Find("java/security/cert/X509Certificate");def=s.Method(factory,"getDefaultAlgorithm","()Ljava/lang/String;",true);instance=s.Method(factory,"getInstance","(Ljava/lang/String;)Ljavax/net/ssl/TrustManagerFactory;",true);init=s.Method(factory,"init","(Ljava/security/KeyStore;)V");managers=s.Method(factory,"getTrustManagers","()[Ljavax/net/ssl/TrustManager;");issuers=s.Method(xtrust,"getAcceptedIssuers","()[Ljava/security/cert/X509Certificate;");encoded=s.Method(certificate,"getEncoded","()[B");s.NoException();}
};
std::vector<Der> ReadBundle(){std::ifstream stream(ROOT_BUNDLE,std::ios::binary);Check(bool(stream),"independent oracle DER bundle opens");auto u32=[&]{uint32_t value=0;stream.read(reinterpret_cast<char*>(&value),4);Check(bool(stream),"complete independent oracle bundle");return value;};Check(u32()==0x31525354,"public DER oracle bundle schema");auto count=u32();Check(count>2&&count<10000,"real public root count bounded");std::vector<Der>roots;for(uint32_t i=0;i<count;++i){auto size=u32();Check(size>32&&size<1000000,"actual public DER size");Der der(size);stream.read(reinterpret_cast<char*>(der.data()),size);Check(bool(stream)&&der[0]==0x30,"public DER certificate sequence");roots.push_back(std::move(der));}Check(stream.peek()==EOF,"oracle has no trailing bytes");return roots;}
std::vector<Der> Export(Session&s,Methods&m,addr_t manager,int form){
 auto array=s.Object(manager,m.issuers,form);Check(array!=0,"accepted issuers returns nonnull array");Check(s.Run("tls_shape",{array,s.Find("[Ljava/security/cert/X509Certificate;")})==3,"accepted issuers has exact typed X509Certificate array");
 std::vector<Der>result;for(size_t i=0;i<s.Length(array);++i){Check(!s.Run("tls_push",{16}),"NDK local frame push");auto cert=s.Element(array,i);Check(s.Run("tls_shape",{cert,m.certificate})&1,"certificate inherits actual base Certificate");Check(s.Run("tls_shape",{cert,m.xcertificate})&1,"certificate is X509Certificate");auto bytes=s.Object(cert,m.encoded,form);Check(s.Run("tls_shape",{bytes,s.Find("[B")})==3,"base-owner getEncoded dispatches to concrete byte array");result.push_back(s.Bytes(bytes));s.Run("tls_pop",{0});}s.Delete(array);s.NoException();return result;
}
void Functional(elf_image&image,const std::vector<Der>&roots){
 Session s(image);unsigned read_count=0,read_mode=0,observer_count=0;std::vector<Der>current{roots[0],roots[1]};
 JavaTlsTrust service(s.host,{[&]{++read_count;Dirty();if(read_mode==1)throw std::runtime_error("TEST public-root reader failure");if(read_mode==2)throw std::bad_alloc();JavaTlsTrust::RootSnapshot result;result.certificates=current;return result;},[&](const auto&){++observer_count;Dirty();}});Methods m(s);
 Check(service.Active(),"service initially active");Check(s.Run("tls_assignable",{m.xtrust,m.trust})==1&&!s.Run("tls_assignable",{m.trust,m.xtrust}),"actual NDK transitive interface assignability direction");
 for(int form=0;form<3;++form){
  auto environment=[&](auto body){std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_INVALID|FE_DIVBYZERO);int flags=std::fetestexcept(FE_ALL_EXCEPT);errno=EDOM;SetLastError(0x12347890);auto value=body();Check(errno==EDOM&&GetLastError()==0x12347890&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==flags,"service restores native errno/LastError/nondefault FENV across dirty reader/observer");return value;};
  auto algorithm=environment([&]{return s.Object(m.factory,m.def,form,0,false,true);});Check(s.host.StringValue(algorithm)==std::optional<std::u16string>(u"PKIX"),"actual static default algorithm PKIX");
  auto factory=environment([&]{return s.Object(m.factory,m.instance,form,s.host.NewString(u"pKiX"),true,true);});Check(factory!=0,"case-insensitive supported algorithm factory");Check(!s.Object(factory,m.managers,form),"uninitialized factory returns no manager array");s.Exception("java/lang/IllegalStateException");
  auto before=read_count;environment([&]{s.Init(factory,m.init,form);return 0;});Check(read_count==before+1,"null-KeyStore init invokes one real configured reader");
  auto managers=s.Object(factory,m.managers,form);Check(s.Run("tls_shape",{managers,s.Find("[Ljavax/net/ssl/TrustManager;")})==3&&s.Length(managers)==1,"typed TrustManager array contains one actual manager");auto manager=s.Element(managers,0);
  Check((s.Run("tls_shape",{manager,m.xtrust})&1)&&(s.Run("tls_shape",{manager,m.trust})&1),"concrete manager implements X509TrustManager and inherited TrustManager");
  auto second=s.Object(factory,m.managers,form);Check(!s.Same(managers,second),"getTrustManagers returns fresh array");s.Run("tls_set_element",{managers,0,0});Check(s.Element(managers,0)==0&&s.Element(second,0)!=0,"manager arrays are independent");
  Check(Export(s,m,manager,form)==current,"original Java CA-export sequence preserves entire DER records");
  auto issuers=s.Object(manager,m.issuers,form),other=s.Object(manager,m.issuers,form);Check(!s.Same(issuers,other),"issuer arrays are fresh");auto cert=s.Element(issuers,0);s.Run("tls_set_element",{issuers,0,0});Check(s.Element(issuers,0)==0&&s.Element(other,0)!=0,"issuer array mutation does not change manager snapshot");
  auto a=s.Object(cert,m.encoded,form),b=s.Object(cert,m.encoded,form);Check(!s.Same(a,b)&&s.Bytes(a)==current[0]&&s.Bytes(b)==current[0],"getEncoded returns fresh full DER arrays");s.Run("tls_set_byte",{a,0,0});Check(s.Bytes(b)==current[0]&&s.Bytes(s.Object(cert,m.encoded,form))==current[0],"mutating byte[] leaves immutable certificate DER intact");
  auto global=s.Run("tls_reference",{cert,0}),weak=s.Run("tls_reference",{cert,2});s.Delete(cert);s.Delete(issuers);s.Delete(other);Check(s.Same(global,weak),"actual global reference retains backed certificate");
  auto old=current;current={roots[2]};s.Init(factory,m.init,form);auto newest=s.Element(s.Object(factory,m.managers,form),0);Check(Export(s,m,newest,form)==current&&Export(s,m,manager,form)==old&&s.Bytes(s.Object(global,m.encoded,form))==old[0],"reinit snapshots new roots while old manager/certificate remain immutable");
  current.clear();s.Init(factory,m.init,form);Check(Export(s,m,s.Element(s.Object(factory,m.managers,form),0),form).empty(),"empty valid root snapshot exports nonnull zero-length issuer array");
  current=old;read_mode=1;s.Init(factory,m.init,form);s.Exception("java/security/KeyStoreException");read_mode=2;s.Init(factory,m.init,form);s.Exception("java/lang/OutOfMemoryError");read_mode=0;
  Check(!s.Object(m.factory,m.instance,form,0,true,true),"null algorithm fails");s.Exception("java/lang/NullPointerException");Check(!s.Object(m.factory,m.instance,form,s.host.NewString(u"TEST-unsupported"),true,true),"unknown algorithm fails");s.Exception("java/security/NoSuchAlgorithmException");
  before=read_count;s.Init(factory,m.init,form,s.host.NewInstance("java/security/KeyStore"));s.Exception("java/security/KeyStoreException");Check(read_count==before,"unsupported explicit KeyStore never invokes root reader");
  s.Run("tls_reference",{global,1});Check(s.Same(weak,0),"weak certificate has no hidden service root after all strong references retire");s.Run("tls_reference",{weak,3});s.NoException();
 }
 Check(observer_count>30&&read_count==15,"real observer and reader counts reflect supported/error init paths");
 auto algorithm=s.Object(m.factory,m.def,0,0,false,true);Check(algorithm!=0,"service live before revocation");service.Revoke();Check(!service.Active(),"revoke changes service admission");
}
void PublicRoots(elf_image&image,const std::vector<Der>&oracle){
 std::fesetround(FE_TOWARDZERO);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_INVALID);errno=E2BIG;SetLastError(0x55773311);int flags=std::fetestexcept(FE_ALL_EXCEPT);
 auto roots=JavaTlsTrust::ReadWindowsRootCertificates();Check(errno==E2BIG&&GetLastError()==0x55773311&&std::fegetround()==FE_TOWARDZERO&&std::fetestexcept(FE_ALL_EXCEPT)==flags,"real native ROOT query restores environment");
 Check(std::set<Der>(roots.certificates.begin(),roots.certificates.end())==std::set<Der>(oracle.begin(),oracle.end())&&roots.certificates.size()==oracle.size(),"entire eligible public ROOT DER set equals independent read-only oracle");
 Session s(image);JavaTlsTrust service(s.host);Methods m(s);auto factory=s.Object(m.factory,m.instance,2,s.host.NewString(u"PKIX"),true,true);s.Init(factory,m.init,1);auto manager=s.Element(s.Object(factory,m.managers,0),0);auto exported=Export(s,m,manager,2);
 Check(std::set<Der>(exported.begin(),exported.end())==std::set<Der>(oracle.begin(),oracle.end())&&exported.size()==oracle.size(),"actual NDK export through default real Windows reader matches all independent public DER");
 printf("PUBLIC-ROOTS enumerated=%zu disallowed=%zu excluded_disallowed=%zu excluded_usage=%zu excluded_explicit_distrust=%zu duplicates=%zu accepted=%zu\n",roots.enumerated_roots,roots.disallowed_certificates,roots.excluded_disallowed,roots.excluded_usage,roots.excluded_explicit_distrust,roots.duplicates,roots.certificates.size());
}
}
int main(int argc,char**argv){try{setvbuf(stdout,nullptr,_IONBF,0);elf_image image{};Check(!elf_load(TLS_LIBRARY,0x7c000000,nullptr,&image),"real NDK JNI caller ELF loads");if(argc>1&&std::string(argv[1])=="--revoked"){Session s(image);JavaTlsTrust service(s.host,{[]{return JavaTlsTrust::RootSnapshot{};},{}});Methods m(s);service.Revoke();s.Object(m.factory,m.def,0,0,false,true);throw std::runtime_error("revoked callback returned success");}auto roots=ReadBundle();Functional(image,roots);PublicRoots(image,roots);for(const auto&call:calls)printf("NDK-CALL %s %u\n",call.first.c_str(),call.second);printf("JAVA-TLS-TRUST-PASS checks=%u actual_NDK_entry_calls=%u forms=%u,%u,%u State=1200 Memory64=1 realROOT=1 peer_verification_claim=0\n",checks,entries,forms[0],forms[1],forms[2]);return 0;}catch(const std::exception&e){fprintf(stderr,"java TLS trust fixture: %s\n",e.what());return 1;}}
