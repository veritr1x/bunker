#include "module_registry_elf.h"
#include <algorithm>
#include <cstring>
#include <limits>
#include <map>
#include <set>
#include <stdexcept>

namespace bunker::windows {
namespace {
struct Header {uint8_t ident[16];uint16_t type,machine;uint32_t version;uint64_t entry,phoff,shoff;uint32_t flags;uint16_t ehsize,phentsize,phnum,shentsize,shnum,shstrndx;};
using Program=AndroidElf64Phdr;
struct Dynamic {int64_t tag;uint64_t value;};
struct Symbol {uint32_t name;uint8_t info,other;uint16_t section;uint64_t value,size;};
static_assert(sizeof(Header)==64&&sizeof(Program)==56&&sizeof(Dynamic)==16&&sizeof(Symbol)==24);
[[noreturn]] void Bad(const char *message){throw std::invalid_argument(std::string("unsupported/invalid ELF address metadata: ")+message);}
struct Reader {
 const uint8_t *bytes;size_t length;
 void Span(uint64_t offset,uint64_t count)const{if(offset>length||count>length-offset)Bad("file table bounds");}
 template<class T>T At(uint64_t offset)const{Span(offset,sizeof(T));T value;std::memcpy(&value,bytes+offset,sizeof(value));return value;}
};
uint64_t Add(uint64_t a,uint64_t b){if(b>UINT64_MAX-a)Bad("address/table overflow");return a+b;}
uint64_t Mul(uint64_t a,uint64_t b){if(a&&b>UINT64_MAX/a)Bad("table multiplication overflow");return a*b;}
}
ModuleAddressImage DescribeModuleElf(const uint8_t *file,size_t length,addr_t bias,std::string filename){
 if(!file||filename.empty()||filename.find('\0')!=std::string::npos)Bad("missing bytes or filename");
 const uint16_t endian=1;if(*reinterpret_cast<const uint8_t*>(&endian)!=1)Bad("host byte order");
 Reader r{file,length};const auto header=r.At<Header>(0);
 if(std::memcmp(header.ident,"\177ELF",4)||header.ident[4]!=2||header.ident[5]!=1||header.ident[6]!=1||header.machine!=183||header.version!=1||(header.type!=2&&header.type!=3)||header.ehsize!=64||header.phentsize!=56||!header.phnum||header.phnum==0xffff)Bad("ELF64 AArch64 header/profile");
 r.Span(header.phoff,Mul(header.phnum,sizeof(Program)));
 std::vector<Program> loads,programs;programs.reserve(header.phnum);std::optional<Program> dynamic;uint64_t low=UINT64_MAX,high=0;
 for(uint64_t i=0;i<header.phnum;++i){const auto p=r.At<Program>(Add(header.phoff,Mul(i,sizeof(Program))));
  programs.push_back(p);
  if(p.type==1){r.Span(p.offset,p.filesz);if(p.filesz>p.memsz)Bad("PT_LOAD file size exceeds memory size");const auto end=Add(p.vaddr,p.memsz);Add(bias,end);low=std::min(low,p.vaddr&~UINT64_C(4095));high=std::max(high,end);loads.push_back(p);}
  if(p.type==2){if(dynamic)Bad("multiple PT_DYNAMIC tables");r.Span(p.offset,p.filesz);if(p.filesz%sizeof(Dynamic))Bad("PT_DYNAMIC size");dynamic=p;}
 }
 if(loads.empty()||!dynamic||high<=low)Bad("missing load/dynamic metadata");
 auto Offset=[&](uint64_t address,uint64_t count){
  std::optional<uint64_t> result;
  for(const auto &p:loads)if(address>=p.vaddr&&address-p.vaddr<=p.filesz&&count<=p.filesz-(address-p.vaddr)){
   const auto at=Add(p.offset,address-p.vaddr);r.Span(at,count);if(result&&*result!=at)Bad("ambiguous file-backed virtual table");result=at;
  }
  if(!result)Bad("virtual table is not file-backed PT_LOAD");
  return *result;
 };
 if(Offset(dynamic->vaddr,dynamic->filesz)!=dynamic->offset)Bad("PT_DYNAMIC file/virtual mismatch");
 std::map<int64_t,uint64_t> tags;bool terminated=false;
 for(uint64_t i=0;i<dynamic->filesz/sizeof(Dynamic);++i){const auto d=r.At<Dynamic>(Add(dynamic->offset,Mul(i,sizeof(Dynamic))));if(!d.tag){terminated=true;break;}
  if(d.tag==4||d.tag==5||d.tag==6||d.tag==10||d.tag==11||d.tag==0x6ffffef5||d.tag==0x6ffffff0){if(!tags.emplace(d.tag,d.value).second)Bad("duplicate dynamic metadata tag");}
 }
 if(!terminated||!tags.count(5)||!tags.count(6)||!tags.count(10)||tags[11]!=sizeof(Symbol)||(!tags.count(4)&&!tags.count(0x6ffffef5)))Bad("missing symbol/string/hash tags");
 const auto strings=Offset(tags.at(5),tags.at(10));const auto string_size=tags.at(10);if(!string_size)Bad("empty dynamic string table");
 std::vector<uint64_t> order;std::set<uint64_t> reachable;uint64_t count=0;
 if(tags.count(0x6ffffef5)){
  const auto address=tags.at(0x6ffffef5),start=Offset(address,16);const auto buckets=r.At<uint32_t>(start),first=r.At<uint32_t>(start+4),words=r.At<uint32_t>(start+8),shift=r.At<uint32_t>(start+12);
  if(!buckets||!words||(words&(words-1))||shift>=64)Bad("GNU hash header");
  Offset(address,Add(Add(16,Mul(words,8)),Mul(buckets,4)));
  const auto bucket_address=Add(address,Add(16,Mul(words,8)));const auto bucket_offset=Offset(bucket_address,Mul(buckets,4));const auto chain_address=Add(bucket_address,Mul(buckets,4));count=first;
  uint64_t budget=length/4;
  for(uint64_t b=0;b<buckets;++b){uint64_t index=r.At<uint32_t>(bucket_offset+b*4);if(!index)continue;if(index<first)Bad("GNU bucket before symbol offset");
   for(;;++index){if(!budget--||!reachable.insert(index).second)Bad("GNU chain cycle/overlap/capacity");const auto value=r.At<uint32_t>(Offset(Add(chain_address,Mul(index-first,4)),4));order.push_back(index);count=std::max(count,Add(index,1));if(value&1)break;}
  }
 }else{
  const auto address=tags.at(4),start=Offset(address,8);const auto buckets=r.At<uint32_t>(start),chains=r.At<uint32_t>(start+4);if(!buckets||!chains)Bad("SysV hash header");
  const auto table=Offset(address,Add(8,Mul(Add(buckets,chains),4))),chain_offset=Add(table,Add(8,Mul(buckets,4)));count=chains;
  for(uint64_t b=0;b<buckets;++b){uint64_t index=r.At<uint32_t>(table+8+b*4);while(index){if(index>=count||!reachable.insert(index).second)Bad("SysV chain bounds/cycle/overlap");index=r.At<uint32_t>(chain_offset+index*4);}}
  for(uint64_t i=0;i<count;++i)order.push_back(i);
 }
 const auto symbols=Offset(tags.at(6),Mul(count,sizeof(Symbol)));std::optional<uint64_t> versions;if(tags.count(0x6ffffff0))versions=Offset(tags.at(0x6ffffff0),Mul(count,2));
 ModuleAddressImage image;image.filename=std::move(filename);image.base=Add(bias,low);image.load_bias=bias;image.span=(Add(high,4095)&~UINT64_C(4095))-low;Add(image.base,image.span);
 image.program_headers=std::move(programs);
 const auto table_bytes=Mul(header.phnum,sizeof(Program));
 for(const auto&p:loads)if(header.phoff>=p.offset&&header.phoff-p.offset<=p.filesz&&table_bytes<=p.filesz-(header.phoff-p.offset)){
  const auto address=Add(Add(bias,p.vaddr),header.phoff-p.offset);
  if(image.mapped_program_headers&&image.mapped_program_headers!=address)Bad("ambiguous mapped program header table");
  image.mapped_program_headers=address;
 }
 for(const auto &p:loads)image.loads.push_back({p.vaddr,p.memsz});
 image.symbols.reserve(order.size());
 for(auto index:order){const auto symbol=r.At<Symbol>(Add(symbols,Mul(index,sizeof(Symbol))));if(symbol.name>=string_size||symbol.size>UINT64_MAX-symbol.value)Bad("symbol string/range bounds");
  const char *name=reinterpret_cast<const char*>(file+strings+symbol.name);const auto remaining=string_size-symbol.name;const auto *end=static_cast<const char*>(std::memchr(name,0,static_cast<size_t>(remaining)));if(!end)Bad("unterminated dynamic symbol name");
  ModuleAddressSymbol result;result.name.assign(name,end);result.value=symbol.value;result.size=symbol.size;result.section=symbol.section;result.type=symbol.info&15;result.binding=symbol.info>>4;result.visibility=symbol.other&3;result.version=versions?r.At<uint16_t>(*versions+index*2):0;result.lookup_eligible=reachable.count(index)!=0;image.symbols.push_back(std::move(result));
 }
 return image;
}
}
