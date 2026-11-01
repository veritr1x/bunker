#include "android_assets.h"
#include "unicode.h"
#include "../fastaes/elfload.h"
#include "traces.h"
#include "asset_java_sample.h"
#include <array>
#include <cstdio>
#include <stdexcept>
#include <thread>
#include <zlib.h>
struct AssetHost{
  recomp::Runtime runtime;bunker::jni::Host host{[](addr_t){return false;}};elf_image &image;alignas(16)std::array<uint8_t,65536> stack{};
  explicit AssetHost(elf_image &i):image(i){host.Install(runtime);runtime.AddTraces(kTraces,std::size(kTraces));}
  addr_t call(size_t slot,addr_t a=0,addr_t b=0,addr_t c=0){State s{};s.gpr.x0.qword=host.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;host.InvokeEnv(slot,s);return s.gpr.x0.qword;}
  addr_t find(const char *s){return call(6,reinterpret_cast<addr_t>(s));}
  addr_t method(const char *owner,const char *name,const char *sig){return call(33,find(owner),reinterpret_cast<addr_t>(name),reinterpret_cast<addr_t>(sig));}
  addr_t run(const char *name,std::initializer_list<addr_t> args){State s{};Reg GPR::*r[]={&GPR::x0,&GPR::x1,&GPR::x2,&GPR::x3,&GPR::x4,&GPR::x5};size_t i=0;for(auto a:args)(s.gpr.*r[i++]).qword=a;s.gpr.sp.qword=reinterpret_cast<addr_t>(stack.data()+stack.size());s.gpr.x30.qword=0xfeedffff;runtime.Run(s,reinterpret_cast<addr_t>(elf_symbol(&image,name)));if(s.gpr.pc.qword!=0xfeedffff||s.gpr.sp.qword!=reinterpret_cast<addr_t>(stack.data()+stack.size()))throw std::runtime_error("NDK asset caller PC/SP corrupted");return s.gpr.x0.qword;}
  addr_t one(addr_t o,addr_t m,addr_t a,addr_t mode){return run("guest_context_one",{host.EnvAddress(),o,m,a,mode});}
  addr_t zero(addr_t o,addr_t m,addr_t mode){return run("guest_context_zero",{host.EnvAddress(),o,m,mode});}
  addr_t construct(addr_t c,addr_t m,addr_t src,addr_t encoding,addr_t mode){return run("guest_context_construct",{host.EnvAddress(),c,m,src,encoding,mode});}
  addr_t close(addr_t o,addr_t m,addr_t mode){return run("guest_context_close",{host.EnvAddress(),o,m,mode});}
  std::u16string text(addr_t s){auto v=host.StringValue(s);if(!v)throw std::runtime_error("expected string token");return *v;}
};
int main(int argc,char **argv){
  if(argc!=3)return 2;using namespace bunker::windows;unsigned checks=0;auto check=[&](bool b,const char *why){if(!b)throw std::runtime_error(why);++checks;};
  elf_image image{};check(!elf_load(ASSET_CONTEXT_IMAGE,0x73000000,nullptr,&image),"actual NDK asset caller image");
  AssetHost game(image);auto manager=CreateJavaAssets(game.host,std::make_shared<ApkAssets>(argv[1]));
  auto open=game.method("android/content/res/AssetManager","open","(Ljava/lang/String;)Ljava/io/InputStream;"),scanner_class=game.find("java/util/Scanner"),constructor=game.method("java/util/Scanner","<init>","(Ljava/io/InputStream;Ljava/lang/String;)V"),delimiter=game.method("java/util/Scanner","useDelimiter","(Ljava/lang/String;)Ljava/util/Scanner;"),next=game.method("java/util/Scanner","next","()Ljava/lang/String;"),close=game.method("java/util/Scanner","close","()V"),stream_close=game.method("java/io/InputStream","close","()V");
  for(addr_t mode=0;mode<3;++mode){
    game.call(19,64);auto stream=game.one(manager,open,game.host.NewString(u"bin/Data/boot.config"),mode);check(stream&&game.call(32,stream,game.find("java/io/InputStream")),"actual APK open returns a typed initialized stream");
    auto weak=game.call(226,stream),scanner=game.construct(scanner_class,constructor,stream,game.host.NewString(u"UTF-8"),mode);game.host.DeleteLocalReference(stream);
    check(scanner&&!game.call(24,weak,0),"Scanner retains its source object independently of caller reference");
    auto result=game.one(scanner,delimiter,game.host.NewString(u"\\z"),mode);check(result&&result!=scanner&&game.call(24,result,scanner)&&game.call(232,result)==1,"useDelimiter returns a fresh caller-local alias");game.host.DeleteLocalReference(result);
    auto token=game.zero(scanner,next,mode);check(game.text(token)==kBootText,"native Scanner result matches every original boot.config UTF16 unit");
    auto data=game.call(169,token);auto length=game.call(168,token);check(length==kBootBytes&&crc32(0,reinterpret_cast<const Bytef*>(data),length)==kBootCrc,"actual APK stream token byte count and CRC match independent ZIP reference");game.call(170,token,data);
    check(!game.zero(scanner,next,mode)&&game.host.PendingException().find("NoSuchElementException")!=std::string::npos,"second whole-stream token reaches EOF");game.host.ClearException();
    check(game.close(scanner,close,mode)==0x1234&&game.close(scanner,close,mode)==0x1234,"Scanner close returns normally and is idempotent");
    check(!game.zero(scanner,next,mode)&&game.host.PendingException().find("IllegalStateException")!=std::string::npos,"closed Scanner rejects next");game.host.ClearException();
    check(game.text(token)==kBootText,"closing source preserves copied token");game.call(20);game.call(227,weak);
  }
  for(auto bad:{u"missing",u"../bin/Data/boot.config",u"/bin/Data/boot.config",u"bin\\Data\\boot.config",u""})check(!game.one(manager,open,game.host.NewString(bad),0)&&game.host.PendingException().find("FileNotFoundException")!=std::string::npos,"missing/invalid asset names fail explicitly"),game.host.ClearException();
  check(!game.one(manager,open,0,1)&&game.host.PendingException().find("NullPointerException")!=std::string::npos,"null asset name");game.host.ClearException();
  check(!game.one(game.host.NewInstance("android/content/res/AssetManager"),open,game.host.NewString(u"x"),2)&&game.host.PendingException().find("UnsupportedOperationException")!=std::string::npos,"uninitialized AssetManager cannot fake a stream");game.host.ClearException();
  AssetHost fixtures(image);auto assets=CreateJavaAssets(fixtures.host,std::make_shared<ApkAssets>(argv[2]));
  auto f_open=fixtures.method("android/content/res/AssetManager","open","(Ljava/lang/String;)Ljava/io/InputStream;"),f_class=fixtures.find("java/util/Scanner"),f_ctor=fixtures.method("java/util/Scanner","<init>","(Ljava/io/InputStream;Ljava/lang/String;)V"),f_delim=fixtures.method("java/util/Scanner","useDelimiter","(Ljava/lang/String;)Ljava/util/Scanner;"),f_next=fixtures.method("java/util/Scanner","next","()Ljava/lang/String;"),f_close=fixtures.method("java/util/Scanner","close","()V"),f_stream_close=fixtures.method("java/io/InputStream","close","()V");
  auto stream=fixtures.one(assets,f_open,fixtures.host.NewString(u"unicode.txt"),0),encoding=fixtures.host.NewString(u"utf8");
  for(addr_t mode=0;mode<3;++mode){
    auto current=fixtures.one(assets,f_open,fixtures.host.NewString(u"unicode.txt"),mode),scanner=fixtures.construct(f_class,f_ctor,current,encoding,mode);
    check(scanner&&!fixtures.zero(scanner,f_next,mode)&&fixtures.host.PendingException().find("UnsupportedOperationException")!=std::string::npos,"unimplemented default Scanner delimiter is explicit");fixtures.host.ClearException();
    check(!fixtures.one(scanner,f_delim,fixtures.host.NewString(u","),mode)&&fixtures.host.PendingException().find("UnsupportedOperationException")!=std::string::npos,"unimplemented regex is rejected without success");fixtures.host.ClearException();
    fixtures.one(scanner,f_delim,fixtures.host.NewString(u"\\z"),mode);auto token=fixtures.zero(scanner,f_next,mode);
    check(fixtures.text(token)==std::u16string({0xfeff,u'A',0,0xe9,0x2603,0xd83d,0xde00,u'\n'}),"UTF8 decoding preserves BOM, NUL, BMP/supplementary units and trailing newline");
    auto empty=fixtures.one(assets,f_open,fixtures.host.NewString(u"empty.txt"),mode),empty_scanner=fixtures.construct(f_class,f_ctor,empty,encoding,mode);fixtures.one(empty_scanner,f_delim,fixtures.host.NewString(u"\\z"),mode);check(!fixtures.zero(empty_scanner,f_next,mode)&&fixtures.host.PendingException().find("NoSuchElementException")!=std::string::npos,"empty asset has no Scanner token");fixtures.host.ClearException();
    auto large=fixtures.one(assets,f_open,fixtures.host.NewString(u"large.txt"),mode),large_scanner=fixtures.construct(f_class,f_ctor,large,encoding,mode);fixtures.one(large_scanner,f_delim,fixtures.host.NewString(u"\\z"),mode);check(fixtures.text(fixtures.zero(large_scanner,f_next,mode))==std::u16string(4097,0x4e2d),"deflated UTF8 stream exceeds default Scanner buffer");
    check(!fixtures.construct(f_class,f_ctor,0,encoding,mode)&&fixtures.host.PendingException().find("NullPointerException")!=std::string::npos,"null Scanner source");fixtures.host.ClearException();
    check(!fixtures.construct(f_class,f_ctor,current,0,mode)&&fixtures.host.PendingException().find("NullPointerException")!=std::string::npos,"null Scanner charset");fixtures.host.ClearException();
    check(!fixtures.construct(f_class,f_ctor,current,fixtures.host.NewString(u"UTF-16"),mode)&&fixtures.host.PendingException().find("UnsupportedOperationException")!=std::string::npos,"unevidenced charsets remain unsupported");fixtures.host.ClearException();
    check(!fixtures.construct(f_class,f_ctor,encoding,encoding,mode)&&fixtures.host.PendingException().find("IllegalArgumentException")!=std::string::npos,"constructor argument type is checked");fixtures.host.ClearException();
  }
  auto malformed=fixtures.one(assets,f_open,fixtures.host.NewString(u"malformed.txt"),0),bad_scanner=fixtures.construct(f_class,f_ctor,malformed,encoding,1);fixtures.one(bad_scanner,f_delim,fixtures.host.NewString(u"\\z"),2);check(!fixtures.zero(bad_scanner,f_next,0)&&fixtures.host.PendingException().find("UnsupportedOperationException")!=std::string::npos,"unsupported malformed UTF8 replacement policy fails explicitly");fixtures.host.ClearException();
  auto scanner=fixtures.construct(f_class,f_ctor,stream,encoding,0);fixtures.one(scanner,f_delim,fixtures.host.NewString(u"\\z"),0);check(fixtures.close(stream,f_stream_close,1)==0x1234&&!fixtures.zero(scanner,f_next,1)&&fixtures.host.PendingException().find("NoSuchElementException")!=std::string::npos,"closing the actual source prevents new Scanner input");fixtures.host.ClearException();
  fixtures.close(scanner,f_close,2);
  fixtures.host.DefineClass("test/JoinConstructor");fixtures.host.DefineConstructor("test/JoinConstructor","()V",[&](const bunker::jni::Host::MethodArguments&){std::thread worker([&]{State s{};addr_t env=0;s.gpr.x0.qword=fixtures.host.VmAddress();s.gpr.x1.qword=reinterpret_cast<addr_t>(&env);fixtures.host.InvokeVm(4,s);s={};s.gpr.x0.qword=fixtures.host.VmAddress();fixtures.host.InvokeVm(5,s);});worker.join();return fixtures.host.NewHostInstance("test/JoinConstructor",std::make_shared<int>(1));});
  auto join_ctor=fixtures.method("test/JoinConstructor","<init>","()V");check(fixtures.call(28,fixtures.find("test/JoinConstructor"),join_ctor)!=0,"constructor callbacks can join another JNI thread without provider-lock deadlock");
  std::printf("Real APK AssetManager/Scanner: %u checks passed; %u-byte boot.config CRC=%08x; actual NDK constructor/object/void direct,V,A\n",checks,kBootBytes,kBootCrc);
}
