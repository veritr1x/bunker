#include "libc.h"
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wmisleading-indentation"
#include "provider_memory.h"
#pragma GCC diagnostic pop
#include "libc_calendar_detail.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <array>
#include <cerrno>
#include <cfenv>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
namespace {
using namespace bunker::windows::libc_calendar;
unsigned checks=0,calls=0,oracle_rows=0;
int guest_error=0;bunker::windows::LibC*provider=nullptr;
void Check(bool v,const char*s){++checks;if(!v){std::fprintf(stderr,"CALENDAR-FAIL %s\n",s);std::abort();}}
void*Resolve(const char*s){if(!std::strcmp(s,"__errno"))return reinterpret_cast<void*>(0x7ffc00000000ULL);return reinterpret_cast<void*>(provider->Marker(s));}
int64_t OracleFloor(int64_t n,int64_t d){int64_t q=n/d,r=n%d;return q-(r<0);}
int64_t OracleDays(int64_t y,unsigned m,unsigned d){y-=m<=2;const int64_t era=OracleFloor(y,400);const unsigned yy=unsigned(y-era*400);const unsigned doy=(153*(m+(m>2?unsigned(-3):9))+2)/5+d-1;return era*146097+int64_t(yy*365+yy/4-yy/100+doy)-719468;}
unsigned Sunday(int y,unsigned month,unsigned occurrence){int64_t first=(OracleDays(y,month,1)+4)%7;if(first<0)first+=7;return unsigned(1+(7-first)%7+7*(occurrence-1));}
int Rule(unsigned profile,int y,YearRule&r){
 if(y<1601||y>30827)return 75;
 r={};if(profile==0){r.standard_name="UTC";return 0;}if(profile==1){r.standard_offset=19800;r.standard_name="IST";return 0;}
 r.has_dst=true;if(profile==2){r.standard_offset=-18000;r.daylight_offset=-14400;r.standard_name="EST";r.daylight_name="EDT";r.daylight_start_utc=OracleDays(y,3,Sunday(y,3,2))*86400+2*3600-r.standard_offset;r.standard_start_utc=OracleDays(y,11,Sunday(y,11,1))*86400+2*3600-r.daylight_offset;}
 else{r.standard_offset=36000;r.daylight_offset=39600;r.standard_name="AEST";r.daylight_name="AEDT";r.daylight_start_utc=OracleDays(y,10,Sunday(y,10,1))*86400+2*3600-r.standard_offset;r.standard_start_utc=OracleDays(y,4,Sunday(y,4,1))*86400+3*3600-r.daylight_offset;}return 0;
}
std::vector<std::string>Split(const std::string&s){std::vector<std::string>v;std::stringstream x(s);std::string t;while(std::getline(x,t,'|'))v.push_back(t);return v;}
int64_t Number(const std::string&s){return std::stoll(s);}
void Oracle(const char*path){
 std::ifstream f(path);Check(bool(f),"actual Bionic TSV opens");std::string line;
 while(std::getline(f,line)){auto v=Split(line);Check(v.size()==24,"oracle row width");unsigned profile=unsigned(Number(v[0]));Tm t;std::memset(&t,0xa5,sizeof(t));t.year=int32_t(Number(v[2])-1900);t.mon=int32_t(Number(v[3]));t.mday=int32_t(Number(v[4]));t.hour=int32_t(Number(v[5]));t.min=int32_t(Number(v[6]));t.sec=int32_t(Number(v[7]));t.isdst=int32_t(Number(v[8]));t.gmtoff=Number(v[9]);t.wday=77;t.yday=88;t.zone=0;
  int error=22;Calendar c([&](int e){error=e;},[=](int y,YearRule&r){return Rule(profile,y,r);});
  const auto result=c.Mktime(reinterpret_cast<addr_t>(&t));if(result!=Number(v[10])||error!=Number(v[11])){std::fprintf(stderr,"ORACLE %u %s got%lld/%d expected%s/%s\n",profile,v[1].c_str(),(long long)result,error,v[10].c_str(),v[11].c_str());Check(false,"mktime actual Bionic timestamp/errno");}
  int32_t fields[]={t.sec,t.min,t.hour,t.mday,t.mon,t.year,t.wday,t.yday,t.isdst};for(unsigned i=0;i<9;++i)Check(fields[i]==Number(v[12+i]),"all normalized or failure-preserved int32 tm fields");Check(t.gmtoff==Number(v[21])&&t.padding==uint32_t(Number(v[23])),"actual Bionic gmtoff and untouched padding");
  Check(v[22]=="NULL"?t.zone==0:t.zone&&std::string(reinterpret_cast<const char*>(t.zone))==v[22],"actual Bionic zone contents, stable owned pointer");++oracle_rows;
  if(result!=-1){const char fmt[]="%Z";const std::string name(reinterpret_cast<const char*>(t.zone));for(size_t cap=0;cap<=name.size()+1;++cap){std::array<char,128>b;b.fill('!');error=22;auto n=c.Strftime(reinterpret_cast<addr_t>(b.data()+8),cap,reinterpret_cast<addr_t>(fmt),reinterpret_cast<addr_t>(&t));Check(n==(cap>name.size()?name.size():0)&&error==(cap>name.size()?22:34),"native Bionic percentZ capacity and ERANGE");for(unsigned i=0;i<8;++i)Check(b[i]=='!',"format prefix canary");for(size_t i=8+cap;i<b.size();++i)Check(b[i]=='!',"format suffix canary");if(n)Check(std::string(b.data()+8)==name,"percentZ actual name");}}
 }
 Check(oracle_rows==96,"96 full native calendar records;8 outsideWindowsyearrange explicitly excluded");
 for(unsigned p=0;p<4;++p){int error=22;Calendar c([&](int e){error=e;},[=](int y,YearRule&r){return Rule(p,y,r);});for(int year:{-10000,100000}){Tm t{};t.year=year-1900;t.mday=1;t.isdst=-1;Check(c.Mktime(reinterpret_cast<addr_t>(&t))==-1&&error==75,"explicit hostzone supported-year failure, no fake Bionicfullrange");}}
 Check(Calendar::Difftime(INT64_MAX,INT64_MAX-1)==1&&Calendar::Difftime(INT64_MIN+1,INT64_MIN)==1,"difftime adjacent INT64extremes not catastrophic cancellation");Check(Calendar::Difftime(INT64_MAX,INT64_MIN)==18446744073709551616.0,"difftime no signed subtraction overflow");
 Tm failure{};failure.year=70;failure.mday=1;const auto unchanged=failure;int error=22,sinkcalls=0;
 Calendar failed([&](int e){error=e;++sinkcalls;errno=E2BIG;SetLastError(0x8181);std::fesetround(FE_UPWARD);},[](int,YearRule&){errno=ERANGE;SetLastError(0x9292);return 5;});errno=EAGAIN;SetLastError(0x7373);std::fesetround(FE_DOWNWARD);
 Check(failed.Mktime(reinterpret_cast<addr_t>(&failure))==-1&&error==5&&sinkcalls==1&&!std::memcmp(&failure,&unchanged,56),"actual query failure once without fake success or output");Check(errno==EAGAIN&&GetLastError()==0x7373&&std::fegetround()==FE_DOWNWARD,"query and sink environment restored");std::fesetround(FE_TONEAREST);
 bool blocked=false;try{Calendar configured([](int){},YearQuery{},"UTC0",true);(void)configured.Mktime(reinterpret_cast<addr_t>(&failure));}catch(const std::runtime_error&){blocked=true;}Check(blocked,"unsupported explicit guestTZ fails closed instead of silentlydiscardingoverride");
}
std::string Unhex(const std::string&s){Check(s.size()%2==0,"hex byte extent");std::string r;for(size_t i=0;i<s.size();i+=2)r.push_back(char(std::stoul(s.substr(i,2),nullptr,16)));return r;}
void Formats(const char*path){std::ifstream f(path);Check(bool(f),"native format TSV");std::string line;unsigned rows=0;while(std::getline(f,line)){auto v=Split(line);Check(v.size()==6,"format oracle width");unsigned p=unsigned(Number(v[0]));int64_t stamp=Number(v[1]);auto pattern=Unhex(v[2]);const auto expected=Unhex(v[5]);int error=22;Calendar c([&](int e){error=e;},[=](int y,YearRule&r){return Rule(p,y,r);});Tm t{};Check(c.LocaltimeR(reinterpret_cast<addr_t>(&stamp),reinterpret_cast<addr_t>(&t))==reinterpret_cast<addr_t>(&t),"format input real native-rule instant");std::array<char,528>buffer;buffer.fill('!');error=22;auto n=c.Strftime(reinterpret_cast<addr_t>(buffer.data()+8),512,reinterpret_cast<addr_t>(pattern.c_str()),reinterpret_cast<addr_t>(&t));if(n!=uint64_t(Number(v[3]))||error!=Number(v[4])||std::string(buffer.data()+8,n)!=expected){std::fprintf(stderr,"FORMAT %u timestamp%lld pattern%s got%llu/%d expected%s/%s\n",p,(long long)stamp,pattern.c_str(),(unsigned long long)n,error,v[3].c_str(),v[4].c_str());Check(false,"all native Bionic C-format bytes");}Check(buffer[7]=='!'&&buffer[520]=='!',"format fullbuffer canaries");++rows;}Check(rows==100,"100 native Bionic standard/ISO/offset/modifier/epoch format records");}
struct Request{uint32_t operation,indirect;int32_t sentinel,pad;uint64_t a,b,c,d;};struct Result{uint64_t integer;double floating;int32_t error,pad;};
std::string Utf8(const wchar_t*s){int n=WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,s,-1,nullptr,0,nullptr,nullptr);Check(n>0,"independent Windows zone UTF8");std::vector<char>b(size_t(n),0);Check(WideCharToMultiByte(CP_UTF8,WC_ERR_INVALID_CHARS,s,-1,b.data(),n,nullptr,nullptr)==n,"zone UTF8 content");return b.data();}
void RealNDK(){
 bunker::windows::LibC libc;provider=&libc;libc.SetErrorSink([](int e){guest_error=e;});recomp::Runtime runtime;libc.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));runtime.AddImport(0x7ffc00000000ULL,[](State&s){s.gpr.x0.qword=reinterpret_cast<addr_t>(&guest_error);});elf_image image{};Check(!elf_load(CALENDAR_LIBRARY,0x5b000000,Resolve,&image),"actualNDK calendar guest loads");
 auto invoke=[&](unsigned op,unsigned indirect,uint64_t a,uint64_t b=0,uint64_t c=0,uint64_t d=0){Request q{op,indirect,22,0,a,b,c,d};struct{uint64_t before;Result r;uint64_t after;}out{0xabcdeffedcbaULL,{},0xfedcbaabcdefULL};alignas(16)std::array<unsigned char,65536>stack{};std::array<unsigned char,64>token;token.fill(0xa9);const auto old=token;State s{};s.gpr.x0.qword=reinterpret_cast<addr_t>(&q);s.gpr.x1.qword=reinterpret_cast<addr_t>(&out.r);s.gpr.x19.qword=0xf123456789abcdefULL;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;errno=EAGAIN;SetLastError(0x7373);std::fesetround(FE_DOWNWARD);std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_DIVBYZERO);auto*m=reinterpret_cast<Memory*>(token.data());Check(runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,"guest_calendar")),m)==m&&token==old,"actualNDK Memory64 token");++calls;Check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size())&&s.gpr.x19.qword==0xf123456789abcdefULL,"NDK PC/SP/callee register");Check(out.before==0xabcdeffedcbaULL&&out.after==0xfedcbaabcdefULL,"actualNDK result canaries");Check(errno==EAGAIN&&GetLastError()==0x7373&&std::fegetround()==FE_DOWNWARD&&std::fetestexcept(FE_ALL_EXCEPT)==FE_DIVBYZERO,"native errno LastError FENV preserved");std::fesetround(FE_TONEAREST);std::feclearexcept(FE_ALL_EXCEPT);return out.r;};
 DYNAMIC_TIME_ZONE_INFORMATION dt{};Check(GetDynamicTimeZoneInformation(&dt)!=TIME_ZONE_ID_INVALID,"independent actual host timezone");TIME_ZONE_INFORMATION yr{};Check(GetTimeZoneInformationForYear(1970,&dt,&yr),"independent1970Windowsrule");const int64_t expected=int64_t(yr.Bias+yr.StandardBias)*60;const auto standard_name=Utf8(yr.StandardName);
 for(unsigned indirect=0;indirect<2;++indirect){
  struct{uint64_t before;Tm tm;uint64_t after;}record{0xaabbccddULL,{},0xddccbbaaULL};record.tm.year=70;record.tm.mday=1;auto r=invoke(0,indirect,reinterpret_cast<addr_t>(&record.tm));Check(int64_t(r.integer)==expected&&r.error==22,"1970Jan1explicitSTD realWindowsbias includingnegativeUTC");Check(record.before==0xaabbccddULL&&record.after==0xddccbbaaULL,"mktime exact56 span");Check(record.tm.gmtoff==-expected&&record.tm.zone,"realWindows gmtoff/name present");
  int64_t epoch=0;auto local=invoke(1,indirect,reinterpret_cast<addr_t>(&epoch));Check(local.integer!=0,"localtime actual static result");Tm saved=*reinterpret_cast<Tm*>(local.integer);const auto saved_zone=std::string(reinterpret_cast<const char*>(saved.zone));auto utc=invoke(3,indirect,reinterpret_cast<addr_t>(&epoch));Check(utc.integer&&utc.integer!=local.integer,"selectedNDK separate localtime andgmtime storage");Check(std::string(reinterpret_cast<const char*>(saved.zone))==saved_zone,"zone lifetime survivesothercalendarcall");auto*g=reinterpret_cast<Tm*>(utc.integer);Check(g->year==70&&g->mon==0&&g->mday==1&&g->hour==0&&g->gmtoff==0&&g->isdst==0&&g->zone&&std::string(reinterpret_cast<const char*>(g->zone))=="UTC","gmtime Unixepoch UTCfields andselectedBionicUTCname");
  for(unsigned op:{2u,4u}){std::array<unsigned char,88>b;b.fill(0xa5);auto rr=invoke(op,indirect,reinterpret_cast<addr_t>(&epoch),reinterpret_cast<addr_t>(b.data()+16));Check(rr.integer==reinterpret_cast<addr_t>(b.data()+16)&&rr.error==22,"_r returns exactcallerbuffer");for(unsigned i=0;i<16;++i)Check(b[i]==0xa5&&b[72+i]==0xa5,"_r exact56canaries");}
  FILETIME before{},after{};GetSystemTimePreciseAsFileTime(&before);int64_t published=-123;auto now=invoke(5,indirect,reinterpret_cast<addr_t>(&published));GetSystemTimePreciseAsFileTime(&after);auto sec=[](FILETIME f){return int64_t((uint64_t(f.dwHighDateTime)<<32|f.dwLowDateTime)/10000000)-11644473600LL;};Check(published==int64_t(now.integer)&&published>=sec(before)-1&&published<=sec(after)&&now.error==22,"time actualWindowsrealtimeepoch/coarseclock1secondbracket exact8bytes");Check(invoke(5,indirect,0).error==22,"time NULLoptionaloutput");
  Check(invoke(6,indirect,uint64_t(INT64_MAX),uint64_t(INT64_MAX-1)).floating==1,"actualNDK doubleFP return diffadjacentMAX");Check(invoke(6,indirect,uint64_t(INT64_MIN+1),uint64_t(INT64_MIN)).floating==1,"actualNDK doubleFP return diffadjacentMIN");
  for(int64_t extreme:{INT64_MIN,INT64_MAX}){auto bad=invoke(3,indirect,reinterpret_cast<addr_t>(&extreme));Check(bad.integer==0&&bad.error==75,"gmtime timestamp beyond int32_tmyear fails without arithmetic overflow");}
  std::array<char,80>name;name.fill('!');const char fmt[]="%Z";auto n=invoke(7,indirect,reinterpret_cast<addr_t>(name.data()+8),64,reinterpret_cast<addr_t>(fmt),reinterpret_cast<addr_t>(&record.tm));Check(n.integer>0&&n.integer<64&&n.error==22&&std::string(name.data()+8)==standard_name,"originalcallerpercentZ64 actualWindowsstandardname");Check(name[7]=='!'&&name[72]=='!',"strftime caller64canaries");
  auto null=invoke(0,indirect,0);Check(int64_t(null.integer)==-1&&null.error==75,"actualNDK NULLmktime selectedBionicerrno75");
 }
 Check(calls==26,"all8APIs directindirect plus meaningfulaliases");
}
}
int main(int argc,char**argv){SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
 if(argc==2&&std::string(argv[1]).find("fault-")==0){Calendar c([](int){},[](int y,YearRule&r){return Rule(0,y,r);});int64_t stamp=0;Tm t{};if(!std::strcmp(argv[1],"fault-read")){c.LocaltimeR(1,reinterpret_cast<addr_t>(&t));return 99;}if(!std::strcmp(argv[1],"fault-write")){void*p=VirtualAlloc(nullptr,4096,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE);if(!p)return 98;DWORD old;VirtualProtect(p,4096,PAGE_READONLY,&old);c.LocaltimeR(reinterpret_cast<addr_t>(&stamp),reinterpret_cast<addr_t>(p));return 99;}return 97;}
 Check(argc==3,"oracleTSVarguments");Oracle(argv[1]);Formats(argv[2]);RealNDK();std::printf("CALENDAR-PASS checks=%u oracle_MK=%u NDK_calls=%u APIs=8 Bionic_tm=56 actual_host_zone=1\n",checks,oracle_rows,calls);}
