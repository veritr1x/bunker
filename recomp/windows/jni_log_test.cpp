#include "jni_host.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include <array>
#include <cstdio>
#include <stdexcept>
int main(){try{
  unsigned checks=0,calls=0;auto check=[&](bool value,const char*why){if(!value)throw std::runtime_error(why);++checks;};
  elf_image image{};check(!elf_load(LOG_GUEST,0x64000000,nullptr,&image),"actual NDK caller loads");
  bunker::jni::Host host([](addr_t){return false;});recomp::Runtime runtime;host.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));
  auto invoke=[&](size_t slot,addr_t a=0){State s{};s.gpr.x0.qword=host.EnvAddress();s.gpr.x1.qword=a;host.InvokeEnv(slot,s);return s.gpr.x0.qword;};
  auto run=[&](const char*name,addr_t exception,unsigned mode){alignas(16)std::array<uint8_t,65536> stack{};State s{};s.gpr.x0.qword=host.EnvAddress();s.gpr.x1.qword=exception;s.gpr.x2.qword=mode;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;
    runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,name)));++calls;check(s.gpr.sp.qword==reinterpret_cast<addr_t>(stack.data()+stack.size())&&s.gpr.pc.qword==0xfeedffff,"actual NDK caller restores SP and returns");return s.gpr.x0.qword;};
  auto raised=[&](const char*type,const std::optional<std::u16string>&message){if(message)host.ThrowException(type,*message);else host.ThrowException(type);auto exception=invoke(15);check(exception!=0,"ExceptionOccurred retains actual Throwable");host.ClearException();return exception;};
  auto expect=[&](addr_t exception,const std::u16string&expected){for(unsigned mode=0;mode<3;++mode){auto result=run("log_trace",exception,mode);check(host.PendingException().empty()&&host.StringValue(result)==std::optional<std::u16string>(expected),"NDK direct/V/A returns actual exception text");auto weak=invoke(226,result);host.DeleteLocalReference(result);check(invoke(24,weak)==1,"formatter result has no hidden callback-frame root");invoke(227,weak);}};
  expect(0,u"");
  std::u16string unicode=u"Missing \U0001f422";unicode.push_back(0);unicode+=u" detail";
  auto exception=raised("java/lang/NoClassDefFoundError",unicode);expect(exception,std::u16string(u"java.lang.NoClassDefFoundError: ")+unicode+u"\n");host.DeleteLocalReference(exception);
  exception=raised("java/lang/RuntimeException",std::nullopt);expect(exception,u"java.lang.RuntimeException\n");host.DeleteLocalReference(exception);
  exception=raised("java/lang/RuntimeException",std::u16string());expect(exception,u"java.lang.RuntimeException: \n");host.DeleteLocalReference(exception);
  host.DefineClass("java/net/UnknownHostException",{},"java/io/IOException",true);host.DefineClass("HostNotFound",{},"java/net/UnknownHostException",true);
  exception=raised("HostNotFound",u"actual lookup failed");expect(exception,u"");host.DeleteLocalReference(exception);
  unsigned overrides=0;host.DefineClass("DiagnosticChild",{},"java/lang/Exception",true);host.DefineObjectMethod("DiagnosticChild","getLocalizedMessage","()Ljava/lang/String;",[&](addr_t){++overrides;return host.NewString(u"localized");});
  exception=raised("DiagnosticChild",u"raw");expect(exception,u"DiagnosticChild: localized\n");check(overrides==3,"formatter uses actual virtual Throwable.toString path");host.DeleteLocalReference(exception);
  for(unsigned mode=0;mode<3;++mode){auto result=run("log_missing_class",mode,0);check(host.PendingException().empty()&&host.StringValue(result)==std::optional<std::u16string>(u"java.lang.NoClassDefFoundError: missing/ActualClass\n"),"FindClass failure survives ExceptionOccurred/Clear and diagnostic formatting");host.DeleteLocalReference(result);}
  for(auto value:{host.NewInstance("java/lang/Throwable"),host.NewString(u"wrong type")}){check(!run("log_trace",value,2)&&!host.PendingException().empty(),"uninitialized/wrong type input rejected");host.ClearException();host.DeleteLocalReference(value);}
  host.DefineClass("UnqualifiedCause",{{"getCause","()Ljava/lang/Throwable;"}},"java/lang/Exception",true);exception=raised("UnqualifiedCause",u"cause not implemented");check(!run("log_trace",exception,2)&&host.PendingException().find("UnsupportedOperationException")!=std::string::npos,"unknown cause behavior is not silently omitted");host.ClearException();host.DeleteLocalReference(exception);
  std::printf("JNI-LOG-PASS checks=%u NDK_calls=%u actual_virtual_overrides=%u\n",checks,calls,overrides);
}catch(const std::exception&e){std::fprintf(stderr,"JNI log test: %s\n",e.what());return 1;}}
