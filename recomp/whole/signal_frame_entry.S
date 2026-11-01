.text
.global frame_handler
.type frame_handler,%function
frame_handler:
.cfi_startproc
    mov x3, sp
    mov x4, x29
    b frame_body
.cfi_endproc
.size frame_handler,.-frame_handler
