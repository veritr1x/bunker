.text
.p2align 2
.global affinity_raw
.type affinity_raw,@function
affinity_raw:
 subq $24,%rsp
 movq $-1,%r8
 movq $0xbabe,%r9
 movq $-1,(%rsp)
 xorl %eax,%eax
 call android_affinity_syscall
 addq $24,%rsp
 ret
.size affinity_raw,.-affinity_raw
.section .note.GNU-stack,"",@progbits
