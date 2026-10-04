#!/usr/bin/env python3
"""Merge the locally built launcher/server into a user-supplied decoded game.

Run the upstream lunar-scripts patcher on the decoded directory first. This tool
does not download or distribute game files. It never edits the source APK.
"""
import argparse
import copy
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import xml.etree.ElementTree as ET
import zipfile

NS = "http://schemas.android.com/apk/res/android"
ET.register_namespace("android", NS)
def attr(name): return "{" + NS + "}" + name
def run(*args): subprocess.run([str(x) for x in args], check=True)

def patch_local_reachability(game):
    """Let this local-only 3.7.1 client load assets with all radios disabled.

    Unity's reachability getter otherwise returns NotReachable in airplane mode,
    and Octo rejects a successful loopback download. Return LAN reachability.
    The RVA was resolved from the matching game's IL2CPP method metadata.
    Refuse unknown binaries rather than applying this offset speculatively.
    """
    path=game/"lib/arm64-v8a/libil2cpp.so"
    data=bytearray(path.read_bytes())
    if data[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H",data,18)[0] != 183:
        raise RuntimeError("Expected the Android ARM64 game library")
    rva=0x4910D4C
    table=struct.unpack_from("<Q",data,32)[0]
    stride,count=struct.unpack_from("<HH",data,54)
    offset=None
    for i in range(count):
        kind,flags,file_offset,address,_,size,_,_=struct.unpack_from("<IIQQQQQQ",data,table+i*stride)
        if kind==1 and flags&1 and address<=rva and rva+16<=address+size:
            offset=file_offset+rva-address
            break
    if offset is None: raise RuntimeError("Reachability method is outside executable ELF data")
    original=bytes.fromhex("f30f1ef8fd7b01a9")
    patched=bytes.fromhex("40008052c0035fd6") # mov w0, #2; ret
    if data[offset:offset+8] not in (original,patched) or data[offset+8:offset+16]!=bytes.fromhex("fd430091738401b0"):
        raise RuntimeError("Unsupported game binary: expected 3.7.1 reachability method")
    data[offset:offset+8]=patched
    path.write_bytes(data)
    print("Local asset reachability enabled (works with radios disabled)")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--decoded-dir",type=Path,required=True)
    p.add_argument("--companion-apk",type=Path,required=True)
    p.add_argument("--sdk",type=Path,default=Path(os.environ.get("ANDROID_HOME",str(Path.home()/"Library/Android/sdk"))))
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--keystore",type=Path,required=True)
    p.add_argument("--port-offset",type=int,default=0,help="The offset the game was patched with (ports 8003/8080/3000)")
    args=p.parse_args()
    root=Path(__file__).resolve().parents[2]
    game=args.decoded_dir.resolve();output=args.output.resolve();output.parent.mkdir(parents=True,exist_ok=True)
    patch_local_reachability(game)
    manifest=game/"AndroidManifest.xml";tree=ET.parse(manifest);doc=tree.getroot();app=doc.find("application")
    if app is None: raise RuntimeError("Game manifest has no application")
    package=doc.attrib["package"]
    old=app.find("meta-data[@"+attr("name")+"='org.lunartear.GAME_ACTIVITY']")
    original=old.get(attr("value")) if old is not None else None
    for activity in list(app.findall("activity")):
        if activity.get(attr("name"))=="org.lunartear.companion.MainActivity":
            app.remove(activity);continue
        for intent in list(activity.findall("intent-filter")):
            if any(x.get(attr("name"))=="android.intent.category.LAUNCHER" for x in intent.findall("category")):
                original=activity.get(attr("name"));activity.remove(intent)
    if not original: raise RuntimeError("Cannot identify the original game launcher")
    if original.startswith("."): original=package+original
    elif "." not in original: original=package+"."+original
    for entry in list(app):
        if entry.get(attr("name")) in ["org.lunartear.GAME_ACTIVITY","org.lunartear.PORT_OFFSET","org.lunartear.companion.ServerService","org.lunartear.companion.ToolsActivity"]:app.remove(entry)
    ET.SubElement(app,"meta-data",{attr("name"):"org.lunartear.GAME_ACTIVITY",attr("value"):original})
    # The launcher and server read the ports the game was built for.
    ET.SubElement(app,"meta-data",{attr("name"):"org.lunartear.PORT_OFFSET",attr("value"):str(args.port_offset)})
    app.set(attr("usesCleartextTraffic"),"true");app.set(attr("allowBackup"),"false");app.set(attr("extractNativeLibs"),"true")
    # The original Unity libraries use 4 KB ELF pages. Request Android's
    # compatibility loader explicitly, including after an APK update.
    app.set(attr("pageSizeCompat"),"enabled")
    # Keep the game's own name ("NieR"), as the iOS build does.
    companion=ET.parse(root/"android/app/src/main/AndroidManifest.xml").getroot()
    permissions={x.get(attr("name")) for x in doc.findall("uses-permission")}
    for permission in companion.findall("uses-permission"):
        if permission.get(attr("name")) not in permissions:doc.insert(0,copy.deepcopy(permission))
    for name in ["activity","service","provider"]:
        for source in companion.findall("application/"+name):
            element=copy.deepcopy(source)
            element.set(attr("name"),"org.lunartear.companion"+element.get(attr("name")))
            if name=="activity":element.set(attr("theme"),"@android:style/Theme.Material.Light.NoActionBar")
            # Authorities are unique per device: use the game's, not the standalone companion's.
            if name=="provider":element.set(attr("authorities"),doc.get("package")+".lunar_loopback")
            app.append(element)
    ET.indent(tree,space="    ");tree.write(manifest,encoding="utf-8",xml_declaration=True)
    # The wrapper uses Android 9+ file APIs. Preserve the game's target SDK to
    # avoid changing Unity's behavior; raise only its minimum supported version.
    yml=game/"apktool.yml";yml.write_text(re.sub(r"minSdkVersion: \d+","minSdkVersion: 28",yml.read_text()))
    with zipfile.ZipFile(args.companion_apk) as source:
        for name in source.namelist():
            if name.startswith(("assets/lunar/", "assets/chaquopy/", "lib/arm64-v8a/")):
                dest=game/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(source.read(name))
    notices=game/"assets/lunar";notices.mkdir(parents=True,exist_ok=True)
    shutil.copy2(root/"LICENSE",notices/"LUNAR_TEAR_LICENSE.txt")
    unsigned=output.with_suffix(".unsigned.apk");merged=output.with_suffix(".merged.apk")
    run("apktool","b",game,"-o",unsigned)
    shutil.copyfile(unsigned,merged)
    with zipfile.ZipFile(merged,"a") as target,zipfile.ZipFile(args.companion_apk) as source:
        dex=[n for n in target.namelist() if re.fullmatch(r"classes\d*\.dex",n)]
        index=max(int(re.search(r"\d+",n).group()) if re.search(r"\d+",n) else 1 for n in dex)+1
        for name in sorted(n for n in source.namelist() if re.fullmatch(r"classes\d*\.dex",n)):
            target.writestr("classes%d.dex"%index,source.read(name),compress_type=zipfile.ZIP_DEFLATED);index+=1
    tools=args.sdk/"build-tools/36.0.0"
    if not tools.is_dir(): raise RuntimeError("Install Android SDK build-tools; expected "+str(tools))
    run(tools/"zipalign","-P","16","-f","4",merged,output)
    if not args.keystore.exists():
        args.keystore.parent.mkdir(parents=True,exist_ok=True)
        run("keytool","-genkeypair","-keystore",args.keystore,"-alias","lunar-local","-storepass","android","-keypass","android","-keyalg","RSA","-keysize","2048","-validity","10000","-dname","CN=Lunar Tear Local Build")
        os.chmod(args.keystore,0o600)
    run(tools/"apksigner","sign","--ks",args.keystore,"--ks-key-alias","lunar-local","--ks-pass","pass:android","--key-pass","pass:android",output)
    run(tools/"apksigner","verify","--verbose",output)
    run(tools/"zipalign","-c","-P","16","4",output)
    unsigned.unlink();merged.unlink()
    print("Combined APK:",output)
    print("Original game activity:",original)

if __name__=="__main__":main()
