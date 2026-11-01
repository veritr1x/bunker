#include "jni_host.h"
#include "../whole/guest_memory.h"

#include <algorithm>
#include <atomic>
#include <climits>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <set>
#include <stdexcept>

namespace bunker::jni {
namespace {
uint64_t ThreadKey() {
  static std::atomic<uint64_t> next{1};
  thread_local const uint64_t key = next.fetch_add(1, std::memory_order_relaxed);
  return key;
}
template <typename T> T Read(addr_t at) { T value; recomp::ReadGuestMemory(&value, at, sizeof(value)); return value; }
template <typename T> void Write(addr_t at, T value) { recomp::WriteGuestMemory(at, &value, sizeof(value)); }
void IntResult(State &s, int32_t value) { s.gpr.x0.qword = static_cast<uint32_t>(value); }
std::string Encode(const std::u16string &text) {
  std::string result;
  for (uint16_t c : text) {
    if (c && c < 0x80) result.push_back(static_cast<char>(c));
    else if (c < 0x800) { result.push_back(static_cast<char>(0xc0 | (c >> 6))); result.push_back(static_cast<char>(0x80 | (c & 63))); }
    else { result.push_back(static_cast<char>(0xe0 | (c >> 12))); result.push_back(static_cast<char>(0x80 | ((c >> 6) & 63))); result.push_back(static_cast<char>(0x80 | (c & 63))); }
  }
  return result;
}
std::u16string Decode(const char *text) {
  if (!text) throw std::invalid_argument("null modified UTF-8 string");
  const auto snapshot = recomp::ReadGuestString(reinterpret_cast<addr_t>(text));
  std::u16string result;
  auto p = reinterpret_cast<const uint8_t *>(snapshot.c_str());
  while (*p) {
    uint32_t c = *p++, minimum = 0;
    unsigned extra = 0;
    if (c < 0x80) {}
    else if ((c & 0xe0) == 0xc0) { c &= 31; extra = 1; minimum = 0x80; }
    else if ((c & 0xf0) == 0xe0) { c &= 15; extra = 2; minimum = 0x800; }
    else throw std::invalid_argument("invalid modified UTF-8 leading byte");
    while (extra--) {
      if ((*p & 0xc0) != 0x80) throw std::invalid_argument("invalid modified UTF-8 continuation");
      c = (c << 6) | (*p++ & 63);
    }
    if (c < minimum && !(c == 0 && minimum == 0x80)) throw std::invalid_argument("overlong modified UTF-8 sequence");
    result.push_back(static_cast<char16_t>(c));
  }
  return result;
}
bool SupportedVersion(int32_t version) { return version == 0x10001 || version == 0x10002 || version == 0x10004 || version == kVersion16; }
}  // namespace

struct Host::Object {
  enum Kind { kClass, kString, kInstance, kThrowable, kBuilder } kind = kInstance;
  std::string class_name, message;
  bool message_present = true;
  uint32_t identity_hash = 0;
  std::type_index host_type=typeid(void);
  std::shared_ptr<void> host_state;
  std::u16string text;
  std::map<addr_t, std::shared_ptr<Object>> object_fields;
  std::map<addr_t, uint64_t> primitive_fields;
};
struct Host::Reference {
  unsigned kind;
  uint64_t owner;
  std::shared_ptr<Object> strong;
  std::weak_ptr<Object> weak;
  std::shared_ptr<Object> Lock() const { return kind == 3 ? weak.lock() : strong; }
};
struct Host::Method {
  enum Builtin { kNone, kClassLoader, kForName, kObjectString, kThrowableString, kMessage, kLocalizedMessage, kStringString,
    kBuilderConstructor, kBuilderAppend, kBuilderString } builtin = kNone;
  MethodDeclaration declaration;
  std::string owner;
  std::function<addr_t(addr_t,const MethodArguments&)> object_handler;
  std::vector<std::string> argument_types;
  addr_t id = 0, native = 0;
};
struct Host::Field { std::string owner, name, signature; bool is_static; addr_t id; };
struct Host::Class {
  std::shared_ptr<Object> object;
  std::string superclass;
  bool bootstrap = false, initialized = false;
  std::map<std::pair<std::string, std::string>, std::unique_ptr<Method>> methods;
  std::map<std::pair<std::string, std::string>, std::unique_ptr<Field>> fields;
};
struct Host::Thread {
  addr_t env_word = 0;
  bool attached = false;
  std::vector<std::vector<addr_t>> frames{1};
  std::shared_ptr<Object> exception;
};
struct Host::UtfLease { std::shared_ptr<Object> owner; std::unique_ptr<std::string> data; };
struct Host::CharLease { std::shared_ptr<Object> owner; std::unique_ptr<std::u16string> data; };

Host::Host(std::function<bool(addr_t)> validator, addr_t marker_base)
    : marker_base_(marker_base), native_entry_validator_(std::move(validator)) {
  if (!native_entry_validator_ || marker_base % 8) throw std::invalid_argument("JNI host needs a native-entry validator and aligned marker base");
  for (size_t i = 4; i < env_table_.size(); ++i) env_table_[i] = EnvMarker(i);
  for (size_t i = 3; i < vm_table_.size(); ++i) vm_table_[i] = VmMarker(i);
  vm_word_ = reinterpret_cast<addr_t>(vm_table_.data());
  DefineClass("java/lang/Object", {{"toString", "()Ljava/lang/String;"}}, "", true);
  DefineClass("java/lang/Class", {{"getClassLoader", "()Ljava/lang/ClassLoader;"},
      {"forName", "(Ljava/lang/String;ZLjava/lang/ClassLoader;)Ljava/lang/Class;", true}}, "java/lang/Object", true);
  DefineClass("java/lang/ClassLoader", {}, "java/lang/Object", true);
  DefineClass("java/lang/BootClassLoader", {}, "java/lang/ClassLoader", true);
  DefineClass("java/lang/String", {{"toString", "()Ljava/lang/String;"}}, "java/lang/Object", true);
  DefineClass("java/lang/AbstractStringBuilder", {}, "java/lang/Object", true);
  DefineClass("java/lang/StringBuilder", {{"<init>","()V"},{"append","(Ljava/lang/String;)Ljava/lang/StringBuilder;"},{"toString","()Ljava/lang/String;"}}, "java/lang/AbstractStringBuilder", true);
  classes_.at("java/lang/StringBuilder")->methods.at({"<init>","()V"})->builtin=Method::kBuilderConstructor;
  classes_.at("java/lang/StringBuilder")->methods.at({"append","(Ljava/lang/String;)Ljava/lang/StringBuilder;"})->builtin=Method::kBuilderAppend;
  classes_.at("java/lang/StringBuilder")->methods.at({"append","(Ljava/lang/String;)Ljava/lang/StringBuilder;"})->argument_types={"Ljava/lang/String;"};
  classes_.at("java/lang/StringBuilder")->methods.at({"toString","()Ljava/lang/String;"})->builtin=Method::kBuilderString;
  empty_string_=std::make_shared<Object>();empty_string_->kind=Object::kString;empty_string_->class_name="java/lang/String";
  DefineClass("java/lang/Throwable", {{"toString", "()Ljava/lang/String;"}, {"getMessage", "()Ljava/lang/String;"}, {"getLocalizedMessage", "()Ljava/lang/String;"}}, "java/lang/Object", true);
  for (auto [name,superclass] : std::vector<std::pair<const char *,const char *>>{
      {"java/lang/Exception","java/lang/Throwable"},{"java/lang/RuntimeException","java/lang/Exception"},
      {"java/lang/IllegalArgumentException","java/lang/RuntimeException"},{"java/lang/IllegalStateException","java/lang/RuntimeException"},
      {"java/lang/NullPointerException","java/lang/RuntimeException"},{"java/lang/IndexOutOfBoundsException","java/lang/RuntimeException"},
      {"java/lang/StringIndexOutOfBoundsException","java/lang/IndexOutOfBoundsException"},{"java/lang/UnsupportedOperationException","java/lang/RuntimeException"},
      {"java/lang/ClassNotFoundException","java/lang/Exception"},{"java/lang/Error","java/lang/Throwable"},
      {"java/lang/LinkageError","java/lang/Error"},{"java/lang/IncompatibleClassChangeError","java/lang/LinkageError"},
      {"java/lang/NoClassDefFoundError","java/lang/LinkageError"},{"java/lang/NoSuchMethodError","java/lang/IncompatibleClassChangeError"},
      {"java/lang/NoSuchFieldError","java/lang/IncompatibleClassChangeError"},{"java/lang/UnsatisfiedLinkError","java/lang/LinkageError"}})
    DefineClass(name, {}, superclass, true);
  auto builtin=[&](const char *owner,const char *name,Method::Builtin kind){classes_.at(owner)->methods.at({name,"()Ljava/lang/String;"})->builtin=kind;};
  builtin("java/lang/Object","toString",Method::kObjectString);builtin("java/lang/String","toString",Method::kStringString);
  builtin("java/lang/Throwable","toString",Method::kThrowableString);builtin("java/lang/Throwable","getMessage",Method::kMessage);builtin("java/lang/Throwable","getLocalizedMessage",Method::kLocalizedMessage);
  classes_.at("java/lang/Class")->methods.at({"getClassLoader", "()Ljava/lang/ClassLoader;"})->builtin = Method::kClassLoader;
  classes_.at("java/lang/Class")->methods.at({"forName", "(Ljava/lang/String;ZLjava/lang/ClassLoader;)Ljava/lang/Class;"})->builtin = Method::kForName;
  application_loader_ = std::make_shared<Object>(); application_loader_->class_name = "java/lang/ClassLoader";
  bootstrap_loader_ = std::make_shared<Object>(); bootstrap_loader_->class_name = "java/lang/BootClassLoader";
  Current(true);
}
Host::~Host() = default;
addr_t Host::EnvMarker(size_t slot) const { return marker_base_ + slot * 8; }
addr_t Host::VmMarker(size_t slot) const { return marker_base_ + 0x1000 + slot * 8; }
Host::Thread &Host::Current(bool attach) {
  auto &thread = threads_[ThreadKey()];
  if (!thread) { thread = std::make_unique<Thread>(); thread->env_word = reinterpret_cast<addr_t>(env_table_.data()); }
  if (attach) thread->attached = true;
  return *thread;
}
addr_t Host::EnvAddress() { std::lock_guard lock(mutex_); auto &t = Current(); return t.attached ? reinterpret_cast<addr_t>(&t.env_word) : 0; }
void Host::RequireEnv(addr_t address) {
  auto &t = Current();
  if (!t.attached || address != reinterpret_cast<addr_t>(&t.env_word)) throw std::runtime_error("JNIEnv belongs to a different or detached thread");
}
void Host::DefineClass(const std::string &name, std::vector<MethodDeclaration> methods, const std::string &superclass, bool bootstrap) {
  std::lock_guard lock(mutex_);
  if (name.empty() || classes_.count(name) || (!superclass.empty() && !classes_.count(superclass))) throw std::invalid_argument("invalid or duplicate Java class");
  auto clazz = std::make_unique<Class>();
  clazz->object = std::make_shared<Object>(); clazz->object->kind = Object::kClass; clazz->object->class_name = name;
  clazz->superclass = superclass;
  clazz->bootstrap = bootstrap; clazz->initialized = bootstrap;
  for (auto &declaration : methods) {
    if (declaration.name.empty() || declaration.signature.empty() || declaration.signature.front() != '(')
      throw std::invalid_argument("invalid method declaration");
    auto key = std::make_pair(declaration.name, declaration.signature);
    if (clazz->methods.count(key)) throw std::invalid_argument("duplicate method declaration");
    auto method = std::make_unique<Method>(); method->declaration = std::move(declaration); method->id = next_method_++; method->owner = name;
    clazz->methods.emplace(key, std::move(method));
  }
  for (auto &method : clazz->methods) method_ids_[method.second->id] = method.second.get();
  classes_.emplace(name, std::move(clazz));
}
void Host::MarkClassInitialized(const std::string &name) {
  std::lock_guard lock(mutex_);
  auto found = classes_.find(name);
  if (found == classes_.end()) throw std::invalid_argument("unknown Java class initialization");
  found->second->initialized = true;
}
void Host::DefineObjectMethod(const std::string &class_name, const std::string &name,
                              const std::string &signature, std::function<addr_t(addr_t)> handler) {
  if(signature.rfind("()L",0)!=0||!handler)throw std::invalid_argument("zero-argument object handler requires an object signature");
  DefineHandler(class_name,name,signature,'L',[handler=std::move(handler)](addr_t object,const MethodArguments&){return handler(object);});
}
void Host::DefineObjectMethod(const std::string &owner,const std::string &name,const std::string &signature,
                              std::function<addr_t(addr_t,const MethodArguments&)> handler){DefineHandler(owner,name,signature,'L',std::move(handler));}
void Host::DefineBooleanMethod(const std::string &owner,const std::string &name,const std::string &signature,
                               std::function<bool(addr_t,const MethodArguments&)> handler){
  if(!handler)throw std::invalid_argument("missing boolean handler");
  DefineHandler(owner,name,signature,'Z',[handler=std::move(handler)](addr_t object,const MethodArguments &arguments){return handler(object,arguments)?1:0;});
}
void Host::DefineVoidMethod(const std::string &owner,const std::string &name,const std::string &signature,std::function<void(addr_t,const MethodArguments&)> handler){
  if(!handler)throw std::invalid_argument("missing void handler");DefineHandler(owner,name,signature,'V',[handler=std::move(handler)](addr_t object,const MethodArguments &arguments){handler(object,arguments);return 0;});
}
void Host::DefineConstructor(const std::string &owner,const std::string &signature,std::function<addr_t(const MethodArguments&)> factory){
  if(!factory)throw std::invalid_argument("missing constructor factory");DefineHandler(owner,"<init>",signature,'V',[factory=std::move(factory)](addr_t,const MethodArguments &arguments){return factory(arguments);});
}
void Host::ThrowException(const std::string &type,const std::u16string &message){std::lock_guard lock(mutex_);if(!Assignable(type,"java/lang/Throwable"))throw std::invalid_argument("host exception needs a declared Throwable class");Raise(type,Encode(message));}
void Host::ThrowException(const std::string &type){std::lock_guard lock(mutex_);if(!Assignable(type,"java/lang/Throwable"))throw std::invalid_argument("host exception needs a declared Throwable class");Raise(type,"",false);}
void Host::DefineHandler(const std::string &class_name,const std::string &name,const std::string &signature,char result,
                         std::function<addr_t(addr_t,const MethodArguments&)> handler){
  std::lock_guard lock(mutex_);
  auto clazz = classes_.find(class_name);
  if(clazz==classes_.end()||name.empty()||signature.empty()||signature[0]!='('||!handler)throw std::invalid_argument("host method requires a known class and handler");
  std::vector<std::string> arguments;size_t at=1;
  while(at<signature.size()&&signature[at]!=')'){
    if(arguments.size()==3)throw std::invalid_argument("host handlers support at most three fixed arguments");
    if(signature[at]=='I'){arguments.push_back("I");++at;continue;}
    if(signature[at]!='L')throw std::invalid_argument("host handlers support only object-reference and jint arguments");
    auto end=signature.find(';',at);if(end==std::string::npos)throw std::invalid_argument("invalid host argument descriptor");
    auto type=signature.substr(at+1,end-at-1);if(!classes_.count(type))throw std::invalid_argument("unknown host argument class");arguments.push_back(signature.substr(at,end-at+1));at=end+1;
  }
  auto returns=at<signature.size()?signature.substr(at+1):"";
  if((result=='Z'&&returns!="Z")||(result=='V'&&returns!="V")||(result=='L'&&(returns.size()<3||returns.front()!='L'||returns.back()!=';'||!classes_.count(returns.substr(1,returns.size()-2)))))throw std::invalid_argument("invalid host result descriptor");
  auto key = std::make_pair(name, signature);
  auto found = clazz->second->methods.find(key);
  if (found != clazz->second->methods.end()) throw std::invalid_argument("duplicate host method");
  auto method = std::make_unique<Method>(); method->declaration = {name, signature, false, false};
  method->owner = class_name; method->id = next_method_++; method->object_handler = std::move(handler);
  method->argument_types=std::move(arguments);
  method_ids_[method->id] = method.get(); clazz->second->methods.emplace(key, std::move(method));
}
void Host::DefineField(const std::string &class_name, const std::string &name, const std::string &signature, bool is_static) {
  std::lock_guard lock(mutex_);
  auto clazz = classes_.find(class_name);
  if (clazz == classes_.end() || name.empty() || (signature != "I" && signature!="[Ljava/lang/String;" && !(signature.size() > 2 && signature.front() == 'L' && signature.back() == ';')))
    throw std::invalid_argument("JNI fields support int, object and nullable String-array signatures on known classes");
  auto key = std::make_pair(name, signature);
  if (clazz->second->fields.count(key)) throw std::invalid_argument("duplicate JNI field");
  auto field = std::make_unique<Field>(Field{class_name, name, signature, is_static, next_method_++});
  field_ids_[field->id] = field.get(); clazz->second->fields.emplace(key, std::move(field));
}
void Host::Raise(const std::string &type, const std::string &message, bool message_present) {
  auto object = std::make_shared<Object>(); object->kind = Object::kThrowable; object->class_name = type; object->message = message;
  object->message_present=message_present;
  Current().exception = std::move(object);
}
std::string Host::PendingException() { std::lock_guard lock(mutex_); auto e = Current().exception; return e ? e->class_name + ": " + e->message : ""; }
void Host::ClearException() { std::lock_guard lock(mutex_); Current().exception.reset(); }
addr_t Host::Local(const std::shared_ptr<Object> &object) {
  if (!object) return 0;
  auto &t = Current();
  addr_t handle = next_reference_++;
  references_.emplace(handle, Reference{1, ThreadKey(), object, {}});
  t.frames.back().push_back(handle);
  return handle;
}
std::shared_ptr<Host::Object> Host::Get(addr_t handle, bool allow_null) {
  if (!handle) { if (!allow_null) Raise("java/lang/NullPointerException", "null JNI reference"); return {}; }
  auto found = references_.find(handle);
  if (found == references_.end() || (found->second.kind == 1 && found->second.owner != ThreadKey())) {
    Raise("java/lang/IllegalArgumentException", "invalid JNI reference"); return {};
  }
  auto object=found->second.Lock();
  if(!object&&!allow_null)Raise("java/lang/NullPointerException","cleared weak JNI reference");
  return object;
}
std::shared_ptr<Host::Object> Host::String(addr_t handle) {
  auto object = Get(handle);
  if (object && object->kind != Object::kString) { Raise("java/lang/IllegalArgumentException", "expected jstring"); return {}; }
  return object;
}
Host::Class *Host::GetClass(addr_t handle) {
  auto object = Get(handle);
  if (!object) return nullptr;
  if (object->kind != Object::kClass) { Raise("java/lang/IllegalArgumentException", "expected jclass"); return nullptr; }
  return classes_.at(object->class_name).get();
}
addr_t Host::NewString(const std::u16string &value) {
  std::lock_guard lock(mutex_);
  auto object = std::make_shared<Object>(); object->kind = Object::kString; object->class_name = "java/lang/String"; object->text = value;
  return Local(object);
}
addr_t Host::NewInstance(const std::string &name) {
  std::lock_guard lock(mutex_);
  if (!classes_.count(name)) throw std::invalid_argument("unknown Java class");
  auto object = std::make_shared<Object>(); object->class_name = name; return Local(object);
}
addr_t Host::HostInstance(const std::string &name,std::type_index type,std::shared_ptr<void> state){
  if(!state)throw std::invalid_argument("host instance requires initialized state");
  std::lock_guard lock(mutex_);auto reference=NewInstance(name);auto object=Get(reference);object->host_type=type;object->host_state=std::move(state);return reference;
}
std::shared_ptr<void> Host::HostState(addr_t reference,std::type_index type){
  std::lock_guard lock(mutex_);auto object=Get(reference);if(!object)return {};
  if(object->host_type!=type||!object->host_state){Raise("java/lang/UnsupportedOperationException","Java object has no configured host state: "+object->class_name);return {};}return object->host_state;
}
Host::ObjectValue Host::CaptureValue(addr_t reference){std::lock_guard lock(mutex_);ObjectValue value;value.owner_=this;value.object_=Get(reference,true);return value;}
addr_t Host::LocalValue(const ObjectValue &value){std::lock_guard lock(mutex_);if(value.object_&&value.owner_!=this)throw std::invalid_argument("Java object value belongs to another host");return Local(value.object_);}
std::optional<std::u16string> Host::StringValue(addr_t reference){
  std::lock_guard lock(mutex_);auto object=Get(reference,true);if(!object)return std::nullopt;
  if(object->kind!=Object::kString){Raise("java/lang/IllegalArgumentException","expected initialized jstring");return std::nullopt;}return object->text;
}
addr_t Host::NewGlobalReference(addr_t reference) { std::lock_guard lock(mutex_); return Ref(reference, 2); }
addr_t Host::NewLocalReference(addr_t reference) { std::lock_guard lock(mutex_); return Ref(reference, 1); }
void Host::DeleteGlobalReference(addr_t reference) { std::lock_guard lock(mutex_); Delete(reference, 2); }
void Host::DeleteLocalReference(addr_t reference) { std::lock_guard lock(mutex_); Delete(reference, 1); }
bool Host::Assignable(const std::string &actual, const std::string &expected) const {
  std::string name = actual;
  while (!name.empty()) {
    if (name == expected) return true;
    auto found = classes_.find(name); if (found == classes_.end()) return false; name = found->second->superclass;
  }
  return false;
}
Host::Field *Host::LookupField(const std::string &class_name, const char *name, const char *signature, bool is_static) {
  if (!name || !signature) { Raise("java/lang/NullPointerException", "null field name/signature"); return nullptr; }
  const auto field_name = recomp::ReadGuestString(reinterpret_cast<addr_t>(name));
  const auto field_signature = recomp::ReadGuestString(reinterpret_cast<addr_t>(signature));
  std::string owner = class_name;
  while (!owner.empty()) {
    auto clazz = classes_.find(owner); if (clazz == classes_.end()) break;
    auto found = clazz->second->fields.find({field_name, field_signature});
    if (found != clazz->second->fields.end()) {
      if (found->second->is_static == is_static) return found->second.get();
      break;
    }
    owner = clazz->second->superclass;
  }
  Raise("java/lang/NoSuchFieldError", field_name + ":" + field_signature); return nullptr;
}
addr_t Host::FieldId(addr_t clazz, const char *name, const char *signature, bool is_static) {
  auto *metadata = GetClass(clazz); if (!metadata) return 0;
  auto *field = LookupField(metadata->object->class_name, name, signature, is_static); return field ? field->id : 0;
}
std::shared_ptr<Host::Object> Host::FieldTarget(addr_t reference, addr_t id, bool is_static, const std::string &kind) {
  auto field = field_ids_.find(id);
  if (field == field_ids_.end()) { Raise("java/lang/NoSuchFieldError", "invalid JNI field ID"); return {}; }
  auto &metadata = *field->second;
  if (metadata.is_static != is_static || (kind == "I" ? metadata.signature != "I" : (metadata.signature.front() != 'L'&&metadata.signature.front()!='['))) {
    Raise("java/lang/IllegalArgumentException", "JNI field type/static mismatch"); return {};
  }
  auto object = Get(reference); if (!object) return {};
  auto actual = is_static ? object->class_name : object->kind == Object::kClass ? "java/lang/Class" : object->class_name;
  if ((is_static && object->kind != Object::kClass) || !Assignable(actual, metadata.owner)) {
    Raise("java/lang/IllegalArgumentException", "JNI field receiver type mismatch"); return {};
  }
  return is_static ? classes_.at(metadata.owner)->object : object;
}
void Host::SetObjectFieldValue(addr_t reference, const std::string &name, const std::string &signature, addr_t value) {
  std::lock_guard lock(mutex_); auto object = Get(reference); if (!object) return;
  auto *field = LookupField(object->class_name, name.c_str(), signature.c_str(), false); if (!field) return;
  auto target = FieldTarget(reference, field->id, false, "object"); if (!target) return;
  auto source = Get(value, true); if (value && !source) return;
  auto actual = source && source->kind == Object::kClass ? "java/lang/Class" : source ? source->class_name : "";
  if (source && !Assignable(actual, signature.front()=='['?signature:signature.substr(1, signature.size() - 2))) { Raise("java/lang/IllegalArgumentException", "JNI object field value type mismatch"); return; }
  target->object_fields[field->id] = source;
}
addr_t Host::GetObjectFieldValue(addr_t reference, const std::string &name, const std::string &signature) {
  std::lock_guard lock(mutex_); auto object = Get(reference); if (!object) return 0;
  auto *field = LookupField(object->class_name, name.c_str(), signature.c_str(), false); if (!field) return 0;
  auto target = FieldTarget(reference, field->id, false, "object"); return target ? Local(target->object_fields[field->id]) : 0;
}
void Host::SetIntFieldValue(addr_t reference, const std::string &name, int32_t value) {
  std::lock_guard lock(mutex_); auto object = Get(reference); if (!object) return;
  auto *field = LookupField(object->class_name, name.c_str(), "I", false); if (!field) return;
  auto target = FieldTarget(reference, field->id, false, "I"); if (target) target->primitive_fields[field->id] = static_cast<uint32_t>(value);
}
addr_t Host::Ref(addr_t handle, unsigned kind) {
  auto object = Get(handle, true); if (!object) return 0;
  if (kind == 1) return Local(object);
  auto next = next_reference_++;
  references_.emplace(next, Reference{kind, {}, kind == 2 ? object : nullptr, object}); return next;
}
void Host::Delete(addr_t handle, unsigned kind) {
  if (!handle) return;
  auto found = references_.find(handle);
  if (found == references_.end() || found->second.kind != kind || (kind == 1 && found->second.owner != ThreadKey())) {
    Raise("java/lang/IllegalArgumentException", "incorrect reference deletion"); return;
  }
  references_.erase(found);
}
addr_t Host::MethodId(addr_t handle, const char *name, const char *signature, bool is_static) {
  auto *clazz = GetClass(handle); if (!clazz) return 0;
  if (!name || !signature) { Raise("java/lang/NullPointerException", "null method name/signature"); return 0; }
  const auto method_name = recomp::ReadGuestString(reinterpret_cast<addr_t>(name));
  const auto method_signature = recomp::ReadGuestString(reinterpret_cast<addr_t>(signature));
  while (clazz) {
    auto found = clazz->methods.find({method_name, method_signature});
    if (found != clazz->methods.end()) {
      if (found->second->declaration.is_static == is_static) return found->second->id;
      break;
    }
    clazz = clazz->superclass.empty() ? nullptr : classes_.at(clazz->superclass).get();
  }
  Raise("java/lang/NoSuchMethodError", method_name + method_signature); return 0;
}
bool Host::ValidateArguments(const Method &method,const MethodArguments &arguments){for(size_t i=0;i<method.argument_types.size();++i){const auto &type=method.argument_types[i];if(type=="I")continue;auto argument=Get(arguments[i],true);if(Current().exception)return false;if(argument&&!Assignable(argument->kind==Object::kClass?"java/lang/Class":argument->class_name,type.substr(1,type.size()-2))){Raise("java/lang/IllegalArgumentException","JNI method argument type mismatch");return false;}}return true;}
addr_t Host::CallObject(std::unique_lock<std::recursive_mutex> &lock, addr_t reference, addr_t id, bool is_static, const std::array<addr_t, 3> &arguments,char expected_result) {
  auto method = method_ids_.find(id);
  if (method == method_ids_.end()) { Raise("java/lang/NoSuchMethodError", "invalid JNI method ID"); return 0; }
  auto object = Get(reference); if (!object) return 0;
  auto *selected = method->second;
  auto actual = is_static ? object->class_name : object->kind == Object::kClass ? "java/lang/Class" : object->class_name;
  if (selected->declaration.is_static != is_static || (is_static && object->kind != Object::kClass) || !Assignable(actual, selected->owner)) { Raise("java/lang/IllegalArgumentException", "JNI method receiver mismatch"); return 0; }
  if(!is_static){
    const auto key=std::make_pair(selected->declaration.name,selected->declaration.signature);
    for(auto clazz=classes_.at(actual).get();clazz;clazz=clazz->superclass.empty()?nullptr:classes_.at(clazz->superclass).get()){
      auto override=clazz->methods.find(key);if(override!=clazz->methods.end()&&!override->second->declaration.is_static){selected=override->second.get();break;}
    }
  }
  auto &metadata=*selected;
  auto close=metadata.declaration.signature.find(')');char result_kind=close==std::string::npos||close+1==metadata.declaration.signature.size()?0:metadata.declaration.signature[close+1];
  if(result_kind!=expected_result||metadata.declaration.name=="<init>"){Raise("java/lang/IllegalArgumentException","JNI method result type mismatch or constructor requires NewObject");return 0;}
  if(metadata.builtin==Method::kBuilderAppend||metadata.builtin==Method::kBuilderString){
    if(object->kind!=Object::kBuilder){Raise("java/lang/UnsupportedOperationException","StringBuilder constructor has not initialized this object");return 0;}
    if(metadata.builtin==Method::kBuilderString)return object->text.empty()?Local(empty_string_):NewString(object->text);
    auto input=Get(arguments[0],true);if(Current().exception)return 0;
    if(input&&input->kind!=Object::kString){Raise("java/lang/IllegalArgumentException","StringBuilder.append(String) requires a string reference");return 0;}
    object->text+=input?input->text:u"null";
    return Local(object);
  }
  if(metadata.builtin==Method::kBuilderConstructor){Raise("java/lang/IllegalArgumentException","StringBuilder constructor requires NewObject");return 0;}
  if(metadata.builtin==Method::kStringString){
    if(object->kind!=Object::kString){Raise("java/lang/UnsupportedOperationException","String object has no initialized string value");return 0;}return Local(object);
  }
  if(metadata.builtin==Method::kMessage||metadata.builtin==Method::kLocalizedMessage||metadata.builtin==Method::kThrowableString){
    if(object->kind!=Object::kThrowable){Raise("java/lang/UnsupportedOperationException","Throwable object has no initialized throwable state");return 0;}
    if(metadata.builtin==Method::kMessage)return object->message_present?NewString(Decode(object->message.c_str())):0;
    const char *getter=metadata.builtin==Method::kLocalizedMessage?"getMessage":"getLocalizedMessage";
    auto getter_id=classes_.at("java/lang/Throwable")->methods.at({getter,"()Ljava/lang/String;"})->id;
    auto message=CallObject(lock,reference,getter_id);if(Current().exception)return 0;
    if(metadata.builtin==Method::kLocalizedMessage)return message;
    auto text=Get(message,true);if(message&&!text)return 0;
    std::string name=object->class_name;std::replace(name.begin(),name.end(),'/','.');
    auto result=Decode(name.c_str());if(text){result+=u": ";result+=text->text;}
    if(message)Delete(message,1);return NewString(result);
  }
  if(metadata.builtin==Method::kObjectString){
    if(object->kind==Object::kClass){Raise("java/lang/UnsupportedOperationException","Class.toString requires complete class/interface metadata");return 0;}
    for(auto clazz=classes_.at(actual).get();clazz&&!clazz->superclass.empty();clazz=classes_.at(clazz->superclass).get())
      if(clazz->methods.count({"hashCode","()I"})){Raise("java/lang/UnsupportedOperationException","Java hashCode override is not implemented: "+clazz->object->class_name);return 0;}
    if(!object->identity_hash){if(!next_identity_hash_)++next_identity_hash_;object->identity_hash=next_identity_hash_++;}
    auto name=actual;std::replace(name.begin(),name.end(),'/','.');char hash[9];std::snprintf(hash,sizeof(hash),"%x",object->identity_hash);
    return NewString(Decode((name+"@"+hash).c_str()));
  }
  if (metadata.builtin == Method::kClassLoader) {
    if (object->kind != Object::kClass) { Raise("java/lang/IllegalArgumentException", "getClassLoader requires a class object"); return 0; }
    return Local(classes_.at(object->class_name)->bootstrap ? bootstrap_loader_ : application_loader_);
  }
  if (metadata.builtin == Method::kForName) {
    auto name = String(arguments[0]); if (!name) return 0;
    auto loader = Get(arguments[2], true); if (arguments[2] && !loader) return 0;
    if (loader && !Assignable(loader->kind == Object::kClass ? "java/lang/Class" : loader->class_name, "java/lang/ClassLoader")) { Raise("java/lang/IllegalArgumentException", "forName requires a ClassLoader"); return 0; }
    if (loader && loader != application_loader_ && loader != bootstrap_loader_) { Raise("java/lang/UnsupportedOperationException", "unconfigured Java ClassLoader"); return 0; }
    auto binary = Encode(name->text), internal = binary;
    std::replace(internal.begin(), internal.end(), '.', '/');
    auto found = classes_.find(internal);
    if (binary.empty() || binary.find('/') != std::string::npos || binary.find('[') != std::string::npos ||
        found == classes_.end() || (loader != application_loader_ && !found->second->bootstrap)) {
      Raise("java/lang/ClassNotFoundException", binary); return 0;
    }
    if (static_cast<uint8_t>(arguments[1]) && !found->second->initialized) {
      Raise("java/lang/UnsupportedOperationException", "Java class initialization is not implemented: " + internal); return 0;
    }
    return Local(found->second->object);
  }
  if (!metadata.object_handler) throw std::runtime_error("Java method has no host implementation: " + metadata.owner + "." + metadata.declaration.name + metadata.declaration.signature);
  if(!ValidateArguments(metadata,arguments))return 0;
  // Keep the receiver and callback alive, but never hold the host registry lock
  // across external code. A callback may wait for another attached JNI thread.
  auto handler = metadata.object_handler;
  auto return_type = expected_result=='L'?metadata.declaration.signature.substr(close+2,metadata.declaration.signature.size()-close-3):"";
  addr_t result;
  lock.unlock();
  try { result = handler(reference,arguments); }
  catch (...) { lock.lock(); throw; }
  lock.lock();
  if(expected_result=='Z')return result?1:0;
  if(expected_result=='V')return 0;
  auto returned = Get(result, true);
  if (result && !returned) return 0;
  if (returned && !Assignable(returned->kind == Object::kClass ? "java/lang/Class" : returned->class_name, return_type)) {
    Raise("java/lang/IllegalArgumentException", "host Java method returned wrong object type"); return 0;
  }
  // The callback retains ownership of its reference; JNI calls return a new
  // local reference owned by the invoking thread, including for global results.
  return Local(returned);
}
addr_t Host::Construct(std::unique_lock<std::recursive_mutex> &lock,addr_t reference,addr_t id,const MethodArguments &arguments){
  auto *clazz=GetClass(reference);if(!clazz)return 0;
  auto found=method_ids_.find(id);if(found==method_ids_.end()){Raise("java/lang/NoSuchMethodError","invalid JNI constructor ID");return 0;}
  auto &method=*found->second;
  if(method.owner!=clazz->object->class_name||method.declaration.is_static||method.declaration.name!="<init>"||method.declaration.signature.back()!='V'){
    Raise("java/lang/IllegalArgumentException","JNI constructor class/method mismatch");return 0;
  }
  if(method.builtin!=Method::kBuilderConstructor){
    if(!method.object_handler)throw std::runtime_error("Java constructor has no host implementation: "+method.owner+method.declaration.signature);
    if(!ValidateArguments(method,arguments))return 0;
    auto factory=method.object_handler;auto owner=method.owner;addr_t result;lock.unlock();try{result=factory(0,arguments);}catch(...){lock.lock();throw;}lock.lock();
    if(Current().exception)return 0;auto object=Get(result,true);if(!object){if(!Current().exception)Raise("java/lang/IllegalStateException","host constructor returned null without an exception");return 0;}if(object->kind!=Object::kInstance||object->class_name!=owner){Raise("java/lang/IllegalArgumentException","host constructor returned the wrong class");return 0;}return Local(object);
  }
  auto object=std::make_shared<Object>();object->kind=Object::kBuilder;object->class_name="java/lang/StringBuilder";object->text.reserve(16);
  return Local(object);
}
bool Host::Arguments(State &state,size_t slot,size_t count,std::array<addr_t,3> &arguments){
  if(!count)return true;
  if(count>arguments.size())throw std::logic_error("unsupported JNI host argument count");
  const bool direct=slot==28||slot==34||slot==114, array=slot==30||slot==36||slot==116;
  if(direct){const addr_t regs[]={state.gpr.x3.qword,state.gpr.x4.qword,state.gpr.x5.qword};std::copy_n(regs,count,arguments.begin());return true;}
  auto pointer=state.gpr.x3.qword;
  if(!pointer){Raise("java/lang/IllegalArgumentException","null JNI argument list");return false;}
  if(array){for(size_t i=0;i<count;++i)arguments[i]=Read<addr_t>(pointer+i*8);return true;}
  // Android AAPCS64 va_list: stack, gr_top, vr_top, gr_offs, vr_offs.
  struct VaList {addr_t stack,gr_top,vr_top;int32_t gr_offs,vr_offs;};static_assert(sizeof(VaList)==32);
  auto list=Read<VaList>(pointer);
  for(size_t i=0;i<count;++i){if(list.gr_offs<0){arguments[i]=Read<addr_t>(list.gr_top+list.gr_offs);list.gr_offs+=8;}else{arguments[i]=Read<addr_t>(list.stack);list.stack+=8;}}
  return true;
}
int32_t Host::Register(addr_t handle, const NativeMethod *methods, int32_t count) {
  auto *clazz = GetClass(handle); if (!clazz) return kError;
  if (count < 0 || (count && !methods)) { Raise("java/lang/IllegalArgumentException", "invalid native method array"); return kError; }
  std::vector<std::pair<Method *, addr_t>> updates;
  std::set<Method *> seen;
  for (int32_t i = 0; i < count; ++i) {
    auto wire = Read<NativeMethod>(reinterpret_cast<addr_t>(methods + i));
    auto *name = reinterpret_cast<const char *>(wire.name), *signature = reinterpret_cast<const char *>(wire.signature);
    if (!name || !signature) { Raise("java/lang/IllegalArgumentException", "null native method descriptor"); return kError; }
    const auto native_name = recomp::ReadGuestString(wire.name);
    const auto native_signature = recomp::ReadGuestString(wire.signature);
    auto found = clazz->methods.find({native_name, native_signature});
    if (found == clazz->methods.end() || !found->second->declaration.is_native) {
      Raise("java/lang/NoSuchMethodError", native_name + native_signature); return kError;
    }
    if (!wire.entry || !native_entry_validator_(wire.entry)) { Raise("java/lang/UnsatisfiedLinkError", native_name); return kError; }
    if (!seen.insert(found->second.get()).second) { Raise("java/lang/IllegalArgumentException", "duplicate native registration"); return kError; }
    updates.emplace_back(found->second.get(), wire.entry);
  }
  for (auto [method, entry] : updates) method->native = entry;
  return kOk;
}
addr_t Host::NativeEntry(const std::string &class_name, const std::string &name, const std::string &signature) const {
  std::lock_guard lock(mutex_); auto clazz = classes_.find(class_name); if (clazz == classes_.end()) return 0;
  auto found = clazz->second->methods.find({name, signature}); return found == clazz->second->methods.end() ? 0 : found->second->native;
}
size_t Host::NativeCount(const std::string &class_name) const {
  std::lock_guard lock(mutex_); auto clazz = classes_.find(class_name); if (clazz == classes_.end()) return 0;
  size_t count = 0; for (auto &entry : clazz->second->methods) if (entry.second->native) ++count; return count;
}

void Host::InvokeVm(size_t slot, State &s) {
  std::lock_guard lock(mutex_);
  if (s.gpr.x0.qword != VmAddress()) throw std::runtime_error("invalid JavaVM pointer");
  auto &thread = Current();
  switch (slot) {
    case 4: case 7:
      if (!s.gpr.x1.qword) { IntResult(s, kError); return; }
      if (s.gpr.x2.qword && !SupportedVersion(Read<int32_t>(s.gpr.x2.qword))) { Write<addr_t>(s.gpr.x1.qword, 0); IntResult(s, kVersionError); return; }
      thread.attached = true; Write(s.gpr.x1.qword, reinterpret_cast<addr_t>(&thread.env_word)); IntResult(s, kOk); return;
    case 5:
      if (!thread.attached) { IntResult(s, kDetached); return; }
      for (auto &frame : thread.frames) for (auto ref : frame) references_.erase(ref);
      thread.frames.clear(); thread.frames.emplace_back(); thread.exception.reset(); thread.attached = false; IntResult(s, kOk); return;
    case 6:
      if (!s.gpr.x1.qword) { IntResult(s, kError); return; }
      Write<addr_t>(s.gpr.x1.qword, 0);
      if (!SupportedVersion(s.gpr.x2.dword)) { IntResult(s, kVersionError); return; }
      if (!thread.attached) { IntResult(s, kDetached); return; }
      Write(s.gpr.x1.qword, reinterpret_cast<addr_t>(&thread.env_word)); IntResult(s, kOk); return;
    default: throw std::runtime_error("unsupported JavaVM slot " + std::to_string(slot));
  }
}

void Host::InvokeEnv(size_t slot, State &s) {
  std::unique_lock lock(mutex_);
  RequireEnv(s.gpr.x0.qword);
  addr_t a = s.gpr.x1.qword, b = s.gpr.x2.qword, c = s.gpr.x3.qword, d = s.gpr.x4.qword;
  switch (slot) {
    case 4: IntResult(s, kVersion16); return;
    case 6: {
      const auto name = a ? recomp::ReadGuestString(a) : std::string("null class name");
      auto found = a ? classes_.find(name) : classes_.end();
      if (found == classes_.end()) { Raise("java/lang/NoClassDefFoundError", name); s.gpr.x0.qword = 0; }
      else s.gpr.x0.qword = Local(found->second->object);
      return;
    }
    case 10: { auto *clazz = GetClass(a); s.gpr.x0.qword = clazz && !clazz->superclass.empty() ? Local(classes_.at(clazz->superclass)->object) : 0; return; }
    case 11: { auto *first = GetClass(a), *second = GetClass(b); s.gpr.x0.qword = first && second && Assignable(first->object->class_name, second->object->class_name); return; }
    case 13: { auto object = Get(a); if (!object || object->kind != Object::kThrowable) { IntResult(s, kError); return; } Current().exception = object; IntResult(s, kOk); return; }
    case 14: { auto *clazz = GetClass(a); if (!clazz) { IntResult(s, kError); return; } if(!Assignable(clazz->object->class_name,"java/lang/Throwable")){Raise("java/lang/IllegalArgumentException","ThrowNew requires a Throwable subclass");IntResult(s,kError);return;}Raise(clazz->object->class_name, b ? recomp::ReadGuestString(b) : "",b!=0); IntResult(s, kOk); return; }
    case 15: s.gpr.x0.qword = Local(Current().exception); return;
    case 16: if (Current().exception) std::fprintf(stderr, "%s\n", PendingException().c_str()); return;
    case 17: Current().exception.reset(); return;
    case 18: throw std::runtime_error(std::string("JNI FatalError: ") + (a ? recomp::ReadGuestString(a) : "null"));
    case 19: if (static_cast<int32_t>(a) < 0) { Raise("java/lang/IllegalArgumentException", "negative local capacity"); IntResult(s, kError); } else { Current().frames.emplace_back(); IntResult(s, kOk); } return;
    case 20: {
      auto &frames = Current().frames;
      if (frames.size() <= 1) { Raise("java/lang/IllegalStateException", "no local frame to pop"); s.gpr.x0.qword = 0; return; }
      auto result = Get(a, true); for (auto ref : frames.back()) references_.erase(ref); frames.pop_back(); s.gpr.x0.qword = Local(result); return;
    }
    case 21: s.gpr.x0.qword = Ref(a, 2); return;
    case 22: Delete(a, 2); return;
    case 23: Delete(a, 1); return;
    case 24: { auto first = Get(a, true), second = Get(b, true); s.gpr.x0.qword = first == second; return; }
    case 25: s.gpr.x0.qword = Ref(a, 1); return;
    case 26: if (static_cast<int32_t>(a) < 0) { Raise("java/lang/IllegalArgumentException", "negative local capacity"); IntResult(s, kError); } else IntResult(s, kOk); return;
    case 28: case 29: case 30: {MethodArguments args{};auto method=method_ids_.find(b);size_t count=method==method_ids_.end()?0:method->second->argument_types.size();s.gpr.x0.qword=Arguments(s,slot,count,args)?Construct(lock,a,b,args):0;return;}
    case 31: { auto object = Get(a); if (!object) { s.gpr.x0.qword = 0; return; } s.gpr.x0.qword = Local(classes_.at(object->kind == Object::kClass ? "java/lang/Class" : object->class_name)->object); return; }
    case 32: { auto *clazz = GetClass(b); auto object = Get(a, true); s.gpr.x0.qword = clazz && (!object || Assignable(object->kind == Object::kClass ? "java/lang/Class" : object->class_name, clazz->object->class_name)); return; }
    case 33: case 113: s.gpr.x0.qword = MethodId(a, reinterpret_cast<const char *>(b), reinterpret_cast<const char *>(c), slot == 113); return;
    case 34: case 35: case 36: case 37: case 38: case 39: {
      std::array<addr_t,3> args{};auto method=method_ids_.find(b);size_t count=method==method_ids_.end()?0:method->second->argument_types.size();
      s.gpr.x0.qword=Arguments(s,slot>=37?slot-3:slot,count,args)?CallObject(lock,a,b,false,args,slot>=37?'Z':'L'):0;return;
    }
    case 61: case 62: case 63: {MethodArguments args{};auto method=method_ids_.find(b);size_t count=method==method_ids_.end()?0:method->second->argument_types.size();s.gpr.x0.qword=Arguments(s,slot-27,count,args)?CallObject(lock,a,b,false,args,'V'):0;return;}
    case 114: case 115: case 116: {
      std::array<addr_t, 3> args{};
      auto method=method_ids_.find(b);size_t count=method!=method_ids_.end()&&method->second->builtin==Method::kForName?3:0;
      s.gpr.x0.qword=Arguments(s,slot,count,args)?CallObject(lock,a,b,true,args):0;return;
    }
    case 94: case 144: s.gpr.x0.qword = FieldId(a, reinterpret_cast<const char *>(b), reinterpret_cast<const char *>(c), slot == 144); return;
    case 95: case 145: { auto target = FieldTarget(a, b, slot == 145, "object"); s.gpr.x0.qword = target ? Local(target->object_fields[b]) : 0; return; }
    case 100: case 150: { auto target = FieldTarget(a, b, slot == 150, "I"); IntResult(s, target ? static_cast<int32_t>(target->primitive_fields[b]) : 0); return; }
    case 104: case 154: {
      auto target = FieldTarget(a, b, slot == 154, "object"); if (!target) return;
      auto source = Get(c, true); if (c && !source) return;
      auto &signature = field_ids_.at(b)->signature;
      if (source && !Assignable(source->kind == Object::kClass ? "java/lang/Class" : source->class_name, signature.front()=='['?signature:signature.substr(1, signature.size() - 2))) { Raise("java/lang/IllegalArgumentException", "JNI object field value type mismatch"); return; }
      target->object_fields[b] = source; return;
    }
    case 109: case 159: { auto target = FieldTarget(a, b, slot == 159, "I"); if (target) target->primitive_fields[b] = static_cast<uint32_t>(c); return; }
    case 163: {
      auto length = static_cast<int32_t>(b);
      if (length < 0 || (length && !a)) { Raise("java/lang/IllegalArgumentException", "invalid UTF-16 input"); s.gpr.x0.qword = 0; return; }
      std::u16string text; for (int32_t i = 0; i < length; ++i) text.push_back(Read<char16_t>(a + i * 2)); s.gpr.x0.qword = NewString(text); return;
    }
    case 164: case 168: { auto object = String(a); IntResult(s, object ? static_cast<int32_t>(slot == 164 ? object->text.size() : Encode(object->text).size()) : 0); return; }
    case 165: case 224: {
      auto object = String(a); if (!object) { s.gpr.x0.qword = 0; return; }
      auto data = std::make_unique<std::u16string>(object->text); auto ptr = reinterpret_cast<addr_t>(data->data());
      char_leases_.emplace(ptr, CharLease{object, std::move(data)}); if (b) Write<uint8_t>(b, 1); s.gpr.x0.qword = ptr; return;
    }
    case 166: case 225: { auto object = String(a); auto lease = char_leases_.find(b); if (!object || lease == char_leases_.end() || lease->second.owner != object) Raise("java/lang/IllegalArgumentException", "invalid UTF-16 lease"); else recomp::WithGuestMemoryWrite(b, (lease->second.data->size() + 1) * 2, [&] { char_leases_.erase(lease); }); return; }
    case 167:
      try { s.gpr.x0.qword = NewString(Decode(reinterpret_cast<const char *>(a))); }
      catch (const std::invalid_argument &error) { Raise("java/lang/IllegalArgumentException", error.what()); s.gpr.x0.qword = 0; }
      return;
    case 169: {
      auto object = String(a); if (!object) { s.gpr.x0.qword = 0; return; }
      auto data = std::make_unique<std::string>(Encode(object->text)); auto ptr = reinterpret_cast<addr_t>(data->c_str());
      utf_leases_.emplace(ptr, UtfLease{object, std::move(data)}); if (b) Write<uint8_t>(b, 1); s.gpr.x0.qword = ptr; return;
    }
    case 170: { auto object = String(a); auto lease = utf_leases_.find(b); if (!object || lease == utf_leases_.end() || lease->second.owner != object) Raise("java/lang/IllegalArgumentException", "invalid UTF-8 lease"); else recomp::WithGuestMemoryWrite(b, lease->second.data->size() + 1, [&] { utf_leases_.erase(lease); }); return; }
    case 215: IntResult(s, Register(a, reinterpret_cast<const NativeMethod *>(b), static_cast<int32_t>(c))); return;
    case 216: { auto *clazz = GetClass(a); if (!clazz) { IntResult(s, kError); return; } for (auto &method : clazz->methods) method.second->native = 0; IntResult(s, kOk); return; }
    case 219: if (!a) { IntResult(s, kError); return; } Write(a, VmAddress()); IntResult(s, kOk); return;
    case 220: case 221: {
      auto object = String(a); auto start = static_cast<int32_t>(b), length = static_cast<int32_t>(c);
      if (!object) return;
      if (start < 0 || length < 0 || static_cast<size_t>(start) > object->text.size() || static_cast<size_t>(length) > object->text.size() - start || (length && !d)) { Raise("java/lang/StringIndexOutOfBoundsException", "invalid string region"); return; }
      auto region = object->text.substr(start, length);
      if (slot == 220) recomp::WriteGuestMemory(d, region.data(), region.size() * 2);
      else { auto encoded = Encode(region); recomp::WriteGuestMemory(d, encoded.data(), encoded.size()); }
      return;
    }
    case 226: s.gpr.x0.qword = Ref(a, 3); return;
    case 227: Delete(a, 3); return;
    case 228: s.gpr.x0.qword = Current().exception != nullptr; return;
    case 232: { auto ref = references_.find(a); s.gpr.x0.qword = ref == references_.end() ? 0 : ref->second.kind; return; }
    default: throw std::runtime_error("unsupported JNIEnv slot " + std::to_string(slot));
  }
}

void Host::Install(recomp::Runtime &runtime) {
  std::lock_guard lock(mutex_);
  if (installed_) throw std::logic_error("JNI host already installed");
  auto protect = [](auto fn) {
    return [fn](State &state) {
      try { fn(state); }
      catch (const std::exception &error) { std::fprintf(stderr, "JNI host: %s\n", error.what()); std::abort(); }
    };
  };
  for (size_t slot = 4; slot < env_table_.size(); ++slot)
    runtime.AddImport(EnvMarker(slot), protect([this, slot](State &s) { InvokeEnv(slot, s); }));
  for (size_t slot = 3; slot < vm_table_.size(); ++slot)
    runtime.AddImport(VmMarker(slot), protect([this, slot](State &s) { InvokeVm(slot, s); }));
  installed_ = true;
}
}  // namespace bunker::jni
