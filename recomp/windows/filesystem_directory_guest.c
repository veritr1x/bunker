#include <dirent.h>
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <sys/stat.h>
_Static_assert(sizeof(void*)==8&&sizeof(struct dirent)==280,"Android directory ABI width");
_Static_assert(offsetof(struct dirent,d_ino)==0&&offsetof(struct dirent,d_off)==8&&offsetof(struct dirent,d_reclen)==16&&offsetof(struct dirent,d_type)==18&&offsetof(struct dirent,d_name)==19,"Android directory field offsets");
_Static_assert(DT_UNKNOWN==0&&DT_DIR==4&&DT_REG==8&&DT_LNK==10,"Android directory types");
struct Observation {uint64_t pointer,inode;int64_t offset;uint32_t record_length,type;char name[256];};
DIR *guest_directory_open(const char *path,int indirect,int *error){
  errno=123;DIR *result;
  if(indirect){DIR *(*volatile operation)(const char*)=opendir;result=operation(path);}else result=opendir(path);
  *error=errno;return result;
}
uint64_t guest_directory_read(DIR *directory,int indirect,struct Observation *out){
  errno=321;struct dirent *entry;
  if(indirect){struct dirent *(*volatile operation)(DIR*)=readdir;entry=operation(directory);}else entry=readdir(directory);
  out->pointer=(uintptr_t)entry;
  if(entry){out->inode=entry->d_ino;out->offset=entry->d_off;out->record_length=entry->d_reclen;out->type=entry->d_type;
    for(unsigned i=0;i<256;++i){out->name[i]=entry->d_name[i];if(!entry->d_name[i])break;}}
  return(uint64_t)(uint32_t)errno<<32|(entry?1:0);
}
uint64_t guest_directory_close(DIR *directory,int indirect){
  errno=123;int result;
  if(indirect){int(*volatile operation)(DIR*)=closedir;result=operation(directory);}else result=closedir(directory);
  return(uint64_t)(uint32_t)errno<<32|(uint32_t)result;
}
uint64_t guest_directory_stat(const char *path,struct stat *out){errno=123;int result=stat(path,out);return(uint64_t)(uint32_t)errno<<32|(uint32_t)result;}
