#include "jni_host.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <algorithm>
#include <array>
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iterator>
#include <sstream>
#include <stdexcept>
#include <vector>
namespace {
unsigned checks=0,calls=0,decodes=0,encodes=0;
void Check(bool v,const char*s){++checks;if(!v)throw std::runtime_error(s);}
std::vector<std::string>Split(const std::string&s){std::vector<std::string>r;std::stringstream f(s);std::string v;while(std::getline(f,v,'|'))r.push_back(v);if(!s.empty()&&s.back()=='|')r.emplace_back();return r;}
std::vector<uint8_t>Bytes(const std::string&s){Check(s.size()%2==0,"oraclehexbytes");std::vector<uint8_t>v;for(size_t i=0;i<s.size();i+=2)v.push_back(uint8_t(std::stoul(s.substr(i,2),nullptr,16)));return v;}
std::u16string Units(const std::string&s){Check(s.size()%4==0,"oracleUTF16units");std::u16string v;for(size_t i=0;i<s.size();i+=4)v.push_back(char16_t(std::stoul(s.substr(i,4),nullptr,16)));return v;}
struct Fixture{
 elf_image image{};recomp::Runtime runtime;bunker::jni::Host host{[](addr_t){return false;}};addr_t strings=0,byteclass=0,ctor=0,getbytes=0;
 Fixture(){static_assert(sizeof(State)==1200&&alignof(State)==16);Check(!elf_load(STRING_BYTES_IMAGE,0x77000000,nullptr,&image),"NDKcallerELFmapping");host.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));strings=Find("java/lang/String");byteclass=Find("[B");ctor=Method(strings,"<init>","([BLjava/lang/String;)V");getbytes=Method(strings,"getBytes","(Ljava/lang/String;)[B");Check(ctor&&getbytes&&host.PendingException().empty(),"actualJNIStringmethodmetadata");}
 addr_t Run(const char*name,std::initializer_list<addr_t>args){alignas(16)std::array<uint8_t,65536>stack{};State s{};Reg GPR::*regs[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5};size_t i=0;for(auto v:args)(s.gpr.*regs[i++]).qword=v;s.gpr.x19.qword=0xf0123456789abcdeULL;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;std::array<uint8_t,16>upper;upper.fill(0xd7);std::memcpy(&s.simd.v[31],upper.data(),16);reinterpret_cast<uint8_t*>(&s)[1199]=0x71;auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,name));Check(entry!=0,"NDKexportexists");auto*token=reinterpret_cast<Memory*>(0xfedcba9876543210ULL);Check(runtime.Run(s,entry,token)==token,"full64opaqueMemory");++calls;Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size())&&s.gpr.x19.qword==0xf0123456789abcdeULL,"actualNDKreturnPCSPcalleeSaved64");Check(!std::memcmp(&s.simd.v[31],upper.data(),16)&&reinterpret_cast<uint8_t*>(&s)[1199]==0x71,"State1200SIMD128highcell");return s.gpr.x0.qword;}
 addr_t Find(const char*n){return Run("sb_find",{host.EnvAddress(),reinterpret_cast<addr_t>(n)});}
 addr_t Method(addr_t c,const char*n,const char*s){return Run("sb_method",{host.EnvAddress(),c,reinterpret_cast<addr_t>(n),reinterpret_cast<addr_t>(s)});}
 addr_t Name(const std::string&s){return host.NewString(std::u16string(s.begin(),s.end()));}
 addr_t Array(const std::vector<uint8_t>&v){return Run("sb_array",{host.EnvAddress(),reinterpret_cast<addr_t>(v.data()),v.size()});}
 addr_t Construct(addr_t a,addr_t n,unsigned form){return Run("sb_ctor",{host.EnvAddress(),strings,ctor,a,n,form});}
 addr_t Encode(addr_t s,addr_t n,unsigned form){return Run("sb_encode",{host.EnvAddress(),s,getbytes,n,form});}
 void Push(){Check(Run("sb_push",{host.EnvAddress(),16})==0,"actualJNIlocalframe");}
 addr_t Pop(addr_t r=0){return Run("sb_pop",{host.EnvAddress(),r});}
 void CheckUnits(addr_t s,const std::u16string&expected){Check(host.StringValue(s)==std::optional<std::u16string>(expected),"initializedStringkind/exactUTF16");std::vector<uint16_t>b(expected.size()+8,0xa55a);auto n=Run("sb_units",{host.EnvAddress(),s,reinterpret_cast<addr_t>(b.data()+4),expected.size()});Check(n==expected.size()&&(expected.empty()||!std::memcmp(b.data()+4,expected.data(),expected.size()*2))&&std::all_of(b.begin(),b.begin()+4,[](auto x){return x==0xa55a;})&&std::all_of(b.end()-4,b.end(),[](auto x){return x==0xa55a;}),"actualJNIUTF16chars/length/exactwrites");Check(Run("sb_shape",{host.EnvAddress(),s,strings})==3,"StringinstanceandGetObjectClassidentity");}
 void CheckBytes(addr_t a,const std::vector<uint8_t>&expected){Check(a&&!host.PendingException().size(),"returnedbytearraywithoutpendingexception");std::vector<uint8_t>b(expected.size()+16,0x9b);auto n=Run("sb_read_array",{host.EnvAddress(),a,reinterpret_cast<addr_t>(b.data()+8),expected.size()});Check(n==expected.size()&&(expected.empty()||!std::memcmp(b.data()+8,expected.data(),expected.size()))&&std::all_of(b.begin(),b.begin()+8,[](auto x){return x==0x9b;})&&std::all_of(b.end()-8,b.end(),[](auto x){return x==0x9b;}),"encodedbytesexact/canaries");Check(Run("sb_shape",{host.EnvAddress(),a,byteclass})==3,"bytearrayactualclassandinstance");}
 void Error(const char*category){Check(host.PendingException().find(category)!=std::string::npos,"exactJavaexceptioncategory");host.ClearException();}
};
}
int main(int argc,char**argv){try{Check(argc==2,"oracleTSVargument");Fixture f;std::ifstream file(argv[1]);Check(bool(file),"actualJDKoracleopens");std::string line;
 while(std::getline(file,line)){if(!line.empty()&&line.back()=='\r')line.pop_back();auto v=Split(line);if(v.empty()||(v[0]!="D"&&v[0]!="E"))continue;Check(v.size()==4,"JDKconversionrecordshape");f.Push();auto name=f.Name(v[1]);
  if(v[0]=="D"){auto input=Bytes(v[2]);auto expected=Units(v[3]);auto a=f.Array(input);for(unsigned form=0;form<3;++form){auto s=f.Construct(a,name,form);if(!s||!f.host.PendingException().empty()){std::fprintf(stderr,"DECODE %s %s form%u pending%s\n",v[1].c_str(),v[2].c_str(),form,f.host.PendingException().c_str());Check(false,"validprofileconstructor");}try{f.CheckUnits(s,expected);}catch(...){std::fprintf(stderr,"DECODE-DIFF %s %s form%u\n",v[1].c_str(),v[2].c_str(),form);throw;}}++decodes;}
  else{auto input=Units(v[2]);auto expected=Bytes(v[3]);auto s=f.host.NewString(input);for(unsigned form=0;form<3;++form){auto a=f.Encode(s,name,form);if(!a||!f.host.PendingException().empty()){std::fprintf(stderr,"ENCODE %s %s form%u pending%s\n",v[1].c_str(),v[2].c_str(),form,f.host.PendingException().c_str());Check(false,"validprofilegetBytes");}try{f.CheckBytes(a,expected);}catch(...){std::fprintf(stderr,"ENCODE-DIFF %s %s form%u\n",v[1].c_str(),v[2].c_str(),form);throw;}}Check(f.host.StringValue(s)==std::optional<std::u16string>(input),"getBytesdoesnotmutateString");++encodes;}
  f.Pop();
 }
 Check(decodes==71&&encodes==47,"allactualJDKprofilevectorsincludingaliases");
 auto utf8=f.Name("UTF-8"),empty=f.Array({}),text=f.host.NewString(u"x");Check(!f.Construct(0,utf8,0),"nullbytearray");f.Error("NullPointerException");Check(!f.Construct(empty,0,1),"nullcharsetconstructor");f.Error("NullPointerException");Check(!f.Encode(text,0,2),"nullcharsetgetBytes");f.Error("NullPointerException");Check(!f.Construct(empty,f.Name("bad charset"),2),"illegalcharsetsyntax");f.Error("UnsupportedEncodingException");Check(!f.Encode(text,f.Name(""),0),"emptycharsetname");f.Error("UnsupportedEncodingException");
 auto outside=f.Name("Shift_JIS");uint64_t args[]={empty,outside};State guarded{};guarded.gpr.x0.qword=f.host.EnvAddress();guarded.gpr.x1.qword=f.strings;guarded.gpr.x2.qword=f.ctor;guarded.gpr.x3.qword=reinterpret_cast<addr_t>(args);bool rejected=false;try{f.host.InvokeEnv(30,guarded);}catch(const std::exception&e){rejected=std::string(e.what()).find("unqualified")!=std::string::npos;}Check(rejected&&f.host.PendingException().empty(),"validoutprofilecharsetisnativeguardnotfakeJavafailure");
 f.Push();auto source=f.host.NewString(u"lifetime"),charset=f.Name("UTF-8"),returned=f.Encode(source,charset,2);auto weak=f.Run("sb_ref",{f.host.EnvAddress(),returned,2});auto promoted=f.Pop(returned);f.CheckBytes(promoted,{'l','i','f','e','t','i','m','e'});Check(f.Run("sb_same",{f.host.EnvAddress(),weak,0})==0,"bytearraypromotedafterStringframeexpiry");f.Run("sb_ref",{f.host.EnvAddress(),promoted,4});Check(f.Run("sb_same",{f.host.EnvAddress(),weak,0})==1,"returnedbytearrayretiredwithoutleakedroots");f.Run("sb_ref",{f.host.EnvAddress(),weak,3});
 auto a=f.Array({'A'}),decoded=f.Construct(a,utf8,2);const uint8_t changed='B';f.Run("sb_set",{f.host.EnvAddress(),a,reinterpret_cast<addr_t>(&changed)});f.CheckUnits(decoded,u"A");
 f.host.DefineClass("OldCtor");f.host.DefineConstructor("OldCtor","()V",[&](const bunker::jni::Host::MethodArguments&){return f.host.NewInstance("OldCtor");});f.host.MarkClassInitialized("OldCtor");auto oldclass=f.Find("OldCtor"),oldctor=f.Method(oldclass,"<init>","()V"),old=f.Run("sb_empty_ctor",{f.host.EnvAddress(),oldclass,oldctor});Check(old&&f.Run("sb_shape",{f.host.EnvAddress(),old,oldclass})==3,"existinggenericconstructorfactorynotweakened");Check(f.host.PendingException().empty(),"nohiddenJavaexceptions");
 std::printf("JNI-STRING-BYTES-PASS checks=%u NDK_calls=%u decode_vectors=%u encode_vectors=%u forms=3 State=1200 Memory64=1\n",checks,calls,decodes,encodes);return 0;
}catch(const std::exception&e){std::fprintf(stderr,"JNI String bytes: %s\n",e.what());return 1;}}
