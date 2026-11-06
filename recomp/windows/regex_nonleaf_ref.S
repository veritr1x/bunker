.text
.global original_regex_call
.type original_regex_call,%function
original_regex_call:
 stp x19,x20,[sp,#-224]!
 stp x21,x22,[sp,#16]
 stp x23,x24,[sp,#32]
 stp x25,x26,[sp,#48]
 stp x27,x28,[sp,#64]
 stp x29,x30,[sp,#80]
 stp q8,q9,[sp,#96]
 stp q10,q11,[sp,#128]
 stp q12,q13,[sp,#160]
 stp q14,q15,[sp,#192]
 mov x9,#0
 movk x9,#0x5001,lsl #16
 add x9,x9,#0xd000
 mov x10,sp
 str x10,[x9]
 mrs x10,fpcr
 str x10,[x9,#8]
 mrs x10,fpsr
 str x10,[x9,#16]
 mrs x10,nzcv
 str x10,[x9,#24]
 mov x9,#0xe000
 movk x9,#0x5001,lsl #16
 mov sp,x9
 adr x10,original_regex_return
 str x10,[sp,#88]
 cbnz w0,original_regex_interior
 add sp,sp,#96
original_regex_interior:
 mov x30,#0xc100
 movk x30,#0x5001,lsl #16
 ldp q0,q1,[x30,#0]
 ldp q2,q3,[x30,#32]
 ldp q4,q5,[x30,#64]
 ldp q6,q7,[x30,#96]
 ldp q8,q9,[x30,#128]
 ldp q10,q11,[x30,#160]
 ldp q12,q13,[x30,#192]
 ldp q14,q15,[x30,#224]
 ldp q16,q17,[x30,#256]
 ldp q18,q19,[x30,#288]
 ldp q20,q21,[x30,#320]
 ldp q22,q23,[x30,#352]
 ldp q24,q25,[x30,#384]
 ldp q26,q27,[x30,#416]
 ldp q28,q29,[x30,#448]
 ldp q30,q31,[x30,#480]
 mov x30,#0xc800
 movk x30,#0x5001,lsl #16
 ldp x9,x10,[x30]
 msr fpcr,x9
 msr fpsr,x10
 ldr x9,[x30,#16]
 msr nzcv,x9
 mov x30,#0xc000
 movk x30,#0x5001,lsl #16
 ldp x0,x1,[x30,#0]
 ldp x2,x3,[x30,#16]
 ldp x4,x5,[x30,#32]
 ldp x6,x7,[x30,#48]
 ldp x8,x9,[x30,#64]
 ldp x10,x11,[x30,#80]
 ldp x12,x13,[x30,#96]
 ldp x14,x15,[x30,#112]
 ldp x16,x17,[x30,#128]
 ldp x18,x19,[x30,#144]
 ldp x20,x21,[x30,#160]
 ldp x22,x23,[x30,#176]
 ldp x24,x25,[x30,#192]
 ldp x26,x27,[x30,#208]
 ldp x28,x29,[x30,#224]
 ldr x30,[x30,#240]
 // The full entry has its real prologue; the second profile begins at its epilogue.
 // X16 distinguishes the TEST entry without changing the seeded NZCV.
 tbnz x16,#5,original_regex_full
 br x16
original_regex_full:
 blr x16
original_regex_return:
 stp x0,x1,[sp,#0]
 stp x2,x3,[sp,#16]
 stp x4,x5,[sp,#32]
 stp x6,x7,[sp,#48]
 stp x8,x9,[sp,#64]
 stp x10,x11,[sp,#80]
 stp x12,x13,[sp,#96]
 stp x14,x15,[sp,#112]
 stp x16,x17,[sp,#128]
 stp x18,x19,[sp,#144]
 stp x20,x21,[sp,#160]
 stp x22,x23,[sp,#176]
 stp x24,x25,[sp,#192]
 stp x26,x27,[sp,#208]
 stp x28,x29,[sp,#224]
 mov x9,sp
 str x9,[sp,#240]
 mrs x9,fpcr
 str x9,[sp,#248]
 mrs x9,fpsr
 str x9,[sp,#256]
 mrs x9,nzcv
 str x9,[sp,#264]
 stp q0,q1,[sp,#272]
 stp q2,q3,[sp,#304]
 stp q4,q5,[sp,#336]
 stp q6,q7,[sp,#368]
 stp q8,q9,[sp,#400]
 stp q10,q11,[sp,#432]
 stp q12,q13,[sp,#464]
 stp q14,q15,[sp,#496]
 stp q16,q17,[sp,#528]
 stp q18,q19,[sp,#560]
 stp q20,q21,[sp,#592]
 stp q22,q23,[sp,#624]
 stp q24,q25,[sp,#656]
 stp q26,q27,[sp,#688]
 stp q28,q29,[sp,#720]
 stp q30,q31,[sp,#752]
 mov x9,#0xd000
 movk x9,#0x5001,lsl #16
 ldp x10,x11,[x9,#8]
 msr fpcr,x10
 msr fpsr,x11
 ldr x10,[x9,#24]
 msr nzcv,x10
 ldr x10,[x9]
 mov sp,x10
 ldp q8,q9,[sp,#96]
 ldp q10,q11,[sp,#128]
 ldp q12,q13,[sp,#160]
 ldp q14,q15,[sp,#192]
 ldp x29,x30,[sp,#80]
 ldp x27,x28,[sp,#64]
 ldp x25,x26,[sp,#48]
 ldp x23,x24,[sp,#32]
 ldp x21,x22,[sp,#16]
 ldp x19,x20,[sp],#224
 ret
