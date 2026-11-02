#include "android_shared_preferences.h"
#include <atomic>
#include <condition_variable>
#include <cstdio>
#include <mutex>
#include <stdexcept>

namespace bunker::windows {
namespace {
constexpr const char *kPrefs="bunker/host/SharedPreferences",*kEditor="bunker/host/PreferencesEditor";
constexpr const char *kMap="bunker/host/PreferencesMap",*kSet="bunker/host/PreferencesSet",*kIterator="bunker/host/PreferencesIterator",*kEntry="bunker/host/PreferencesEntry";
addr_t Env(jni::Host&h,size_t n,addr_t a=0,addr_t b=0,addr_t c=0){::State s{};s.gpr.x0.qword=h.EnvAddress();s.gpr.x1.qword=a;s.gpr.x2.qword=b;s.gpr.x3.qword=c;h.InvokeEnv(n,s);return s.gpr.x0.qword;}
void Healthy(jni::Host&h){if(!h.PendingException().empty())throw std::runtime_error("SharedPreferences JNI operation failed: "+h.PendingException());}
std::u16string Text(jni::Host&h,addr_t s){auto value=h.StringValue(s);Healthy(h);if(!value)throw std::runtime_error("SharedPreferences null key/name profile is unsupported");return *value;}
struct Store {
  std::mutex mutex,commit;std::condition_variable committed;bool writing=false;SharedPreferencesSnapshot values;std::u16string name;std::atomic<uint32_t> failure{0};
};
struct CommitTurn {
  Store&store;
  explicit CommitTurn(Store&s):store(s){std::unique_lock lock(store.commit);while(store.writing)store.committed.wait(lock);store.writing=true;}
  ~CommitTurn(){{std::lock_guard lock(store.commit);store.writing=false;}store.committed.notify_all();}
};
struct Editor {std::shared_ptr<Store>store;std::mutex mutex;std::map<std::u16string,std::optional<SharedPreferenceValue>> pending;};
struct Map {std::shared_ptr<const SharedPreferencesSnapshot> values;};
struct Entry {std::u16string key;SharedPreferenceValue value;};
struct Item {bool entry=false;Entry pair;SharedPreferenceValue value;};
struct Collection {std::shared_ptr<const std::vector<Item>>items;};
struct Iterator {std::shared_ptr<const std::vector<Item>>items;std::mutex mutex;size_t next=0;};
struct Number {SharedPreferenceValue value;};
template<class T>std::shared_ptr<T> Payload(jni::Host&h,addr_t object){auto p=h.ReadHostState<T>(object);Healthy(h);if(!p)throw std::runtime_error("SharedPreferences payload is absent");return p;}
SharedPreferenceValue Bits(SharedPreferenceValue::Kind kind,uint64_t bits){SharedPreferenceValue v;v.kind=kind;v.bits=bits;return v;}
// Java String.getBytes("UTF-8") replaces each malformed UTF16 code unit with
// ASCII '?'. Valid surrogate pairs become the actual four UTF8 bytes.
std::u16string UriEncode(const std::u16string&s){
  constexpr char16_t hex[]=u"0123456789ABCDEF";std::u16string out;
  auto byte=[&](uint8_t b){out+=u'%';out+=hex[b>>4];out+=hex[b&15];};
  for(size_t i=0;i<s.size();++i){uint32_t c=s[i];if((c>=u'A'&&c<=u'Z')||(c>=u'a'&&c<=u'z')||(c>=u'0'&&c<=u'9')||std::u16string(u"_-!.~'()*").find(char16_t(c))!=std::u16string::npos){out+=char16_t(c);continue;}
    if(c>=0xd800&&c<=0xdbff){if(i+1<s.size()&&s[i+1]>=0xdc00&&s[i+1]<=0xdfff)c=0x10000+((c-0xd800)<<10)+(s[++i]-0xdc00);else c='?';}else if(c>=0xdc00&&c<=0xdfff)c='?';
    if(c<0x80)byte(uint8_t(c));else if(c<0x800){byte(0xc0|(c>>6));byte(0x80|(c&63));}else if(c<0x10000){byte(0xe0|(c>>12));byte(0x80|((c>>6)&63));byte(0x80|(c&63));}else{byte(0xf0|(c>>18));byte(0x80|((c>>12)&63));byte(0x80|((c>>6)&63));byte(0x80|(c&63));}
  }return out;
}
}
struct AndroidSharedPreferences::State {
  struct Slot {std::mutex mutex;std::condition_variable cv;bool loading=false,ready=false;std::string failed;std::shared_ptr<Store>store;jni::Host::ObjectValue object;};
  jni::Host&host;addr_t context;std::u16string package;SharedPreferencesBackend backend;std::mutex mutex;bool active=true;std::map<std::u16string,std::shared_ptr<Slot>>slots;
  State(jni::Host&h,addr_t c,std::u16string p,SharedPreferencesBackend b):host(h),context(Env(h,226,c)),package(std::move(p)),backend(std::move(b)){Healthy(h);}
  ~State(){Env(host,227,context);} // Required attached, quiesced, Host-live owner contract.
  addr_t Open(addr_t receiver,const jni::Host::MethodArguments&a){
    if(!Env(host,24,receiver,context))throw std::runtime_error("SharedPreferences unsupported Context identity");Healthy(host);
    const auto name=Text(host,a[0]);if(static_cast<int32_t>(a[1])!=0|| (name!=package&&name!=package+u".v2.playerprefs"))throw std::runtime_error("SharedPreferences unsupported mode/store profile");
    std::shared_ptr<Slot>slot;{std::lock_guard lock(mutex);auto&v=slots[name];if(!v)v=std::make_shared<Slot>();slot=v;}
    jni::Host::ObjectValue object;bool initialize=false;
    {std::unique_lock lock(slot->mutex);while(slot->loading)slot->cv.wait(lock);if(!slot->failed.empty())throw std::runtime_error(slot->failed);if(slot->ready)object=slot->object;else{slot->loading=true;initialize=true;}}
    if(initialize){try{
      auto store=std::make_shared<Store>();store->name=name;auto loaded=backend.read(name);if(loaded)store->values=std::move(*loaded);
      const auto local=host.NewHostInstance(kPrefs,store);Healthy(host);object=host.CaptureValue(local);host.DeleteLocalReference(local);Healthy(host);
      {std::lock_guard lock(slot->mutex);slot->store=std::move(store);slot->object=object;slot->ready=true;slot->loading=false;}slot->cv.notify_all();
    }catch(const std::exception&e){{std::lock_guard lock(slot->mutex);slot->failed=std::string("SharedPreferences store load failed: ")+e.what();slot->loading=false;}slot->cv.notify_all();throw;}catch(...){{std::lock_guard lock(slot->mutex);slot->failed="SharedPreferences store load failed with unknown error";slot->loading=false;}slot->cv.notify_all();throw;}}
    return host.LocalValue(object); // No provider/state/store lock spans Host calls.
  }
  addr_t Box(const SharedPreferenceValue&v){
    if(v.kind==SharedPreferenceValue::String)return host.NewString(v.text);
    if(v.kind==SharedPreferenceValue::StringSet){auto items=std::make_shared<std::vector<Item>>();for(auto&s:v.strings){Item i;i.value.kind=SharedPreferenceValue::String;i.value.text=s;items->push_back(std::move(i));}return host.NewHostInstance(kSet,std::make_shared<Collection>(Collection{items}));}
    const char*name=v.kind==SharedPreferenceValue::Integer?"java/lang/Integer":v.kind==SharedPreferenceValue::Float?"java/lang/Float":v.kind==SharedPreferenceValue::Boolean?"java/lang/Boolean":v.kind==SharedPreferenceValue::Long?"java/lang/Long":nullptr;
    if(!name)throw std::runtime_error("SharedPreferences unsupported stored type");return host.NewHostInstance(name,std::make_shared<Number>(Number{v}));
  }
  addr_t Edit(addr_t receiver){auto e=std::make_shared<Editor>();e->store=Payload<Store>(host,receiver);return host.NewHostInstance(kEditor,e);}
  int32_t Int(addr_t receiver,const jni::Host::MethodArguments&a){auto store=Payload<Store>(host,receiver);auto key=Text(host,a[0]);std::optional<SharedPreferenceValue>v;{std::lock_guard lock(store->mutex);auto i=store->values.find(key);if(i!=store->values.end())v=i->second;}if(!v)return static_cast<int32_t>(a[1]);if(v->kind!=SharedPreferenceValue::Integer){host.ThrowException("java/lang/ClassCastException");return 0;}return static_cast<int32_t>(static_cast<uint32_t>(v->bits));}
  addr_t All(addr_t receiver){auto store=Payload<Store>(host,receiver);auto copy=std::make_shared<SharedPreferencesSnapshot>();{std::lock_guard lock(store->mutex);*copy=store->values;}return host.NewHostInstance(kMap,std::make_shared<Map>(Map{copy}));}
  addr_t Put(addr_t receiver,const jni::Host::MethodArguments&a,SharedPreferenceValue::Kind kind){auto editor=Payload<Editor>(host,receiver);auto key=Text(host,a[0]);std::optional<SharedPreferenceValue>value;
    if(kind==SharedPreferenceValue::String){if(a[1]){SharedPreferenceValue v;v.kind=kind;v.text=Text(host,a[1]);value=std::move(v);}}
    else value=Bits(kind,static_cast<uint32_t>(a[1]));
    {std::lock_guard lock(editor->mutex);editor->pending[key]=std::move(value);}return host.NewLocalReference(receiver);
  }
  void Apply(addr_t receiver){auto editor=Payload<Editor>(host,receiver);auto store=editor->store;CommitTurn ordered(*store);SharedPreferencesSnapshot snapshot;
    {std::lock_guard memory(store->mutex);std::lock_guard batch(editor->mutex);for(auto &[key,v]:editor->pending){if(v)store->values[key]=*v;else store->values.erase(key);}editor->pending.clear();snapshot=store->values;}
    uint32_t error=0;try{error=backend.write(store->name,snapshot);}catch(const std::exception&e){std::fprintf(stderr,"SharedPreferences apply persistence failure: %s\n",e.what());error=0xffffffffu;}catch(...){std::fprintf(stderr,"SharedPreferences apply unknown persistence failure\n");error=0xffffffffu;}
    if(error){uint32_t zero=0;store->failure.compare_exchange_strong(zero,error);std::fprintf(stderr,"SharedPreferences apply persistent status=%u; completion verification required\n",error);std::fflush(stderr);}
  }
};
AndroidSharedPreferences::AndroidSharedPreferences(jni::Host&host,addr_t context,std::u16string package,SharedPreferencesBackend backend){
  if(!context||package.empty()||!backend.read||!backend.write)throw std::invalid_argument("SharedPreferences requires actual Context, package and real backend");Healthy(host);state_=std::make_shared<State>(host,context,std::move(package),std::move(backend));std::weak_ptr<State>weak=state_;
  auto get=[weak]{auto s=weak.lock();if(!s)throw std::runtime_error("SharedPreferences adapter owner expired");{std::lock_guard lock(s->mutex);if(!s->active)throw std::runtime_error("SharedPreferences adapter owner retired");}return s;};
  host.DefineClass("java/lang/ClassCastException",{},"java/lang/RuntimeException",true);host.DefineClass("java/util/NoSuchElementException",{},"java/lang/RuntimeException",true);
  host.DefineInterface("android/content/SharedPreferences",{});host.DefineInterface("android/content/SharedPreferences$Editor",{});host.DefineInterface("java/util/Map",{});host.DefineInterface("java/util/Set",{});host.DefineInterface("java/util/Iterator",{});host.DefineInterface("java/util/Map$Entry",{});
  host.DefineClass(kPrefs,{},"java/lang/Object",true,{"android/content/SharedPreferences"});host.DefineClass(kEditor,{},"java/lang/Object",true,{"android/content/SharedPreferences$Editor"});host.DefineClass(kMap,{},"java/lang/Object",true,{"java/util/Map"});host.DefineClass(kSet,{},"java/lang/Object",true,{"java/util/Set"});host.DefineClass(kIterator,{},"java/lang/Object",true,{"java/util/Iterator"});host.DefineClass(kEntry,{},"java/lang/Object",true,{"java/util/Map$Entry"});
  host.DefineClass("java/lang/Number",{},"java/lang/Object",true,{"java/io/Serializable"});for(auto n:{"java/lang/Integer","java/lang/Float","java/lang/Long"})host.DefineClass(n,{},"java/lang/Number",true);host.DefineClass("java/lang/Boolean",{},"java/lang/Object",true,{"java/io/Serializable"});
  host.DefineObjectMethod("android/content/Context","getSharedPreferences","(Ljava/lang/String;I)Landroid/content/SharedPreferences;",[get](addr_t r,const jni::Host::MethodArguments&a){return get()->Open(r,a);});
  host.DefineObjectMethod("android/content/SharedPreferences","edit","()Landroid/content/SharedPreferences$Editor;",[get](addr_t r){return get()->Edit(r);});
  host.DefineIntMethod("android/content/SharedPreferences","getInt","(Ljava/lang/String;I)I",[get](addr_t r,const jni::Host::MethodArguments&a){return get()->Int(r,a);});
  host.DefineObjectMethod("android/content/SharedPreferences","getAll","()Ljava/util/Map;",[get](addr_t r){return get()->All(r);});
  host.DefineObjectMethod("android/content/SharedPreferences$Editor","putString","(Ljava/lang/String;Ljava/lang/String;)Landroid/content/SharedPreferences$Editor;",[get](addr_t r,const jni::Host::MethodArguments&a){return get()->Put(r,a,SharedPreferenceValue::String);});
  host.DefineObjectMethod("android/content/SharedPreferences$Editor","putInt","(Ljava/lang/String;I)Landroid/content/SharedPreferences$Editor;",[get](addr_t r,const jni::Host::MethodArguments&a){return get()->Put(r,a,SharedPreferenceValue::Integer);});
  host.DefineObjectMethod("android/content/SharedPreferences$Editor","putFloat","(Ljava/lang/String;F)Landroid/content/SharedPreferences$Editor;",[get](addr_t r,const jni::Host::MethodArguments&a){return get()->Put(r,a,SharedPreferenceValue::Float);});
  host.DefineVoidMethod("android/content/SharedPreferences$Editor","apply","()V",[get](addr_t r,const jni::Host::MethodArguments&){get()->Apply(r);});
  host.DefineObjectMethod("java/util/Map","entrySet","()Ljava/util/Set;",[get](addr_t r){auto s=get();auto map=Payload<Map>(s->host,r);auto items=std::make_shared<std::vector<Item>>();for(auto&[key,value]:*map->values){Item i;i.entry=true;i.pair={key,value};items->push_back(std::move(i));}return s->host.NewHostInstance(kSet,std::make_shared<Collection>(Collection{items}));});
  host.DefineObjectMethod("java/util/Set","iterator","()Ljava/util/Iterator;",[get](addr_t r){auto s=get();auto set=Payload<Collection>(s->host,r);auto i=std::make_shared<Iterator>();i->items=set->items;return s->host.NewHostInstance(kIterator,i);});
  host.DefineBooleanMethod("java/util/Iterator","hasNext","()Z",[get](addr_t r,const jni::Host::MethodArguments&){auto s=get();auto i=Payload<Iterator>(s->host,r);std::lock_guard lock(i->mutex);return i->next<i->items->size();});
  host.DefineObjectMethod("java/util/Iterator","next","()Ljava/lang/Object;",[get](addr_t r){auto s=get();auto i=Payload<Iterator>(s->host,r);std::optional<Item>item;{std::lock_guard lock(i->mutex);if(i->next<i->items->size())item=(*i->items)[i->next++];}if(!item){s->host.ThrowException("java/util/NoSuchElementException");return addr_t(0);}return item->entry?s->host.NewHostInstance(kEntry,std::make_shared<Entry>(item->pair)):s->Box(item->value);});
  host.DefineObjectMethod("java/util/Map$Entry","getKey","()Ljava/lang/Object;",[get](addr_t r){auto s=get();return s->host.NewString(Payload<Entry>(s->host,r)->key);});
  host.DefineObjectMethod("java/util/Map$Entry","getValue","()Ljava/lang/Object;",[get](addr_t r){auto s=get();return s->Box(Payload<Entry>(s->host,r)->value);});
  host.DefineIntMethod("java/lang/Number","intValue","()I",[get](addr_t r,const jni::Host::MethodArguments&){auto s=get();auto n=Payload<Number>(s->host,r);if(n->value.kind!=SharedPreferenceValue::Integer)throw std::runtime_error("SharedPreferences unported Number.intValue conversion");return static_cast<int32_t>(static_cast<uint32_t>(n->value.bits));});
  host.DefineFloatBitsMethod("java/lang/Number","floatValue","()F",[get](addr_t r,const jni::Host::MethodArguments&){auto s=get();auto n=Payload<Number>(s->host,r);if(n->value.kind!=SharedPreferenceValue::Float)throw std::runtime_error("SharedPreferences unported Number.floatValue conversion");return static_cast<uint32_t>(n->value.bits);});
  host.DefineStaticObjectMethod("android/net/Uri","encode","(Ljava/lang/String;)Ljava/lang/String;",[get](addr_t,const jni::Host::MethodArguments&a){auto s=get();if(!a[0])return addr_t(0);auto text=Text(s->host,a[0]),encoded=UriEncode(text);return encoded==text?s->host.NewLocalReference(a[0]):s->host.NewString(encoded);});
}
AndroidSharedPreferences::~AndroidSharedPreferences(){if(state_){{std::lock_guard lock(state_->mutex);state_->active=false;}state_.reset();}}
void AndroidSharedPreferences::CheckPersistence()const{if(!state_)throw std::runtime_error("SharedPreferences adapter expired");std::vector<std::shared_ptr<State::Slot>>slots;{std::lock_guard lock(state_->mutex);for(auto&[name,slot]:state_->slots)slots.push_back(slot);}for(auto&slot:slots){std::shared_ptr<Store>store;{std::lock_guard lock(slot->mutex);if(!slot->failed.empty())throw std::runtime_error(slot->failed);store=slot->store;}if(store&&store->failure.load())throw std::runtime_error("SharedPreferences persistence verification failed status="+std::to_string(store->failure.load()));}}
}
