"""Negative checks for the recursive State ABI comparator used by overlays."""
import argparse
from pathlib import Path
import subprocess
import tempfile


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tool',type=Path,required=True);a=p.parse_args()
    def module(body,layout='e-p:64:64-i64:64-i128:128'):
        return f'target datalayout = "{layout}"\n{body}\n@witness = external global %struct.State\n'
    cases=[
        ('names_are_not_layout',module('%struct.State = type { %one }\n%one = type { i64, [2 x i32] }'),
         module('%struct.State = type { %renamed }\n%renamed = type { i64, [2 x i32] }'),True),
        ('same_size_different_fields',module('%struct.State = type { i32, i32, i64 }'),
         module('%struct.State = type { i64, i32, i32 }'),False),
        ('packed_offsets',module('%struct.State = type { i8, i64 }'),
         module('%struct.State = type <{ i8, i64 }>'),False),
        ('opaque_is_not_proof',module('%struct.State = type opaque'),module('%struct.State = type opaque'),False),
        ('primitive_alignment_even_in_packed_parent',module('%struct.State = type <{ i64 }>'),
         module('%struct.State = type <{ i64 }>','e-p:64:64-i64:32-i128:128'),False),
    ]
    with tempfile.TemporaryDirectory(prefix='il2cpp-layout-')as name:
        root=Path(name)
        for title,left,right,equal in cases:
            old=root/'old.ll';new=root/'new.ll';old.write_text(left);new.write_text(right)
            result=subprocess.run([str(a.tool),str(old),str(new),str(root/'shape')],capture_output=True)
            assert (result.returncode==0)==equal,(title,result.stdout,result.stderr)
            print(title,'passed')
    print('Five independent State ABI comparator positive/negative checks passed.')


if __name__=='__main__':main()
