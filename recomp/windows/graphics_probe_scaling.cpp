// Native EGL/Vulkan fixed-buffer proof. Guest EGL/GL providers are untouched.
#define wmain graphics_probe_unused_main
#include "graphics_probe.cpp"
#undef wmain
#include "native_window.h"
using bunker::windows::NativeWindows;
int wmain(int argc,wchar_t **argv){
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
  flag("success",false);flag("visible_window_created",false);int status=1;
  try{
    require(argc==2,"Need absolute isolated scaling ANGLE DLL directory");Probe p;p.run(argv[1]);flag("success",false);
    const char *extensions=p.eglQueryString(p.display,0x3055);
    require(extensions&&std::string(extensions).find("EGL_ANGLE_window_fixed_size")!=std::string::npos,"Variant did not enable real fixed-size extension");
    flag("native_fixed_size_extension",true);
    using Create=E(WINAPI*)(E,E,HWND,const I*);using Query=U(WINAPI*)(E,E,I,I*);using Attrib=U(WINAPI*)(E,E,I,I);using Swap=U(WINAPI*)(E,E);using Interval=U(WINAPI*)(E,I);
    auto create=p.glSymbol<Create>("eglCreateWindowSurface");auto query=p.glSymbol<Query>("eglQuerySurface");auto attribute=p.glSymbol<Attrib>("eglSurfaceAttrib");auto swap=p.glSymbol<Swap>("eglSwapBuffers");auto interval=p.glSymbol<Interval>("eglSwapInterval");
    const I config_attributes[]={0x3033,4,0x3040,0x40,0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3031,0,0x3038};E config=nullptr;I count=0;
    p.eglCheck(p.eglChooseConfig(p.display,config_attributes,&config,1,&count),"native scaling window config");require(count==1&&config,"No native RGBA window config");
    bunker::jni::Host java([](addr_t){return false;});NativeWindows windows(java);auto window=windows.Create(640,360,u"Bunker native fixed swapchain",false);auto java_surface=windows.NewSurface(window);auto token=windows.FromSurface(java_surface);
    auto hwnd=static_cast<HWND>(windows.NativeHandle(token));bunker::windows::WindowDpiScope dpi(hwnd);
    const I context_attrs[]={0x3098,3,0x30fb,1,0x3038};E context=p.eglCreateContext(p.display,config,nullptr,context_attrs);require(context,"Scaling window context failed");
    const I fixed[]={0x3201,1,0x3057,160,0x3056,90,0x3038};E surface=create(p.display,config,hwnd,fixed);require(surface,"Real160x90 fixed swapchain creation failed EGL="+hex(p.eglGetError()));
    auto size=[&](I w,I h){I x=-1,y=-1,f=-1;p.eglCheck(query(p.display,surface,0x3057,&x),"logical buffer width");p.eglCheck(query(p.display,surface,0x3056,&y),"logical buffer height");p.eglCheck(query(p.display,surface,0x3201,&f),"fixed buffer flag");require(x==w&&y==h&&f==1,"Native logical fixed-buffer size query mismatch");};
    size(160,90);p.eglCheck(p.eglMakeCurrent(p.display,surface,surface,context),"bind actual fixed swapchain");
    U program=p.program({p.shader(0x8b31,"#version 310 es\nvoid main(){const vec2 v[3]=vec2[3](vec2(-1,-1),vec2(3,-1),vec2(-1,3));gl_Position=vec4(v[gl_VertexID],0,1);}"),p.shader(0x8b30,"#version 310 es\nprecision highp float;layout(location=0) out vec4 color;void main(){color=vec4(0,1,0,1);}")});
    U vao=0;p.glGenVertexArrays(1,&vao);p.glBindVertexArray(vao);size_t samples=0;
    auto draw=[&](I w,I h){p.glViewport(0,0,w,h);p.glUseProgram(program);p.glClearColor(1,0,0,1);p.glClear(0x4000);p.glDrawArrays(4,0,3);p.glFinish();
      for(auto xy:{std::pair<I,I>{0,0},{w-1,h-1},{w/2,h/2}}){std::array<uint8_t,4> pixel{};p.glReadPixels(xy.first,xy.second,1,1,0x1908,0x1401,pixel.data());require(pixel==std::array<uint8_t,4>{0,255,0,255},"Native fixed-buffer corner/center readback failed");++samples;}
      p.glCheck("native fixed buffer render/readback");p.eglCheck(swap(p.display,surface),"real native scaled window present");};
    draw(160,90);draw(160,90);
    windows.ResizeClient(window,800,450);require(windows.Describe(token).client_width==800&&windows.Describe(token).client_height==450,"Physical HWND resize failed");size(160,90);draw(160,90);draw(160,90);size(160,90);
    p.eglCheck(attribute(p.display,surface,0x3057,128),"resize logical buffer width");p.eglCheck(attribute(p.display,surface,0x3056,72),"resize logical buffer height");p.eglCheck(swap(p.display,surface),"apply fixed buffer attributes at swap");size(128,72);draw(128,72);draw(128,72);
    require(!attribute(p.display,surface,0x3057,0)&&p.eglGetError()!=0x3000,"Zero fixed width falsely succeeded");size(128,72);
    require(!attribute(p.display,surface,0x3056,-1)&&p.eglGetError()!=0x3000,"Negative fixed height falsely succeeded");size(128,72);
    require(!attribute(p.display,surface,0x3057,0x7fffffff)&&p.eglGetError()!=0x3000,"Oversized fixed width falsely succeeded");size(128,72);
    p.eglCheck(interval(p.display,0),"native scaled immediate interval");draw(128,72);draw(128,72);
    p.eglCheck(interval(p.display,1),"native scaled FIFO interval");draw(128,72);draw(128,72);
    p.glDeleteVertexArrays(1,&vao);p.glDeleteProgram(program);p.eglCheck(p.eglMakeCurrent(p.display,nullptr,nullptr,nullptr),"unbind fixed native objects");p.eglCheck(p.eglDestroySurface(p.display,surface),"destroy fixed native swapchain");p.eglCheck(p.eglDestroyContext(p.display,context),"destroy fixed native context");
    const I normal[]={0x3038};E default_surface=create(p.display,config,hwnd,normal);require(default_surface,"Normal native window surface regressed");I default_width=0;p.eglCheck(query(p.display,default_surface,0x3057,&default_width),"normal physical buffer width");require(default_width==800,"Nonfixed native window did not use physical width");
    require(!attribute(p.display,default_surface,0x3057,160)&&p.eglGetError()==0x3009,"Nonfixed SurfaceAttrib falsely enabled fixed mode");p.eglCheck(p.eglDestroySurface(p.display,default_surface),"destroy normal native surface");
    const I invalid[]={0x3201,1,0x3057,0x7fffffff,0x3056,90,0x3038};require(!create(p.display,config,hwnd,invalid)&&p.eglGetError()!=0x3000,"Oversized native fixed swapchain falsely created");
    windows.Release(token);windows.Close(window);java.DeleteLocalReference(java_surface);window.reset();number("fixed_readback_samples",samples);number("fixed_readback_verified_bytes",samples*4);number("fixed_real_presents",11);
    flag("physical_resize_keeps_logical_buffer",true);flag("surface_attrib_real_resize",true);flag("invalid_dimensions_rejected",true);flag("normal_surface_regression",true);
    text("stage","native scaled swapchain and logical resize/present proof complete");flag("success",true);status=0;modules();
  }catch(const std::exception &e){flag("success",false);text("failure",e.what());modules();}
  std::cout<<"{\n";bool first=true;for(const auto &[key,value]:report){if(!first)std::cout<<",\n";first=false;std::cout<<"  "<<quote(key)<<": "<<value;}std::cout<<"\n}\n";return status;
}
