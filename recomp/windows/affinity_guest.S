.text
.p2align 2
.global affinity_raw
.type affinity_raw,%function
affinity_raw:
 stp x29,x30,[sp,#-16]!
 mov x29,sp
 mov x4,#-1
 mov x5,#0xbabe
 mov x6,#-1
 adrp x16,:got:syscall
 ldr x16,[x16,:got_lo12:syscall]
 blr x16
 ldp x29,x30,[sp],#16
 ret
.size affinity_raw,.-affinity_raw
.section .note.GNU-stack,"",%progbits
