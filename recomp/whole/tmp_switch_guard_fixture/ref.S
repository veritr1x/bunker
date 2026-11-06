.text
.global original_dispatch
.type original_dispatch,%function
original_dispatch:
 stp x19,x20,[sp,#-512]!
 stp x21,x22,[sp,#16]
 stp x23,x24,[sp,#32]
 stp x25,x26,[sp,#48]
 stp x27,x28,[sp,#64]
 stp x29,x30,[sp,#80]
 mov x29,sp
 mov x19,x0
 mov x25,x1
 mov x22,x2
 mov x20,x3
 mov x26,x4
 str x4,[sp,#0x140]
 mrs x23,fpcr
 mrs x24,fpsr
 mov x9,#0xc00000
 msr fpcr,x9
 mov x9,#0x9f
 movk x9,#0x0800,lsl #16
 msr fpsr,x9
 mov x9,#0xa0000000
 msr nzcv,x9
 mov x9,#0x6666
 movk x9,#0x6666,lsl #16
 movk x9,#0xbbbb,lsl #32
 movk x9,#0xbbbb,lsl #48
 mov x10,#0x5555
 movk x10,#0x5555,lsl #16
 movk x10,#0xaaaa,lsl #32
 movk x10,#0xaaaa,lsl #48
 mov x27,#0x7777
 movk x27,#0x7777,lsl #16
 movk x27,#0xcccc,lsl #32
 movk x27,#0xcccc,lsl #48
 blr x25
 str x0,[x20]
 mrs x11,nzcv
 str x11,[x20,#8]
 mrs x11,fpcr
 str x11,[x20,#16]
 mrs x11,fpsr
 str x11,[x20,#24]
 stp x8,x9,[x20,#32]
 str x10,[x20,#48]
 str x22,[x20,#56]
 str x27,[x20,#64]
 mov x11,sp
 cmp x11,x29
 cset w11,eq
 mov x12,#0x50000000
 cmp x19,x12
 cset w12,eq
 and w11,w11,w12
 ldr x12,[sp,#0x140]
 cmp x26,x12
 cset w12,eq
 and w11,w11,w12
 str x11,[x20,#72]
 msr fpcr,x23
 msr fpsr,x24
 ldp x29,x30,[sp,#80]
 ldp x27,x28,[sp,#64]
 ldp x25,x26,[sp,#48]
 ldp x23,x24,[sp,#32]
 ldp x21,x22,[sp,#16]
 ldp x19,x20,[sp]
 add sp,sp,#512
 ret
