// Native ARM64 boundary only. The same NDK core object is lifted unchanged.
.text
.global sshll_native_wrapper
.type sshll_native_wrapper, %function
sshll_native_wrapper:
  stp x19, x20, [sp, #-64]!
  stp x21, x22, [sp, #16]
  stp x23, x24, [sp, #32]
  str x30, [sp, #48]
  mov x21, x0
  mov x19, x1
  mov x20, x2
  mrs x22, fpcr
  mrs x23, fpsr
  mrs x24, nzcv
  ldr x3, [x20, #64]
  msr nzcv, x3
  ldr x3, [x20, #72]
  msr fpsr, x3
  ldr x3, [x20, #80]
  msr fpcr, x3
  mov x0, x19
  mov x1, x20
  blr x21
  mrs x3, nzcv
  str x3, [x19, #96]
  mrs x3, fpsr
  str x3, [x19, #104]
  mrs x3, fpcr
  str x3, [x19, #112]
  msr fpcr, x22
  msr fpsr, x23
  msr nzcv, x24
  ldr x30, [sp, #48]
  ldp x23, x24, [sp, #32]
  ldp x21, x22, [sp, #16]
  ldp x19, x20, [sp], #64
  ret
.size sshll_native_wrapper, .-sshll_native_wrapper
