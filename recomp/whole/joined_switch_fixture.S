/* Unity ctor129: three independently bounded paths join one S32 switch. */
.text
.global masked_switch_dispatch
.type masked_switch_dispatch, %function
masked_switch_dispatch:
.cfi_startproc
    str x24, [sp, #-16]!
    mov w24, w0
    tbz x1, #0, .Lpath0
    tbnz x1, #1, .Lpath1
    b .Lpath2
.Lpath0:
    cmp w24, #20
    b.ls .Ldispatch
    b .Ldefault
.Lpath1:
#ifdef MULTI_DIFFERENT_BOUND
    cmp w24, #21
#elif defined(MULTI_NARROWER_PATH)
    cmp w24, #19
#elif defined(MULTI_SOURCE_MISMATCH)
    cmp w23, #20
#else
    cmp w24, #20
#endif
#ifdef MULTI_UNGUARDED_PATH
    b .Ldispatch
#elif defined(MULTI_INDEX_CLOBBER)
    b.hi .Ldefault
    add w24, w24, #1
    b .Ldispatch
#else
    b.ls .Ldispatch
    b .Ldefault
#endif
.Lpath2:
    cmp w24, #20
    b.hi .Ldefault
.Ldispatch:
    adrp x9, .Ltable
    mov w8, w24
    add x9, x9, :lo12:.Ltable
    ldrsw x8, [x9, x8, lsl #2]
    mov w2, wzr
    add x8, x8, x9
    br x8
.Lcase0:
    add x1, x1, #1
    b .Lreturn
.Lcase1:
    add x1, x1, #2
    b .Lreturn
.Lcase2:
    add x1, x1, #3
    b .Lreturn
.Lcase3:
    add x1, x1, #4
    b .Lreturn
.Lcase4:
    add x1, x1, #5
    b .Lreturn
.Lcase5:
    add x1, x1, #6
    b .Lreturn
.Lcase6:
    add x1, x1, #7
    b .Lreturn
.Lcase7:
    add x1, x1, #8
    b .Lreturn
.Lcase8:
    add x1, x1, #9
    b .Lreturn
.Lcase9:
    add x1, x1, #10
    b .Lreturn
.Lcase10:
    add x1, x1, #11
    b .Lreturn
.Lcase11:
    add x1, x1, #12
    b .Lreturn
.Lcase12:
    add x1, x1, #13
    b .Lreturn
.Lcase13:
    add x1, x1, #14
    b .Lreturn
.Lcase14:
    add x1, x1, #15
    b .Lreturn
.Lcase15:
    add x1, x1, #16
    b .Lreturn
.Lcase16:
    add x1, x1, #17
    b .Lreturn
.Lcase17:
    add x1, x1, #18
    b .Lreturn
.Lcase18:
    add x1, x1, #19
    b .Lreturn
.Lcase19:
    add x1, x1, #20
    b .Lreturn
.Lcase20:
    add x1, x1, #21
    b .Lreturn
.Lreturn:
    mov x0, x1
    ldr x24, [sp], #16
    ret
.Ldefault:
    eor x0, x1, #0xff
    ldr x24, [sp], #16
    ret
.cfi_endproc
.size masked_switch_dispatch, .-masked_switch_dispatch
.p2align 2
.Ltable:
    .word .Lcase0-.Ltable
    .word .Lcase1-.Ltable
    .word .Lcase2-.Ltable
    .word .Lcase3-.Ltable
    .word .Lcase4-.Ltable
    .word .Lcase5-.Ltable
    .word .Lcase6-.Ltable
    .word .Lcase7-.Ltable
    .word .Lcase8-.Ltable
    .word .Lcase9-.Ltable
    .word .Lcase10-.Ltable
    .word .Lcase11-.Ltable
    .word .Lcase12-.Ltable
    .word .Lcase13-.Ltable
    .word .Lcase14-.Ltable
    .word .Lcase15-.Ltable
    .word .Lcase16-.Ltable
    .word .Lcase17-.Ltable
    .word .Lcase18-.Ltable
    .word .Lcase19-.Ltable
    .word .Lcase20-.Ltable
