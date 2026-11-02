.text
.global bsearch_original_comparator
.type bsearch_original_comparator,%function
bsearch_original_comparator:
.cfi_startproc
 .inst 0xb9400008
 .inst 0xb9400029
 .inst 0x4b090100
 .inst 0xd65f03c0
.cfi_endproc
.size bsearch_original_comparator,.-bsearch_original_comparator
.global bsearch_poison_comparator
.type bsearch_poison_comparator,%function
bsearch_poison_comparator:
.cfi_startproc
 stp x29,x30,[sp,#-16]!
 bl bsearch_logged_comparator
 movk x0,#0xa5a5,lsl#48
 movk x0,#0x3c3c,lsl#32
 ldp x29,x30,[sp],#16
 ret
.cfi_endproc
.size bsearch_poison_comparator,.-bsearch_poison_comparator
.global bsearch_fixture_invoke
.type bsearch_fixture_invoke,%function
bsearch_fixture_invoke:
.cfi_startproc
 sub sp,sp,#176
 stp x19,x20,[sp]
 stp x21,x22,[sp,#16]
 stp x23,x24,[sp,#32]
 stp x25,x26,[sp,#48]
 stp x27,x28,[sp,#64]
 stp x29,x30,[sp,#80]
 stp d8,d9,[sp,#96]
 stp d10,d11,[sp,#112]
 stp d12,d13,[sp,#128]
 stp d14,d15,[sp,#144]
 str x0,[sp,#160]
 mov x19,#0x1919
 mov x20,#0x2020
 mov x21,#0x2121
 mov x22,#0x2222
 mov x23,#0x2323
 mov x24,#0x2424
 mov x25,#0x2525
 mov x26,#0x2626
 mov x27,#0x2727
 mov x28,#0x2828
 mov x29,#0x2929
 mov x2,#0xd8
 fmov d8,x2
 mov x2,#0xd9
 fmov d9,x2
 mov x2,#0xda
 fmov d10,x2
 mov x2,#0xdb
 fmov d11,x2
 mov x2,#0xdc
 fmov d12,x2
 mov x2,#0xdd
 fmov d13,x2
 mov x2,#0xde
 fmov d14,x2
 mov x2,#0xdf
 fmov d15,x2
 stp x19,x20,[x0]
 stp x21,x22,[x0,#16]
 stp x23,x24,[x0,#32]
 stp x25,x26,[x0,#48]
 stp x27,x28,[x0,#64]
 str x29,[x0,#80]
 stp d8,d9,[x0,#88]
 stp d10,d11,[x0,#104]
 stp d12,d13,[x0,#120]
 stp d14,d15,[x0,#136]
 mov x2,sp
 str x2,[x0,#152]
 bl bsearch_guest_case
 ldr x1,[sp,#160]
 stp x19,x20,[x1,#160]
 stp x21,x22,[x1,#176]
 stp x23,x24,[x1,#192]
 stp x25,x26,[x1,#208]
 stp x27,x28,[x1,#224]
 str x29,[x1,#240]
 stp d8,d9,[x1,#248]
 stp d10,d11,[x1,#264]
 stp d12,d13,[x1,#280]
 stp d14,d15,[x1,#296]
 mov x2,sp
 str x2,[x1,#312]
 ldp d8,d9,[sp,#96]
 ldp d10,d11,[sp,#112]
 ldp d12,d13,[sp,#128]
 ldp d14,d15,[sp,#144]
 ldp x19,x20,[sp]
 ldp x21,x22,[sp,#16]
 ldp x23,x24,[sp,#32]
 ldp x25,x26,[sp,#48]
 ldp x27,x28,[sp,#64]
 ldp x29,x30,[sp,#80]
 add sp,sp,#176
 ret
.cfi_endproc
.size bsearch_fixture_invoke,.-bsearch_fixture_invoke
