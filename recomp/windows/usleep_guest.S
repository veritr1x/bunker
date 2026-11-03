.text
.p2align 2
.global sleep_direct
.type sleep_direct,%function
sleep_direct:
stp x29,x30,[sp,#-16]!
mov x29,sp
bl usleep
ldp x29,x30,[sp],#16
ret
.size sleep_direct,.-sleep_direct
.global sleep_indirect
.type sleep_indirect,%function
sleep_indirect:
stp x29,x30,[sp,#-16]!
mov x29,sp
adrp x16,:got:usleep
ldr x16,[x16,:got_lo12:usleep]
blr x16
ldp x29,x30,[sp],#16
ret
.size sleep_indirect,.-sleep_indirect
.global sleep_exclusive
.type sleep_exclusive,%function
sleep_exclusive:
stp x29,x30,[sp,#-48]!
mov x29,sp
stp x19,x20,[sp,#16]
stp x21,x22,[sp,#32]
mov x19,x1
mov x20,x2
mov x21,x3
ldxr x22,[x19]
bl sleep_direct
str w0,[x20]
stxr w4,x22,[x19]
str w4,[x21]
ldp x21,x22,[sp,#32]
ldp x19,x20,[sp,#16]
ldp x29,x30,[sp],#48
ret
.size sleep_exclusive,.-sleep_exclusive
.section .note.GNU-stack,"",%progbits
