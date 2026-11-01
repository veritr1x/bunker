#include "masked_switch_driver.h"
extern uint64_t masked_switch_dispatch(uint64_t, uint64_t);
int main(void) { return run_masked_switch(masked_switch_dispatch); }
