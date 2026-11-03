#pragma once
#include <algorithm>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <stdexcept>
#include <vector>

namespace bunker::windows {
// Diagnostic-only RGBA8 writer. Input is bottom-up OpenGL pixel order.
inline void WriteFramePng(const std::filesystem::path &path,uint32_t width,uint32_t height,
                          const std::vector<uint8_t> &rgba){
  if(!width||!height||uint64_t(width)*height*4!=rgba.size())throw std::invalid_argument("PNG frame extent");
  auto be=[](std::vector<uint8_t>&v,uint32_t x){for(int n=24;n>=0;n-=8)v.push_back(uint8_t(x>>n));};
  auto chunk=[&](std::vector<uint8_t>&out,const char *kind,const std::vector<uint8_t>&data){
    if(data.size()>UINT32_MAX)throw std::overflow_error("PNG chunk size");
    be(out,uint32_t(data.size()));const size_t start=out.size();
    for(unsigned i=0;i<4;++i){out.push_back(uint8_t(kind[i]));}
    out.insert(out.end(),data.begin(),data.end());
    uint32_t crc=UINT32_MAX;for(size_t i=start;i<out.size();++i){crc^=out[i];for(unsigned b=0;b<8;++b)crc=(crc>>1)^((crc&1)?0xedb88320u:0);}
    be(out,~crc);
  };
  std::vector<uint8_t> scan;scan.reserve(rgba.size()+height);
  const size_t stride=size_t(width)*4;
  for(uint32_t row=0;row<height;++row){scan.push_back(0);const auto first=rgba.begin()+size_t(height-1-row)*stride;scan.insert(scan.end(),first,first+stride);}
  std::vector<uint8_t> z{0x78,0x01};uint32_t a=1,b=0;
  for(uint8_t x:scan){a=(a+x)%65521;b=(b+a)%65521;}
  for(size_t offset=0;offset<scan.size();){const size_t n=std::min<size_t>(65535,scan.size()-offset);z.push_back(offset+n==scan.size()?1:0);
    const auto len=uint16_t(n),inverse=uint16_t(~len);z.push_back(uint8_t(len));z.push_back(uint8_t(len>>8));z.push_back(uint8_t(inverse));z.push_back(uint8_t(inverse>>8));
    z.insert(z.end(),scan.begin()+offset,scan.begin()+offset+n);offset+=n;}
  be(z,(b<<16)|a);std::vector<uint8_t> out{137,80,78,71,13,10,26,10},ihdr;
  be(ihdr,width);be(ihdr,height);ihdr.insert(ihdr.end(),{8,6,0,0,0});chunk(out,"IHDR",ihdr);chunk(out,"IDAT",z);chunk(out,"IEND",{});
  if(std::filesystem::exists(path))throw std::runtime_error("Preserve existing frame PNG");
  std::ofstream file(path,std::ios::binary);if(!file||!file.write(reinterpret_cast<const char*>(out.data()),std::streamsize(out.size())))throw std::runtime_error("Cannot write frame PNG");
}
}
