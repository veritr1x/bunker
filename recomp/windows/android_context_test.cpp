#include "android_context.h"
#include <jni.h>
#include <cstdio>
#include <cstring>
#include <stdexcept>

static_assert(offsetof(JNINativeInterface, CallObjectMethodA) / 8 == 36);
static_assert(offsetof(JNINativeInterface, GetFieldID) / 8 == 94);
static_assert(offsetof(JNINativeInterface, GetObjectField) / 8 == 95);
static_assert(offsetof(JNINativeInterface, GetIntField) / 8 == 100);
static_assert(offsetof(JNINativeInterface, SetObjectField) / 8 == 104);
static_assert(offsetof(JNINativeInterface, SetIntField) / 8 == 109);

int main() {
  using namespace bunker;
  unsigned checks = 0;
  auto require = [&](bool condition, const char *message) { if (!condition) throw std::runtime_error(message); ++checks; };
  jni::Host host([](addr_t) { return false; });
  windows::AndroidContext context(host, {u"test.package", u"/data/app/test/base.apk", u"/data/app/test/lib/arm64", u"/data/user/0/test.package", 33, 0x10});
  auto call = [&](size_t slot, addr_t a = 0, addr_t b = 0, addr_t c = 0) {
    State state{}; state.gpr.x0.qword = host.EnvAddress(); state.gpr.x1.qword = a; state.gpr.x2.qword = b; state.gpr.x3.qword = c;
    host.InvokeEnv(slot, state); return state.gpr.x0.qword;
  };
  auto find = [&](const char *name) { return call(6, reinterpret_cast<addr_t>(name)); };
  auto method = [&](addr_t clazz, const char *name, const char *signature) { return call(33, clazz, reinterpret_cast<addr_t>(name), reinterpret_cast<addr_t>(signature)); };
  auto field = [&](addr_t clazz, const char *name, const char *signature) { return call(94, clazz, reinterpret_cast<addr_t>(name), reinterpret_cast<addr_t>(signature)); };
  auto activity = context.Activity(), activity_class = call(31, activity);
  auto info_method = method(activity_class, "getApplicationInfo", "()Landroid/content/pm/ApplicationInfo;");
  require(info_method != 0, "inherited Context method ID");
  auto info = call(36, activity, info_method), info_class = call(31, info);
  require(info && call(24, info_class, find("android/content/pm/ApplicationInfo")), "getApplicationInfo receiver/result type");
  auto source_id = field(info_class, "sourceDir", "Ljava/lang/String;");
  auto source = call(95, info, source_id), bytes = call(169, source);
  require(bytes && !std::strcmp(reinterpret_cast<const char *>(bytes), "/data/app/test/base.apk"), "ApplicationInfo.sourceDir actual configured value"); call(170, source, bytes);
  require(call(100, info, field(info_class, "targetSdkVersion", "I")) == 33 && call(100, info, field(info_class, "flags", "I")) == 0x10, "ApplicationInfo primitive fields");
  auto assets = call(34, activity, method(activity_class, "getAssets", "()Landroid/content/res/AssetManager;"));
  require(assets && call(32, assets, find("android/content/res/AssetManager")), "getAssets typed object");
  auto package = call(35, activity, method(activity_class, "getPackageName", "()Ljava/lang/String;"));
  bytes = call(169, package); require(!std::strcmp(reinterpret_cast<const char *>(bytes), "test.package"), "getPackageName value"); call(170, package, bytes);
  auto application = call(36, activity, method(activity_class, "getApplicationContext", "()Landroid/content/Context;"));
  require(call(24, activity, application), "application-context object identity");
  auto wrong = host.NewString(u"not an ApplicationInfo"); call(95, wrong, source_id);
  require(!host.PendingException().empty(), "field receiver mismatch rejected"); host.ClearException();
  require(field(info_class, "missing", "I") == 0 && !host.PendingException().empty(), "unknown field rejected"); host.ClearException();
  call(100, info, source_id); require(!host.PendingException().empty(), "object/int field kind mismatch rejected"); host.ClearException();
  call(104, info, source_id, assets); require(!host.PendingException().empty(), "wrong object field type rejected"); host.ClearException();
  auto updated = host.NewString(u"/updated/base.apk"); call(104, info, source_id, updated);
  host.DeleteLocalReference(updated);
  source = call(95, info, source_id); bytes = call(169, source);
  require(bytes && !std::strcmp(reinterpret_cast<const char *>(bytes), "/updated/base.apk"), "object field retains strong ownership after local deletion"); call(170, source, bytes);
  auto open_method=method(find("android/content/res/AssetManager"),"open","(Ljava/lang/String;)Ljava/io/InputStream;");
  require(open_method&&!call(34,assets,open_method,host.NewString(u"bin/Data/boot.config"))&&host.PendingException().find("UnsupportedOperationException")!=std::string::npos,"unconfigured APK asset reader cannot fabricate a stream");host.ClearException();
  require(!host.PendingException().size(), "catalog leaves no pending exception");
  std::printf("Android context JNI catalog: %u checks passed.\n", checks);
}
