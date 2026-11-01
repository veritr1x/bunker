.text
.global safepoint_loop
.type safepoint_loop, %function
safepoint_loop:
.cfi_startproc
// x20 and q31 remain live roots used after this import-free loop. They are
// changed inside it, so checking only the initial State cannot pass the test.
    mov x20, x0
    dup v31.2d, x0
    mov x21, #0
    dup v30.2d, x21
    mrs x22, tpidr_el0
    sub sp, sp, #32
    str x22, [sp]
.global safepoint_loop_head
.protected safepoint_loop_head
safepoint_loop_head:
    eor x20, x20, #8
    add x21, x21, #1
    dup v30.2d, x21
    add v29.2d, v31.2d, v30.2d
    subs x9, x9, #1
    b.ne safepoint_loop_head
.global safepoint_loop_done
.protected safepoint_loop_done
safepoint_loop_done:
    fadd s5, s3, s4
    str s5, [x1, #8]
    str x20, [x1]
    str q31, [x1, #16]
    str q29, [x1, #32]
    ldr x22, [sp]
    add sp, sp, #32
    ret
.cfi_endproc
.size safepoint_loop, .-safepoint_loop
