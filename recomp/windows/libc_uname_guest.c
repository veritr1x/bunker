#include <sys/utsname.h>
#include <errno.h>
#include <stdint.h>
#include <stddef.h>
_Static_assert(sizeof(struct utsname)==390,"Bionic utsname six65-byte fields");
_Static_assert(_Alignof(struct utsname)==1,"Bionic utsname byte alignment");
_Static_assert(sizeof(((struct utsname*)0)->sysname)==65,"Bionic UTS field width");
_Static_assert(offsetof(struct utsname,sysname)==0&&offsetof(struct utsname,nodename)==65&&offsetof(struct utsname,release)==130&&offsetof(struct utsname,version)==195&&offsetof(struct utsname,machine)==260&&offsetof(struct utsname,domainname)==325,"Bionic UTS field offsets");
struct uname_result {int32_t result,error;int64_t widened;};
_Static_assert(sizeof(struct uname_result)==16&&offsetof(struct uname_result,widened)==8,"NDK status observation ABI");
int64_t guest_uname(struct utsname*out,int indirect,int sentinel,struct uname_result*observed){
 errno=sentinel;
 __typeof__(&uname) volatile query=uname;
 const int result=indirect?query(out):uname(out);
 observed->result=result;observed->error=errno;observed->widened=(int64_t)result;
 return (int64_t)result;
}
uint64_t guest_uname_layout(unsigned index){
 const uint64_t values[]={sizeof(struct utsname),_Alignof(struct utsname),offsetof(struct utsname,sysname),offsetof(struct utsname,nodename),offsetof(struct utsname,release),offsetof(struct utsname,version),offsetof(struct utsname,machine),offsetof(struct utsname,domainname)};
 return index<8?values[index]:UINT64_MAX;
}
