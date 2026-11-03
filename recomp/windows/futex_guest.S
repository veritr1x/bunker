.text
.p2align 2
.global futex_direct
.type futex_direct,%function
futex_direct:
stp x29,x30,[sp,#-16]!
mov x29,sp
bl syscall
ldp x29,x30,[sp],#16
ret
.size futex_direct,.-futex_direct
.global futex_indirect
.type futex_indirect,%function
futex_indirect:
stp x29,x30,[sp,#-16]!
mov x29,sp
adrp x16,:got:syscall
ldr x16,[x16,:got_lo12:syscall]
blr x16
ldp x29,x30,[sp],#16
ret
.size futex_indirect,.-futex_indirect
.global futex_exclusive
.type futex_exclusive,%function
futex_exclusive:
stp x29,x30,[sp,#-48]!
mov x29,sp
stp x19,x20,[sp,#16]
stp x21,x22,[sp,#32]
mov x19,x1
mov x20,x2
mov x21,x3
ldxr x22,[x19]
mov x0,#98
mov x1,x19
mov x2,#0x81
mov x3,#1
mov x4,xzr
mov x5,xzr
mov x6,xzr
bl futex_direct
str x0,[x20]
stxr w4,x22,[x19]
str w4,[x21]
ldp x21,x22,[sp,#32]
ldp x19,x20,[sp,#16]
ldp x29,x30,[sp],#48
ret
.size futex_exclusive,.-futex_exclusive
.section .note.GNU-stack,"",%progbits
