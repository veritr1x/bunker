// Native-only ABI/fenv boundary; actual NDK ST3 core is shared with both hosts.
.text
.global st3_native_wrapper
.type st3_native_wrapper,%function
st3_native_wrapper:
 stp x19,x20,[sp,#-80]!
 stp x21,x22,[sp,#16]
 stp x23,x24,[sp,#32]
 stp x25,x26,[sp,#48]
 str x30,[sp,#64]
 mov x19,x0
 mov x20,x1
 mov x21,x2
 mov x25,x3
 mov x26,x4
 mrs x22,fpcr
 mrs x23,fpsr
 mrs x24,nzcv
 mov x0,x20
 mov x1,x21
 mov x2,x25
 mov x3,x26
 ldr x4,[x21,#736]
 msr nzcv,x4
 blr x19
 msr fpcr,x22
 msr fpsr,x23
 msr nzcv,x24
 ldr x30,[sp,#64]
 ldp x25,x26,[sp,#48]
 ldp x23,x24,[sp,#32]
 ldp x21,x22,[sp,#16]
 ldp x19,x20,[sp],#80
 ret
.size st3_native_wrapper,.-st3_native_wrapper
.section .note.GNU-stack,"",%progbits
