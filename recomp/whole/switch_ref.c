#include "switch_driver.h"
extern uint64_t switch_dispatch(uint32_t, uint64_t);
int main(void) { return run_switch_cases(switch_dispatch); }
