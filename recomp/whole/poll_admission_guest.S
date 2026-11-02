.text
.global admission_exclusive
.type admission_exclusive,%function
admission_exclusive:
.cfi_startproc
 ldxr x10,[x0]
.global admission_exclusive_loop
.protected admission_exclusive_loop
admission_exclusive_loop:
 ldr w11,[x1]
 cbz w11,admission_exclusive_loop
 add x10,x10,#1
 stxr w12,x10,[x0]
 str w12,[x2]
 ret
.cfi_endproc
.size admission_exclusive,.-admission_exclusive
.global admission_boundary
.type admission_boundary,%function
admission_boundary:
.cfi_startproc
 ret
.cfi_endproc
.size admission_boundary,.-admission_boundary
.global admission_child
.type admission_child,%function
admission_child:
.cfi_startproc
.global admission_child_loop
.protected admission_child_loop
admission_child_loop:
 add x22,x22,#1
 ldr w9,[x0]
 cbz w9,admission_child_loop
 ret
.cfi_endproc
.size admission_child,.-admission_child
.global admission_parent
.type admission_parent,%function
admission_parent:
.cfi_startproc
 stp x19,x20,[sp,#-32]!
 stp x21,x30,[sp,#16]
 mov x19,x0
 mov x20,x1
 adrp x0,.Lmodule
 add x0,x0,:lo12:.Lmodule
 mov w1,#2
 bl dlopen
 mov x21,x0
.Lafter_open:
 ldr w9,[x19,#8]
 cmp w9,#1
 b.lo .Lafter_open
 mov x0,x21
 bl dlclose
.Lafter_close:
 ldr w9,[x19,#8]
 cmp w9,#2
 b.lo .Lafter_close
 str x20,[x19,#16]
 ldp x21,x30,[sp,#16]
 ldp x19,x20,[sp],#32
 ret
.cfi_endproc
.size admission_parent,.-admission_parent
.section .rodata
.Lmodule:
.asciz "admission-test.so"
