// Exact original scalar instruction; synthetic directed opcode oracle only.
.text
.global display_fcsel_native
.type display_fcsel_native,%function
display_fcsel_native:
  sub sp,sp,#32
  str d8,[sp]
  mrs x9,nzcv
  str x9,[sp,#8]
  msr nzcv,x0
  fmov s8,w1
  fmov s0,wzr
  .inst 0x1e281c08
  str q8,[x2]
  ldr x9,[sp,#8]
  msr nzcv,x9
  ldr d8,[sp]
  add sp,sp,#32
  ret
.size display_fcsel_native,.-display_fcsel_native
