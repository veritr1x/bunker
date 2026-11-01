"""Relocatable wrapper around exactly104 audited bytes of the original Unity ELF."""
import hashlib
import json
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_LITTLE_ENDIAN
from elftools.elf.elffile import ELFFile

ELF_SHA='3bc0bb2434171854839f9e4da00504f4ff413e0237ecea80b8a1cbbf6c8d3c9f'
CODE_SHA='b48e85dc743d429026ca348a1c1becc34a52e21daa37807e462311f987dd6a7f'
START,END=0x91bce0,0x91bd48
RECORD_BYTES=792


def prepare(library:Path,out:Path):
    if hashlib.sha256(library.read_bytes()).hexdigest()!=ELF_SHA:raise ValueError('Exact matrix gate requires the pinned original Unity ELF')
    with library.open('rb') as stream:
        elf=ELFFile(stream);section=elf.get_section_by_name('.text')
        code=section.data()[START-section['sh_addr']:END-section['sh_addr']]
    if len(code)!=104 or hashlib.sha256(code).hexdigest()!=CODE_SHA:raise ValueError('Original matrix bytes changed')
    disassembler=Cs(CS_ARCH_ARM64,CS_MODE_LITTLE_ENDIAN);instructions=list(disassembler.disasm(code,START))
    if len(instructions)!=26 or instructions[-1].mnemonic!='ret':raise ValueError('Original matrix bounds/control flow changed')
    if any(i.mnemonic not in ('ld1','st1','fmul','fmla') for i in instructions[:-1]):raise ValueError('Original function has an unaudited branch/address/global operation')
    raw=out/'original-matrix.bin';raw.write_bytes(code)
    source=out/'matrix.S';lines=['.text','.p2align 2','.global unity_matrix_call','.type unity_matrix_call, %function','unity_matrix_call:','.cfi_startproc','sub sp, sp, #1024','.cfi_def_cfa_offset 1024']
    for i in range(19,31,2):lines += [f'stp x{i}, x{i+1}, [sp, #{(i-19)*8}]']
    for i in range(8,16,2):lines += [f'stp q{i}, q{i+1}, [sp, #{96+(i-8)*16}]']
    lines += ['str x0, [sp, #224]','str x1, [sp, #232]','str x2, [sp, #240]','str x3, [sp, #248]',
              'mrs x6, fpcr','str x6, [sp, #256]','mrs x6, fpsr','str x6, [sp, #264]',
              'str x18, [sp, #272]','mov x6, sp','str x6, [sp, #280]',
              'msr fpcr, x4','uxtw x6, w5','msr fpsr, x6',
              'cmp xzr, xzr','tbnz x5, #63, 1f','ccmp xzr, xzr, #5, ne','b 2f','1:','ccmp xzr, xzr, #10, ne','2:',
              'adrp x6, matrix_vector_seeds','add x6, x6, :lo12:matrix_vector_seeds']
    for i in range(32):lines += [f'ldr q{i}, [x6, #{i*16}]']
    for i in range(3,30):
        value=0x1020304050600000|i
        lines += [f'movz x{i}, #{value&65535}',*[f'movk x{i}, #{(value>>shift)&65535}, lsl #{shift}'for shift in (16,32,48)]]
    lines += ['ldr x0, [sp, #232]','ldr x1, [sp, #240]','ldr x2, [sp, #248]','bl unity_original_matrix','.Lmatrix_return:']
    for i in range(0,28,2):lines += [f'stp x{i}, x{i+1}, [sp, #{288+i*8}]']
    lines += ['str x28, [sp, #512]','str x29, [sp, #520]','str x30, [sp, #528]','ldr x0, [sp, #224]']
    for i in range(3):lines += [f'ldr x1, [sp, #{288+i*8}]',f'ldr x2, [sp, #{232+i*8}]','sub x1, x1, x2',f'str x1, [x0, #{i*8}]']
    for i in range(3,30):lines += [f'ldr x1, [sp, #{288+i*8}]',f'str x1, [x0, #{i*8}]']
    lines += ['ldr x1, [sp, #528]','adr x2, .Lmatrix_return','sub x1, x1, x2','str x1, [x0, #240]',
              'mov x1, sp','ldr x2, [sp, #280]','sub x1, x1, x2','str x1, [x0, #248]']
    for i in range(32):lines += [f'str q{i}, [x0, #{256+i*16}]']
    lines += ['mrs x1, fpcr','str x1, [x0, #768]','mrs x1, fpsr','str x1, [x0, #776]',
              'cset w1, mi','lsl x1, x1, #31','cset w2, eq','orr x1, x1, x2, lsl #30',
              'cset w2, cs','orr x1, x1, x2, lsl #29','cset w2, vs','orr x1, x1, x2, lsl #28','str x1, [x0, #784]',
              'ldr x1, [sp, #256]','msr fpcr, x1','ldr x1, [sp, #264]','msr fpsr, x1','ldr x18, [sp, #272]']
    for i in range(8,16,2):lines += [f'ldp q{i}, q{i+1}, [sp, #{96+(i-8)*16}]']
    for i in range(19,31,2):lines += [f'ldp x{i}, x{i+1}, [sp, #{(i-19)*8}]']
    lines += ['add sp, sp, #1024','ret','.cfi_endproc','.size unity_matrix_call, .-unity_matrix_call',
              '.p2align 2','.global unity_original_matrix','.hidden unity_original_matrix','.type unity_original_matrix, %function',
              'unity_original_matrix:','.cfi_startproc',f'.incbin {json.dumps(str(raw.resolve()))}',
              '.cfi_endproc','.size unity_original_matrix, .-unity_original_matrix',
              '.section .rodata','.p2align 4','matrix_vector_seeds:']
    for i in range(32):lines += [f'.quad {0x1122334455660000|i}, {0x8877665544330000|i}']
    source.write_text('\n'.join(lines)+'\n')
    metadata={'original_elf_sha256':ELF_SHA,'code_sha256':CODE_SHA,'rva_start':hex(START),'rva_end_exclusive':hex(END),'bytes':104,
              'relocation_proof':'26 fixed instructions: LD1/ST1/F MUL/FMLA and finalRET; no PC-relative operand, global address, stack access, call, or interior control transfer. Wrapper is separate instrumentation; original104bytes remain unchanged.',
              'instructions':[{'pc':hex(i.address),'mnemonic':i.mnemonic,'operands':i.op_str}for i in instructions],
              'register_record':'X0..X2 are post-minus-input pointer deltas; X3..X29 raw; X30 post-minus-local-return-address; SP post-minus-call-SP; then all32Q regs, FPCR,FPSR,NZCV. All other content remains raw.'}
    (out/'extraction.json').write_text(json.dumps(metadata,indent=2)+'\n')
    return source,metadata
