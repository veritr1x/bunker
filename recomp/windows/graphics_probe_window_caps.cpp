// Read-only present-scaling queries on an actual NativeWindows HWND using the
// exact Vulkan instance/device selected by the accepted ANGLE EGL display.
#define wmain graphics_probe_unused_main
#include "graphics_probe.cpp"
#undef wmain
#include "native_window.h"
#include <cstring>
#include <EGL/egl.h>
#include <EGL/eglext.h>
#include <EGL/eglext_angle.h>
#define VK_USE_PLATFORM_WIN32_KHR 1
#define VK_NO_PROTOTYPES 1
#include <vulkan/vulkan.h>
using bunker::windows::NativeWindows;
template<class T>T Bits(EGLAttrib value){T typed;static_assert(sizeof(typed)==sizeof(value));std::memcpy(&typed,&value,sizeof(typed));return typed;}
template<class T>T VulkanProc(PFN_vkGetInstanceProcAddr get,VkInstance instance,const char *name){auto pointer=get(instance,name);require(pointer,std::string("Missing Vulkan procedure ")+name);T typed;static_assert(sizeof(typed)==sizeof(pointer));std::memcpy(&typed,&pointer,sizeof(typed));return typed;}
bool Extension(const char *const *extensions,const char *wanted){for(unsigned i=0;i<256&&extensions[i];++i)if(std::string(extensions[i])==wanted)return true;return false;}
int wmain(int argc,wchar_t **argv){
  SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX|SEM_NOOPENFILEERRORBOX);
  flag("success",false);flag("visible_window_created",false);int status=1;
  try{
    require(argc==2,"Need absolute accepted ANGLE DLL directory");Probe p;p.run(argv[1]);flag("success",false);
    text("stage","query exact ANGLE Vulkan device and actual NativeWindows HWND");
    auto displayQuery=p.glSymbol<PFNEGLQUERYDISPLAYATTRIBEXTPROC>("eglQueryDisplayAttribEXT");
    auto deviceQuery=p.glSymbol<PFNEGLQUERYDEVICEATTRIBEXTPROC>("eglQueryDeviceAttribEXT");
    EGLAttrib device_value=0;require(displayQuery(p.display,EGL_DEVICE_EXT,&device_value),"Cannot query ANGLE EGL device");
    auto device=Bits<EGLDeviceEXT>(device_value);
    auto attribute=[&](EGLint name){EGLAttrib value=0;require(deviceQuery(device,name,&value),"Cannot query ANGLE Vulkan device attribute "+hex(name));return value;};
    auto instance=Bits<VkInstance>(attribute(EGL_VULKAN_INSTANCE_ANGLE));
    auto physical=Bits<VkPhysicalDevice>(attribute(EGL_VULKAN_PHYSICAL_DEVICE_ANGLE));
    auto get=Bits<PFN_vkGetInstanceProcAddr>(attribute(EGL_VULKAN_GET_INSTANCE_PROC_ADDR));
    auto instance_extensions=Bits<const char*const*>(attribute(EGL_VULKAN_INSTANCE_EXTENSIONS_ANGLE));
    auto device_extensions=Bits<const char*const*>(attribute(EGL_VULKAN_DEVICE_EXTENSIONS_ANGLE));
    const bool instance_maintenance=Extension(instance_extensions,VK_EXT_SURFACE_MAINTENANCE_1_EXTENSION_NAME);
    const bool device_maintenance=Extension(device_extensions,VK_EXT_SWAPCHAIN_MAINTENANCE_1_EXTENSION_NAME);
    flag("angle_instance_surface_maintenance_enabled",instance_maintenance);flag("angle_device_swapchain_maintenance_enabled",device_maintenance);
    auto features=Bits<const VkPhysicalDeviceFeatures2*>(attribute(EGL_VULKAN_FEATURES_ANGLE));bool enabled=false;
    auto chain=reinterpret_cast<const VkBaseOutStructure*>(features->pNext);for(unsigned n=0;chain&&n<128;++n,chain=chain->pNext){
      if(chain->sType==VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SWAPCHAIN_MAINTENANCE_1_FEATURES_EXT)enabled=reinterpret_cast<const VkPhysicalDeviceSwapchainMaintenance1FeaturesEXT*>(chain)->swapchainMaintenance1==VK_TRUE;
    }
    flag("angle_swapchain_maintenance_feature_enabled",enabled);
    require(instance_maintenance&&device_maintenance&&enabled,"Accepted ANGLE did not enable required native scaling extensions/features");
    auto create=VulkanProc<PFN_vkCreateWin32SurfaceKHR>(get,instance,"vkCreateWin32SurfaceKHR");
    auto destroy=VulkanProc<PFN_vkDestroySurfaceKHR>(get,instance,"vkDestroySurfaceKHR");
    auto capabilities=VulkanProc<PFN_vkGetPhysicalDeviceSurfaceCapabilities2KHR>(get,instance,"vkGetPhysicalDeviceSurfaceCapabilities2KHR");
    auto present_modes=VulkanProc<PFN_vkGetPhysicalDeviceSurfacePresentModesKHR>(get,instance,"vkGetPhysicalDeviceSurfacePresentModesKHR");
    auto properties=VulkanProc<PFN_vkGetPhysicalDeviceProperties>(get,instance,"vkGetPhysicalDeviceProperties");
    VkPhysicalDeviceProperties props{};properties(physical,&props);text("vulkan_device",props.deviceName);number("max_image_dimension_2d",props.limits.maxImageDimension2D);
    bunker::jni::Host java([](addr_t){return false;});NativeWindows windows(java);
    auto window=windows.Create(640,360,u"Bunker native present scaling capabilities",false);auto java_surface=windows.NewSurface(window);auto token=windows.FromSurface(java_surface);
    auto native=static_cast<HWND>(windows.NativeHandle(token));bunker::windows::WindowDpiScope dpi(native);
    VkWin32SurfaceCreateInfoKHR info{};info.sType=VK_STRUCTURE_TYPE_WIN32_SURFACE_CREATE_INFO_KHR;info.hinstance=GetModuleHandleW(nullptr);info.hwnd=native;
    VkSurfaceKHR surface=VK_NULL_HANDLE;require(create(instance,&info,nullptr,&surface)==VK_SUCCESS,"Cannot create Vulkan query surface for actual NativeWindows HWND");
    try{
      uint32_t count=0;require(present_modes(physical,surface,&count,nullptr)==VK_SUCCESS&&count&&count<32,"Cannot enumerate HWND present modes");
      std::vector<VkPresentModeKHR> modes(count);require(present_modes(physical,surface,&count,modes.data())==VK_SUCCESS,"Cannot read HWND present modes");modes.resize(count);
      std::string output="[";bool first=true;bool fifo=false,all_stretch=true;
      for(auto mode:modes){VkSurfacePresentModeEXT present{};present.sType=VK_STRUCTURE_TYPE_SURFACE_PRESENT_MODE_EXT;present.presentMode=mode;
        VkPhysicalDeviceSurfaceInfo2KHR query{};query.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SURFACE_INFO_2_KHR;query.pNext=&present;query.surface=surface;
        VkSurfacePresentScalingCapabilitiesEXT scaling{};scaling.sType=VK_STRUCTURE_TYPE_SURFACE_PRESENT_SCALING_CAPABILITIES_EXT;
        VkSurfaceCapabilities2KHR caps{};caps.sType=VK_STRUCTURE_TYPE_SURFACE_CAPABILITIES_2_KHR;caps.pNext=&scaling;
        require(capabilities(physical,&query,&caps)==VK_SUCCESS,"Cannot query actual HWND/mode scaling limits");
        require(caps.surfaceCapabilities.currentExtent.width==640&&caps.surfaceCapabilities.currentExtent.height==360,"Actual Vulkan HWND extent differs from NativeWindows physical pixels");
        fifo|=mode==VK_PRESENT_MODE_FIFO_KHR;all_stretch&=(scaling.supportedPresentScaling&VK_PRESENT_SCALING_STRETCH_BIT_EXT)!=0;
        if(!first)output+=',';
        first=false;
        output+="{\"mode\":"+std::to_string(mode)+",\"scaling_flags\":"+std::to_string(scaling.supportedPresentScaling)+",\"gravity_x\":"+std::to_string(scaling.supportedPresentGravityX)+",\"gravity_y\":"+std::to_string(scaling.supportedPresentGravityY)+",\"min_width\":"+std::to_string(scaling.minScaledImageExtent.width)+",\"min_height\":"+std::to_string(scaling.minScaledImageExtent.height)+",\"max_width\":"+std::to_string(scaling.maxScaledImageExtent.width)+",\"max_height\":"+std::to_string(scaling.maxScaledImageExtent.height)+"}";
      }
      report["actual_hwnd_present_modes"]=output+"]";flag("actual_hwnd_all_modes_stretch",all_stretch);require(fifo&&all_stretch,"Actual HWND modes lack required real STRETCH scaling");
      windows.ResizeClient(window,800,450);
      VkSurfacePresentModeEXT present{};present.sType=VK_STRUCTURE_TYPE_SURFACE_PRESENT_MODE_EXT;present.presentMode=VK_PRESENT_MODE_FIFO_KHR;
      VkPhysicalDeviceSurfaceInfo2KHR query{};query.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SURFACE_INFO_2_KHR;query.pNext=&present;query.surface=surface;
      VkSurfacePresentScalingCapabilitiesEXT scaling{};scaling.sType=VK_STRUCTURE_TYPE_SURFACE_PRESENT_SCALING_CAPABILITIES_EXT;
      VkSurfaceCapabilities2KHR caps{};caps.sType=VK_STRUCTURE_TYPE_SURFACE_CAPABILITIES_2_KHR;caps.pNext=&scaling;
      require(capabilities(physical,&query,&caps)==VK_SUCCESS&&caps.surfaceCapabilities.currentExtent.width==800&&caps.surfaceCapabilities.currentExtent.height==450,"Vulkan capabilities did not follow actual physical HWND resize");
      flag("actual_hwnd_physical_resize_verified",true);number("actual_hwnd_initial_width",640);number("actual_hwnd_initial_height",360);number("actual_hwnd_resized_width",800);number("actual_hwnd_resized_height",450);
    }catch(...){destroy(instance,surface,nullptr);throw;}
    destroy(instance,surface,nullptr);windows.Release(token);windows.Close(window);java.DeleteLocalReference(java_surface);window.reset();
    text("stage","actual HWND native scaling capabilities verified; no swapchain or scaling enabled");flag("success",true);status=0;modules();
  }catch(const std::exception &e){flag("success",false);text("failure",e.what());modules();}
  std::cout<<"{\n";bool first=true;for(const auto &[key,value]:report){if(!first)std::cout<<",\n";first=false;std::cout<<"  "<<quote(key)<<": "<<value;}std::cout<<"\n}\n";return status;
}
