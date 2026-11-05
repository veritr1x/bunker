.text
.global neg_actual
.type neg_actual,%function
neg_actual:
 ldr q0,[x0]
 .inst 0x2ea0b800 // Original Unity70161a78: NEG V0.2S,V0.2S.
 str q0,[x1]
 ret
.size neg_actual,.-neg_actual
.global neg_distinct
.type neg_distinct,%function
neg_distinct:
 ldr q5,[x0]
 .inst 0x2ea0b8a3 // Same2S arrangement, distinct V3 destination/V5 source.
 str q3,[x1]
 ret
.size neg_distinct,.-neg_distinct
