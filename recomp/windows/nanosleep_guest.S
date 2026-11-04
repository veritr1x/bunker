.text
.p2align 2
.global nanosleep_direct
.type nanosleep_direct,%function
nanosleep_direct:
stp x29,x30,[sp,#-16]!
mov x29,sp
bl nanosleep
ldp x29,x30,[sp],#16
ret
.size nanosleep_direct,.-nanosleep_direct
.global nanosleep_indirect
.type nanosleep_indirect,%function
nanosleep_indirect:
stp x29,x30,[sp,#-16]!
mov x29,sp
adrp x16,:got:nanosleep
ldr x16,[x16,:got_lo12:nanosleep]
blr x16
ldp x29,x30,[sp],#16
ret
.size nanosleep_indirect,.-nanosleep_indirect
.section .note.GNU-stack,"",%progbits
