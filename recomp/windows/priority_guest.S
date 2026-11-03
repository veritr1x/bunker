.text
.p2align 2
.global priority_raw
.type priority_raw,%function
priority_raw:
 stp x29,x30,[sp,#-16]!
 mov x29,sp
 adrp x16,:got:getpriority
 ldr x16,[x16,:got_lo12:getpriority]
 blr x16
 ldp x29,x30,[sp],#16
 ret
.size priority_raw,.-priority_raw
.section .note.GNU-stack,"",%progbits
