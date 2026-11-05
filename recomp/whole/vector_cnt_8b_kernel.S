.text
.global cnt_actual
.type cnt_actual,%function
cnt_actual:
 ldr q0,[x0]
 .inst 0x0e205800 // Actual Unity7033b780: CNT V0.8B,V0.8B.
 str q0,[x1]
 ret
.size cnt_actual,.-cnt_actual
.global cnt_distinct
.type cnt_distinct,%function
cnt_distinct:
 ldr q5,[x0]
 .inst 0x0e2058a3 // CNT V3.8B,V5.8B.
 str q3,[x1]
 ret
.size cnt_distinct,.-cnt_distinct
.global cnt_sum
.type cnt_sum,%function
cnt_sum:
 ldr q0,[x0]
 .inst 0x0e205800 // Exact adjacent original pair.
 .inst 0x2e303800 // Actual Unity7033b784: UADDLV H0,V0.8B.
 str q0,[x1]
 ret
.size cnt_sum,.-cnt_sum

.global uadd_actual
.type uadd_actual,%function
uadd_actual:
 ldr q0,[x0]
 .inst 0x2e303800
 str q0,[x1]
 ret
.size uadd_actual,.-uadd_actual
.global uadd_distinct
.type uadd_distinct,%function
uadd_distinct:
 ldr q5,[x0]
 .inst 0x2e3038a3
 str q3,[x1]
 ret
.size uadd_distinct,.-uadd_distinct

.global cnt_loop56
.type cnt_loop56,%function
cnt_loop56:
 stp x21,x30,[sp,#-16]!
 mov x21,x0
 mov x9,xzr
 mov w8,wzr
1:
 ldr d0,[x21,x9]
 add x9,x9,#8
 cmp x9,#0x38
 .inst 0x0e205800
 .inst 0x2e303800
 fmov w10,s0
 add w8,w8,w10
 b.ne 1b
 str w8,[x1]
 ldp x21,x30,[sp],#16
 ret
.size cnt_loop56,.-cnt_loop56
