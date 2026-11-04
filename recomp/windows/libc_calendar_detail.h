#pragma once
#include "provider_memory.h"
#include "libc_uname_detail.h"
#include "libc_wall_time_detail.h"
#include <algorithm>
#include <array>
#include <cstdio>
#include <functional>
#include <limits>
#include <map>
#include <mutex>
#include <set>
#include <string>
#include <utility>
#ifndef _WIN32
#include <sys/time.h>
#endif

namespace bunker::windows::libc_calendar {
struct Tm {
  int32_t sec,min,hour,mday,mon,year,wday,yday,isdst;
  uint32_t padding;
  int64_t gmtoff;
  addr_t zone;
};
static_assert(sizeof(Tm)==56 && alignof(Tm)==8);
static_assert(offsetof(Tm,isdst)==32 && offsetof(Tm,gmtoff)==40 && offsetof(Tm,zone)==48);
struct YearRule {
  int32_t standard_offset=0,daylight_offset=0;
  bool has_dst=false;
  int64_t daylight_start_utc=0,standard_start_utc=0;
  std::string standard_name,daylight_name;
};
using YearQuery=std::function<int(int,YearRule&)>;
using NativeEnvironment=libc_detail::uname_detail::NativeEnvironment;
inline int64_t Floor(int64_t a,int64_t b){const auto q=a/b,r=a%b;return q-(r<0);}
inline bool Add(int64_t a,int64_t b,int64_t &out){
  if((b>0&&a>INT64_MAX-b)||(b<0&&a<INT64_MIN-b))return false;
  out=a+b;return true;
}
inline int64_t Days(int64_t y,unsigned m,unsigned d){
  y-=m<=2;const int64_t era=Floor(y,400),yoe=y-era*400;
  const int64_t doy=(153*(static_cast<int>(m)+(m>2?-3:9))+2)/5+d-1;
  return era*146097+yoe*365+yoe/4-yoe/100+doy-719468;
}
inline void Civil(int64_t days,int64_t &year,unsigned &month,unsigned &day){
  days+=719468;const auto era=Floor(days,146097),doe=days-era*146097;
  const auto yoe=(doe-doe/1460+doe/36524-doe/146096)/365;
  year=yoe+era*400;const auto doy=doe-(365*yoe+yoe/4-yoe/100),mp=(5*doy+2)/153;
  day=static_cast<unsigned>(doy-(153*mp+2)/5+1);month=static_cast<unsigned>(mp+(mp<10?3:-9));year+=month<=2;
}
inline bool Utc(int64_t value,Tm &out){
  const auto days=Floor(value,86400);const auto seconds=value%86400+(value%86400<0?86400:0);
  int64_t y;unsigned m,d;Civil(days,y,m,d);
  if(y-1900<INT32_MIN||y-1900>INT32_MAX)return false;
  out.sec=static_cast<int32_t>(seconds%60);out.min=static_cast<int32_t>(seconds/60%60);out.hour=static_cast<int32_t>(seconds/3600);
  out.mday=static_cast<int32_t>(d);out.mon=static_cast<int32_t>(m-1);out.year=static_cast<int32_t>(y-1900);
  out.wday=static_cast<int32_t>((days%7+11)%7);out.yday=static_cast<int32_t>(days-Days(y,1,1));out.isdst=0;out.gmtoff=0;return true;
}
inline int Compare(const Tm &a,const Tm &b){
  const int32_t x[]={a.year,a.mon,a.mday,a.hour,a.min,a.sec},y[]={b.year,b.mon,b.mday,b.hour,b.min,b.sec};
  for(unsigned i=0;i<6;++i)if(x[i]!=y[i])return x[i]<y[i]?-1:1;
  return 0;
}
inline bool Int32(int64_t n){return INT32_MIN<=n&&n<=INT32_MAX;}
inline bool Normalize(const Tm &input,bool normalize_seconds,Tm &out,int32_t &saved_seconds){
  out=input;int64_t sec=input.sec,min=input.min,hour=input.hour,day=input.mday,mon=input.mon,year=input.year;
  if(normalize_seconds){min+=Floor(sec,60);sec-=Floor(sec,60)*60;if(!Int32(min))return false;}
  hour+=Floor(min,60);min-=Floor(min,60)*60;if(!Int32(hour))return false;
  day+=Floor(hour,24);hour-=Floor(hour,24)*24;if(!Int32(day))return false;
  year+=Floor(mon,12);mon-=Floor(mon,12)*12;
  year+=1900;if(!Int32(year))return false;
  const auto days=Days(year,static_cast<unsigned>(mon+1),1)+day-1;unsigned m,d;Civil(days,year,m,d);
  if(!Int32(year-1900))return false;
  saved_seconds=0;
  if(sec<0||sec>=60){
    const auto saved=year<1970?sec-59:sec;if(!Int32(saved))return false;
    saved_seconds=static_cast<int32_t>(saved);sec=year<1970?59:0;
  }
  out.sec=static_cast<int32_t>(sec);out.min=static_cast<int32_t>(min);out.hour=static_cast<int32_t>(hour);out.mday=static_cast<int32_t>(d);out.mon=static_cast<int32_t>(m-1);out.year=static_cast<int32_t>(year-1900);return true;
}
inline const char *Intern(const std::string &text){
  static std::mutex mutex;static std::set<std::string> names;
  std::lock_guard<std::mutex> lock(mutex);auto result=names.insert(text);
  if(result.second)recomp::InvalidateGuestMemory(reinterpret_cast<addr_t>(result.first->c_str()),result.first->size()+1);
  return result.first->c_str();
}
inline Tm &SharedTm(bool local){static Tm values[2]{};return values[local?0:1];}
inline std::recursive_mutex &SharedMutex(){static std::recursive_mutex mutex;return mutex;}
#ifdef _WIN32
inline int64_t Transition(int year,const SYSTEMTIME &date,int32_t old_offset){
  const auto y=date.wYear?date.wYear:year;unsigned day=date.wDay;
  if(!date.wYear){
    const auto weekday=static_cast<unsigned>((Days(y,date.wMonth,1)%7+11)%7);
    day=1+(date.wDayOfWeek+7-weekday)%7+7*(date.wDay-1);
    const auto next=date.wMonth==12?Days(y+1,1,1):Days(y,date.wMonth+1,1);
    if(Days(y,date.wMonth,day)>=next)day-=7;
  }
  return Days(y,date.wMonth,day)*86400+date.wHour*3600+date.wMinute*60+date.wSecond-old_offset;
}
inline YearQuery HostQuery(){
  NativeEnvironment native;DYNAMIC_TIME_ZONE_INFORMATION zone{};
  if(GetDynamicTimeZoneInformation(&zone)==TIME_ZONE_ID_INVALID){const int error=libc_detail::uname_detail::WindowsError(GetLastError());return [error](int,YearRule&){return error;};}
  return [zone](int year,YearRule &out) mutable ->int {
    NativeEnvironment native;
    if(year<1601||year>30827)return 75;
    TIME_ZONE_INFORMATION value{};
    if(!GetTimeZoneInformationForYear(static_cast<USHORT>(year),&zone,&value))return libc_detail::uname_detail::WindowsError(GetLastError());
    YearRule result;
    const int64_t standard=-60*(int64_t(value.Bias)+value.StandardBias),daylight=-60*(int64_t(value.Bias)+value.DaylightBias);
    if(!Int32(standard)||!Int32(daylight))return 75;
    result.standard_offset=static_cast<int32_t>(standard);result.daylight_offset=static_cast<int32_t>(daylight);
    result.standard_name=libc_detail::uname_detail::Wide(value.StandardName,std::wcslen(value.StandardName));
    result.daylight_name=libc_detail::uname_detail::Wide(value.DaylightName,std::wcslen(value.DaylightName));
    result.has_dst=!zone.DynamicDaylightTimeDisabled&&value.DaylightDate.wMonth&&value.StandardDate.wMonth;
    if(result.has_dst){result.daylight_start_utc=Transition(year,value.DaylightDate,result.standard_offset);result.standard_start_utc=Transition(year,value.StandardDate,result.daylight_offset);}
    out=std::move(result);return 0;
  };
}
#else
inline YearQuery HostQuery(){return [](int,YearRule&){return 38;};}
#endif
inline int QueryHostYear(int year,YearRule &out){return HostQuery()(year,out);}

class Calendar {
 public:
  explicit Calendar(std::function<void(int)> sink,YearQuery query={},std::string virtual_TZ={},bool virtual_TZ_present=false)
    :sink_(std::move(sink)),custom_query_(bool(query)),query_(query?std::move(query):HostQuery()),virtual_TZ_(std::move(virtual_TZ)),virtual_TZ_present_(virtual_TZ_present){}
  int64_t Time(addr_t output){
    NativeEnvironment native;
    int64_t seconds;
#ifdef _WIN32
    FILETIME now{};GetSystemTimeAsFileTime(&now);seconds=libc_detail::UnixTimeval((uint64_t(now.dwHighDateTime)<<32)|now.dwLowDateTime).seconds;
#else
    timeval now{};if(::gettimeofday(&now,nullptr)){Error(errno?errno:5);return -1;}seconds=now.tv_sec;
#endif
    if(output){recomp::WriteGuestMemory(output,&seconds,sizeof(seconds));}
    return seconds;
  }
  int64_t Mktime(addr_t address){
    NativeEnvironment native;std::lock_guard<std::recursive_mutex> lock(SharedMutex());CheckEnvironment();
    if(!address){Error(75);return -1;}
    Tm value;recomp::ReadGuestMemory(&value,address,sizeof(value));
    const auto original=value;const auto result=Resolve(value);
    if(std::memcmp(&original,&value,sizeof(value)))recomp::WriteGuestMemory(address,&value,sizeof(value));
    if(!result.ok||result.value==-1)Error(result.error?result.error:75);
    return result.ok?result.value:-1;
  }
  addr_t Localtime(addr_t input){return Broken(input,reinterpret_cast<addr_t>(&SharedTm(true)),true);}
  addr_t Gmtime(addr_t input){return Broken(input,reinterpret_cast<addr_t>(&SharedTm(false)),false);}
  addr_t LocaltimeR(addr_t input,addr_t output){return Broken(input,output,true);}
  addr_t GmtimeR(addr_t input,addr_t output){return Broken(input,output,false);}
  uint64_t Strftime(addr_t output,uint64_t capacity,addr_t format,addr_t input){
    NativeEnvironment native;std::lock_guard<std::recursive_mutex> lock(SharedMutex());CheckEnvironment();
    Tm value;recomp::ReadGuestMemory(&value,input,sizeof(value));
    const auto pattern=format?recomp::ReadGuestString(format):std::string("%c");
    const auto text=Format(pattern,value,0);
    if(!capacity){Error(34);return 0;}
    const auto count=std::min<uint64_t>(text.size(),capacity);
    if(count)recomp::WriteGuestMemory(output,text.data(),static_cast<size_t>(count));
    if(text.size()>=capacity){Error(34);return 0;}
    const char nul=0;recomp::WriteGuestMemory(output+text.size(),&nul,1);return text.size();
  }
  static double Difftime(int64_t a,int64_t b){
    NativeEnvironment native;
    if(a>=b)return static_cast<double>(static_cast<uint64_t>(a)-static_cast<uint64_t>(b));
    return -static_cast<double>(static_cast<uint64_t>(b)-static_cast<uint64_t>(a));
  }
 private:
  struct Answer{bool ok;int64_t value;int error;};
  std::function<void(int)> sink_;bool custom_query_;YearQuery query_;std::string virtual_TZ_;bool virtual_TZ_present_;std::map<int,YearRule> years_;int query_error_=0;
  void Error(int value){if(sink_)sink_(value);}
  void CheckEnvironment(){if(!custom_query_&&(virtual_TZ_present_||!virtual_TZ_.empty()))throw std::runtime_error("guest TZ override is outside the real-Windows-zone calendar profile");}
  const YearRule *Rule(int year){
    auto at=years_.find(year);if(at!=years_.end())return &at->second;
    YearRule value;const int error=query_(year,value);
    if(error){query_error_=error;return nullptr;}
    return &years_.emplace(year,std::move(value)).first->second;
  }
  bool Local(int64_t seconds,Tm &out){
    Tm utc{};if(!Utc(seconds,utc))return false;int64_t year=int64_t(utc.year)+1900;
    if(year<1601||year>30827)return false;
    for(unsigned attempt=0;attempt<3;++attempt){
      const auto *rule=Rule(static_cast<int>(year));if(!rule)return false;
      const bool dst=rule->has_dst&&(rule->daylight_start_utc<rule->standard_start_utc?
        seconds>=rule->daylight_start_utc&&seconds<rule->standard_start_utc:
        seconds>=rule->daylight_start_utc||seconds<rule->standard_start_utc);
      const auto offset=dst?rule->daylight_offset:rule->standard_offset;int64_t local;
      if(!Add(seconds,offset,local)||!Utc(local,out))return false;
      const auto localyear=int64_t(out.year)+1900;
      if(localyear!=year){if(localyear<1601||localyear>30827)return false;year=localyear;continue;}
      out.isdst=dst?1:0;out.gmtoff=offset;out.zone=reinterpret_cast<addr_t>(Intern(dst?rule->daylight_name:rule->standard_name));return true;
    }
    query_error_=5;return false;
  }
  bool Search(const Tm &input,bool normalize_seconds,int64_t &result,Tm &normalized){
    Tm wanted;int32_t saved=0;if(!Normalize(input,normalize_seconds,wanted,saved))return false;
    int64_t lo=INT64_MIN,hi=INT64_MAX;
    for(unsigned step=0;step<128;++step){
      int64_t t=lo/2+hi/2;if(t<lo)t=lo;else if(t>hi)t=hi;
      Tm actual{};const bool converted=Local(t,actual);int direction=converted?Compare(actual,wanted):(t>0?1:-1);
      if(direction){
        if(t==lo){if(t==INT64_MAX)return false;++t;++lo;}
        else if(t==hi){if(t==INT64_MIN)return false;--t;--hi;}
        if(lo>hi)return false;
        if(direction>0)hi=t;else lo=t;
        continue;
      }
      if(wanted.isdst>=0&&wanted.isdst!=actual.isdst){
        const auto *rule=Rule(wanted.year+1900);if(!rule||!rule->has_dst)return false;
        const int64_t wanted_offset=wanted.isdst?rule->daylight_offset:rule->standard_offset;
        const int64_t other_offset=wanted.isdst?rule->standard_offset:rule->daylight_offset;
        int64_t alternate;Tm alternate_tm{};
        if(!Add(t,other_offset-wanted_offset,alternate)||!Local(alternate,alternate_tm)||alternate_tm.isdst!=wanted.isdst||Compare(alternate_tm,wanted)!=0)return false;
        t=alternate;
      }
      if(!Add(t,saved,result))return false;
      normalized=input;return Local(result,normalized);
    }
    throw std::runtime_error("calendar binary-search budget exceeded");
  }
  bool Twice(const Tm &input,int64_t &result,Tm &out){return Search(input,false,result,out)||Search(input,true,result,out);}
  Answer Resolve(Tm &value){
    query_error_=0;if(value.isdst>1)value.isdst=1;
    int64_t result;Tm normalized;
    if(Twice(value,result,normalized)){value=normalized;return {true,result,0};}
    if(value.isdst>=0){
      Tm wanted;int32_t saved=0;
      if(Normalize(value,true,wanted,saved)){
        const int64_t year=int64_t(wanted.year)+1900;
        if(1601<=year&&year<=30827){const auto *rule=Rule(static_cast<int>(year));
          if(rule&&rule->has_dst){
            const int64_t same=value.isdst?rule->daylight_offset:rule->standard_offset,other=value.isdst?rule->standard_offset:rule->daylight_offset;
            const int64_t sec=int64_t(value.sec)+other-same;
            if(Int32(sec)){Tm retry=value;retry.sec=static_cast<int32_t>(sec);retry.isdst=!value.isdst;
              if(Twice(retry,result,normalized)){value=normalized;return {true,result,0};}
            }
          }
        }
      }
    }
    return {false,-1,query_error_?query_error_:75};
  }
  addr_t Broken(addr_t input,addr_t output,bool local){
    NativeEnvironment native;std::lock_guard<std::recursive_mutex> lock(SharedMutex());if(local)CheckEnvironment();
    int64_t seconds;recomp::ReadGuestMemory(&seconds,input,sizeof(seconds));
    Tm value;recomp::ReadGuestMemory(&value,output,sizeof(value));
    query_error_=0;const bool okay=local?Local(seconds,value):Utc(seconds,value);
    if(!okay){Error(query_error_?query_error_:75);return 0;}
    if(!local)value.zone=reinterpret_cast<addr_t>(Intern("UTC"));
    recomp::WriteGuestMemory(output,&value,sizeof(value));return output;
  }
  static std::string Number(int64_t value,unsigned width,char pad='0'){
    auto text=std::to_string(value);if(text.size()<width){
      if(value<0&&pad=='0')text="-"+std::string(width-text.size(),pad)+text.substr(1);
      else text.insert(0,width-text.size(),pad);
    }return text;
  }
  std::string ZoneName(const Tm &value){
    std::string name=value.zone?recomp::ReadGuestString(value.zone):std::string();
    if(!name.empty()||value.isdst<0)return name;
    const auto year=int64_t(value.year)+1900;if(year<1601||year>30827){Error(75);throw std::runtime_error("strftime zone year outside Windows calendar range");}
    const auto *rule=Rule(static_cast<int>(year));if(!rule){Error(query_error_);throw std::runtime_error("strftime Windows zone query failed");}
    return value.isdst?rule->daylight_name:rule->standard_name;
  }
  std::string Format(const std::string &pattern,const Tm &t,unsigned depth){
    if(depth>8)throw std::runtime_error("strftime expansion nesting exceeded");
    static const char *short_days[]={"Sun","Mon","Tue","Wed","Thu","Fri","Sat"};
    static const char *long_days[]={"Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"};
    static const char *short_months[]={"Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"};
    static const char *long_months[]={"January","February","March","April","May","June","July","August","September","October","November","December"};
    std::string out;
    const int64_t year=int64_t(t.year)+1900;
    for(size_t at=0;at<pattern.size();++at){
      if(pattern[at]!='%'){out.push_back(pattern[at]);continue;}
      if(++at==pattern.size())throw std::runtime_error("incomplete strftime conversion");
      char modifier=0;
      while(pattern[at]=='_'||pattern[at]=='-'||pattern[at]=='0'||pattern[at]=='^'||pattern[at]=='#'){modifier=pattern[at];if(++at==pattern.size())throw std::runtime_error("incomplete strftime modifier");}
      if(pattern[at]=='E'||pattern[at]=='O'){if(++at==pattern.size())throw std::runtime_error("incomplete strftime alternative");}
      const char code=pattern[at];std::string part;unsigned width=2;char pad='0';bool numeric=false;int64_t number=0;
      auto expand=[&](const char *p){return Format(p,t,depth+1);};
      switch(code){
        case '%':part="%";break;case 'n':part="\n";break;case 't':part="\t";break;
        case 'a':part=t.wday>=0&&t.wday<7?short_days[t.wday]:"?";break;
        case 'A':part=t.wday>=0&&t.wday<7?long_days[t.wday]:"?";break;
        case 'b':case 'h':part=t.mon>=0&&t.mon<12?short_months[t.mon]:"?";break;
        case 'B':part=t.mon>=0&&t.mon<12?long_months[t.mon]:"?";break;
        case 'c':part=expand("%a %b %e %H:%M:%S %Y");break;
        case 'x':case 'D':part=expand("%m/%d/%y");break;
        case 'X':case 'T':part=expand("%H:%M:%S");break;
        case 'r':part=expand("%I:%M:%S %p");break;
        case 'R':part=expand("%H:%M");break;
        case 'F':part=expand("%Y-%m-%d");break;
        case 'p':case 'P':part=t.hour<12?"AM":"PM";if(code=='P')part=t.hour<12?"am":"pm";break;
        case 'C':number=year/100;numeric=true;break;
        case 'd':case 'e':number=t.mday;numeric=true;if(code=='e')pad=' ';break;
        case 'H':case 'k':number=t.hour;numeric=true;if(code=='k')pad=' ';break;
        case 'I':case 'l':number=t.hour%12;if(!number)number=12;numeric=true;if(code=='l')pad=' ';break;
        case 'j':number=int64_t(t.yday)+1;width=3;numeric=true;break;
        case 'm':number=int64_t(t.mon)+1;numeric=true;break;
        case 'M':number=t.min;numeric=true;break;
        case 'S':number=t.sec;numeric=true;break;
        case 'u':number=t.wday?t.wday:7;width=1;numeric=true;break;
        case 'w':number=t.wday;width=1;numeric=true;break;
        case 'U':number=(t.yday+7-t.wday)/7;numeric=true;break;
        case 'W':number=(t.yday+7-(t.wday?t.wday-1:6))/7;numeric=true;break;
        case 'y':number=year%100;if(number<0)number=-number;numeric=true;break;
        case 'Y':number=year;width=4;numeric=true;break;
        case 'V':case 'g':case 'G':{
          const auto day=Days(year,1,1)+t.yday;const auto weekday=t.wday?t.wday:7;const auto thursday=day+4-weekday;
          int64_t iso_year;unsigned month,dom;Civil(thursday,iso_year,month,dom);
          if(code=='V')number=(thursday-Days(iso_year,1,1))/7+1;
          else if(code=='G'){number=iso_year;width=4;}else{number=iso_year%100;if(number<0)number=-number;}
          numeric=true;break;
        }
        case 'z':{
          if(t.isdst<0)break;
          const auto magnitude=t.gmtoff<0?uint64_t(-(t.gmtoff+1))+1:uint64_t(t.gmtoff);
          part=t.gmtoff<0?"-":"+";part+=Number(static_cast<int64_t>(magnitude/3600),2)+Number(static_cast<int64_t>(magnitude/60%60),2);break;
        }
        case 'Z':part=ZoneName(t);break;
        case 's':{Tm copy=t;auto result=Resolve(copy);if(!result.ok)Error(result.error?result.error:75);part=std::to_string(result.ok?result.value:-1);break;}
        default:throw std::runtime_error(std::string("unsupported strftime conversion: %")+code);
      }
      if(numeric){if(modifier=='_')pad=' ';else if(modifier=='-')width=0;else if(modifier=='0')pad='0';part=Number(number,width,pad);}
      if(modifier=='^')for(char &c:part)if(c>='a'&&c<='z')c=static_cast<char>(c-'a'+'A');
      if(modifier=='#')for(char &c:part){if(c>='A'&&c<='Z')c=static_cast<char>(c-'A'+'a');else if(c>='a'&&c<='z')c=static_cast<char>(c-'a'+'A');}
      out+=part;
    }
    return out;
  }
};
}  // namespace bunker::windows::libc_calendar
