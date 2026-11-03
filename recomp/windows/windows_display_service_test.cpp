#include "windows_display_service.h"
#include "android_context.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <windows.h>
#include <array>
#include <cerrno>
#include <cfenv>
#include <cstdio>
#include <cstring>
#include <memory>
#include <stdexcept>
struct Test {
 recomp::Runtime runtime;bunker::jni::Host host{[](addr_t){return false;}};elf_image image{};unsigned checks=0;
 Test(){if(elf_load(DISPLAY_IMAGE,0x74000000,nullptr,&image))throw std::runtime_error("NDK fixture load");host.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));}
 void check(bool x,const char*why){if(!x)throw std::runtime_error(why);++checks;}
 addr_t call(size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){State s{};s.gpr.x0.qword=host.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;host.InvokeEnv(slot,s);return s.gpr.x0.qword;}
 addr_t run(const char*name,std::initializer_list<addr_t>args){alignas(16)std::array<uint8_t,65536>stack{};State s{};Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5,&GPR::x6};unsigned i=0;for(auto x:args)(s.gpr.*r[i++]).qword=x;auto entry=reinterpret_cast<addr_t>(elf_symbol(&image,name));if(!entry)throw std::runtime_error("NDK export missing");s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;runtime.Run(s,entry);check(s.gpr.pc.qword==0xfeedffff&&s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size()),"NDK PC/SP");return s.gpr.x0.qword;}
};
int main(){try{
 Test h;bunker::windows::AndroidContextConfig config{};config.package_name=u"bunker.display.test";config.source_dir=u"/data/app/test.apk";config.native_library_dir=u"/data/app/lib";config.data_dir=u"/data/user/0/test";config.target_sdk=33;bunker::windows::AndroidContext context(h.host,config);
 unsigned observed=0;bunker::windows::WindowsDisplayService service(h.host,[&](const auto&i){++observed;std::printf("DISPLAY id=%d size=%dx%d rotation=%d winScale=%u winDpi=%ux%u androidDpi=%d refresh=%u/%u appOffsetPolicy=%lld nominalBudgetPolicy=%lld SDR=true\n",i.id,i.width,i.height,i.rotation,i.windows_scale_percent,i.windows_effective_dpi_x,i.windows_effective_dpi_y,i.density_dpi,i.refresh_numerator,i.refresh_denominator,(long long)i.app_vsync_offset_ns,(long long)i.nominal_presentation_budget_ns);});
 errno=EDOM;SetLastError(0x12345678);std::fesetround(FE_DOWNWARD);auto inventory=service.Displays();h.check(errno==EDOM&&GetLastError()==0x12345678&&std::fegetround()==FE_DOWNWARD,"native query environment preserved");std::fesetround(FE_TONEAREST);h.check(!inventory.empty(),"actual Windows logical displays available for positive gate");
 std::feclearexcept(FE_ALL_EXCEPT);std::feraiseexcept(FE_INVALID|FE_INEXACT);int before_exceptions=std::fetestexcept(FE_ALL_EXCEPT);std::fesetround(FE_UPWARD);auto second=service.Displays();h.check(std::fetestexcept(FE_ALL_EXCEPT)==before_exceptions&&std::fegetround()==FE_UPWARD,"metadata query preserves raised FP flags and rounding");h.check(second.size()==inventory.size()&&second[0].refresh_bits==inventory[0].refresh_bits,"refresh bits independent of caller rounding");std::feclearexcept(FE_ALL_EXCEPT);std::fesetround(FE_TONEAREST);
 auto activity=context.Activity(),key=h.host.NewString(u"display");auto manager=h.run("wd_service",{h.host.EnvAddress(),activity,key});h.check(manager&&h.host.PendingException().empty(),"real Context service object");h.check(!h.run("wd_service",{h.host.EnvAddress(),activity,0})&&h.host.PendingException().empty(),"null service name follows Android13 registry");
 auto again=h.run("wd_service",{h.host.EnvAddress(),activity,key});h.check(h.call(24,manager,again),"service identity with fresh local");h.check(!h.run("wd_get",{h.host.EnvAddress(),manager,0xffffffff,0})&&!h.run("wd_get",{h.host.EnvAddress(),manager,INT32_MAX,2})&&h.host.PendingException().empty(),"missing IDs truthful null");
 auto unsupported=h.host.NewString(u"location");h.check(!h.run("wd_service",{h.host.EnvAddress(),activity,unsupported})&&h.host.PendingException().find("UnsupportedOperationException")!=std::string::npos,"unsupported service is a Java boundary, not native abort");auto pending=h.host.PendingException();h.check(!h.run("wd_service",{h.host.EnvAddress(),activity,key})&&h.host.PendingException()==pending,"pending unsupported-service exception preserved");h.host.ClearException();h.host.DeleteLocalReference(unsupported);
 for(const auto &info:inventory){
  DEVMODEW native{};native.dmSize=sizeof(native);std::wstring name(info.device.begin(),info.device.end());h.check(EnumDisplaySettingsW(name.c_str(),ENUM_CURRENT_SETTINGS,&native)!=FALSE,"independent native mode query");h.check(info.width==static_cast<int32_t>(native.dmPelsWidth)&&info.height==static_cast<int32_t>(native.dmPelsHeight),"independent native dimensions");h.check(info.rotation==static_cast<int32_t>(native.dmDisplayOrientation),"native rotation quarter turns");h.check(info.density_dpi==static_cast<int32_t>((uint64_t(info.windows_scale_percent)*160+50)/100),"Windows UI scale to Android density policy");
  auto display=h.run("wd_get",{h.host.EnvAddress(),manager,static_cast<uint32_t>(info.id),0});h.check(display!=0,"native enumerated display JNI object");
  for(unsigned form=0;form<3;++form){auto object=h.run("wd_get",{h.host.EnvAddress(),manager,static_cast<uint32_t>(info.id),form});h.check(object&&h.call(24,object,display),"getDisplay direct/V/A ownership");
   for(auto pair:{std::pair<const char*,int32_t>{"getDisplayId",info.id},{"getRotation",info.rotation},{"getWidth",info.width},{"getHeight",info.height}})h.check(static_cast<int32_t>(h.run("wd_int",{h.host.EnvAddress(),display,reinterpret_cast<addr_t>(pair.first),form}))==pair.second,"actual NDK integer display value");
   h.check(static_cast<uint32_t>(h.run("wd_float",{h.host.EnvAddress(),display,form}))==info.refresh_bits,"actual refresh float S0 bits");h.check(!h.run("wd_bool",{h.host.EnvAddress(),display,form}),"actual SDR renderer capability policy");
   h.check(h.run("wd_long",{h.host.EnvAddress(),display,reinterpret_cast<addr_t>("getAppVsyncOffsetNanos"),form})==0,"actual long no phase-advance policy");h.check(h.run("wd_long",{h.host.EnvAddress(),display,reinterpret_cast<addr_t>("getPresentationDeadlineNanos"),form})==static_cast<uint64_t>(info.nominal_presentation_budget_ns),"actual long observed-refresh nominal period policy");h.host.DeleteLocalReference(object);
  }
  auto metrics=h.run("wd_metrics",{h.host.EnvAddress()});h.check(metrics!=0,"real DisplayMetrics constructor");for(const char *field:{"widthPixels","heightPixels","densityDpi"})h.check(h.run("wd_field",{h.host.EnvAddress(),metrics,reinterpret_cast<addr_t>(field)})==0,"Android13 empty constructor zero fields");h.run("wd_fill",{h.host.EnvAddress(),display,metrics});
  for(auto pair:{std::pair<const char*,int32_t>{"widthPixels",info.width},{"heightPixels",info.height},{"densityDpi",info.density_dpi}})h.check(static_cast<int32_t>(h.run("wd_field",{h.host.EnvAddress(),metrics,reinterpret_cast<addr_t>(pair.first)}))==pair.second,"real JNI metrics field");
  h.run("wd_fill",{h.host.EnvAddress(),display,0});h.check(h.host.PendingException().find("NullPointerException")!=std::string::npos,"null metrics exception");h.host.ClearException();h.host.DeleteLocalReference(metrics);h.host.DeleteLocalReference(display);
 }
 h.check(observed>0&&h.host.PendingException().empty(),"observed genuine display queries without hidden exception");std::printf("Windows display JNI: %u checks, %zu native logical displays; constructor methods direct/V/A, actual native mode and explicit SDR/scheduling policy\n",h.checks,inventory.size());return 0;
 }catch(const std::exception&e){std::fprintf(stderr,"WINDOWS-DISPLAY-FAIL %s\n",e.what());return 1;}}
