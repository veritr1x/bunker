#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <stdint.h>
static int (*volatile opener)(const char*,int,...)=open;
static ssize_t (*volatile reader)(int,void*,size_t)=read;
static int (*volatile duplicator)(int)=dup;
static int (*volatile closer)(int)=close;
__attribute__((visibility("default"))) int64_t guest_urandom(int operation,uint64_t a,uint64_t b,uint64_t c,int pointer,int *error){
  errno=731;
  int64_t result;
  switch(operation){
    case 0:result=pointer?opener((const char*)a,(int)b,(unsigned)c):open((const char*)a,(int)b,(unsigned)c);break;
    case 1:result=pointer?reader((int)a,(void*)b,(size_t)c):read((int)a,(void*)b,(size_t)c);break;
    case 2:result=pointer?duplicator((int)a):dup((int)a);break;
    case 3:result=pointer?closer((int)a):close((int)a);break;
    default:result=-99;
  }
  *error=errno;return result;
}
