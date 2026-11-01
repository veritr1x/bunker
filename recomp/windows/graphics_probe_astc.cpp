// Real offscreen ASTC acceptance against the pinned backend's public GL API.
// Oracle is the separately linked official Arm decoder, never a guest adapter.
#define wmain graphics_probe_base_main
#include "graphics_probe.cpp"
#undef wmain
#include "astcenc.h"
#include <algorithm>
#include <cmath>
#include <memory>

using Bytes = std::vector<uint8_t>;
struct Decoder {
  astcenc_context *context = nullptr;
  Decoder(unsigned bx, unsigned by, bool srgb) {
    astcenc_config config{};
    require(astcenc_config_init(srgb ? ASTCENC_PRF_LDR_SRGB : ASTCENC_PRF_LDR, bx, by, 1,
      ASTCENC_PRE_FASTEST, ASTCENC_FLG_DECOMPRESS_ONLY, &config) == ASTCENC_SUCCESS, "Oracle config failed");
    require(astcenc_context_alloc(&config, 1, &context) == ASTCENC_SUCCESS, "Oracle context failed");
  }
  ~Decoder() { astcenc_context_free(context); }
  Bytes decode(unsigned w, unsigned h, const Bytes &data) {
    Bytes out(w*h*4); void *slice = out.data();
    astcenc_image image{w,h,1,ASTCENC_TYPE_U8,&slice};
    const astcenc_swizzle swizzle{ASTCENC_SWZ_R,ASTCENC_SWZ_G,ASTCENC_SWZ_B,ASTCENC_SWZ_A};
    require(astcenc_decompress_image(context, data.data(), data.size(), &image, &swizzle, 0) == ASTCENC_SUCCESS, "Oracle decode failed");
    astcenc_decompress_reset(context); return out;
  }
};
Bytes solid(std::array<uint8_t,4> color) {
  Bytes result{0xfc,0xfd,0xff,0xff,0xff,0xff,0xff,0xff};
  for (auto c : color) { result.push_back(c); result.push_back(c); }
  return result;
}
Bytes image(unsigned w,unsigned h,unsigned bx,unsigned by,unsigned seed=0) {
  const std::array<std::array<uint8_t,4>,3> colors{{{43,173,0,255},{255,0,127,17},{0,115,255,255}}};
  Bytes data; unsigned n=((w+bx-1)/bx)*((h+by-1)/by);
  for(unsigned i=0;i<n;i++){auto b=solid(colors[(i+seed)%3]);data.insert(data.end(),b.begin(),b.end());}
  return data;
}
#define TEXTURE_APIS(X) \
 X(void, glActiveTexture, (U)) \
 X(void, glBindSampler, (U,U)) \
 X(void, glGetTexImageANGLE, (U,I,U,U,void*)) \
 X(void, glTexImage2D, (U,I,I,I,I,I,U,U,const void*)) \
 X(void, glGenTextures, (I,U*)) \
 X(void, glDeleteTextures, (I,const U*)) \
 X(void, glBindTexture, (U,U)) \
 X(void, glTexParameteri, (U,U,I)) \
 X(void, glCompressedTexImage2D, (U,I,U,I,I,I,I,const void*)) \
 X(void, glCompressedTexSubImage2D, (U,I,I,I,I,I,U,I,const void*)) \
 X(void, glTexStorage2D, (U,I,U,I,I)) \
 X(void, glTexStorage3D, (U,I,U,I,I,I)) \
 X(void, glCompressedTexSubImage3D, (U,I,I,I,I,I,I,I,U,I,const void*)) \
 X(void, glGetTexLevelParameteriv, (U,I,U,I*)) \
 X(I, glGetUniformLocation, (U,const char*)) \
 X(void, glUniform1f, (I,float))
