#include <algorithm>
#include <atomic>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <stdexcept>
#include <thread>
#include <vector>
#include <windows.h>
#include <winioctl.h>

#include "filesystem.h"
#include "tracked_memory_test.h"
#include "sample.h"
#ifdef HAVE_GUEST_FILE_FIXTURE
#include "../fastaes/elfload.h"
#include "android_context.h"
#include "file_traces.h"
static bunker::windows::FileSystem *guest_files;
static void *ResolveFile(const char *name) { return reinterpret_cast<void *>(guest_files->Marker(name)); }
#endif

static uint32_t Crc32(const void *data, size_t length) {
  auto bytes = static_cast<const uint8_t *>(data); uint32_t result = 0xffffffff;
  for (size_t i = 0; i < length; ++i) {
    result ^= bytes[i]; for (unsigned j = 0; j < 8; ++j) result = (result >> 1) ^ (0xedb88320 & (0 - (result & 1)));
  }
  return ~result;
}
int main() {
  using namespace bunker::windows;
  unsigned checks = 0;
  auto require = [&](bool condition, const char *reason) { if (!condition) throw std::runtime_error(reason); ++checks; };
  std::filesystem::path root = std::filesystem::u8path(FILES_ROOT);
  FileSystem files;
  files.MountFile("/data/app/bunker/base.apk", root / "base.apk");
  files.MountDirectory("/data/user/0/bunker/files", root / "sandbox", true);
  files.SetWorkingDirectory("/data/user/0/bunker/files");
  AndroidStat info{}, by_fd{};
  require(files.Stat("/data/app/bunker/base.apk", &info) == 0 && info.size == static_cast<int64_t>(kApkSize) && info.mode == (0100000 | 0444), "real APK guest stat layout/size/mode");
  int apk = files.Open("/data/app/bunker/base.apk", 0);
  require(apk >= 1000 && files.FStat(apk, &by_fd) == 0 && info.inode == by_fd.inode && info.size == by_fd.size, "fstat same-file identity");
  require(info.modification_time.nanoseconds >= 0 && info.modification_time.nanoseconds < 1000000000 && !info.pad1 && !info.pad2 && !info.unused4 && !info.unused5, "Android timestamp and padding fields");
  std::vector<uint8_t> sample(kAssetLength);
  require(files.Seek(apk, kAssetOffset, SEEK_SET) == static_cast<int64_t>(kAssetOffset), "APK asset-range 64-bit seek");
  require(files.Read(apk, sample.data(), sample.size()) == static_cast<int64_t>(sample.size()) && Crc32(sample.data(), sample.size()) == kAssetCrc, "actual APK asset-range checksum");
  auto stream = files.FOpen("/data/app/bunker/base.apk", "rb");
  require(stream && files.FSeek(stream, kAssetOffset, SEEK_SET) == 0 && files.FTell(stream) == static_cast<int64_t>(kAssetOffset), "stdio seek/tell ABI");
  std::fill(sample.begin(), sample.end(), 0);
  require(files.FRead(sample.data(), 1, sample.size(), stream) == sample.size() && Crc32(sample.data(), sample.size()) == kAssetCrc, "stdio reads exact real asset bytes");
  require(files.FClose(stream) == 0 && files.FClose(stream) == -1 && files.Error() == 9, "FILE lifetime/double close");
  uint64_t map_offset = kAssetOffset & ~4095ULL, delta = kAssetOffset - map_offset, map_size = delta + kAssetLength;
  auto mapped = files.Mmap(0, map_size, 1, linux_flags::map_private, apk, map_offset);
  require(mapped != UINT64_MAX && Crc32(reinterpret_cast<const void *>(mapped + delta), kAssetLength) == kAssetCrc, "mmap aligns Android 4K offset to Windows 64K granularity");
  require(files.Mprotect(mapped, map_size, 3) == 0, "private file mapping can become writable");
  *reinterpret_cast<uint8_t *>(mapped + delta) ^= 0xff;
  require(files.Munmap(mapped, map_size) == 0, "file mapping ownership");
  require(files.Seek(apk, kAssetOffset, SEEK_SET) == static_cast<int64_t>(kAssetOffset) && files.Read(apk, sample.data(), sample.size()) == static_cast<int64_t>(sample.size()) && Crc32(sample.data(), sample.size()) == kAssetCrc, "private mmap changes do not modify original APK");
  require(files.Close(apk) == 0 && files.Read(apk, sample.data(), 1) == -1 && files.Error() == 9, "guest fd ownership");
  require(files.Open("/data/app/bunker/base.apk", linux_flags::write_only) < 0 && files.Error() == 30, "APK mount is read-only");
  require(files.Access("/data/app/bunker/base.apk", 0) == 0 && files.Access("/data/app/bunker/base.apk", 1) == -1 && files.Error() == 13, "virtual asset executable permission is not fabricated");
  require(files.Open("/outside/data.bin", 0) < 0 && files.Error() == 2, "unmounted absolute path rejected");
  require(files.Open("../../../../../Windows/win.ini", 0) < 0 && files.Error() == 2, "virtual traversal cannot escape mounts");
  require(files.Open("NUL", 0) < 0 && files.Error() == 22, "Windows device alias blocked");
  require(files.Open("C:\\Windows\\win.ini", 0) < 0 && files.Error() == 22, "native host path not a guest path");
  int bytes = files.Open("bytes.bin", 0);
  uint8_t buffer[1001]{};
  require(bytes >= 0 && files.Read(bytes, buffer, sizeof(buffer)) == 1000 && files.Read(bytes, buffer, 1) == 0, "read partial EOF and EOF");
  require(files.Seek(bytes, 0, SEEK_SET) == 0 && files.Read(bytes, nullptr, 1) == -1 && files.Error() == 14, "read EFAULT");
  require(files.Seek(bytes, -1, SEEK_SET) == -1 && files.Error() == 22, "negative seek EINVAL");
  require(files.Seek(bytes, 100000, SEEK_SET) == 100000 && files.Read(bytes, buffer, 1) == 0, "POSIX file seek beyond EOF");
  files.Close(bytes);
  auto empty = files.FOpen("empty.bin", "rb");
  require(empty && files.FRead(buffer, 1, 1, empty) == 0 && files.FEof(empty) && !files.FError(empty), "stdio EOF flags");
  require(files.FSeek(empty, 0, SEEK_SET) == 0 && !files.FEof(empty), "fseek clears EOF"); files.FClose(empty);
  int created = files.Open("created.bin", linux_flags::read_write | linux_flags::create | linux_flags::truncate, 0600);
  const uint8_t data[] = {0, 10, 13, 255, 17};
  require(created >= 0 && files.Write(created, data, sizeof(data)) == sizeof(data) && files.Seek(created, 0, 0) == 0 && files.Read(created, buffer, sizeof(data)) == sizeof(data) && !std::memcmp(data, buffer, sizeof(data)), "binary fd write/read"); files.Close(created);
  require(files.Open("created.bin", linux_flags::write_only | linux_flags::create | linux_flags::exclusive) < 0 && files.Error() == 17, "exclusive create EEXIST");
  created = files.Open("created.bin", linux_flags::read_write);
  auto shared = files.Mmap(0, sizeof(data), 3, linux_flags::map_shared, created, 0);
  require(shared != UINT64_MAX, "shared writable file mapping");
  *reinterpret_cast<uint8_t *>(shared) = 0x5a;
  require(files.Munmap(shared, sizeof(data)) == 0 && files.Seek(created, 0, 0) == 0 && files.Read(created, buffer, 1) == 1 && buffer[0] == 0x5a, "shared file mapping updates file bytes"); files.Close(created);
  created = files.Open("created.bin", 0);
  require(files.Mmap(0, sizeof(data), 3, linux_flags::map_shared, created, 0) == UINT64_MAX && files.Error() == 13, "shared writable mapping requires writable descriptor"); files.Close(created);
  auto written = files.FOpen("stream.bin", "wb+");
  require(written && files.FWrite(data, 1, sizeof(data), written) == sizeof(data) && files.FFlush(written) == 0 && files.FSeek(written, 0, 0) == 0 && files.FRead(buffer, 1, sizeof(data), written) == sizeof(data) && !std::memcmp(data, buffer, sizeof(data)), "binary stdio write/flush/read"); files.FClose(written);
  auto anonymous = files.Mmap(0, 8192, 3, linux_flags::map_private | linux_flags::map_anonymous, -1, 0);
  require(anonymous != UINT64_MAX && std::all_of(reinterpret_cast<uint8_t *>(anonymous), reinterpret_cast<uint8_t *>(anonymous) + 8192, [](auto b) { return b == 0; }), "anonymous mmap zero initialization");
  files.SetError(123);
  require(files.Madvise(anonymous,8192,0)==0&&files.Error()==123,"normal advice preserves errno on success");
  require(files.Madvise(anonymous+4096,1,0)==0,"normal advice rounds a partial length to one page");
  require(files.Madvise(anonymous+1,0,0)==-1&&files.Error()==22,"normal advice requires alignment even for zero length");
  require(files.Madvise(0,0,0)==0&&files.Madvise(anonymous+8192,0,0)==0,"aligned empty advice does not require mapped pages");
  require(files.Madvise(anonymous,8193,0)==-1&&files.Error()==12,"normal advice rejects a partially unmapped rounded range");
  require(files.Madvise(0,1,0)==-1&&files.Error()==12,"normal advice rejects unmapped memory");
  require(files.Madvise(anonymous,UINT64_MAX,0)==-1&&files.Error()==22,"normal advice rejects length rounding overflow");
  require(files.Madvise(UINT64_MAX-4095,4096,0)==-1&&files.Error()==22,"normal advice rejects end-address overflow");
  for(int advice:{1,4,999,-1})require(files.Madvise(anonymous,0,advice)==-1&&files.Error()==22,"unsupported advice is rejected even for an empty range");
  uint64_t advice_data=0x1020304050607080;recomp::WriteGuestMemory(anonymous,&advice_data,8);
  auto advice_reservation=bunker::test::ReserveAcrossOperation(anonymous,8,[&]{if(files.Madvise(anonymous,8192,0))throw std::runtime_error("normal advice failed");});
  require(advice_reservation.status==0&&*reinterpret_cast<uint64_t*>(anonymous)==advice_data,"normal advice preserves bytes and guest exclusive reservations");
  require(files.Mprotect(anonymous,8192,1)==0&&files.Madvise(anonymous,8192,0)==0,"normal advice accepts read-only mappings without touching bytes");
  auto advice_heap=std::make_unique<uint8_t[]>(16384);
  auto heap_page=(reinterpret_cast<addr_t>(advice_heap.get())+4095)&~UINT64_C(4095);
  require(files.Madvise(heap_page,4096,0)==0,"normal advice accepts committed CRT guest heap outside mmap registry");
  require(files.Madvise(reinterpret_cast<addr_t>(&main)&~UINT64_C(4095),1,0)==0,"normal advice accepts committed executable image pages");
  auto raw_mapping=reinterpret_cast<addr_t>(VirtualAlloc(nullptr,16384,MEM_RESERVE,PAGE_NOACCESS));
  require(raw_mapping&&VirtualAlloc(reinterpret_cast<void*>(raw_mapping),4096,MEM_COMMIT,PAGE_READONLY)&&VirtualAlloc(reinterpret_cast<void*>(raw_mapping+12288),4096,MEM_COMMIT,PAGE_NOACCESS),"prepare committed range with a reserved hole");
  require(files.Madvise(raw_mapping,16384,0)==-1&&files.Error()==12,"normal advice rejects a hole between committed regions");
  require(VirtualAlloc(reinterpret_cast<void*>(raw_mapping+4096),8192,MEM_COMMIT,PAGE_READWRITE)&&files.Madvise(raw_mapping,16384,0)==0,"normal advice walks adjacent committed regions with different protections");
  MEMORY_BASIC_INFORMATION advice_info{};VirtualQuery(reinterpret_cast<void*>(raw_mapping+12288),&advice_info,sizeof(advice_info));
  require(advice_info.Protect==PAGE_NOACCESS&&VirtualFree(reinterpret_cast<void*>(raw_mapping),0,MEM_RELEASE),"normal advice preserves protection and does not commit reserved memory");
  require(files.Mmap(anonymous, 8192, 3, linux_flags::map_private | linux_flags::map_anonymous | linux_flags::map_fixed_no_replace, -1, 0) == UINT64_MAX && files.Error() == 17, "MAP_FIXED_NOREPLACE cannot replace live guest mapping");
  require(files.Munmap(anonymous, 4096) == -1 && files.Error() == 95, "partial unmap is explicitly unsupported");
  require(files.Mprotect(anonymous, 8192, 1) == 0 && files.Munmap(anonymous, 8192) == 0, "anonymous mmap protection and release");
  require(files.Munmap(anonymous, 8192) == -1 && files.Error() == 22, "stale mmap rejected");
  require(files.Mmap(0, 0, 1, 2, -1, 0) == UINT64_MAX && files.Error() == 22, "zero mmap length rejected");
  auto sparse_path = root / "sandbox/large.bin";
  HANDLE sparse = CreateFileW(sparse_path.c_str(), GENERIC_READ | GENERIC_WRITE, FILE_SHARE_READ, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
  require(sparse != INVALID_HANDLE_VALUE, "create sparse metadata fixture");
  DWORD returned; require(DeviceIoControl(sparse, FSCTL_SET_SPARSE, nullptr, 0, nullptr, 0, &returned, nullptr), "mark large fixture sparse");
  LARGE_INTEGER position; position.QuadPart = 0x100000010LL;
  require(SetFilePointerEx(sparse, position, nullptr, FILE_BEGIN) && SetEndOfFile(sparse), "large sparse fixture size");
  position.QuadPart = 0x100000005LL;
  uint8_t marker = 0x7f; DWORD stored;
  require(SetFilePointerEx(sparse, position, nullptr, FILE_BEGIN) && WriteFile(sparse, &marker, 1, &stored, nullptr) && stored == 1, "large fixture marker"); CloseHandle(sparse);
  int large = files.Open("large.bin", 0);
  require(large >= 0 && files.FStat(large, &info) == 0 && info.size == 0x100000010LL, "Android stat retains >4GB size on Windows LLP64");
  require(files.Seek(large, 0x100000005LL, 0) == 0x100000005LL && files.Read(large, buffer, 1) == 1 && buffer[0] == 0x7f, "64-bit fd offset beyond Windows long range");
  auto large_map = files.Mmap(0, 16, 1, 2, large, 0x100000000LL);
  require(large_map != UINT64_MAX && reinterpret_cast<const uint8_t *>(large_map)[5] == 0x7f && files.Munmap(large_map, 16) == 0, "64-bit mmap offset high word"); files.Close(large);
  auto large_stream = files.FOpen("large.bin", "rb");
  require(large_stream && files.FSeek(large_stream, 0x100000005LL, 0) == 0 && files.FTell(large_stream) == 0x100000005LL && files.FRead(buffer, 1, 1, large_stream) == 1 && buffer[0] == 0x7f, "64-bit stdio seek/tell on Windows LLP64"); files.FClose(large_stream);
  auto errno_address = files.ErrnoAddress();
  *reinterpret_cast<int32_t *>(errno_address) = 123;
  std::thread worker([&] { require(files.Error() == 0 && files.ErrnoAddress() != errno_address, "thread-local Android errno"); files.Close(-1); require(files.Error() == 9, "worker errno update"); });
  worker.join(); require(files.Error() == 123, "worker errno isolation");
  addr_t previous_errno = 0;
  for (unsigned i = 0; i < 3; ++i) {
    std::thread replacement([&] {
      require(files.Error() == 0 && files.ErrnoAddress() != previous_errno, "new native threads do not inherit errno through reused OS thread IDs");
      previous_errno = files.ErrnoAddress(); files.Close(-1);
    });
    replacement.join();
  }
  recomp::Runtime runtime; files.Install(runtime);
  // Actual provider writes must defeat a reservation even when bytes return to
  // the loaded value. A value-only compare/exchange would incorrectly succeed.
  const uint64_t sequence[]={9,7};
  int aba_file=files.Open("aba.bin",linux_flags::read_write|linux_flags::create|linux_flags::truncate,0600);
  require(aba_file>=0&&files.Write(aba_file,sequence,sizeof(sequence))==sizeof(sequence)&&files.Seek(aba_file,0,0)==0,"prepare actual file ABA bytes");
  alignas(64) uint64_t aba_buffer[16]{};uint64_t seven=7;recomp::WriteGuestMemory(reinterpret_cast<addr_t>(aba_buffer),&seven,8);
  auto reservation=bunker::test::ReserveAcrossOperation(reinterpret_cast<addr_t>(aba_buffer),8,[&]{if(files.Read(aba_file,aba_buffer,8)!=8||files.Read(aba_file,aba_buffer,8)!=8)throw std::runtime_error("file ABA read failed");});
  require(reservation.status==1&&aba_buffer[0]==7,"cross-thread fd read ABA invalidates guest exclusive reservation");
  files.Close(aba_file);auto aba_stream=files.FOpen("aba.bin","rb");
  reservation=bunker::test::ReserveAcrossOperation(reinterpret_cast<addr_t>(aba_buffer),8,[&]{if(files.FRead(aba_buffer,8,1,aba_stream)!=1||files.FRead(aba_buffer,8,1,aba_stream)!=1)throw std::runtime_error("stdio ABA read failed");});
  require(reservation.status==1&&aba_buffer[0]==7,"cross-thread fread ABA invalidates guest exclusive reservation");
  reservation=bunker::test::ReserveAcrossOperation(reinterpret_cast<addr_t>(aba_buffer),8,[&]{if(files.FRead(aba_buffer,8,1,aba_stream)!=0)throw std::runtime_error("expected EOF");});
  require(reservation.status==0,"EOF makes no tracked destination write");files.FClose(aba_stream);
  alignas(64) AndroidStat tracked_stat{};files.Stat("bytes.bin",&tracked_stat);
  reservation=bunker::test::ReserveAcrossOperation(reinterpret_cast<addr_t>(&tracked_stat),8,[&]{if(files.Stat("bytes.bin",&tracked_stat))throw std::runtime_error("tracked stat failed");});
  require(reservation.status==1,"same-value stat output invalidates reservation");
  aba_file=files.Open("aba.bin",0);
  files.FStat(aba_file,&tracked_stat);
  reservation=bunker::test::ReserveAcrossOperation(reinterpret_cast<addr_t>(&tracked_stat.size),8,[&]{if(files.FStat(aba_file,&tracked_stat))throw std::runtime_error("tracked fstat failed");});
  require(reservation.status==1&&tracked_stat.size==16,"fstat publishes complete Android wire structure");files.Close(aba_file);
  // fread publishes trailing bytes of an incomplete item, not only the item
  // count returned to its caller. Preserve the untouched tail of the buffer.
  auto partial=files.FOpen("bytes.bin","rb");files.FSeek(partial,995,0);std::memset(aba_buffer,0xcd,sizeof(aba_buffer));
  require(files.FRead(aba_buffer,3,3,partial)==1&&reinterpret_cast<uint8_t*>(aba_buffer)[4]==static_cast<uint8_t>(999*37+11)&&reinterpret_cast<uint8_t*>(aba_buffer)[5]==0xcd,"fread tracks five actual bytes while returning one complete item");files.FClose(partial);
  std::vector<uint8_t> large_io(65536+73);for(size_t i=0;i<large_io.size();++i)large_io[i]=static_cast<uint8_t>(i*17+5);
  auto large_io_file=files.FOpen("bounce.bin","wb+");require(large_io_file&&files.FWrite(large_io.data(),7,large_io.size()/7,large_io_file)==large_io.size()/7&&files.FSeek(large_io_file,0,0)==0,"stdio tracked input spans bounce-buffer boundary");
  std::vector<uint8_t> roundtrip(large_io.size(),0);auto complete_bytes=large_io.size()/7*7;
  require(files.FRead(roundtrip.data(),1,complete_bytes,large_io_file)==complete_bytes&&std::equal(roundtrip.begin(),roundtrip.begin()+complete_bytes,large_io.begin()),"stdio tracked copy-back spans bounce-buffer boundary");files.FClose(large_io_file);
  aba_file=files.Open("input-snapshot.bin",linux_flags::write_only|linux_flags::create|linux_flags::truncate,0600);aba_buffer[0]=7;
  reservation=bunker::test::ReserveAcrossOperation(reinterpret_cast<addr_t>(aba_buffer),8,[&]{if(files.Write(aba_file,aba_buffer,8)!=8)throw std::runtime_error("snapshot write failed");});
  require(reservation.status==0,"fd write snapshots guest input without invalidating its reservation");files.Close(aba_file);
  std::atomic<addr_t> worker_errno{0};std::atomic<bool> errno_go{false};std::thread errno_worker([&]{files.SetError(123);worker_errno=files.ErrnoAddress();while(!errno_go.load())std::this_thread::yield();files.SetError(9);files.SetError(123);});
  while(!worker_errno.load())std::this_thread::yield();
  reservation=bunker::test::ReserveAcrossOperation(worker_errno.load(),4,[&]{errno_go=true;errno_worker.join();});
  require(reservation.status==1&&*reinterpret_cast<int32_t*>(worker_errno.load())==123,"cross-thread errno ABA is tracked");
  State call{}; call.gpr.x0.qword = reinterpret_cast<addr_t>("/data/app/bunker/base.apk"); call.gpr.x1.qword = 0; call.gpr.x30.qword = 0xfeedffff;
  runtime.Run(call, files.Marker("open"));
  require(static_cast<int32_t>(call.gpr.x0.dword) >= 1000 && call.gpr.pc.qword == 0xfeedffff, "typed guest file import marker"); files.Close(call.gpr.x0.dword);
#ifdef HAVE_GUEST_FILE_FIXTURE
  guest_files = &files;
  elf_image image;
  require(elf_load(GUEST_FILES_IMAGE, 0x60000000, ResolveFile, &image) == 0, "NDK caller ELF data image");
  runtime.AddTraces(kTraces, sizeof(kTraces) / sizeof(kTraces[0]));
  alignas(16) uint8_t guest_stack[1 << 16];
  auto invoke = [&](const char *name, std::initializer_list<addr_t> arguments) {
    State state{}; Reg GPR::*registers[] = {&GPR::x0, &GPR::x1, &GPR::x2, &GPR::x3, &GPR::x4, &GPR::x5, &GPR::x6, &GPR::x7};
    size_t index = 0; for (auto arg : arguments) (state.gpr.*registers[index++]).qword = arg;
    state.gpr.sp.qword = reinterpret_cast<addr_t>(guest_stack + sizeof(guest_stack)); state.gpr.x30.qword = 0xfeedffff;
    auto entry = reinterpret_cast<addr_t>(elf_symbol(&image, name));
    state.gpr.pc.qword = entry; runtime.Run(state, entry);
    if (state.gpr.pc.qword != 0xfeedffff || state.gpr.sp.qword != reinterpret_cast<addr_t>(guest_stack + sizeof(guest_stack))) throw std::runtime_error("NDK guest caller did not restore PC/SP");
    return state.gpr.x0.qword;
  };
  auto advised=files.Mmap(0,8192,3,linux_flags::map_private|linux_flags::map_anonymous,-1,0);
  require(advised!=UINT64_MAX,"translated advice test allocation");
  constexpr uint64_t advice_invalid=(UINT64_C(0xffffffff)<<32)|22,advice_unmapped=(UINT64_C(0xffffffff)<<32)|12;
  require(invoke("guest_madvise",{advised,8192,0})==123,"translated NDK normal advice and unchanged errno");
  require(invoke("guest_madvise",{advised+4096,1,0})==123,"translated NDK partial-page range");
  require(invoke("guest_madvise",{0,0,0})==123,"translated NDK empty range");
  require(invoke("guest_madvise",{advised+1,0,0})==advice_invalid,"translated NDK address alignment");
  require(invoke("guest_madvise",{advised,UINT64_MAX,0})==advice_invalid,"translated NDK length overflow");
  require(invoke("guest_madvise",{UINT64_MAX-4095,4096,0})==advice_invalid,"translated NDK end-address overflow");
  require(invoke("guest_madvise",{advised,8193,0})==advice_unmapped,"translated NDK range coverage");
  require(invoke("guest_madvise",{0,4096,0})==advice_unmapped,"translated NDK unmapped pages");
  require(invoke("guest_madvise",{advised,8192,4})==advice_invalid,"translated NDK discard advice explicitly unsupported");
  require(files.Munmap(advised,8192)==0&&invoke("guest_madvise",{advised,1,0})==advice_unmapped,"translated NDK stale mapping");
  addr_t apk_path = reinterpret_cast<addr_t>("/data/app/bunker/base.apk");
  require(invoke("guest_fd_checksum", {apk_path, kAssetOffset, kAssetLength, kApkSize}) == kAssetCrc, "translated NDK fd/stat/seek caller checksum");
  require(invoke("guest_stdio_checksum", {apk_path, kAssetOffset, kAssetLength}) == kAssetCrc, "translated NDK FILE/fseek/ftell caller checksum");
  require(invoke("guest_mmap_checksum", {apk_path, kAssetOffset, kAssetLength}) == kAssetCrc, "translated NDK mmap caller checksum");
  require(invoke("guest_large_stdio", {reinterpret_cast<addr_t>("large.bin")}) == 0x7f, "translated NDK >4GB stat/stdio caller");
  require(invoke("guest_missing_errno", {reinterpret_cast<addr_t>("missing.bin")}) == 2, "translated NDK errno indirection");
  require(invoke("guest_legacy_stdio", {}) == 22, "translated legacy __sF stride and actual standard output");
  auto legacy_stdio = files.StandardStreamsAddress();
  require(files.FClose(legacy_stdio+152)==0 && files.FWrite("x",1,1,legacy_stdio+152)==0 && files.Error()==9, "guest stdout close does not close native host stdout");
  bunker::jni::Host host([](addr_t) { return false; });
  AndroidContextConfig context_config;
  context_config.package_name = kPackageName; context_config.target_sdk = kTargetSdk; context_config.activity_class = kLaunchActivity;
  AndroidContext context(host, context_config); host.Install(runtime);
  auto activity = context.Activity();
  require(invoke("guest_context_checksum", {host.VmAddress(), activity, kAssetOffset, kAssetLength, kApkSize, static_cast<addr_t>(kTargetSdk)}) == kAssetCrc && host.PendingException().empty(), "translated JNI ApplicationInfo.sourceDir/getAssets to real APK checksum");
  host.DeleteLocalReference(activity);
#endif
  std::printf("Windows Android file ABI: %u checks passed; real APK asset %s raw CRC32=%08x, >4GB stat/seek/mmap, stdio, errno, mount boundaries.\n", checks, kAssetName, kAssetCrc);
}
