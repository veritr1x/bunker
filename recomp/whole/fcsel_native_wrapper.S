// Only the native ARM64 reference boundary; the NDK core object is shared unchanged.
.text
.global fcsel_native_wrapper
.type fcsel_native_wrapper,%function
fcsel_native_wrapper:
  stp x19,x20,[sp,#-64]!
  stp x21,x22,[sp,#16]
  stp x23,x24,[sp,#32]
  str x30,[sp,#48]
  mov x19,x0
  mov x20,x1
  mov x21,x2
  mrs x22,fpcr
  mrs x23,fpsr
  mrs x24,nzcv
  mov x0,x20
  mov x1,x21
  ldr x3,[x21,#736]
  msr nzcv,x3
  blr x19
  msr fpcr,x22
  msr fpsr,x23
  msr nzcv,x24
  ldr x30,[sp,#48]
  ldp x23,x24,[sp,#32]
  ldp x21,x22,[sp,#16]
  ldp x19,x20,[sp],#64
  ret
.size fcsel_native_wrapper,.-fcsel_native_wrapper
