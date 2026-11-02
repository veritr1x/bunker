#pragma once

#include <array>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <string>
#include <thread>
#include <typeindex>
#include <vector>

#include "../whole/runtime.h"

namespace bunker::jni {
constexpr int32_t kOk = 0, kError = -1, kDetached = -2, kVersionError = -3;
constexpr int32_t kVersion16 = 0x00010006;
constexpr size_t kEnvSlots = 233, kVmSlots = 8;
struct NativeMethod { addr_t name, signature, entry; };
static_assert(sizeof(NativeMethod) == 24);
struct MethodDeclaration {
  std::string name, signature;
  bool is_static = false, is_native = false;
};

// A checked host for explicitly declared Java classes. This is not a Java
// interpreter: unsupported JNI calls fail instead of returning fake success.
class Host {
  struct Object;
  class ProviderLock;
 public:
  // Descriptor-checked reference/jint/jlong/jfloat arguments. I/F use low32
  // bits (F is raw binary32, not a numeric integer); J retains all64 bits.
  // Reference arrays retain their full descriptor. Three Java arguments max;
  // actual AAPCS64 GP/FP allocation is separate. D/primitive arrays unsupported.
  using MethodArguments=std::array<addr_t,3>;
  // Strong references used inside host-supplied Java object state. They are
  // opaque C++ graph edges, not guest JNI handles or global-reference slots.
  class ObjectValue { friend class Host; const Host *owner_=nullptr;std::shared_ptr<Object> object_; };
  explicit Host(std::function<bool(addr_t)> native_entry_validator,
                addr_t marker_base = 0x7ff000000000ULL);
  ~Host();
  Host(const Host &) = delete;
  Host &operator=(const Host &) = delete;
  void Install(recomp::Runtime &runtime);
  // Application metadata defaults to an uninitialized application-loader class.
  // bootstrap=true is for initialized framework classes implemented by this host.
  void DefineClass(const std::string &name, std::vector<MethodDeclaration> methods = {},
                   const std::string &superclass = "java/lang/Object", bool bootstrap = false,
                   std::vector<std::string> interfaces = {});
  // A genuine interface has no superclass and cannot be instantiated. This
  // catalog does not invent implementing classes or execute default bodies.
  void DefineInterface(const std::string &name, std::vector<MethodDeclaration> methods,
                       bool bootstrap = true);
  // Only call after the host has supplied the class's initialization effects.
  // A metadata declaration alone does not execute Java <clinit>.
  void MarkClassInitialized(const std::string &name);
  // External object/boolean/void handlers run without the provider lock in an
  // owned local frame. Receiver/reference arguments are borrowed callee locals;
  // returning an object produces one fresh caller local. Temporary locals and
  // unbalanced user frames expire on return, including exceptional returns.
  void DefineObjectMethod(const std::string &class_name, const std::string &name,
                          const std::string &signature, std::function<addr_t(addr_t)> handler);
  void DefineObjectMethod(const std::string &class_name,const std::string &name,const std::string &signature,
                          std::function<addr_t(addr_t,const MethodArguments&)> handler);
  void DefineStaticObjectMethod(const std::string &owner,const std::string &name,const std::string &signature,
                                std::function<addr_t(addr_t,const MethodArguments&)> handler);
  void BindStaticObjectMethod(const std::string &owner,const std::string &name,const std::string &signature,
                              std::function<addr_t(addr_t,const MethodArguments&)> handler);
  void BindStaticVoidMethod(const std::string &owner,const std::string &name,const std::string &signature,
                            std::function<void(addr_t,const MethodArguments&)> handler);
  void DefineBooleanMethod(const std::string &class_name,const std::string &name,const std::string &signature,
                           std::function<bool(addr_t,const MethodArguments&)> handler);
  void DefineIntMethod(const std::string &owner,const std::string &name,const std::string &signature,
                       std::function<int32_t(addr_t,const MethodArguments&)> handler);
  void DefineStaticIntMethod(const std::string &owner,const std::string &name,const std::string &signature,
                             std::function<int32_t(addr_t,const MethodArguments&)> handler);
  // The callback returns exact binary32 bits; never numerically cast bits to
  // float. The guest result is S0. Scalar callbacks share owned-frame cleanup.
  void DefineFloatBitsMethod(const std::string &owner,const std::string &name,const std::string &signature,
                             std::function<uint32_t(addr_t,const MethodArguments&)> handler);
  void DefineStaticFloatBitsMethod(const std::string &owner,const std::string &name,const std::string &signature,
                                   std::function<uint32_t(addr_t,const MethodArguments&)> handler);
  // Attach a supplied body to an existing, unimplemented nonnative declaration.
  // DefineBooleanMethod retains its duplicate-declaration rejection.
  void BindBooleanMethod(const std::string &class_name,const std::string &name,const std::string &signature,
                         std::function<bool(addr_t,const MethodArguments&)> handler);
  void DefineVoidMethod(const std::string &owner,const std::string &name,const std::string &signature,
                        std::function<void(addr_t,const MethodArguments&)> handler);
  // Factories use the same owned frame and borrowed argument rules. Return a
  // non-null NewInstance/NewHostInstance of the exact owner, or a Java exception.
  // One fresh caller-local result survives cleanup; builtin StringBuilder is
  // separate.
  void DefineConstructor(const std::string &owner,const std::string &signature,std::function<addr_t(const MethodArguments&)> factory);
  void ThrowException(const std::string &type,const std::u16string &message);
  void ThrowException(const std::string &type);
  void DefineField(const std::string &class_name, const std::string &name,
                   const std::string &signature, bool is_static = false);
  addr_t NewString(const std::u16string &value);
  addr_t NewInstance(const std::string &class_name);
  template<class T> addr_t NewHostInstance(const std::string &name,std::shared_ptr<T> state){return HostInstance(name,typeid(T),std::move(state));}
  template<class T> std::shared_ptr<T> ReadHostState(addr_t reference){return std::static_pointer_cast<T>(HostState(reference,typeid(T)));}
  ObjectValue CaptureValue(addr_t reference);
  addr_t LocalValue(const ObjectValue &value);
  std::optional<std::u16string> StringValue(addr_t reference);
  // Exact metadata name (including array descriptors), with no Java execution.
  std::optional<std::string> ClassNameValue(addr_t reference);
  addr_t NewGlobalReference(addr_t reference);
  addr_t NewLocalReference(addr_t reference);
  void DeleteGlobalReference(addr_t reference);
  void DeleteLocalReference(addr_t reference);
  void SetObjectFieldValue(addr_t object, const std::string &name, const std::string &signature, addr_t value);
  addr_t GetObjectFieldValue(addr_t object, const std::string &name, const std::string &signature);
  void SetIntFieldValue(addr_t object, const std::string &name, int32_t value);
  addr_t VmAddress() const { return reinterpret_cast<addr_t>(&vm_word_); }
  addr_t EnvAddress();
  addr_t VmMarker(size_t slot) const;
  addr_t EnvMarker(size_t slot) const;
  void InvokeVm(size_t slot, State &state);
  void InvokeEnv(size_t slot, State &state);
  addr_t NativeEntry(const std::string &class_name, const std::string &name,
                     const std::string &signature) const;
  size_t NativeCount(const std::string &class_name) const;
  std::string PendingException();
  void ClearException();

