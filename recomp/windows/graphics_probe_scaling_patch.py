"""Apply a bounded native Win32 Vulkan scaling prototype in the isolated pin.

This never touches angle-native or its accepted bundle. The actual HWND query
must pass first. Native present scaling supplies the logical swapchain images;
no GL framebuffer redirection or extension-string rewriting is used.
"""
from pathlib import Path
import difflib
import hashlib
import json

ROOT=Path(__file__).resolve().parent.parent/'work/angle-scaling'
SOURCE=ROOT/'src'
FILES=['src/libANGLE/Surface.h','src/libANGLE/Surface.cpp','src/libANGLE/queryutils.cpp',
       'src/libANGLE/renderer/SurfaceImpl.h','src/libANGLE/renderer/SurfaceImpl.cpp',
       'src/libANGLE/renderer/vulkan/SurfaceVk.h','src/libANGLE/renderer/vulkan/SurfaceVk.cpp',
       'src/libANGLE/renderer/vulkan/win32/DisplayVkWin32.h','src/libANGLE/renderer/vulkan/win32/DisplayVkWin32.cpp']


def main():
    stamp=ROOT/'scaling-patch.json'
    if stamp.exists():
        record=json.loads(stamp.read_text())
        for name,digest in record['files_sha256'].items():
            if hashlib.sha256((SOURCE/name).read_bytes()).hexdigest()!=digest:raise RuntimeError('Scaling source changed:'+name)
        print('Scaling prototype patch already verified');return
    before={p:(SOURCE/p).read_text() for p in FILES};data=dict(before)
    def replace(file,old,new,count=1):
        if data[file].count(old)!=count:raise RuntimeError('Scaling patch anchor:'+file+' count'+str(data[file].count(old)))
        data[file]=data[file].replace(old,new)
    # Propagate real backend size validation before changing frontend dimensions.
    for file in ['src/libANGLE/Surface.h','src/libANGLE/Surface.cpp']:
        for axis in ['Width','Height']:
            if file.endswith('.h'):replace(file,'void setFixed'+axis+'(EGLint '+axis.lower()+');','Error setFixed'+axis+'(EGLint '+axis.lower()+');')
            else:
                var=axis.lower()
                replace(file,'void Surface::setFixed'+axis+'(EGLint '+var+')\n{\n    mFixed'+axis+' = '+var+';\n    mImplementation->setFixed'+axis+'('+var+');\n}',
                        'Error Surface::setFixed'+axis+'(EGLint '+var+')\n{\n    ANGLE_TRY(mImplementation->validateFixedSize('+(var+', getHeight()' if axis=='Width' else 'getWidth(), '+var)+'));\n    mImplementation->setFixed'+axis+'('+var+');\n    mFixed'+axis+' = '+var+';\n    onStateChange(angle::SubjectMessage::SurfaceChanged);\n    return NoError();\n}')
    replace('src/libANGLE/renderer/SurfaceImpl.h','    virtual void setFixedWidth(EGLint width);',
            '    virtual egl::Error validateFixedSize(EGLint width, EGLint height) const;\n    virtual void setFixedWidth(EGLint width);')
    replace('src/libANGLE/renderer/SurfaceImpl.cpp','void SurfaceImpl::setFixedWidth(EGLint width)',
            'egl::Error SurfaceImpl::validateFixedSize(EGLint, EGLint) const\n{\n    return egl::NoError();\n}\n\nvoid SurfaceImpl::setFixedWidth(EGLint width)')
    for axis in ['Width','Height']:
        replace('src/libANGLE/queryutils.cpp','surface->setFixed'+axis+'(value);\n            break;','return surface->setFixed'+axis+'(value);')
    header='src/libANGLE/renderer/vulkan/SurfaceVk.h'
    replace(header,'    void setSwapInterval(const egl::Display *display, EGLint interval) override;\n\n    // Sizes',
            '    void setSwapInterval(const egl::Display *display, EGLint interval) override;\n    egl::Error validateFixedSize(EGLint width, EGLint height) const override;\n    void setFixedWidth(EGLint width) override;\n    void setFixedHeight(EGLint height) override;\n\n    // Sizes')
    replace(header,'    bool mIsSurfaceSizedBySwapchain;','''    bool mIsSurfaceSizedBySwapchain;
    bool mNativeFixedSize;
    EGLint mRequestedFixedWidth;
    EGLint mRequestedFixedHeight;
    VkExtent2D mFixedMinExtent = {1, 1};
    VkExtent2D mFixedMaxExtent = {0, 0};
    mutable VkExtent2D mLastPhysicalExtent = {0, 0};''')
    cpp='src/libANGLE/renderer/vulkan/SurfaceVk.cpp'
    replace(cpp,'#include "libANGLE/renderer/vulkan/SurfaceVk.h"','#include "libANGLE/renderer/vulkan/SurfaceVk.h"\n#include <cstdio>\n#include <cstdlib>')
    replace(cpp,'      mIsSurfaceSizedBySwapchain(false),','''      mIsSurfaceSizedBySwapchain(false),
      mNativeFixedSize(surfaceState.attributes.getAsInt(EGL_FIXED_SIZE_ANGLE, EGL_FALSE) == EGL_TRUE),
      mRequestedFixedWidth(surfaceState.attributes.getAsInt(EGL_WIDTH, 0)),
      mRequestedFixedHeight(surfaceState.attributes.getAsInt(EGL_HEIGHT, 0)),''')
    replace(cpp,'egl::Error WindowSurfaceVk::initialize(const egl::Display *display)\n{','''egl::Error WindowSurfaceVk::initialize(const egl::Display *display)
{
    if (mNativeFixedSize && (mRequestedFixedWidth <= 0 || mRequestedFixedHeight <= 0))
        return egl::Error(EGL_BAD_PARAMETER, "Native Vulkan fixed buffers require positive dimensions.");''')
    anchor='    ANGLE_TRY(GetPresentModes(displayVk, physicalDevice, mSurface, &mPresentModes));'
    replace(cpp,anchor,anchor+'''

    if (mNativeFixedSize)
    {
        if (!IsWindows() || !renderer->getFeatures().supportsSurfaceMaintenance1.enabled ||
            !renderer->getFeatures().supportsSwapchainMaintenance1.enabled)
            return angle::Result::Continue;
        const auto &limits = renderer->getPhysicalDeviceProperties().limits;
        mFixedMaxExtent.width = std::min(limits.maxImageDimension2D, limits.maxFramebufferWidth);
        mFixedMaxExtent.height = std::min(limits.maxImageDimension2D, limits.maxFramebufferHeight);
        for (vk::PresentMode mode : mPresentModes)
        {
            VkSurfacePresentModeEXT present = {};
            present.sType = VK_STRUCTURE_TYPE_SURFACE_PRESENT_MODE_EXT;
            present.presentMode = vk::ConvertPresentModeToVkPresentMode(mode);
            VkPhysicalDeviceSurfaceInfo2KHR query = {};
            query.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SURFACE_INFO_2_KHR;
            query.surface = mSurface;
            query.pNext = &present;
            VkSurfacePresentScalingCapabilitiesEXT scaling = {};
            scaling.sType = VK_STRUCTURE_TYPE_SURFACE_PRESENT_SCALING_CAPABILITIES_EXT;
            VkSurfaceCapabilities2KHR caps = {};
            caps.sType = VK_STRUCTURE_TYPE_SURFACE_CAPABILITIES_2_KHR;
            caps.pNext = &scaling;
            ANGLE_VK_TRY(displayVk, vkGetPhysicalDeviceSurfaceCapabilities2KHR(physicalDevice, &query, &caps));
            if ((scaling.supportedPresentScaling & VK_PRESENT_SCALING_STRETCH_BIT_EXT) == 0)
                return angle::Result::Continue;
            mFixedMinExtent.width = std::max(mFixedMinExtent.width, scaling.minScaledImageExtent.width);
            mFixedMinExtent.height = std::max(mFixedMinExtent.height, scaling.minScaledImageExtent.height);
            mFixedMaxExtent.width = std::min(mFixedMaxExtent.width, scaling.maxScaledImageExtent.width);
            mFixedMaxExtent.height = std::min(mFixedMaxExtent.height, scaling.maxScaledImageExtent.height);
        }
        if (static_cast<uint32_t>(mRequestedFixedWidth) < mFixedMinExtent.width ||
            static_cast<uint32_t>(mRequestedFixedHeight) < mFixedMinExtent.height ||
            static_cast<uint32_t>(mRequestedFixedWidth) > mFixedMaxExtent.width ||
            static_cast<uint32_t>(mRequestedFixedHeight) > mFixedMaxExtent.height)
            return angle::Result::Continue;
    }
''')
    replace(cpp,'    VkImageCompressionControlEXT compressionInfo = {};','''    VkSwapchainPresentScalingCreateInfoEXT scalingInfo = {};
    if (mNativeFixedSize)
    {
        scalingInfo.sType = VK_STRUCTURE_TYPE_SWAPCHAIN_PRESENT_SCALING_CREATE_INFO_EXT;
        scalingInfo.scalingBehavior = VK_PRESENT_SCALING_STRETCH_BIT_EXT;
        vk::AddToPNextChain(&swapchainInfo, &scalingInfo);
    }

    VkImageCompressionControlEXT compressionInfo = {};''')
    replace(cpp,'        VkSurfacePresentModeCompatibilityEXT compatibleModes = {};','''        VkSurfacePresentScalingCapabilitiesEXT scaling = {};
        if (mNativeFixedSize)
        {
            scaling.sType = VK_STRUCTURE_TYPE_SURFACE_PRESENT_SCALING_CAPABILITIES_EXT;
            vk::AddToPNextChain(&surfaceCaps2, &scaling);
        }

        VkSurfacePresentModeCompatibilityEXT compatibleModes = {};''')
    replace(cpp,'        *surfaceCapsOut = surfaceCaps2.surfaceCapabilities;','''        if (mNativeFixedSize)
        {
            ANGLE_VK_CHECK(context,
                (scaling.supportedPresentScaling & VK_PRESENT_SCALING_STRETCH_BIT_EXT) != 0 &&
                static_cast<uint32_t>(mRequestedFixedWidth) >= scaling.minScaledImageExtent.width &&
                static_cast<uint32_t>(mRequestedFixedHeight) >= scaling.minScaledImageExtent.height &&
                static_cast<uint32_t>(mRequestedFixedWidth) <= scaling.maxScaledImageExtent.width &&
                static_cast<uint32_t>(mRequestedFixedHeight) <= scaling.maxScaledImageExtent.height,
                VK_ERROR_INITIALIZATION_FAILED);
            // Force recreation on present-mode changes. Every fixed-size
            // swapchain is validated for its exact mode and scaling caps.
            if (compatiblePresentModesOut)
            {
                compatiblePresentModesOut->resize(1);
                (*compatiblePresentModesOut)[0] = surfacePresentMode.presentMode;
            }
        }
        *surfaceCapsOut = surfaceCaps2.surfaceCapabilities;''')
    replace(cpp,'    adjustSurfaceExtent(&surfaceCapsOut->currentExtent);','''    adjustSurfaceExtent(&surfaceCapsOut->currentExtent);
    if (mNativeFixedSize)
    {
        mLastPhysicalExtent = surfaceCapsOut->currentExtent;
        surfaceCapsOut->currentExtent.width = static_cast<uint32_t>(mRequestedFixedWidth);
        surfaceCapsOut->currentExtent.height = static_cast<uint32_t>(mRequestedFixedHeight);
    }''')
    replace(cpp,'if (renderer->getFeatures().avoidInvisibleWindowSwapchainRecreate.enabled)',
            'if (!mNativeFixedSize && renderer->getFeatures().avoidInvisibleWindowSwapchainRecreate.enabled)')
    anchor='void WindowSurfaceVk::setSwapInterval(const egl::Display *display, EGLint interval)'
    setters='''egl::Error WindowSurfaceVk::validateFixedSize(EGLint width, EGLint height) const
{
    if (!mNativeFixedSize || width <= 0 || height <= 0 ||
        static_cast<uint32_t>(width) < mFixedMinExtent.width ||
        static_cast<uint32_t>(height) < mFixedMinExtent.height ||
        static_cast<uint32_t>(width) > mFixedMaxExtent.width ||
        static_cast<uint32_t>(height) > mFixedMaxExtent.height)
        return egl::Error(EGL_BAD_PARAMETER, "Fixed buffer dimensions exceed actual Vulkan limits.");
    return egl::NoError();
}

void WindowSurfaceVk::setFixedWidth(EGLint width) { mRequestedFixedWidth = width; }
void WindowSurfaceVk::setFixedHeight(EGLint height) { mRequestedFixedHeight = height; }

'''
    replace(cpp,anchor,setters+anchor)
    replace(cpp,'    mLastSwapchain = newSwapChain;','''    mLastSwapchain = newSwapChain;
    if (mNativeFixedSize && std::getenv("BUNKER_ANGLE_SCALING_TRACE"))
    {
        std::fprintf(stderr, "BUNKER_SCALING_SWAPCHAIN buffer=%ux%u physical=%ux%u mode=%u flags=%u\\n",
                     swapchainInfo.imageExtent.width, swapchainInfo.imageExtent.height,
                     mLastPhysicalExtent.width, mLastPhysicalExtent.height,
                     static_cast<unsigned>(swapchainInfo.presentMode),
                     static_cast<unsigned>(scalingInfo.scalingBehavior));
    }''')
    replace(cpp,'    if (renderer->getFeatures().supportsSwapchainMaintenance1.enabled)\n    {\n        swapchainInfo.flags |= VK_SWAPCHAIN_CREATE_DEFERRED_MEMORY_ALLOCATION_BIT_EXT;',
            '    if (!mNativeFixedSize && renderer->getFeatures().supportsSwapchainMaintenance1.enabled)\n    {\n        swapchainInfo.flags |= VK_SWAPCHAIN_CREATE_DEFERRED_MEMORY_ALLOCATION_BIT_EXT;')
    h='src/libANGLE/renderer/vulkan/win32/DisplayVkWin32.h'
    replace(h,'    void terminate() override;','    void terminate() override;\n    void generateExtensions(egl::DisplayExtensions *outExtensions) const override;')
    replace(h,'    ATOM mWindowClass;','    bool mNativePresentScaling = false;\n    ATOM mWindowClass;')
    win='src/libANGLE/renderer/vulkan/win32/DisplayVkWin32.cpp'
    anchor='    vkDestroySurfaceKHR(instance, surfaceVk, nullptr);'
    replace(win,anchor,'''    mNativePresentScaling = false;
    if (mRenderer->getFeatures().supportsSurfaceMaintenance1.enabled &&
        mRenderer->getFeatures().supportsSwapchainMaintenance1.enabled)
    {
        uint32_t count = 0;
        if (vkGetPhysicalDeviceSurfacePresentModesKHR(physDevice, surfaceVk, &count, nullptr) == VK_SUCCESS && count > 0)
        {
            std::vector<VkPresentModeKHR> modes(count);
            if (vkGetPhysicalDeviceSurfacePresentModesKHR(physDevice, surfaceVk, &count, modes.data()) == VK_SUCCESS)
            {
                mNativePresentScaling = true;
                for (VkPresentModeKHR mode : modes)
                {
                    VkSurfacePresentModeEXT present = {};
                    present.sType = VK_STRUCTURE_TYPE_SURFACE_PRESENT_MODE_EXT;
                    present.presentMode = mode;
                    VkPhysicalDeviceSurfaceInfo2KHR query = {};
                    query.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SURFACE_INFO_2_KHR;
                    query.surface = surfaceVk;
                    query.pNext = &present;
                    VkSurfacePresentScalingCapabilitiesEXT scaling = {};
                    scaling.sType = VK_STRUCTURE_TYPE_SURFACE_PRESENT_SCALING_CAPABILITIES_EXT;
                    VkSurfaceCapabilities2KHR caps = {};
                    caps.sType = VK_STRUCTURE_TYPE_SURFACE_CAPABILITIES_2_KHR;
                    caps.pNext = &scaling;
                    if (vkGetPhysicalDeviceSurfaceCapabilities2KHR(physDevice, &query, &caps) != VK_SUCCESS ||
                        (scaling.supportedPresentScaling & VK_PRESENT_SCALING_STRETCH_BIT_EXT) == 0)
                        mNativePresentScaling = false;
                }
            }
        }
    }
''' +anchor)
    anchor='const char *DisplayVkWin32::getWSIExtension() const'
    replace(win,anchor,'''void DisplayVkWin32::generateExtensions(egl::DisplayExtensions *outExtensions) const
{
    DisplayVk::generateExtensions(outExtensions);
    outExtensions->windowFixedSize = mNativePresentScaling;
}

'''+anchor)
    for name,text in data.items():(SOURCE/name).write_text(text,newline='\n')
    patch=''.join(''.join(difflib.unified_diff(before[name].splitlines(True),data[name].splitlines(True),fromfile='a/'+name,tofile='b/'+name)) for name in FILES)
    (ROOT/'native-present-scaling.patch').write_text(patch,newline='\n')
    record={'source_pin':'890b5d8fa2988e3719e0d80421bf3e927db9cd5c','scope':'Isolated native present-scaling prototype; unaccepted until real GPU tests pass',
            'patch_sha256':hashlib.sha256((ROOT/'native-present-scaling.patch').read_bytes()).hexdigest(),
            'files_sha256':{name:hashlib.sha256((SOURCE/name).read_bytes()).hexdigest() for name in FILES}}
    stamp.write_text(json.dumps(record,indent=2)+'\n')
    print('Isolated native scaling prototype patched'+str(len(FILES))+' files')


if __name__=='__main__':main()
