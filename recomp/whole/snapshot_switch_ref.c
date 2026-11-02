#include "snapshot_switch_driver.h"
extern uint64_t snapshot_switch_dispatch(uint64_t,uint64_t);
int main(void){return run_snapshot_switch(snapshot_switch_dispatch);}
