#pragma once

#include <array>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
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
 public:
  explicit Host(std::function<bool(addr_t)> native_entry_validator,
                addr_t marker_base = 0x7ff000000000ULL);
  ~Host();
  Host(const Host &) = delete;
  Host &operator=(const Host &) = delete;
  void Install(recomp::Runtime &runtime);
  // Application metadata defaults to an uninitialized application-loader class.
  // bootstrap=true is for initialized framework classes implemented by this host.
  void DefineClass(const std::string &name, std::vector<MethodDeclaration> methods = {},
                   const std::string &superclass = "java/lang/Object", bool bootstrap = false);
  // Only call after the host has supplied the class's initialization effects.
  // A metadata declaration alone does not execute Java <clinit>.
  void MarkClassInitialized(const std::string &name);
  void DefineObjectMethod(const std::string &class_name, const std::string &name,
                          const std::string &signature, std::function<addr_t(addr_t)> handler);
  void DefineField(const std::string &class_name, const std::string &name,
                   const std::string &signature, bool is_static = false);
  addr_t NewString(const std::u16string &value);
  addr_t NewInstance(const std::string &class_name);
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
  struct Object;
  struct Reference;
  struct Method;
  struct Field;
  struct Class;
  struct Thread;
  struct UtfLease;
  struct CharLease;
  Thread &Current(bool attach = false);
  void RequireEnv(addr_t address);
  void Raise(const std::string &type, const std::string &message);
  addr_t Local(const std::shared_ptr<Object> &object);
  std::shared_ptr<Object> Get(addr_t reference, bool allow_null = false);
  std::shared_ptr<Object> String(addr_t reference);
  Class *GetClass(addr_t reference);
  void Delete(addr_t reference, unsigned kind);
  addr_t Ref(addr_t reference, unsigned kind);
  addr_t MethodId(addr_t clazz, const char *name, const char *signature, bool is_static);
  Field *LookupField(const std::string &class_name, const char *name, const char *signature, bool is_static);
  addr_t FieldId(addr_t clazz, const char *name, const char *signature, bool is_static);
  std::shared_ptr<Object> FieldTarget(addr_t object, addr_t field, bool is_static, const std::string &signature_kind);
  bool Assignable(const std::string &actual, const std::string &expected) const;
  addr_t CallObject(std::unique_lock<std::recursive_mutex> &lock, addr_t object, addr_t method, bool is_static = false,
                    const std::array<addr_t, 3> &arguments = {});
  int32_t Register(addr_t clazz, const NativeMethod *methods, int32_t count);

  mutable std::recursive_mutex mutex_;
  std::array<addr_t, kEnvSlots> env_table_{};
  std::array<addr_t, kVmSlots> vm_table_{};
  addr_t vm_word_ = 0, marker_base_;
  bool installed_ = false;
  addr_t next_reference_ = 0x7ff100000000ULL, next_method_ = 0x7ff200000000ULL;
  std::function<bool(addr_t)> native_entry_validator_;
  std::map<uint64_t, std::unique_ptr<Thread>> threads_;
  std::map<std::string, std::unique_ptr<Class>> classes_;
  std::map<addr_t, Reference> references_;
  std::map<addr_t, Method *> method_ids_;
  std::map<addr_t, Field *> field_ids_;
  std::map<addr_t, UtfLease> utf_leases_;
  std::map<addr_t, CharLease> char_leases_;
  std::shared_ptr<Object> application_loader_;
  std::shared_ptr<Object> bootstrap_loader_;
};
}  // namespace bunker::jni