 private:
  struct Reference;
  struct Method;
  struct Field;
  struct Class;
  struct Thread;
  struct UtfLease;
  struct CharLease;
  Thread &Current(bool attach = false);
  void RequireEnv(addr_t address);
  addr_t HostInstance(const std::string &name,std::type_index type,std::shared_ptr<void> state);
  std::shared_ptr<void> HostState(addr_t reference,std::type_index type);
  void DefineHandler(const std::string &owner,const std::string &name,const std::string &signature,char result,
                     std::function<addr_t(addr_t,const MethodArguments&)> handler,bool is_static=false,bool bind_existing=false);
  void Raise(const std::string &type, const std::string &message, bool message_present = true);
  addr_t Local(const std::shared_ptr<Object> &object);
  std::shared_ptr<Object> Get(addr_t reference, bool allow_null = false);
  std::shared_ptr<Object> String(addr_t reference);
  Class *GetClass(addr_t reference);
  Class *FindReferenceArrayClass(const std::string &name);
  addr_t ObjectClass(const std::shared_ptr<Object> &object);
  void RetireReference(addr_t reference);
  void RetireObject(std::shared_ptr<Object> &object);
  void Delete(addr_t reference, unsigned kind);
  addr_t Ref(addr_t reference, unsigned kind);
  addr_t MethodId(addr_t clazz, const char *name, const char *signature, bool is_static);
  Field *LookupField(const std::string &class_name, const char *name, const char *signature, bool is_static);
  addr_t FieldId(addr_t clazz, const char *name, const char *signature, bool is_static);
  std::shared_ptr<Object> FieldTarget(addr_t object, addr_t field, bool is_static, const std::string &signature_kind);
  bool Assignable(const std::string &actual, const std::string &expected) const;
  addr_t CallObject(ProviderLock &lock, addr_t object, addr_t method, bool is_static = false,
                    MethodArguments arguments = {},char expected_result = 'L',
                    State *argument_state=nullptr,size_t argument_form=0);
  addr_t Construct(ProviderLock &lock,addr_t clazz, addr_t method,const MethodArguments &arguments);
  addr_t InvokeHandler(ProviderLock&,std::shared_ptr<Object> receiver,const Method&,const MethodArguments&,char result);
  void DrainCallbackFrame(ProviderLock&,size_t depth,std::shared_ptr<Object> &exception);
  bool ValidateArguments(const Method &method,const MethodArguments &arguments);
  bool Arguments(State &state,size_t slot,size_t count,MethodArguments &arguments,const Method *method);
  int32_t Register(addr_t clazz, const NativeMethod *methods, int32_t count);

  mutable std::recursive_mutex mutex_;
  std::array<addr_t, kEnvSlots> env_table_{};
  std::array<addr_t, kVmSlots> vm_table_{};
  addr_t vm_word_ = 0, marker_base_;
  bool installed_ = false;
  addr_t next_reference_ = 0x7ff100000000ULL, next_method_ = 0x7ff200000000ULL;
  uint32_t next_identity_hash_ = 1;
  std::function<bool(addr_t)> native_entry_validator_;
  mutable std::map<uint64_t, std::unique_ptr<Thread>> threads_;
  std::map<std::string, std::unique_ptr<Class>> classes_;
  std::map<addr_t, Reference> references_;
  std::map<addr_t, Method *> method_ids_;
  std::map<addr_t, Field *> field_ids_;
  std::map<addr_t, UtfLease> utf_leases_;
  std::map<addr_t, CharLease> char_leases_;
  std::shared_ptr<Object> application_loader_;
  std::shared_ptr<Object> bootstrap_loader_;
  std::shared_ptr<Object> empty_string_;
};
}  // namespace bunker::jni
