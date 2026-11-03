// Exact original70423960 scalar instruction; synthetic directed opcode oracle.
.text
.global display_constructor_fcsel_native
.type display_constructor_fcsel_native,%function
display_constructor_fcsel_native:
  fmov s0,w0
  mov w3,#0x42700000
  fmov s1,w3
  fmov s2,#10.0
  fcmp s0,s2
  .inst 0x1e204c20
  str q0,[x1]
  ret
.size display_constructor_fcsel_native,.-display_constructor_fcsel_native
