.text
.global original380
.type original380,%function
original380:
 stp x19,x20,[sp,#-64]!
 stp x21,x22,[sp,#16]
 stp x23,x24,[sp,#32]
 stp x29,x30,[sp,#48]
 mov x29,sp
 mov x21,x3
 mrs x23,fpcr
 mrs x24,fpsr
 msr fpcr,x1
 msr fpsr,x2
 mov x9,#0xa0000000
 msr nzcv,x9
 ldp q0,q1,[x21,#32]
 ldp q2,q3,[x21,#64]
 mov x19,#0x1919
 movk x19,#0xaaaa,lsl #48
 mov x20,#0x2020
 movk x20,#0xbbbb,lsl #48
 mov x9,#0xdee4
 movk x9,#0x7042,lsl #16
 blr x9

 mrs x9,fpsr
 str x9,[x21]
 mrs x9,nzcv
 str x9,[x21,#8]
 mrs x9,fpcr
 str x9,[x21,#16]
 stp q0,q1,[x21,#32]
 stp q2,q3,[x21,#64]
 mov x10,#0x1919
 movk x10,#0xaaaa,lsl #48
 cmp x19,x10
 cset w9,eq
 mov x10,#0x2020
 movk x10,#0xbbbb,lsl #48
 cmp x20,x10
 cset w10,eq
 and w9,w9,w10
 mov x10,sp
 cmp x10,x29
 cset w10,eq
 and w9,w9,w10
 str x9,[x21,#96]
 msr fpcr,x23
 msr fpsr,x24
 ldp x29,x30,[sp,#48]
 ldp x23,x24,[sp,#32]
 ldp x21,x22,[sp,#16]
 ldp x19,x20,[sp],#64
 ret

.global width_callback
.type width_callback,%function
width_callback:
 ldr w9,[x0,#0x30]
 add w9,w9,#1
 str w9,[x0,#0x30]
 ldr w0,[x0,#0x20]
 ret
.global height_callback
.type height_callback,%function
height_callback:
 ldr w9,[x0,#0x34]
 add w9,w9,#1
 str w9,[x0,#0x34]
 ldr w0,[x0,#0x24]
 ret
