.text
.global delivery_loop
.type delivery_loop,%function
delivery_loop:
.cfi_startproc
  mov x20,x0
  dup v31.2d,x0
  mov x21,#0
  mrs x22,tpidr_el0
  sub sp,sp,#32
  str x22,[sp]
.global delivery_loop_head
.protected delivery_loop_head
delivery_loop_head:
  eor x20,x20,#8
  add x21,x21,#1
  dup v30.2d,x21
  add v29.2d,v31.2d,v30.2d
  ldr w9,[x2]
  cbz w9,delivery_loop_head
  str x20,[x1]
  str q31,[x1,#16]
  str q29,[x1,#32]
  ldr x22,[sp]
  add sp,sp,#32
  ret
.cfi_endproc
.size delivery_loop,.-delivery_loop
