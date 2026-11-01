#include "jni_host.h"
#include <jni.h>

#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <thread>

using bunker::jni::Host;
static_assert(sizeof(void *) == 8);
static_assert(sizeof(JNINativeInterface) == bunker::jni::kEnvSlots * 8);
static_assert(sizeof(JNIInvokeInterface) == bunker::jni::kVmSlots * 8);
static_assert(offsetof(JNINativeInterface, FindClass) / 8 == 6);
static_assert(offsetof(JNINativeInterface, RegisterNatives) / 8 == 215);
static_assert(offsetof(JNINativeInterface, GetJavaVM) / 8 == 219);
static_assert(offsetof(JNINativeInterface, GetObjectRefType) / 8 == 232);
static_assert(offsetof(JNIInvokeInterface, AttachCurrentThread) / 8 == 4);
static_assert(offsetof(JNIInvokeInterface, GetEnv) / 8 == 6);

int main() {
  unsigned checks = 0;
  auto require = [&](bool condition, const char *message) {
    if (!condition) throw std::runtime_error(message);
    ++checks;
  };
  Host host([](addr_t address) { return address == 0x400009ac || address == 0x40000b7c; });
  host.DefineClass("com/unity3d/player/NativeLoader", {{"load", "(Ljava/lang/String;)Z", true, true}, {"unload", "()Z", true, true}});
  auto env = host.EnvAddress();
  auto call = [&](size_t slot, addr_t a = 0, addr_t b = 0, addr_t c = 0, addr_t d = 0) {
    State state{}; state.gpr.x0.qword = host.EnvAddress(); state.gpr.x1.qword = a; state.gpr.x2.qword = b; state.gpr.x3.qword = c; state.gpr.x4.qword = d;
    host.InvokeEnv(slot, state); return state.gpr.x0.qword;
  };
  auto vm = [&](size_t slot, addr_t a = 0, addr_t b = 0) {
    State state{}; state.gpr.x0.qword = host.VmAddress(); state.gpr.x1.qword = a; state.gpr.x2.qword = b;
    host.InvokeVm(slot, state); return static_cast<int32_t>(state.gpr.x0.dword);
  };
  require(*reinterpret_cast<addr_t *>(host.VmAddress()) != 0, "JavaVM pointer-word layout");
  auto table = *reinterpret_cast<const addr_t **>(env);
  require(table[6] == host.EnvMarker(6) && table[215] == host.EnvMarker(215), "JNI marker table slots");
  addr_t received = 0;
  require(vm(6, reinterpret_cast<addr_t>(&received), JNI_VERSION_1_6) == JNI_OK && received == env, "GetEnv current thread");
  require(vm(6, reinterpret_cast<addr_t>(&received), 0x10008) == JNI_EVERSION && received == 0, "GetEnv version rejection");
  received = 0;
  require(call(219, reinterpret_cast<addr_t>(&received)) == 0 && received == host.VmAddress(), "GetJavaVM");
  auto clazz = call(6, reinterpret_cast<addr_t>("com/unity3d/player/NativeLoader"));
  require(clazz && call(232, clazz) == JNILocalRefType, "FindClass local handle");
  require(call(113, clazz, reinterpret_cast<addr_t>("load"), reinterpret_cast<addr_t>("(Ljava/lang/String;)Z")) != 0, "static method resolution");
  require(call(33, clazz, reinterpret_cast<addr_t>("load"), reinterpret_cast<addr_t>("(Ljava/lang/String;)Z")) == 0 && !host.PendingException().empty(), "static/nonstatic mismatch");
  host.ClearException();
  bunker::jni::NativeMethod methods[] = {{reinterpret_cast<addr_t>("load"), reinterpret_cast<addr_t>("(Ljava/lang/String;)Z"), 0x400009ac},
                                       {reinterpret_cast<addr_t>("unload"), reinterpret_cast<addr_t>("()Z"), 0xbad}};
  require(static_cast<int32_t>(call(215, clazz, reinterpret_cast<addr_t>(methods), 2)) == JNI_ERR && host.NativeCount("com/unity3d/player/NativeLoader") == 0, "native registration is transactional");
  host.ClearException(); methods[1].entry = 0x40000b7c;
  require(call(215, clazz, reinterpret_cast<addr_t>(methods), 2) == JNI_OK, "native registration");
  require(host.NativeEntry("com/unity3d/player/NativeLoader", "load", "(Ljava/lang/String;)Z") == 0x400009ac && host.NativeCount("com/unity3d/player/NativeLoader") == 2, "native registry addresses");
  auto global_class = call(21, clazz);
  require(call(232, global_class) == JNIGlobalRefType && call(24, clazz, global_class), "global identity");
  call(23, global_class);
  require(!host.PendingException().empty() && call(232, global_class) == JNIGlobalRefType, "wrong reference deletion rejected");
  host.ClearException(); call(22, global_class);
  require(call(232, global_class) == JNIInvalidRefType, "global deletion");
  const std::u16string text{u'A', 0, 0xd83d, 0xde00, 0xe9};
  auto string = host.NewString(text);
  const char encoded[] = "A\xc0\x80\xed\xa0\xbd\xed\xb8\x80\xc3\xa9";
  require(call(164, string) == 5 && call(168, string) == 11, "UTF16 and modified UTF8 lengths");
  uint8_t copied = 0;
  auto chars = call(169, string, reinterpret_cast<addr_t>(&copied));
  require(copied && !std::strcmp(reinterpret_cast<const char *>(chars), encoded), "modified UTF8 encoding");
  call(170, string, chars);
  auto decoded = call(167, reinterpret_cast<addr_t>(encoded));
  auto utf16 = call(165, decoded, reinterpret_cast<addr_t>(&copied));
  require(!std::memcmp(reinterpret_cast<const void *>(utf16), text.data(), text.size() * 2), "modified UTF8 decoding");
  call(166, decoded, utf16);
  require(call(167, reinterpret_cast<addr_t>("\xe0\x80\x80")) == 0 && !host.PendingException().empty(), "noncanonical UTF8 rejected");
  host.ClearException();
  require(call(167, reinterpret_cast<addr_t>("\xf0\x9f\x98\x80")) == 0 && !host.PendingException().empty(), "four-byte UTF8 rejected by modified UTF8 API");
  host.ClearException();
  char16_t region[4] = {1, 1, 1, 1};
  call(220, string, 1, 3, reinterpret_cast<addr_t>(region));
  require(region[0] == 0 && region[1] == 0xd83d && region[2] == 0xde00 && region[3] == 1, "UTF16 region bounds");
  call(220, string, 4, 2, reinterpret_cast<addr_t>(region));
  require(!host.PendingException().empty(), "bad string region raises exception"); host.ClearException();
  require(call(19, 4) == 0, "PushLocalFrame");
  auto frame_string = host.NewString(u"frame"), frame_global = call(21, frame_string);
  auto escaped = call(20, frame_string);
  require(escaped && escaped != frame_string && call(232, frame_string) == 0 && call(24, escaped, frame_global), "PopLocalFrame escapes exactly one reference");
  call(23, escaped); call(22, frame_global);
  auto ephemeral = host.NewString(u"ephemeral"), weak = call(226, ephemeral);
  require(call(232, weak) == JNIWeakGlobalRefType, "weak reference type");
  call(23, ephemeral);
  require(call(24, weak, 0) && call(25, weak) == 0, "expired weak reference clears");
  call(227, weak);
  require(call(6, reinterpret_cast<addr_t>("does/not/Exist")) == 0 && call(228), "missing class raises exception");
  auto exception = call(15); require(exception && call(232, exception) == JNILocalRefType, "ExceptionOccurred creates local reference");
  call(17); require(!call(228), "ExceptionClear");
  auto global_string = call(21, string);
  std::thread thread([&] {
    addr_t own_env = 123;
    require(vm(6, reinterpret_cast<addr_t>(&own_env), JNI_VERSION_1_6) == JNI_EDETACHED && own_env == 0, "unattached worker GetEnv");
    require(vm(4, reinterpret_cast<addr_t>(&own_env)) == JNI_OK && own_env && own_env != env, "AttachCurrentThread distinct env");
    require(call(164, global_string) == 5, "global reference visible across threads");
    require(call(164, string) == 0 && !host.PendingException().empty(), "local reference rejected across threads");
    host.ClearException(); require(vm(5) == JNI_OK && !host.EnvAddress(), "DetachCurrentThread");
  });
  thread.join();
  bool rejected = false;
  try { call(61); } catch (const std::runtime_error &) { rejected = true; }
  require(rejected, "unsupported JNI call must fail explicitly");
  recomp::Runtime runtime;
  host.Install(runtime);
  State marker{}; marker.gpr.x0.qword = env; marker.gpr.x30.qword = 0xfeedffff;
  runtime.Run(marker, host.EnvMarker(4));
  require(marker.gpr.x0.qword == JNI_VERSION_1_6 && marker.gpr.pc.qword == 0xfeedffff, "Runtime marker dispatch");
  require(call(216, clazz) == 0 && host.NativeCount("com/unity3d/player/NativeLoader") == 0, "UnregisterNatives");
  std::printf("JNI host: %u checks passed (NDK table layout, native registration, strings, references, exceptions, threads, runtime markers).\n", checks);
}
