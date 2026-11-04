#include <android/sensor.h>
#include <stdint.h>
uintptr_t sensor_direct(void){return (uintptr_t)ASensorManager_getInstance();}
uintptr_t sensor_pointer(uintptr_t address){ASensorManager*(*call)(void)=(ASensorManager*(*)(void))address;return (uintptr_t)call();}
