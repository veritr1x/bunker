#include "android_assets.h"
#include "unicode.h"
#include <algorithm>
#include <mutex>
namespace bunker::windows {
namespace {
struct Manager {std::shared_ptr<ApkAssets> reader;};
struct Stream {std::mutex mutex;std::vector<uint8_t> bytes;size_t position=0;bool closed=false;};
struct Scanner {std::mutex mutex;jni::Host::ObjectValue source;std::shared_ptr<Stream> stream;bool whole=false,closed=false;};
bool Charset(const std::u16string &name){auto n=name;for(auto &c:n)if(c>=u'A'&&c<=u'Z')c+=u'a'-u'A';return n==u"utf-8"||n==u"utf8";}
}
addr_t CreateJavaAssets(jni::Host &host,std::shared_ptr<ApkAssets> reader){
  host.DefineClass("java/io/IOException",{},"java/lang/Exception",true);
  host.DefineClass("java/io/FileNotFoundException",{},"java/io/IOException",true);
  host.DefineClass("java/util/NoSuchElementException",{},"java/lang/RuntimeException",true);
  host.DefineClass("java/io/InputStream",{},"java/lang/Object",true);
  host.DefineClass("android/content/res/AssetManager",{},"java/lang/Object",true);
  host.DefineClass("android/content/res/AssetManager$AssetInputStream",{},"java/io/InputStream",true);
  host.DefineClass("java/util/Scanner",{},"java/lang/Object",true);
  host.DefineObjectMethod("android/content/res/AssetManager","open","(Ljava/lang/String;)Ljava/io/InputStream;",[&host](addr_t receiver,const jni::Host::MethodArguments &args)->addr_t{
    auto manager=host.ReadHostState<Manager>(receiver);if(!manager)return 0;
    auto name=host.StringValue(args[0]);if(!name){if(host.PendingException().empty())host.ThrowException("java/lang/NullPointerException",u"fileName");return 0;}
    if(!manager->reader){host.ThrowException("java/lang/UnsupportedOperationException",u"AssetManager has no configured APK reader");return 0;}
    try{auto stream=std::make_shared<Stream>();stream->bytes=manager->reader->Read(Utf8(*name));return host.NewHostInstance("android/content/res/AssetManager$AssetInputStream",stream);}
    catch(const AssetError &error){host.ThrowException(error.kind==AssetError::NotFound?"java/io/FileNotFoundException":"java/io/IOException",Utf16(error.what()));return 0;}
    catch(const std::invalid_argument &){host.ThrowException("java/io/FileNotFoundException",u"asset name is not valid Unicode");return 0;}
  });
  host.DefineVoidMethod("java/io/InputStream","close","()V",[&host](addr_t receiver,const jni::Host::MethodArguments&){auto stream=host.ReadHostState<Stream>(receiver);if(stream){std::lock_guard lock(stream->mutex);stream->closed=true;}});
  host.DefineConstructor("java/util/Scanner","(Ljava/io/InputStream;Ljava/lang/String;)V",[&host](const jni::Host::MethodArguments &args)->addr_t{
    auto stream=host.ReadHostState<Stream>(args[0]);if(!stream)return 0;
    auto charset=host.StringValue(args[1]);if(!charset){if(host.PendingException().empty())host.ThrowException("java/lang/NullPointerException",u"charsetName");return 0;}
    if(!Charset(*charset)){host.ThrowException("java/lang/UnsupportedOperationException",u"Scanner adapter supports UTF-8 only");return 0;}
    auto scanner=std::make_shared<Scanner>();scanner->stream=stream;scanner->source=host.CaptureValue(args[0]);return host.NewHostInstance("java/util/Scanner",scanner);
  });
  host.DefineObjectMethod("java/util/Scanner","useDelimiter","(Ljava/lang/String;)Ljava/util/Scanner;",[&host](addr_t receiver,const jni::Host::MethodArguments &args)->addr_t{
    auto scanner=host.ReadHostState<Scanner>(receiver);if(!scanner)return 0;
    auto delimiter=host.StringValue(args[0]);if(!delimiter){if(host.PendingException().empty())host.ThrowException("java/lang/NullPointerException",u"pattern");return 0;}
    if(*delimiter!=u"\\z"){host.ThrowException("java/lang/UnsupportedOperationException",u"Scanner adapter supports the evidenced end-of-input delimiter only");return 0;}
    std::lock_guard lock(scanner->mutex);scanner->whole=true;return host.NewLocalReference(receiver);
  });
  host.DefineObjectMethod("java/util/Scanner","next","()Ljava/lang/String;",[&host](addr_t receiver)->addr_t{
    auto scanner=host.ReadHostState<Scanner>(receiver);if(!scanner)return 0;
    std::lock_guard lock(scanner->mutex);
    if(scanner->closed){host.ThrowException("java/lang/IllegalStateException",u"Scanner closed");return 0;}
    if(!scanner->whole){host.ThrowException("java/lang/UnsupportedOperationException",u"Scanner adapter requires the evidenced end-of-input delimiter");return 0;}
    std::string bytes;
    {std::lock_guard io(scanner->stream->mutex);auto &stream=*scanner->stream;if(stream.closed||stream.position==stream.bytes.size()){host.ThrowException("java/util/NoSuchElementException");return 0;}bytes.assign(reinterpret_cast<const char*>(stream.bytes.data()+stream.position),stream.bytes.size()-stream.position);stream.position=stream.bytes.size();}
    try{return host.NewString(Utf16(bytes));}
    catch(const std::invalid_argument &){host.ThrowException("java/lang/UnsupportedOperationException",u"Malformed UTF-8 replacement decoding is not implemented");return 0;}
  });
  host.DefineVoidMethod("java/util/Scanner","close","()V",[&host](addr_t receiver,const jni::Host::MethodArguments&){auto scanner=host.ReadHostState<Scanner>(receiver);if(!scanner)return;std::lock_guard lock(scanner->mutex);if(scanner->closed)return;{std::lock_guard io(scanner->stream->mutex);scanner->stream->closed=true;}scanner->closed=true;scanner->source={};scanner->stream.reset();});
  auto manager=std::make_shared<Manager>();manager->reader=std::move(reader);return host.NewHostInstance("android/content/res/AssetManager",manager);
}
}
