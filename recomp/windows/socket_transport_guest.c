#include <arpa/inet.h>
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdint.h>
#include <stddef.h>
#include <sys/ioctl.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <sys/uio.h>
#include <unistd.h>
#include "socket_transport_cases.h"
_Static_assert(sizeof(socklen_t)==4&&sizeof(nfds_t)==4,"Android socket/poll widths");
_Static_assert(sizeof(struct pollfd)==8&&offsetof(struct pollfd,revents)==6,"Android pollfd");
_Static_assert(sizeof(fd_set)==128&&sizeof(struct timeval)==16,"Android fdset/timeval");
_Static_assert(sizeof(struct iovec)==16&&sizeof(struct msghdr)==56,"Android vector/message");
_Static_assert(offsetof(struct msghdr,msg_iov)==16&&offsetof(struct msghdr,msg_iovlen)==24&&offsetof(struct msghdr,msg_flags)==48,"Android message offsets");
#define CALL(name,args) do{if(indirect){__typeof__(&name) volatile fn=name;value=(int64_t)fn args;}else value=(int64_t)name args;}while(0)
int64_t guest_socket_operation(int operation,const uint64_t*a,int indirect,int*error){int64_t value=-1;int*saved_errno=__errno();*saved_errno=123;switch(operation){
 case NET_SOCKET:CALL(socket,((int)a[0],(int)a[1],(int)a[2]));break;
 case NET_BIND:CALL(bind,((int)a[0],(const struct sockaddr*)(uintptr_t)a[1],(socklen_t)a[2]));break;
 case NET_LISTEN:CALL(listen,((int)a[0],(int)a[1]));break;
 case NET_CONNECT:CALL(connect,((int)a[0],(const struct sockaddr*)(uintptr_t)a[1],(socklen_t)a[2]));break;
 case NET_ACCEPT:CALL(accept,((int)a[0],(struct sockaddr*)(uintptr_t)a[1],(socklen_t*)(uintptr_t)a[2]));break;
 case NET_SEND:CALL(send,((int)a[0],(const void*)(uintptr_t)a[1],(size_t)a[2],(int)a[3]));break;
 case NET_RECV:CALL(recv,((int)a[0],(void*)(uintptr_t)a[1],(size_t)a[2],(int)a[3]));break;
 case NET_SENDTO:CALL(sendto,((int)a[0],(const void*)(uintptr_t)a[1],(size_t)a[2],(int)a[3],(const struct sockaddr*)(uintptr_t)a[4],(socklen_t)a[5]));break;
 case NET_RECVFROM:CALL(recvfrom,((int)a[0],(void*)(uintptr_t)a[1],(size_t)a[2],(int)a[3],(struct sockaddr*)(uintptr_t)a[4],(socklen_t*)(uintptr_t)a[5]));break;
 case NET_GETSOCKNAME:CALL(getsockname,((int)a[0],(struct sockaddr*)(uintptr_t)a[1],(socklen_t*)(uintptr_t)a[2]));break;
 case NET_GETPEERNAME:CALL(getpeername,((int)a[0],(struct sockaddr*)(uintptr_t)a[1],(socklen_t*)(uintptr_t)a[2]));break;
 case NET_SETSOCKOPT:CALL(setsockopt,((int)a[0],(int)a[1],(int)a[2],(const void*)(uintptr_t)a[3],(socklen_t)a[4]));break;
 case NET_GETSOCKOPT:CALL(getsockopt,((int)a[0],(int)a[1],(int)a[2],(void*)(uintptr_t)a[3],(socklen_t*)(uintptr_t)a[4]));break;
 case NET_SHUTDOWN:CALL(shutdown,((int)a[0],(int)a[1]));break;
 case NET_SENDMSG:CALL(sendmsg,((int)a[0],(const struct msghdr*)(uintptr_t)a[1],(int)a[2]));break;
 case NET_RECVMSG:CALL(recvmsg,((int)a[0],(struct msghdr*)(uintptr_t)a[1],(int)a[2]));break;
 case NET_CLOSE:CALL(close,((int)a[0]));break;
 case NET_DUP:CALL(dup,((int)a[0]));break;
 case NET_DUP2:CALL(dup2,((int)a[0],(int)a[1]));break;
 case NET_FCNTL:CALL(fcntl,((int)a[0],(int)a[1],(int)a[2]));break;
 case NET_IOCTL:if(indirect){int(*volatile fn)(int,int,...)=ioctl;value=fn((int)a[0],(int)a[1],(void*)(uintptr_t)a[2]);}else value=ioctl((int)a[0],(int)a[1],(void*)(uintptr_t)a[2]);break;
 case NET_PIPE:CALL(pipe,((int*)(uintptr_t)a[0]));break;
 case NET_READ:CALL(read,((int)a[0],(void*)(uintptr_t)a[1],(size_t)a[2]));break;
 case NET_WRITE:CALL(write,((int)a[0],(const void*)(uintptr_t)a[1],(size_t)a[2]));break;
 case NET_POLL:CALL(poll,((struct pollfd*)(uintptr_t)a[0],(nfds_t)a[1],(int)a[2]));break;
 case NET_SELECT:CALL(select,((int)a[0],(fd_set*)(uintptr_t)a[1],(fd_set*)(uintptr_t)a[2],(fd_set*)(uintptr_t)a[3],(struct timeval*)(uintptr_t)a[4]));break;
 case NET_INET_NTOP:CALL(inet_ntop,((int)a[0],(const void*)(uintptr_t)a[1],(char*)(uintptr_t)a[2],(socklen_t)a[3]));break;
 case NET_OPEN:CALL(open,((const char*)(uintptr_t)a[0],(int)a[1],(mode_t)a[2]));break;
 case NET_SEEK:CALL(lseek,((int)a[0],(off_t)a[1],(int)a[2]));break;
 default:*saved_errno=22;break;
 }*error=*saved_errno;return value;}
