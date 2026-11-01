.text
.global nonlocal_probe
.type nonlocal_probe,%function
// x0=264-byte environment, x1=528-byte observation/input, x2=variant.
// All saved register inputs are deliberately visible at the actual import.
nonlocal_probe:
  sub sp,sp,#288
  stp x18,x19,[sp,#0]
  stp x20,x21,[sp,#16]
  stp x22,x23,[sp,#32]
  stp x24,x25,[sp,#48]
  stp x26,x27,[sp,#64]
  stp x28,x29,[sp,#80]
  str x30,[sp,#96]
  stp q8,q9,[sp,#112]
  stp q10,q11,[sp,#144]
  stp q12,q13,[sp,#176]
  stp q14,q15,[sp,#208]
  stp x0,x1,[sp,#240]
  str x2,[sp,#256]
  mov x9,x1
  ldp x18,x19,[x9,#0]
  ldp x20,x21,[x9,#16]
  ldp x22,x23,[x9,#32]
  ldp x24,x25,[x9,#48]
  ldp x26,x27,[x9,#64]
  ldp x28,x29,[x9,#80]
  ldp q8,q9,[x9,#128]
  ldp q10,q11,[x9,#160]
  ldp q12,q13,[x9,#192]
  ldp q14,q15,[x9,#224]
  mov x10,sp
  str x10,[x9,#96]
  mrs x10,fpcr
  str x10,[x9,#112]
  mrs x10,fpsr
  str x10,[x9,#120]
#ifdef NONLOCAL_REFERENCE_JUMP
  cmp x2,#4
  b.eq 0f
#endif
  cmp x2,#0
  b.ne 2f
0:
  adr x10,1f
  str x10,[x9,#104]
  bl setjmp
1: b 9f
2:
#ifdef NONLOCAL_REFERENCE_JUMP
  cmp x2,#5
  b.eq 6f
#endif
  cmp x2,#1
  b.ne 4f
6:
  adr x10,3f
  str x10,[x9,#104]
  bl _setjmp
3: b 9f
4: sub x1,x2,#2
  adr x10,5f
  str x10,[x9,#104]
  bl sigsetjmp
5:
9:
#ifdef NONLOCAL_REFERENCE_JUMP
  ldr x11,[sp,#256]
  cmp x11,#4
  b.lo 8f
  cbnz w0,8f
  bl reference_change_mask
  mov x18,#0xbeef
  movk x18,#0xdead,lsl #48
  mov x19,#0
  mov x20,#0
  mov x21,#0
  mov x22,#0
  mov x23,#0
  mov x24,#0
  mov x25,#0
  mov x26,#0
  mov x27,#0
  mov x28,#0
  mov x29,#0
  movi v8.16b,#0xaa
  movi v9.16b,#0xaa
  movi v10.16b,#0xaa
  movi v11.16b,#0xaa
  movi v12.16b,#0xaa
  movi v13.16b,#0xaa
  movi v14.16b,#0xaa
  movi v15.16b,#0xaa
  mov x10,#0x400000
  msr fpcr,x10
  mov x10,#0x9f
  msr fpsr,x10
  ldr x0,[sp,#240]
  ldr x11,[sp,#256]
  mov w1,#-7
  cmp x11,#5
  csel w1,wzr,w1,eq
  bl longjmp
  brk #0
8:
#endif
  ldr x9,[sp,#248]
  str x0,[x9,#256]
  str x18,[x9,#272]
  stp x19,x20,[x9,#280]
  stp x21,x22,[x9,#296]
  stp x23,x24,[x9,#312]
  stp x25,x26,[x9,#328]
  stp x27,x28,[x9,#344]
  str x29,[x9,#360]
  mov x10,sp
  str x10,[x9,#368]
  str x30,[x9,#376]
  stp q8,q9,[x9,#384]
  stp q10,q11,[x9,#416]
  stp q12,q13,[x9,#448]
  stp q14,q15,[x9,#480]
  mrs x10,fpcr
  str x10,[x9,#512]
  mrs x10,fpsr
  str x10,[x9,#520]
  ldp x18,x19,[sp,#0]
  ldp x20,x21,[sp,#16]
  ldp x22,x23,[sp,#32]
  ldp x24,x25,[sp,#48]
  ldp x26,x27,[sp,#64]
  ldp x28,x29,[sp,#80]
  ldr x30,[sp,#96]
  ldp q8,q9,[sp,#112]
  ldp q10,q11,[sp,#144]
  ldp q12,q13,[sp,#176]
  ldp q14,q15,[sp,#208]
  add sp,sp,#288
  ret
.size nonlocal_probe,.-nonlocal_probe
.section .note.GNU-stack,"",%progbits
