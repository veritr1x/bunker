#include "package_test_session.h"
#include <functional>
int main(){try{
 unsigned checks=0;auto check=[&](bool value,const char *why){if(!value)throw std::runtime_error(why);++checks;};
 elf_image image{};check(!elf_load(PACKAGE_IMAGE,0x74000000,nullptr,&image),"actual NDK reference-array result fixture loads");Session h(image);
 h.host.DefineClass("java/io/File");h.host.DefineClass("ChildFile",{},"java/io/File");h.host.DefineClass("ArrayResultProbe",{{"bound","()[Ljava/io/File;",true}});
 auto owner=h.find("ArrayResultProbe"),receiver=h.host.NewInstance("ArrayResultProbe"),file_class=h.find("java/io/File"),child_class=h.find("ChildFile"),object_class=h.find("java/lang/Object"),string_class=h.find("java/lang/String");
 auto make=[&](addr_t component,addr_t value=0){return h.call(172,2,component,value);};
 auto same=[&](addr_t a,addr_t b){return h.call(24,a,b)!=0;};
 auto error=[&](const char *name){check(h.host.PendingException().find(name)!=std::string::npos,"expected Java exception category");h.host.ClearException();};
 auto weak=[&](addr_t value){return h.call(226,value);};
 auto run=[&](addr_t object,addr_t method,int mode,bool stat,addr_t input=0,bool one=false){struct Guard {uint64_t before=0x1122334455667788ULL,value=0,after=0x8877665544332211ULL;} g;
   auto result=one?h.run("array_result_one",{h.host.EnvAddress(),object,method,input,static_cast<addr_t>(mode),stat,reinterpret_cast<addr_t>(&g.value)}):h.run("array_result_zero",{h.host.EnvAddress(),object,method,static_cast<addr_t>(mode),stat,reinterpret_cast<addr_t>(&g.value)});
   check(g.before==0x1122334455667788ULL&&g.after==0x8877665544332211ULL&&g.value==0x123456789abcdef0ULL,"NDK direct/V/A result transport preserves jvalue and output canaries");return result;};
 auto method=[&](const char *name,const char *sig,bool stat=false){return h.call(stat?113:33,owner,reinterpret_cast<addr_t>(name),reinterpret_cast<addr_t>(sig));};
 int behavior=0;addr_t raw=0,array_weak=0,element_weak=0,temp_weak=0,cleared=0;
 auto body=[&](addr_t borrowed){
   check(h.call(232,borrowed)==1,"callback receiver is an owned borrowed local");
   check(h.call(19,16)==0,"callback may create a nested user frame");
   auto element=h.host.NewInstance(behavior==4?"ChildFile":"java/io/File");element_weak=weak(element);
   auto temp=h.host.NewString(u"callback-only temporary");temp_weak=weak(temp);
   raw=make(behavior==2?string_class:behavior==4?child_class:behavior==5?object_class:file_class,behavior==2?temp:element);array_weak=weak(raw);
   if(behavior==1)return addr_t(0);
   if(behavior==3)return element;
   if(behavior==6)return cleared;
   if(behavior==7){h.host.DeleteLocalReference(raw);return raw;}
   if(behavior==8)h.host.ThrowException("java/lang/IllegalStateException",u"array-result callback exception");
   return raw;
 };
 h.host.DefineObjectMethod("ArrayResultProbe","files","()[Ljava/io/File;",body);
 h.host.DefineStaticObjectMethod("ArrayResultProbe","staticFiles","()[Ljava/io/File;",[&](addr_t r,const bunker::jni::Host::MethodArguments&){return body(r);});
 h.host.BindStaticObjectMethod("ArrayResultProbe","bound","()[Ljava/io/File;",[&](addr_t r,const bunker::jni::Host::MethodArguments&){return body(r);});
 auto dead=h.host.NewInstance("java/io/File");cleared=weak(dead);h.host.DeleteLocalReference(dead);check(same(cleared,0),"cleared weak test starts genuinely unrooted");
 for(int profile=0;profile<3;++profile){bool stat=profile!=0;auto id=method(profile==0?"files":profile==1?"staticFiles":"bound","()[Ljava/io/File;",stat);check(id!=0,"array return method declaration resolves");
   for(int mode=0;mode<4;++mode)for(behavior=0;behavior<=8;++behavior){auto result=run(stat?owner:receiver,id,mode,stat);
     check(same(temp_weak,0),"callback-only temporary dies before return");check(!h.call(232,raw),"callback array handle expires at owned-frame boundary");
     if(behavior==0||behavior==4){check(result&&h.call(232,result)==1&&same(result,array_weak),"typed/covariant array result promotes one independent caller local");auto actual=h.call(31,result);check(h.host.ClassNameValue(actual)==std::optional<std::string>(behavior==4?"[LChildFile;":"[Ljava/io/File;"),"promoted result retains exact runtime array class");h.host.DeleteLocalReference(actual);
       check(h.call(171,result)==2&&!same(element_weak,0),"array strongly retains its initialized elements");auto first=h.call(173,result,0);check(same(first,element_weak),"returned array exposes actual element identity");h.host.DeleteLocalReference(first);h.host.DeleteLocalReference(result);
     }else if(behavior==1||behavior==6)check(!result&&h.host.PendingException().empty(),"null and cleared weak array results remain null without exception");
     else{check(!result,"invalid or exceptional array result never escapes");error(behavior==8?"IllegalStateException":"IllegalArgumentException");}
     check(same(array_weak,0)&&same(element_weak,0),"callback frame or promoted array leaves no hidden element/result root");h.call(227,array_weak);h.call(227,element_weak);h.call(227,temp_weak);
   }
 }
 auto text=h.host.NewString(u"covariant"),strings=make(string_class,text),files=make(file_class),children=make(child_class),objects=make(object_class),nested=make(h.find("[Ljava/io/File;"),files);
 for(auto definition:std::vector<std::pair<const char*,const char*>>{{"objects","[Ljava/lang/Object;"},{"typed","[Ljava/io/File;"},{"nested","[[Ljava/io/File;"},{"ordinary","Ljava/lang/Object;"},{"ordinaryFile","Ljava/io/File;"}}){
   auto sig=std::string("(Ljava/lang/Object;)")+definition.second;
   auto echo=[&](addr_t,const bunker::jni::Host::MethodArguments &args){check(!args[0]||h.call(232,args[0])==1,"reference argument is borrowed into array-result callback frame");return args[0];};
   h.host.DefineObjectMethod("ArrayResultProbe",definition.first,sig,echo);h.host.DefineStaticObjectMethod("ArrayResultProbe",std::string("static_")+definition.first,sig,echo);
   for(bool stat:{false,true}){auto name=(stat?std::string("static_"):std::string())+definition.first;auto id=method(name.c_str(),sig.c_str(),stat);
     for(int mode=0;mode<4;++mode)for(auto input:{addr_t(0),strings,files,children,objects,nested,text}){
       bool accepted=!input||std::string(definition.first)=="ordinary"||(std::string(definition.first)=="objects"&&input!=text)||(std::string(definition.first)=="typed"&&(input==files||input==children))||(std::string(definition.first)=="nested"&&input==nested);
       auto result=run(stat?owner:receiver,id,mode,stat,input,true);
       if(accepted){check(same(result,input)&&h.host.PendingException().empty(),"reference-array covariance and ordinary Object returns retain identity");if(result){check(result!=input&&h.call(232,result)==1,"borrowed return gets a fresh caller-local handle");h.host.DeleteLocalReference(result);}}
       else{check(!result,"wrong array rank/component or scalar return rejected");error("IllegalArgumentException");}
       check(h.call(232,input)==(input?1:0),"return validation never consumes caller input");
     }
   }
 }
 behavior=0;auto files_id=method("files","()[Ljava/io/File;");check(!h.run("package_empty",{h.host.EnvAddress(),receiver,files_id,0}),"array result cannot use boolean JNI family");error("IllegalArgumentException");check(h.run("package_void",{h.host.EnvAddress(),receiver,files_id,0})==0x1234,"void wrapper completes transport");error("IllegalArgumentException");
 unsigned rejected=0;for(auto signature:std::vector<std::string>{"()[I","()[[I","()[D","()[V","()[LUnknown;","()[Ljava/io/File","()[Ljava/io/File;;","()[","()D","()F","()I","(DDDD)[Ljava/io/File;","(IIII)[Ljava/io/File;",std::string("()")+std::string(256,'[')+"Ljava/io/File;"})for(bool convenience:{false,true}){bool caught=false;try{auto name="invalid"+std::to_string(rejected++);if(convenience)h.host.DefineObjectMethod("ArrayResultProbe",name,signature,[](addr_t){return addr_t(0);});else h.host.DefineObjectMethod("ArrayResultProbe",name,signature,[](addr_t,const bunker::jni::Host::MethodArguments&){return addr_t(0);});}catch(const std::invalid_argument&){caught=true;}check(caught,"invalid/primitive/FP/over-limit descriptor remains unsupported");}
 bool ordinary_guard=false;try{h.host.DefineObjectMethod("ArrayResultProbe","badObject","()LUnknown;",[](addr_t){return addr_t(0);});}catch(const std::invalid_argument&){ordinary_guard=true;}check(ordinary_guard,"ordinary Lobject declaration still requires known exact class");
 auto max_descriptor=std::string(255,'[')+"Ljava/io/File;";h.host.DefineObjectMethod("ArrayResultProbe","rank255","()"+max_descriptor,[](addr_t){return addr_t(0);});check(!run(receiver,method("rank255",("()"+max_descriptor).c_str()),0,false)&&h.host.PendingException().empty(),"maximum supported reference-array rank retains null return semantics");
 check(h.host.PendingException().empty(),"all array-result callbacks leave clean JNI state");
 std::printf("JNI reference-array results: %u checks; actual NDK instance/static direct/V/A and stack-V, typed/null/covariant results, owned-frame lifetime and preserved rejection guards\n",checks);
}catch(const std::exception &error){std::fprintf(stderr,"JNI array result: %s\n",error.what());return 1;}}
