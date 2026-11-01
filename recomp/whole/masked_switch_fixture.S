/* Mirrors Unity ctor95's loop, W/X masked index and table-relative S32 rows. */
.text
.global masked_switch_dispatch
.type masked_switch_dispatch, %function
masked_switch_dispatch:
.cfi_startproc
    mov x8, x0
    adrp x9, .Ltable
    add x9, x9, :lo12:.Ltable
.Lguard:
    and w11, w8, #0x7fffffff
    cmp w11, #4
    b.hi .Ldefault
#ifdef MASK_SOURCE_CLOBBER
    add x8, x8, #1
#else
    nop
#endif
.Lrecompute:
#ifdef MASK_DIFFERENT_WIDTH
    and x11, x8, #0x1ffffffff
#else
    and x11, x8, #0x7fffffff
#endif
    ldrsw x11, [x9, x11, lsl #2]
    add x11, x11, x9
    br x11
.Lcase1:
    eor x1, x1, #0xff
.Lcase0:
    add x1, x1, #7
    b .Lnext
.Lcase3:
    add x1, x1, #11
#ifdef MASK_CASE_BASE_CLOBBER
    add x9, x9, #4
#else
    nop
#endif
    b .Lnext
.Lnext:
    add x8, x8, #1
    cmp x8, #5
    b.lo .Lguard
    mov x0, x1
    ret
.Ldefault:
#ifdef MASK_GUARD_BYPASS
    b .Lrecompute
#else
    eor x0, x1, #0xff
    ret
#endif
.cfi_endproc
.size masked_switch_dispatch, .-masked_switch_dispatch
.p2align 2
.Ltable:
    .word .Lcase0-.Ltable, .Lcase1-.Ltable, .Lcase1-.Ltable
    .word .Lcase3-.Ltable, .Lcase0-.Ltable
