#pragma once
#include "jni_host.h"
#include "apk_assets.h"
namespace bunker::windows {
// Installs the evidenced AssetManager/Scanner subset and returns an initialized
// local AssetManager. A missing reader is explicit unsupported configuration.
addr_t CreateJavaAssets(jni::Host &host,std::shared_ptr<ApkAssets> reader);
}
