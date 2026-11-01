.text
.p2align 2
#if defined(NONLOCAL_TAIL)
.global nonlocal_fixture
.type nonlocal_fixture,%function
nonlocal_fixture:
  b setjmp
.size nonlocal_fixture,.-nonlocal_fixture
#elif defined(NONLOCAL_INDIRECT)
.global nonlocal_fixture
.type nonlocal_fixture,%function
nonlocal_fixture:
  adrp x9,:got:setjmp
  ldr x9,[x9,:got_lo12:setjmp]
  blr x9
  ret
.size nonlocal_fixture,.-nonlocal_fixture
#elif defined(NONLOCAL_WRONG_IMPORT)
.global nonlocal_fixture
.type nonlocal_fixture,%function
nonlocal_fixture:
  bl unrelated_import
  ret
.size nonlocal_fixture,.-nonlocal_fixture
#elif defined(NONLOCAL_LOCAL_SHADOW) || defined(NONLOCAL_DEFINED_INTERPOSABLE)
.global nonlocal_fixture
.type nonlocal_fixture,%function
nonlocal_fixture:
  bl setjmp
  ret
.size nonlocal_fixture,.-nonlocal_fixture
#ifdef NONLOCAL_LOCAL_SHADOW
.local setjmp
#else
.global setjmp
#endif
.type setjmp,%function
setjmp:
  mov w0,#0
  ret
.size setjmp,.-setjmp
#elif defined(NONLOCAL_NONEXEC_POST)
.global nonlocal_fixture
.type nonlocal_fixture,%function
nonlocal_fixture:
  bl setjmp
.size nonlocal_fixture,.-nonlocal_fixture
#else
.macro probe name,api,value
.global \name
.type \name,%function
\name:
  stp x19,x30,[sp,#-16]!
  mov x19,x0
  bl \api
  // No symbol, FDE, or data relocation marks this return PC as a trace head.
  mov w0,#\value
  str w0,[x19]
  ldp x19,x30,[sp],#16
  ret
.size \name,.-\name
.endm
#ifdef NONLOCAL_PADDED_PLT
probe nonlocal_set,.Lcustom_plt,0x31
#else
probe nonlocal_set,setjmp,0x31
#endif
probe nonlocal_under,_setjmp,0x32
probe nonlocal_sig,sigsetjmp,0x33
#ifdef NONLOCAL_PADDED_PLT
.section .plt.nonlocal,"ax",%progbits
.Lcustom_plt:
  bti c
  nop
  adrp x16,:got:setjmp
  ldr x17,[x16,:got_lo12:setjmp]
  nop
  nop
  nop
  br x17
#endif
#endif
.section .note.GNU-stack,"",%progbits
