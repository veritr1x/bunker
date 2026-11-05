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

.global neg4_actual
.type neg4_actual,%function
neg4_actual:
 ldr q17,[x0]
 .inst 0x6ea0ba31 // Original Unity70651858: NEG V17.4S,V17.4S.
 str q17,[x1]
 ret
.size neg4_actual,.-neg4_actual
.global neg4_distinct
.type neg4_distinct,%function
neg4_distinct:
 ldr q5,[x0]
 .inst 0x6ea0b8a3 // Same4S arrangement, distinct V3 destination/V5 source.
 str q3,[x1]
 ret
.size neg4_distinct,.-neg4_distinct
