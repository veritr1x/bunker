.text
.global callback_register
.type callback_register, %function
callback_register:
.cfi_startproc
#if defined(CALLBACK_UNKNOWN)
    mov x0, x3
    b __cxa_atexit
#elif defined(CALLBACK_MIXED)
    cbz x3, 1f
    adrp x0, .Ldestructor
    add x0, x0, :lo12:.Ldestructor
    b 2f
1:  mov x0, x3
2:  b __cxa_atexit
#elif defined(CALLBACK_CLOBBER)
    adrp x0, .Ldestructor
    add x0, x0, :lo12:.Ldestructor
    bl unrelated_import
    b __cxa_atexit
#elif defined(CALLBACK_NONEXEC)
    adrp x0, .Ldso
    add x0, x0, :lo12:.Ldso
    b __cxa_atexit
#elif defined(CALLBACK_MISALIGNED)
    adrp x0, .Ldestructor
    add x0, x0, :lo12:.Ldestructor+1
    b __cxa_atexit
#elif defined(CALLBACK_WRONG_IMPORT)
    adrp x0, .Ldestructor
    add x0, x0, :lo12:.Ldestructor
    b unrelated_import
#elif defined(CALLBACK_W_CLOBBER)
    adrp x0, .Ldestructor
    add x0, x0, :lo12:.Ldestructor
    mov w0, wzr
    b __cxa_atexit
#elif defined(CALLBACK_TRUNCATED)
    adrp x0, .Ldestructor
    add w0, w0, :lo12:.Ldestructor
    b __cxa_atexit
#elif defined(CALLBACK_NUMERIC)
    // The test replaces these immediate bits with the executable callback RVA.
    // An executable-looking number is still not a relocatable image pointer.
    movz x0, #0
    movk x0, #0, lsl #16
    b __cxa_atexit
#else
    stp x29, x30, [sp, #-16]!
    mov x29, sp
    mov x1, x0
    adrp x8, .Ldestructor
    add x8, x8, :lo12:.Ldestructor
    adrp x2, .Ldso
    add x2, x2, :lo12:.Ldso
    mov x0, x8
#ifdef CALLBACK_PADDED_PLT
    bl .Lcustom_plt
#else
    bl __cxa_atexit
#endif
    adrp x0, .Lplain
    add x0, x0, :lo12:.Lplain
    bl atexit
    ldp x29, x30, [sp], #16
    ret
#endif
.cfi_endproc
.size callback_register, .-callback_register

#if !defined(CALLBACK_UNKNOWN) && !defined(CALLBACK_MIXED) && !defined(CALLBACK_CLOBBER) && !defined(CALLBACK_NONEXEC) && !defined(CALLBACK_MISALIGNED) && !defined(CALLBACK_WRONG_IMPORT) && !defined(CALLBACK_W_CLOBBER) && !defined(CALLBACK_TRUNCATED) && !defined(CALLBACK_NUMERIC)
.global callback_register_tail
.type callback_register_tail, %function
callback_register_tail:
.cfi_startproc
    mov x1, x0
    adrp x0, .Ltail
    add x0, x0, :lo12:.Ltail
    adrp x2, .Ldso
    add x2, x2, :lo12:.Ldso
    b __cxa_atexit
.cfi_endproc
.size callback_register_tail, .-callback_register_tail
#endif

// Deliberately no symbol type, exported name, relocation pointer or FDE for
// any destructor. These local labels disappear entirely with --strip-all.
.Ldestructor:
    ldr x8, [x0]
    lsl x8, x8, #4
    add x8, x8, #7
    str x8, [x0]
    ret
.Ltail:
    ldr x8, [x0]
    add x8, x8, #13
    str x8, [x0]
    ret
.Lplain:
    adrp x8, callback_plain_count
    add x8, x8, :lo12:callback_plain_count
    ldr x9, [x8]
    add x9, x9, #11
    str x9, [x8]
    ret

#ifdef CALLBACK_PADDED_PLT
.section .plt.custom,"ax",%progbits
.Lcustom_plt:
    adrp x16, :got:__cxa_atexit
    ldr x17, [x16, :got_lo12:__cxa_atexit]
    nop
    nop
    nop
    br x17
#endif
.data
.p2align 3
.Ldso: .quad 0
.global callback_plain_count
.protected callback_plain_count
callback_plain_count: .quad 0
