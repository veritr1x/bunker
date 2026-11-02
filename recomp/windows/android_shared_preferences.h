#pragma once
#include "jni_host.h"
#include <map>
#include <set>
#include <optional>

namespace bunker::windows {
// Strings/keys are exact UTF16, ordered case-sensitively inside the snapshot.
// Float is binary32 bits, not a numerically converted integer.
struct SharedPreferenceValue {
  enum Kind : uint8_t { String=1, Integer=2, Float=3, Boolean=4, Long=5, StringSet=6 } kind=String;
  std::u16string text;
  uint64_t bits=0;
  std::set<std::u16string> strings;
};
using SharedPreferencesSnapshot=std::map<std::u16string,SharedPreferenceValue>;
struct SharedPreferencesBackend {
  // Native storage only: callbacks must not recursively apply/open the same
  // store or drive JNI. No Host/adapter/store mutex is held during either call.
  // nullopt means an actually observed missing store. Errors must throw.
  std::function<std::optional<SharedPreferencesSnapshot>(const std::u16string&)> read;
  // One complete snapshot. Zero means real persistent success. Nonzero is a
  // native error, retained for the explicit completion verification boundary.
  std::function<uint32_t(const std::u16string&,const SharedPreferencesSnapshot&)> write;
};
class AndroidSharedPreferences {
 public:
  AndroidSharedPreferences(jni::Host&,addr_t actual_context,std::u16string package,SharedPreferencesBackend);
  ~AndroidSharedPreferences();
  AndroidSharedPreferences(const AndroidSharedPreferences&)=delete;
  AndroidSharedPreferences&operator=(const AndroidSharedPreferences&)=delete;
  // After callers quiesce, before normal successful completion. Does no write.
  void CheckPersistence() const;
 private:
  struct State;
  std::shared_ptr<State> state_;
};
}
