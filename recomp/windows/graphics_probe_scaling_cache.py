"""Optional local object-cache seed for the isolated ANGLE variant.

Copies, never hardlinks, the accepted build. Only byte-identical source files
inherit the old timestamps; changed headers/sources retain fresh timestamps so
Ninja's recorded relative dependencies force the required recompilation.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil

WORK=Path(__file__).resolve().parent.parent/'work'


def main():
    base=WORK/'angle-native/src';variant=WORK/'angle-scaling/src'
    old=base/'out/BunkerVulkanAstc';new=variant/'out/BunkerVulkanScaling'
    if new.exists():return
    if not old.exists():return
    shutil.copytree(old,new,copy_function=shutil.copy2)
    matched=0
    for folder,dirs,files in os.walk(variant):
        dirs[:]=[name for name in dirs if name not in ('.git','out','__pycache__')]
        for name in files:
            target=Path(folder)/name;source=base/target.relative_to(variant)
            if source.is_file() and target.stat().st_size==source.stat().st_size:
                if hashlib.sha256(target.read_bytes()).digest()==hashlib.sha256(source.read_bytes()).digest():
                    state=source.stat();os.utime(target,ns=(state.st_atime_ns,state.st_mtime_ns));matched+=1
    (WORK/'angle-scaling/cache-seed.json').write_text(json.dumps({'copied_from':str(old),'copied_to':str(new),'byte_identical_source_mtimes':matched,
        'method':'Independent copies; relative Ninja dependency records reused; changed sources retain new timestamps'},indent=2)+'\n')
    print('Independent ANGLE object cache copied; identical source files:'+str(matched),flush=True)


if __name__=='__main__':main()
