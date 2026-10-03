#!/usr/bin/env python3
"""Write LunarDevice.xcodeproj: provisioning placeholder plus UI-test controller.

Targets:
  Provision    app with the game's bundle ID; built (never installed) so Xcode
               creates a development profile for this device.
  ControlHost  small app that hosts the UI-test runner.
  Control      UI tests that launch and tap the installed game.
"""
from pathlib import Path
import hashlib

HERE = Path(__file__).resolve().parent


def oid(name):
    return hashlib.sha1(name.encode()).hexdigest()[:24].upper()


def config(name, settings):
    body = "".join(f"\t\t\t\t{k} = {v};\n" for k, v in sorted(settings.items()))
    return f"\t\t{oid('cfg' + name)} = {{isa = XCBuildConfiguration; buildSettings = {{\n{body}\t\t\t}}; name = Debug; }};\n"


COMMON = {
    "CODE_SIGN_STYLE": "Automatic", "IPHONEOS_DEPLOYMENT_TARGET": "15.0", "SDKROOT": "iphoneos",
    "TARGETED_DEVICE_FAMILY": '"1,2"', "GENERATE_INFOPLIST_FILE": "YES", "CLANG_ENABLE_OBJC_ARC": "YES", "CLANG_ENABLE_MODULES": "YES",
    "DEVELOPMENT_TEAM": '"$(LUNAR_TEAM)"', "CURRENT_PROJECT_VERSION": "1", "MARKETING_VERSION": "1.0",
}
TARGETS = [
    ("Provision", "com.apple.product-type.application", "app", "Provision/main.m",
     {"PRODUCT_BUNDLE_IDENTIFIER": '"$(LUNAR_BUNDLE_ID)"', "PRODUCT_NAME": "Provision", "INFOPLIST_KEY_UILaunchScreen_Generation": "YES"}),
    ("ControlHost", "com.apple.product-type.application", "app", "ControlHost/main.m",
     {"PRODUCT_BUNDLE_IDENTIFIER": '"$(LUNAR_BUNDLE_ID).controlhost"', "PRODUCT_NAME": "ControlHost", "INFOPLIST_KEY_UILaunchScreen_Generation": "YES"}),
    ("Control", "com.apple.product-type.bundle.ui-testing", "xctest", "Control/ControlTests.m",
     {"PRODUCT_BUNDLE_IDENTIFIER": '"$(LUNAR_BUNDLE_ID).control"', "PRODUCT_NAME": "Control", "TEST_TARGET_NAME": "ControlHost"}),
]


def main():
    objects = []
    group_children = []
    product_children = []
    target_ids = []
    for name, kind, extension, source, settings in TARGETS:
        file_ref, build_file, product = oid("src" + name), oid("bf" + name), oid("prod" + name)
        sources, frameworks = oid("phase-src" + name), oid("phase-fw" + name)
        target, configs = oid("target" + name), oid("list" + name)
        objects.append(f"\t\t{file_ref} = {{isa = PBXFileReference; lastKnownFileType = sourcecode.c.objc; path = {source}; sourceTree = \"<group>\"; }};\n")
        product_type = "wrapper.application" if extension == "app" else "wrapper.cfbundle"
        objects.append(f"\t\t{product} = {{isa = PBXFileReference; explicitFileType = {product_type}; includeInIndex = 0; path = {name}.{extension}; sourceTree = BUILT_PRODUCTS_DIR; }};\n")
        objects.append(f"\t\t{build_file} = {{isa = PBXBuildFile; fileRef = {file_ref}; }};\n")
        objects.append(f"\t\t{sources} = {{isa = PBXSourcesBuildPhase; buildActionMask = 2147483647; files = ({build_file}, ); runOnlyForDeploymentPostprocessing = 0; }};\n")
        objects.append(f"\t\t{frameworks} = {{isa = PBXFrameworksBuildPhase; buildActionMask = 2147483647; files = (); runOnlyForDeploymentPostprocessing = 0; }};\n")
        objects.append(config(name, {**COMMON, **settings}))
        objects.append(f"\t\t{configs} = {{isa = XCConfigurationList; buildConfigurations = ({oid('cfg' + name)}, ); defaultConfigurationIsVisible = 0; defaultConfigurationName = Debug; }};\n")
        dependencies = ""
        if name == "Control":
            proxy, dependency = oid("proxy"), oid("dependency")
            objects.append(f"\t\t{proxy} = {{isa = PBXContainerItemProxy; containerPortal = {oid('project')}; proxyType = 1; remoteGlobalIDString = {oid('targetControlHost')}; remoteInfo = ControlHost; }};\n")
            objects.append(f"\t\t{dependency} = {{isa = PBXTargetDependency; target = {oid('targetControlHost')}; targetProxy = {proxy}; }};\n")
            dependencies = f"{dependency}, "
        objects.append(f"\t\t{target} = {{isa = PBXNativeTarget; buildConfigurationList = {configs}; buildPhases = ({sources}, {frameworks}, ); buildRules = (); "
                       f"dependencies = ({dependencies}); name = {name}; productName = {name}; productReference = {product}; productType = \"{kind}\"; }};\n")
        group_children.append(file_ref)
        product_children.append(product)
        target_ids.append(target)
    products, main = oid("products"), oid("main")
    objects.append(f"\t\t{products} = {{isa = PBXGroup; children = ({', '.join(product_children)}, ); name = Products; sourceTree = \"<group>\"; }};\n")
    objects.append(f"\t\t{main} = {{isa = PBXGroup; children = ({', '.join(group_children)}, {products}, ); sourceTree = \"<group>\"; }};\n")
    objects.append(config("project", {"SDKROOT": "iphoneos", "IPHONEOS_DEPLOYMENT_TARGET": "15.0", "ONLY_ACTIVE_ARCH": "YES"}))
    objects.append(f"\t\t{oid('listproject')} = {{isa = XCConfigurationList; buildConfigurations = ({oid('cfgproject')}, ); defaultConfigurationIsVisible = 0; defaultConfigurationName = Debug; }};\n")
    objects.append(f"\t\t{oid('project')} = {{isa = PBXProject; attributes = {{BuildIndependentTargetsInParallel = 1; LastUpgradeCheck = 1600; }}; "
                   f"buildConfigurationList = {oid('listproject')}; compatibilityVersion = \"Xcode 14.0\"; developmentRegion = en; hasScannedForEncodings = 0; "
                   f"knownRegions = (en, Base, ); mainGroup = {main}; productRefGroup = {products}; projectDirPath = \"\"; projectRoot = \"\"; "
                   f"targets = ({', '.join(target_ids)}, ); }};\n")
    text = "// !$*UTF8*$!\n{\n\tarchiveVersion = 1;\n\tclasses = {\n\t};\n\tobjectVersion = 56;\n\tobjects = {\n" + "".join(objects) + f"\t}};\n\trootObject = {oid('project')};\n}}\n"
    (HERE / "LunarDevice.xcodeproj/project.pbxproj").write_text(text)
    print("Wrote", HERE / "LunarDevice.xcodeproj")


if __name__ == "__main__":
    main()
