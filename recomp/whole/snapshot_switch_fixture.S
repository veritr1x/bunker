/* A loop makes X13's global expression ambiguous; only the final read is bounded. */
.text
.global snapshot_switch_dispatch
.type snapshot_switch_dispatch, %function
snapshot_switch_dispatch:
.cfi_startproc
    stp x19, x30, [sp, #-16]!
.cfi_def_cfa_offset 16
.cfi_offset x19, -16
.cfi_offset x30, -8
#ifdef SNAP_W_INDEX
    mov w13, w0
#else
    mov x13, x0
#endif
    and w2, w1, #3
    cbz w2, .Lguard
.Lloop:
#ifdef SNAP_W_INDEX
    add w13, w13, #1
#else
    add x13, x13, #1
#endif
    sub w2, w2, #1
    cbnz w2, .Lloop
.Lguard:
    adrp x19, .Ltable
    add x19, x19, :lo12:.Ltable
#ifdef SNAP_GUARD_BYPASS
    tbz x1, #2, .Lload
#endif
#ifdef SNAP_OTHER_REGISTER
    cmp x0, #15
#elif defined(SNAP_GUARD_WIDTH_MISMATCH)
    cmp w13, #15
#elif defined(SNAP_NARROW_LOAD_MISMATCH)
    cmp x13, #15
#elif defined(SNAP_GUARD_LO)
    cmp x13, #16
#elif defined(SNAP_W_INDEX)
    cmp w13, #15
#else
    cmp x13, #15
#endif
#ifdef SNAP_FLAG_CLOBBER
    adds x12, x12, #1
#endif
#if defined(SNAP_NO_GUARD)
#elif defined(SNAP_WRONG_CONDITION)
    b.ne .Ldefault
#elif defined(SNAP_SIGNED_CONDITION)
    b.gt .Ldefault
#elif defined(SNAP_GUARD_LO)
    b.lo .Lload
    b .Ldefault
#elif defined(SNAP_GUARD_LS)
    b.ls .Lload
    b .Ldefault
#else
    b.hi .Ldefault
#endif
#ifdef SNAP_SOURCE_CLOBBER
    add x13, x13, #1
#endif
#ifdef SNAP_W_ALIAS_CLOBBER
    mov w13, w3
#endif
#ifdef SNAP_CONDITIONAL_CLOBBER
    tbz x1, #2, .Lload
    mov x13, #16
#endif
#ifdef SNAP_CALLER_CLOBBER
    bl .Lclobber
#endif
.Lload:
#ifdef SNAP_SEPARATE_DEST
    ldrsw x9, [x19, x13, lsl #2]
    add x9, x9, x19
    br x9
#elif defined(SNAP_STRIDE_MISMATCH)
    ldrsw x13, [x19, x13]
    add x13, x13, x19
    br x13
#elif defined(SNAP_SIGNED_W_INDEX)
    ldrsw x13, [x19, w13, sxtw #2]
    add x13, x13, x19
    br x13
#elif defined(SNAP_W_INDEX) || defined(SNAP_NARROW_LOAD_MISMATCH)
    ldrsw x13, [x19, w13, uxtw #2]
    add x13, x13, x19
    br x13
#else
    ldrsw x13, [x19, x13, lsl #2]
    add x13, x13, x19
    br x13
#endif
.macro CASE value
.Lcase\value:
#ifdef SNAP_UNGUARDED_BACKEDGE
    .if \value == 0
    b .Lload
    .endif
#endif
    add x0, x1, #(\value+1)
    b .Lreturn
.endm
.irp n,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15
    CASE \n
.endr
.Ldefault:
    eor x0, x1, #0xff
.Lreturn:
    ldp x19, x30, [sp], #16
    ret
.cfi_endproc
.size snapshot_switch_dispatch, .-snapshot_switch_dispatch
.Loutside:
    ret
#ifdef SNAP_CALLER_CLOBBER
.Lclobber:
.cfi_startproc
    mov x13, #16
    ret
.cfi_endproc
#endif
#ifdef SNAP_RODATA_TABLE
.section .rodata
#else
.text
#endif
.p2align 2
.Ltable:
.irp n,0,1,2,3,4,5,6,7,8,9,10,11,12,13,14
    .word .Lcase\n-.Ltable
.endr
#if defined(SNAP_OUTSIDE_TARGET)
    .word .Loutside-.Ltable
#elif !defined(SNAP_TABLE_OOB)
    .word .Lcase15-.Ltable
#endif
