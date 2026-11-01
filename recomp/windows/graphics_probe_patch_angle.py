"""Apply recorded portability and profile-correct ASTC decoder changes.

Edits only the ignored detached ANGLE build checkout. The reusable patch is
preserved separately from the upstream/MSYS2 portability changes for review.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent/'work/angle-native'
SOURCE=ROOT/'src'

def run(args,cwd):
    result=subprocess.run([x.as_posix() if isinstance(x,Path) else str(x) for x in args],cwd=cwd,text=True,capture_output=True)
    if result.returncode:raise RuntimeError(result.stdout+result.stderr)
    return result.stdout

def replace(path,old,new,count=1):
    file=SOURCE/path;data=file.read_text()
    if data.count(old)!=count:raise RuntimeError(f'Patch anchor {path}: expected{count}, got{data.count(old)}')
    file.write_text(data.replace(old,new))

def main():
    patches=[('src/build','001-add-mingw-toolchain.patch'),('src','002-buildflags-fixes.patch'),('src','003-angle-src-fixes.patch'),('src/third_party/vulkan_memory_allocator','005-vulkan-memory-allocator-updates.patch'),('src/third_party/spirv-tools/src','006-spirv-updates.patch'),('src/third_party/vulkan-loader/src','007-vulkan-loader-updates.patch')]
    previous=json.loads((ROOT/'portability-patches.json').read_text()) if (ROOT/'portability-patches.json').exists() else []
    evidence=[]
    for relative,name in patches:
        path=ROOT/'recipe'/name;directory=ROOT/relative
        record={'repository':relative,'patch':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        if record not in previous:
            try:
                run(['git','apply','--reverse','--check',path],directory)
            except RuntimeError:
                run(['git','apply',path],directory)
        evidence.append(record)
    # The package workaround deletes real Vulkan texture descriptor updates.
    # Preserve upstream behavior and emit the allocator template symbols that
    # GCC needs instead of removing functionality to avoid the link error.
    program='src/libANGLE/renderer/vulkan/ProgramExecutableVk.cpp'
    upstream=run(['git','show','HEAD:'+program],SOURCE)
    if (SOURCE/program).read_text()!=upstream:
        (SOURCE/program).write_text(upstream)
    allocator=SOURCE/'src/libANGLE/renderer/vulkan/vk_cache_utils.cpp'
    allocator_data=allocator.read_text()
    allocator_anchor='uint32_t UpdateDescriptorSetsBuilder::WriteDescriptorSetAllocator::updateDescriptorSets('
    allocator_marker='// Emit allocator definitions used by inline callers in other translation units.'
    if allocator_marker not in allocator_data:
        instantiations=allocator_marker+'\n'+''.join('template '+t+' *UpdateDescriptorSetsBuilder::DescriptorInfoAllocator<'+t+'>::allocate(uint32_t);\n' for t in ['VkWriteDescriptorSet','VkDescriptorBufferInfo','VkDescriptorImageInfo','VkBufferView'])+'\n'
        if allocator_data.count(allocator_anchor)!=1:raise RuntimeError('Allocator instantiation anchor changed')
        allocator.write_text(allocator_data.replace(allocator_anchor,instantiations+allocator_anchor))
    descriptor_fix={'restored_upstream_file':program,'restored_sha256':hashlib.sha256((SOURCE/program).read_bytes()).hexdigest(),'allocator_sha256':hashlib.sha256(allocator.read_bytes()).hexdigest(),'reason':'Reject MSYS2 removal of real Vulkan sampled texture updates; instantiate missing GCC allocator symbols'}
    (ROOT/'descriptor-portability-fix.json').write_text(json.dumps(descriptor_fix,indent=2)+'\n')
    (SOURCE/'build/config/gclient_args.gni').write_text('build_with_chromium = false\n')
    json_gn=SOURCE/'third_party/jsoncpp/BUILD.gn'
    json_data=json_gn.read_text()
    import_line='import("//testing/libfuzzer/fuzzer_test.gni")'
    if '# Bunker standalone:' not in json_data:
        if import_line not in json_data:raise RuntimeError('Missing jsoncpp standalone import anchor')
        json_gn.write_text('# Bunker standalone: fuzzer target exists only in Chromium builds.\n'+json_data.replace(import_line,'if (build_with_chromium) {\n  '+import_line+'\n}'))
    json_data=json_gn.read_text()
    if 'import("//build_overrides/build.gni")' not in json_data:
        json_gn.write_text('import("//build_overrides/build.gni")\n'+json_data)
    zlib_gn=SOURCE/'third_party/zlib/BUILD.gn'
    zlib_data=zlib_gn.read_text()
    zlib_data=zlib_data.replace('if (is_win && !is_clang)', 'if (is_msvc && !is_clang)')
    zlib_data=zlib_data.replace('if (!is_win || is_clang)', 'if (!is_msvc || is_clang)')
    zlib_gn.write_text(zlib_data)
    wrapper=SOURCE/'build/toolchain/gcc_solink_wrapper.py'
    wrapper_data=wrapper.read_text()
    if 'def IsPEFile(' not in wrapper_data:
        wrapper_data=wrapper_data.replace('def CollectSONAME(args):','def IsPEFile(path):\n  with open(path, "rb") as binary:\n    return binary.read(2) == b"MZ"\n\n\ndef CollectSONAME(args):')
        wrapper_data=wrapper_data.replace("sys.platform == 'win32' and 'MINGW' in sys.version",'IsPEFile(args.sofile)')
        wrapper.write_text(wrapper_data)
    stamp=ROOT/'profile-patch.json'
    files=['src/image_util/loadimage.h','src/image_util/loadimage.inc','src/image_util/loadimage_astc.cpp','src/image_util/AstcDecompressor.h','src/image_util/AstcDecompressor.cpp','src/image_util/AstcDecompressorNoOp.cpp','src/libANGLE/renderer/load_functions_data.json','src/libANGLE/renderer/load_functions_table_autogen.cpp']
    if not stamp.exists():
        before={p:(SOURCE/p).read_text() for p in files}
        # Public image loader adds a compile-time profile; existing linear users
        # and unit tests retain their existing default behavior.
        replace(files[0],'template <size_t blockWidth, size_t blockHeight>','template <size_t blockWidth, size_t blockHeight, bool isSRGB = false>')
        replace(files[1],'template <size_t blockWidth, size_t blockHeight>','template <size_t blockWidth, size_t blockHeight, bool isSRGB>')
        for path in [files[0],files[2]]:
            replace(path,'uint32_t blockHeight,\n','uint32_t blockHeight,\n                          bool isSRGB,\n')
        replace(files[1],'depth, blockWidth, blockHeight, input, inputRowPitch,','depth, blockWidth, blockHeight, isSRGB, input, inputRowPitch,')
        replace(files[2],'imgHeight, blockWidth, blockHeight, input, blockSize, output);','imgHeight, blockWidth, blockHeight, input, blockSize, output, isSRGB);')
        replace(files[3],'uint8_t *output) = 0;','uint8_t *output, bool isSRGB = false) = 0;')
        replace(files[4],'uint8_t *output) override','uint8_t *output, bool isSRGB) override')
        replace(files[5],'uint8_t *output) override','uint8_t *output, bool isSRGB) override')
        replace(files[4],'uint32_t blockHeight,\n                                           astcenc_error *error)','uint32_t blockHeight,\n                                           bool isSRGB,\n                                           astcenc_error *error)')
        replace(files[4],'        // TODO(gregschlom): Do we need a special case for sRGB images? (And pass\n        //                   ASTCENC_PRF_LDR_SRGB here?)\n        astcenc_config_init(ASTCENC_PRF_LDR,','        astcenc_config_init(isSRGB ? ASTCENC_PRF_LDR_SRGB : ASTCENC_PRF_LDR,')
        replace(files[4],'MakeDecoderContext(5, 5, &error)','MakeDecoderContext(5, 5, false, &error)')
        replace(files[4],'get(uint32_t blockWidth, uint32_t blockHeight)','get(uint32_t blockWidth, uint32_t blockHeight, bool isSRGB)')
        replace(files[4],'mContexts[{blockWidth, blockHeight}]','mContexts[{blockWidth, blockHeight, isSRGB}]')
        replace(files[4],'MakeDecoderContext(blockWidth, blockHeight, &value.error)','MakeDecoderContext(blockWidth, blockHeight, isSRGB, &value.error)')
        replace(files[4],'uint32_t blockHeight;\n','uint32_t blockHeight;\n        bool isSRGB;\n')
        replace(files[4],'blockHeight == other.blockHeight;','blockHeight == other.blockHeight && isSRGB == other.isSRGB;')
        replace(files[4],'return k.blockWidth << 8 | k.blockHeight;','return (static_cast<size_t>(k.isSRGB) << 16) | (k.blockWidth << 8) | k.blockHeight;')
        replace(files[4],'mContextCache->get(blockWidth, blockHeight)','mContextCache->get(blockWidth, blockHeight, isSRGB)')
        data=json.loads((SOURCE/files[6]).read_text());n=0
        for fmt,backings in data.items():
            if fmt.startswith('GL_COMPRESSED_SRGB8_ALPHA8_ASTC_'):
                for types in backings.values():
                    for key,value in types.items():
                        if value.startswith('LoadASTCToRGBA8<'):
                            types[key]=value[:-1]+', true>';n+=1
        if n!=14:raise RuntimeError(f'Expected14 sRGB ASTC format loaders, got{n}')
        (SOURCE/files[6]).write_text(json.dumps(data,indent=2)+'\n')
        run([sys.executable,'gen_load_functions_table.py'],SOURCE/'src/libANGLE/renderer')
        import difflib
        patch=''.join(''.join(difflib.unified_diff(before[p].splitlines(True),(SOURCE/p).read_text().splitlines(True),fromfile='a/'+p,tofile='b/'+p)) for p in files)
        (ROOT/'profile-correct-astc.patch').write_text(patch)
        stamp.write_text(json.dumps({'loader_count':n,'patch_sha256':hashlib.sha256(patch.encode()).hexdigest(),'files_sha256':{p:hashlib.sha256((SOURCE/p).read_bytes()).hexdigest() for p in files}},indent=2)+'\n')
    # The older package pin predates upstream's slice loop. Port that actual
    # decoding behavior too: array/cube-array uploads must decode every layer.
    if 'for (size_t slice = 0; slice < depth; ++slice)' not in (SOURCE/files[2]).read_text():
        replace(files[2],'''    int32_t result =
        decompressor.decompress(context.singleThreadPool, context.multiThreadPool, imgWidth,
                                imgHeight, blockWidth, blockHeight, input, blockSize, output, isSRGB);
    if (result != 0)
    {
        WARN() << "ASTC decompression failed: " << decompressor.getStatusString(result);
    }''','''    for (size_t slice = 0; slice < depth; ++slice)
    {
        int32_t result =
            decompressor.decompress(context.singleThreadPool, context.multiThreadPool, imgWidth,
                                    imgHeight, blockWidth, blockHeight, input, blockSize, output, isSRGB);
        if (result != 0)
        {
            WARN() << "ASTC decompression failed: " << decompressor.getStatusString(result);
        }
        input += inputDepthPitch;
        output += outputDepthPitch;
    }''')
    import difflib
    patch=''.join(''.join(difflib.unified_diff(run(['git','show','HEAD:'+p],SOURCE).splitlines(True),(SOURCE/p).read_text().splitlines(True),fromfile='a/'+p,tofile='b/'+p)) for p in files)
    (ROOT/'profile-correct-astc.patch').write_text(patch,newline='\n')
    stamp.write_text(json.dumps({'version':2,'loader_count':14,'patch_sha256':hashlib.sha256((ROOT/'profile-correct-astc.patch').read_bytes()).hexdigest(),'files_sha256':{p:hashlib.sha256((SOURCE/p).read_bytes()).hexdigest() for p in files}},indent=2)+'\n')
    fixes=''
    for relative,path in [('src/third_party/jsoncpp','BUILD.gn'),('src/third_party/zlib','BUILD.gn')]:
        fixes += run(['git','diff','--',path],ROOT/relative)
    fixes += run(['git','diff','--','toolchain/gcc_solink_wrapper.py'],SOURCE/'build')
    fixes += run(['git','diff','--','src/libANGLE/renderer/vulkan/vk_cache_utils.cpp'],SOURCE)
    (ROOT/'standalone-gn-fixes.patch').write_text(fixes,newline='\n')
    (ROOT/'portability-patches.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print('Portability patches and14 profile-correct sRGB ASTC loaders ready')

if __name__=='__main__':main()