#define TEX_DECLARE(ret,name,args) using name##T = ret(WINAPI*)args; name##T name=nullptr;
struct Textures {
  Probe &p; TEXTURE_APIS(TEX_DECLARE)
  U vao=0,program2d=0,programArray=0;
  size_t bytes=0,cases=0;
  explicit Textures(Probe &probe) : p(probe) {
#define TEX_LOAD(ret,name,args) name=p.glSymbol<name##T>(#name);
    TEXTURE_APIS(TEX_LOAD)
#undef TEX_LOAD
    const char *vertex="#version 310 es\nvoid main(){const vec2 v[3]=vec2[3](vec2(-1,-1),vec2(3,-1),vec2(-1,3));gl_Position=vec4(v[gl_VertexID],0,1);}";
    program2d=p.program({p.shader(0x8b31,vertex),p.shader(0x8b30,"#version 310 es\nprecision highp float;layout(binding=0) uniform highp sampler2D tex;uniform highp float lod;layout(location=0) out vec4 color;void main(){color=textureLod(tex,gl_FragCoord.xy/vec2(8),lod);}")});
    programArray=p.program({p.shader(0x8b31,vertex),p.shader(0x8b30,"#version 310 es\nprecision highp float;layout(binding=0) uniform highp sampler2DArray tex;uniform highp float layer;layout(location=0) out vec4 color;void main(){color=textureLod(tex,vec3(gl_FragCoord.xy/vec2(8),layer),0.0);}")});
    glActiveTexture(0x84c0);glBindSampler(0,0);
    p.glGenVertexArrays(1,&vao);p.glBindVertexArray(vao);p.glViewport(0,0,8,8);
    U solidProgram=p.program({p.shader(0x8b31,vertex),p.shader(0x8b30,"#version 310 es\nprecision highp float;layout(location=0) out vec4 color;void main(){color=vec4(1,0,0,1);}")});
    p.glUseProgram(solidProgram);p.glClearColor(0,0,1,1);p.glClear(0x4000);p.glDrawArrays(4,0,3);p.glFinish();std::array<uint8_t,256> control{};p.glReadPixels(0,0,8,8,0x1908,0x1401,control.data());p.glCheck("texture pipeline solid control");require(control[0]==255&&control[1]==0&&control[2]==0&&control[3]==255,"Texture pipeline solid control failed");p.glDeleteProgram(solidProgram);
  }
  ~Textures(){p.glDeleteVertexArrays(1,&vao);p.glDeleteProgram(program2d);p.glDeleteProgram(programArray);}
  void parameters(U target,bool mip=false){glTexParameteri(target,0x2800,0x2600);glTexParameteri(target,0x2801,mip?0x2700:0x2600);}
  void state(U target,I level,U format,unsigned w,unsigned h){
    I f=0,c=0,x=0,y=0;
    glGetTexLevelParameteriv(target,level,0x1003,&f);glGetTexLevelParameteriv(target,level,0x86a1,&c);
    glGetTexLevelParameteriv(target,level,0x1000,&x);glGetTexLevelParameteriv(target,level,0x1001,&y);
    p.glCheck("ASTC logical texture queries");
    require(U(f)==format&&c==1&&x==I(w)&&y==I(h),"ASTC logical texture query mismatch");
  }
  void sample(const Bytes &decoded,unsigned w,unsigned h,bool srgb,bool skip,bool array=false,float selector=0){
    U program=array?programArray:program2d;p.glUseProgram(program);
    glUniform1f(glGetUniformLocation(program,array?"layer":"lod"),selector);
    p.glClearColor(0,0,0,0);p.glClear(0x4000);p.glDrawArrays(4,0,3);p.glFinish();
    std::array<uint8_t,256> got{};p.glReadPixels(0,0,8,8,0x1908,0x1401,got.data());p.glCheck("ASTC sample/readback");
    for(unsigned y=0;y<8;y++)for(unsigned x=0;x<8;x++)for(unsigned c=0;c<4;c++){
      unsigned tx=std::min(w-1,unsigned((x+0.5)*w/8)),ty=std::min(h-1,unsigned((y+0.5)*h/8));
      int expected=decoded[(ty*w+tx)*4+c];
      if(srgb&&!skip&&c<3){double v=expected/255.0;expected=std::lround(255*(v<=0.04045?v/12.92:std::pow((v+0.055)/1.055,2.4)));}
      int tolerance=srgb&&!skip&&c<3?1:0;
      require(std::abs(int(got[(y*8+x)*4+c])-expected)<=tolerance,"ASTC sampled byte mismatch in case"+std::to_string(cases)+" byte"+std::to_string((y*8+x)*4+c)+" got"+std::to_string(got[(y*8+x)*4+c])+" expected"+std::to_string(expected));bytes++;
    }cases++;
  }
  void run(){
    { U control=0;glGenTextures(1,&control);glBindTexture(0x0de1,control);parameters(0x0de1);Bytes pixels(7*5*4);for(size_t i=0;i<pixels.size();i+=4){pixels[i]=43;pixels[i+1]=173;pixels[i+2]=0;pixels[i+3]=255;}glTexImage2D(0x0de1,0,0x8058,7,5,0,0x1908,0x1401,pixels.data());p.glCheck("uncompressed control");Bytes back(pixels.size());glGetTexImageANGLE(0x0de1,0,0x1908,0x1401,back.data());p.glCheck("uncompressed readback");require(back==pixels,"Uncompressed upload/readback failed");sample(pixels,7,5,false,false);glDeleteTextures(1,&control);number("uncompressed_control_verified_bytes",bytes);cases=0;bytes=0;flag("uncompressed_control",true);}
    I n=0;p.glGetIntegerv(0x86a2,&n);std::vector<I> formats(n);p.glGetIntegerv(0x86a3,formats.data());p.glCheck("Compressed format list");
    const std::array<std::array<unsigned,2>,14> footprints{{{4,4},{5,4},{5,5},{6,5},{6,6},{8,5},{8,6},{8,8},{10,5},{10,6},{10,8},{10,10},{12,10},{12,12}}};
    for(unsigned index=0;index<14;index++)for(bool srgb:{false,true}){
      unsigned bx=footprints[index][0],by=footprints[index][1];U format=(srgb?0x93d0:0x93b0)+index;
      require(std::find(formats.begin(),formats.end(),I(format))!=formats.end(),"ASTC format absent from compressed format query");
      Decoder oracle(bx,by,srgb);U texture=0;glGenTextures(1,&texture);glBindTexture(0x0de1,texture);parameters(0x0de1);
      auto data=image(7,5,bx,by);glCompressedTexImage2D(0x0de1,0,format,7,5,0,I(data.size()),data.data());p.glCheck("ASTC full upload");state(0x0de1,0,format,7,5);
      auto decoded=oracle.decode(7,5,data);sample(decoded,7,5,srgb,false);
      if(srgb){glTexParameteri(0x0de1,0x8a48,0x8a4a);sample(decoded,7,5,true,true);}
      auto replacement=solid({115,43,255,73});std::copy(replacement.begin(),replacement.end(),data.begin());
      glCompressedTexSubImage2D(0x0de1,0,0,0,std::min(bx,7u),std::min(by,5u),format,16,replacement.data());p.glCheck("ASTC block subimage");
      sample(oracle.decode(7,5,data),7,5,srgb,srgb);glDeleteTextures(1,&texture);
      glGenTextures(1,&texture);glBindTexture(0x0de1,texture);parameters(0x0de1,true);glTexStorage2D(0x0de1,4,format,8,8);
      for(unsigned level=0;level<4;level++){
        unsigned size=8>>level;auto mip=image(size,size,bx,by,level);
        glCompressedTexSubImage2D(0x0de1,level,0,0,size,size,format,I(mip.size()),mip.data());p.glCheck("ASTC immutable mip upload");state(0x0de1,level,format,size,size);
        sample(oracle.decode(size,size,mip),size,size,srgb,false,false,float(level));
      }glDeleteTextures(1,&texture);
      glGenTextures(1,&texture);glBindTexture(0x8c1a,texture);parameters(0x8c1a);glTexStorage3D(0x8c1a,1,format,7,5,2);
      auto first=image(7,5,bx,by,0),second=image(7,5,bx,by,1),both=first;both.insert(both.end(),second.begin(),second.end());
      glCompressedTexSubImage3D(0x8c1a,0,0,0,0,7,5,2,format,I(both.size()),both.data());p.glCheck("ASTC two-layer upload");
      sample(oracle.decode(7,5,first),7,5,srgb,false,true,0);sample(oracle.decode(7,5,second),7,5,srgb,false,true,1);
      glDeleteTextures(1,&texture);
    }
    const Bytes sensitive{0x41,0x01,0x65,0x6c,0xa8,0x12,0x21,0xff,0x4d,0x3a,0x40,0x59,0x52,0x7d,0xa6,0x05};
    Decoder linear(8,8,false),srgb(8,8,true);auto l=linear.decode(8,8,sensitive),s=srgb.decode(8,8,sensitive);
    size_t differences=0;for(size_t i=0;i<l.size();i++)differences+=l[i]!=s[i];require(differences>0,"Profile-sensitive oracle vector did not distinguish profiles");
    U texture=0;glGenTextures(1,&texture);glBindTexture(0x0de1,texture);parameters(0x0de1);
    glCompressedTexImage2D(0x0de1,0,0x93d7,8,8,0,16,sensitive.data());glTexParameteri(0x0de1,0x8a48,0x8a4a);sample(s,8,8,true,true);
    glDeleteTextures(1,&texture);number("astc_profile_sensitive_bytes",differences);
    number("astc_sample_cases",cases);number("astc_verified_bytes",bytes);number("astc_formats",28);flag("astc_sampling",true);
  }
};
int wmain(int argc,wchar_t **argv){
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
  flag("success",false);flag("astc_sampling",false);flag("visible_window_created",false);
  text("dependency_kind","workspace pinned ANGLE Vulkan with real ASTC decoder; source provenance required");
  int status=1;
  try{require(argc==2,"Need absolute DLL directory");Probe p;try{p.run(argv[1]);text("stage","ASTC28format+mip+subimage+array+profile sampling");Textures textures(p);textures.run();text("stage","complete");status=0;}catch(...){modules();throw;}modules();}
  catch(const std::exception &e){flag("success",false);text("failure",e.what());}
  if(!report.count("loaded_modules"))modules();
  std::cout<<"{\n";bool first=true;for(const auto &[key,value]:report){if(!first)std::cout<<",\n";first=false;std::cout<<"  "<<quote(key)<<": "<<value;}std::cout<<"\n}\n";return status;
}
