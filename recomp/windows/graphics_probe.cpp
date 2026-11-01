// Isolated native capability diagnostic. No guest runtime or window creation.
// Minimal ABI declarations/constants follow the Khronos EGL/GLES registry and
// ANGLE's EGL_ANGLE_platform_angle_vulkan extension; no external SDK is assumed.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>
#include <array>
#include <cstdint>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

using I = int32_t; using U = uint32_t; using E = void *;
static_assert(sizeof(void *) == 8, "This diagnostic requires Windows x64");
std::string quote(const std::string &s) {
  std::ostringstream out; out << '"';
  for (unsigned char c : s) {
    if (c == '"' || c == '\\') out << '\\' << c;
    else if (c == '\n') out << "\\n";
    else if (c == '\r') out << "\\r";
    else if (c == '\t') out << "\\t";
    else if (c < 32) out << '?';
    else out << c;
  }
  out << '"'; return out.str();
}
std::string utf8(const std::wstring &s) {
  int n = WideCharToMultiByte(CP_UTF8, 0, s.data(), int(s.size()), nullptr, 0, nullptr, nullptr);
  std::string result(n, '\0');
  WideCharToMultiByte(CP_UTF8, 0, s.data(), int(s.size()), result.data(), n, nullptr, nullptr);
  return result;
}
std::map<std::string, std::string> report;
void text(const std::string &k, const std::string &v) { report[k] = quote(v); }
void flag(const std::string &k, bool v) { report[k] = v ? "true" : "false"; }
void number(const std::string &k, int64_t v) { report[k] = std::to_string(v); }
void require(bool v, const std::string &message) { if (!v) throw std::runtime_error(message); }
std::string hex(U v) { std::ostringstream o; o << "0x" << std::hex << v; return o.str(); }
void modules();

#define EGL_APIS(X) \
 X(const char *, eglQueryString, (E, I)) \
 X(void *, eglGetProcAddress, (const char *)) \
 X(U, eglInitialize, (E, I *, I *)) \
 X(U, eglBindAPI, (U)) \
 X(U, eglChooseConfig, (E, const I *, E *, I, I *)) \
 X(E, eglCreateContext, (E, E, E, const I *)) \
 X(E, eglCreatePbufferSurface, (E, E, const I *)) \
 X(U, eglMakeCurrent, (E, E, E, E)) \
 X(U, eglDestroyContext, (E, E)) \
 X(U, eglDestroySurface, (E, E)) \
 X(U, eglTerminate, (E)) \
 X(I, eglGetError, ())
#define GL_APIS(X) \
 X(const unsigned char *, glGetString, (U)) \
 X(const unsigned char *, glGetStringi, (U, U)) \
 X(void, glGetIntegerv, (U, I *)) \
 X(U, glGetError, ()) \
 X(U, glCreateShader, (U)) \
 X(void, glShaderSource, (U, I, const char *const *, const I *)) \
 X(void, glCompileShader, (U)) \
 X(void, glGetShaderiv, (U, U, I *)) \
 X(void, glGetShaderInfoLog, (U, I, I *, char *)) \
 X(void, glDeleteShader, (U)) \
 X(U, glCreateProgram, ()) \
 X(void, glAttachShader, (U, U)) \
 X(void, glLinkProgram, (U)) \
 X(void, glGetProgramiv, (U, U, I *)) \
 X(void, glGetProgramInfoLog, (U, I, I *, char *)) \
 X(void, glDeleteProgram, (U)) \
 X(void, glUseProgram, (U)) \
 X(void, glGenVertexArrays, (I, U *)) \
 X(void, glBindVertexArray, (U)) \
 X(void, glDeleteVertexArrays, (I, const U *)) \
 X(void, glViewport, (I, I, I, I)) \
 X(void, glClearColor, (float, float, float, float)) \
 X(void, glClear, (U)) \
 X(void, glDrawArrays, (U, I, I)) \
 X(void, glPixelStorei, (U, I)) \
 X(void, glReadPixels, (I, I, I, I, U, U, void *)) \
 X(void, glGenBuffers, (I, U *)) \
 X(void, glBindBuffer, (U, U)) \
 X(void, glBufferData, (U, intptr_t, const void *, U)) \
 X(void, glBindBufferBase, (U, U, U)) \
 X(void, glDispatchCompute, (U, U, U)) \
 X(void, glMemoryBarrier, (U)) \
 X(void *, glMapBufferRange, (U, intptr_t, intptr_t, U)) \
 X(unsigned char, glUnmapBuffer, (U)) \
 X(void, glDeleteBuffers, (I, const U *)) \
 X(void, glFinish, ())
#define DECLARE(ret, name, args) using name##T = ret (WINAPI *) args; name##T name = nullptr;
struct Probe {
  HMODULE egl = nullptr, gles = nullptr;
  E display = nullptr, context = nullptr, surface = nullptr;
  EGL_APIS(DECLARE)
  GL_APIS(DECLARE)
  ~Probe() {
    if (display && eglMakeCurrent) eglMakeCurrent(display, nullptr, nullptr, nullptr);
    if (display && context && eglDestroyContext) eglDestroyContext(display, context);
    if (display && surface && eglDestroySurface) eglDestroySurface(display, surface);
    if (display && eglTerminate) eglTerminate(display);
    // DLLs remain loaded until process exit: driver worker teardown is external.
  }
  template<class T> T eglSymbol(const char *name) {
    auto p = GetProcAddress(egl, name); require(p, std::string("Missing EGL export ") + name);
    return reinterpret_cast<T>(reinterpret_cast<void *>(p));
  }
  template<class T> T glSymbol(const char *name) {
    auto p = eglGetProcAddress(name);
    if (!p) p = reinterpret_cast<void *>(GetProcAddress(gles, name));
    require(p, std::string("Missing GLES entry ") + name); return reinterpret_cast<T>(p);
  }
  void eglCheck(U ok, const char *operation) {
    if (!ok) throw std::runtime_error(std::string(operation) + " failed EGL=" + hex(eglGetError()));
  }
  void glCheck(const char *operation) {
    U e = glGetError(); require(e == 0, std::string(operation) + " GL error=" + hex(e));
  }
  U shader(U kind, const char *source) {
    U s = glCreateShader(kind); require(s, "glCreateShader failed");
    glShaderSource(s, 1, &source, nullptr); glCompileShader(s);
    I ok = 0; glGetShaderiv(s, 0x8b81, &ok);
    char log[8192] = {}; glGetShaderInfoLog(s, sizeof(log)-1, nullptr, log);
    require(ok, std::string("Shader compilation failed: ") + log); return s;
  }
  U program(const std::vector<U> &shaders) {
    U p = glCreateProgram(); require(p, "glCreateProgram failed");
    for (U s : shaders) glAttachShader(p, s);
    glLinkProgram(p); I ok = 0; glGetProgramiv(p, 0x8b82, &ok);
    char log[8192] = {}; glGetProgramInfoLog(p, sizeof(log)-1, nullptr, log);
    require(ok, std::string("Program linking failed: ") + log);
    for (U s : shaders) glDeleteShader(s);
    return p;
  }
  void run(const std::wstring &directory) {
    text("stage", "load installed diagnostic DLLs");
    require(SetDefaultDllDirectories(LOAD_LIBRARY_SEARCH_DEFAULT_DIRS), "SetDefaultDllDirectories failed");
    auto cookie = AddDllDirectory(directory.c_str()); require(cookie, "AddDllDirectory failed");
    const DWORD flags = LOAD_LIBRARY_SEARCH_DLL_LOAD_DIR | LOAD_LIBRARY_SEARCH_DEFAULT_DIRS;
    egl = LoadLibraryExW((directory + L"\\libEGL.dll").c_str(), nullptr, flags);
    require(egl, "LoadLibrary libEGL.dll failed Win32=" + std::to_string(GetLastError()));
    gles = LoadLibraryExW((directory + L"\\libGLESv2.dll").c_str(), nullptr, flags);
    require(gles, "LoadLibrary libGLESv2.dll failed Win32=" + std::to_string(GetLastError()));
#define EGL_LOAD(ret, name, args) name = eglSymbol<name##T>(#name);
    EGL_APIS(EGL_LOAD)
#undef EGL_LOAD
    const char *client = eglQueryString(nullptr, 0x3055);
    text("egl_client_extensions", client ? client : "");
    std::string clients = std::string(" ") + (client ? client : "") + " ";
    require(clients.find(" EGL_ANGLE_platform_angle_vulkan ") != std::string::npos,
            "Installed ANGLE does not advertise EGL_ANGLE_platform_angle_vulkan");
    using GetPlatform = E (WINAPI *)(U, void *, const I *);
    auto getPlatform = reinterpret_cast<GetPlatform>(eglGetProcAddress("eglGetPlatformDisplayEXT"));
    require(getPlatform, "eglGetPlatformDisplayEXT unavailable");
    // Vulkan hardware only. No null/software/D3D/default-backend fallback.
    const I platform[] = {0x3203, 0x3450, 0x3209, 0x320a, 0x3038};
    text("stage", "initialize explicit ANGLE Vulkan hardware display");
    display = getPlatform(0x3202, nullptr, platform);
    require(display, "No ANGLE Vulkan hardware display EGL=" + hex(eglGetError()));
    I major = 0, minor = 0; eglCheck(eglInitialize(display, &major, &minor), "eglInitialize");
    text("egl_version", std::to_string(major) + "." + std::to_string(minor));
    for (auto pair : {std::pair<const char *, I>{"egl_vendor", 0x3053}, {"egl_display_extensions", 0x3055}}) {
      const char *s = eglQueryString(display, pair.second); text(pair.first, s ? s : "");
    }
    eglCheck(eglBindAPI(0x30a0), "eglBindAPI(OpenGL_ES)");
    const I configAttribs[] = {0x3033, 1, 0x3040, 0x40, 0x3024, 8, 0x3023, 8, 0x3022, 8, 0x3021, 8, 0x3038};
    E config = nullptr; I count = 0;
    eglCheck(eglChooseConfig(display, configAttribs, &config, 1, &count), "eglChooseConfig");
    require(count == 1 && config, "No ES3 RGBA8 pbuffer config");
    const I contextAttribs[] = {0x3098, 3, 0x30fb, 1, 0x3038};
    text("stage", "create GLES3.1 context and8x8 offscreen pbuffer");
    context = eglCreateContext(display, config, nullptr, contextAttribs);
    require(context, "GLES3.1 context creation failed EGL=" + hex(eglGetError()));
    const I surfaceAttribs[] = {0x3057, 8, 0x3056, 8, 0x3038};
    surface = eglCreatePbufferSurface(display, config, surfaceAttribs);
    require(surface, "Pbuffer creation failed EGL=" + hex(eglGetError()));
    eglCheck(eglMakeCurrent(display, surface, surface, context), "eglMakeCurrent");
#define GL_LOAD(ret, name, args) name = glSymbol<name##T>(#name);
    GL_APIS(GL_LOAD)
#undef GL_LOAD
    for (auto pair : {std::pair<const char *, U>{"gl_vendor", 0x1f00}, {"gl_renderer", 0x1f01}, {"gl_version", 0x1f02}, {"glsl_version", 0x8b8c}}) {
      const auto *s = glGetString(pair.second); require(s, "glGetString returned null");
      text(pair.first, reinterpret_cast<const char *>(s));
    }
    I glMajor = 0, glMinor = 0;
    glGetIntegerv(0x821b, &glMajor); glGetIntegerv(0x821c, &glMinor);
    number("gl_major", glMajor); number("gl_minor", glMinor);
    require(glMajor > 3 || (glMajor == 3 && glMinor >= 1), "Actual context is below GLES3.1");
    flag("gles31", true);
    std::set<std::string> extensions; I n = 0; glGetIntegerv(0x821d, &n);
    std::string list;
    for (I i = 0; i < n; ++i) {
      auto s = glGetStringi(0x1f03, i); require(s, "glGetStringi returned null");
      extensions.emplace(reinterpret_cast<const char *>(s));
      if (!list.empty()) list += ' ';
      list += reinterpret_cast<const char *>(s);
    }
    text("gl_extensions", list); number("gl_extension_count", n);
    const char *aep[] = {"GL_KHR_debug", "GL_KHR_texture_compression_astc_ldr", "GL_KHR_blend_equation_advanced", "GL_OES_sample_shading", "GL_OES_sample_variables", "GL_OES_shader_image_atomic", "GL_OES_shader_multisample_interpolation", "GL_OES_texture_stencil8", "GL_OES_texture_storage_multisample_2d_array", "GL_EXT_copy_image", "GL_EXT_draw_buffers_indexed", "GL_EXT_geometry_shader", "GL_EXT_gpu_shader5", "GL_EXT_primitive_bounding_box", "GL_EXT_shader_io_blocks", "GL_EXT_tessellation_shader", "GL_EXT_texture_border_clamp", "GL_EXT_texture_buffer", "GL_EXT_texture_cube_map_array", "GL_EXT_texture_sRGB_decode"};
    std::string missing;
    for (auto s : aep) if (!extensions.count(s)) { if (!missing.empty()) missing += ' '; missing += s; }
    text("aep_missing_named_extensions", missing);
    bool aepAdvertised = extensions.count("GL_ANDROID_extension_pack_es31a");
    flag("aep_advertised", aepAdvertised);
    bool limits = true;
    for (auto row : {std::array<I, 3>{0x92d0, 1, 0}, {0x92d6, 8, 1}, {0x90ce, 4, 2}, {0x90da, 4, 3}}) {
      I value = 0; glGetIntegerv(row[0], &value);
      const char *keys[] = {"max_fragment_atomic_counter_buffers", "max_fragment_atomic_counters", "max_fragment_image_uniforms", "max_fragment_shader_storage_blocks"};
      number(keys[row[2]], value); limits &= value >= row[1];
    }
    flag("aep_fragment_limits", limits); glCheck("version/extension/limit queries");
    text("stage", "draw8x8 full-screen triangle and verify256 readback bytes");
    U draw = program({shader(0x8b31, R"(#version 310 es
void main(){const vec2 p[3]=vec2[3](vec2(-1,-1),vec2(3,-1),vec2(-1,3));gl_Position=vec4(p[gl_VertexID],0,1);})"),
      shader(0x8b30, "#version 310 es\nprecision highp float;layout(location=0) out vec4 color;void main(){color=vec4(1,0,0,1);}")});
    U vao = 0; glGenVertexArrays(1, &vao); glBindVertexArray(vao);
    glViewport(0, 0, 8, 8); glClearColor(0, 0, 1, 1); glClear(0x4000);
    glUseProgram(draw); glDrawArrays(4, 0, 3); glFinish();
    std::array<unsigned char, 256> pixels{}; glPixelStorei(0x0d05, 1);
    glReadPixels(0, 0, 8, 8, 0x1908, 0x1401, pixels.data()); glCheck("draw/readback");
    for (size_t i = 0; i < pixels.size(); ++i) require(pixels[i] == (i % 4 == 0 || i % 4 == 3 ? 255 : 0), "Draw readback mismatch at byte" + std::to_string(i));
    glDeleteVertexArrays(1, &vao); glDeleteProgram(draw); flag("draw_readback", true);
    number("draw_verified_bytes", pixels.size());
    text("stage", "compute64 SSBO values, memory barrier, map/readback");
    U compute = program({shader(0x91b9, R"(#version 310 es
layout(local_size_x=8) in;layout(std430,binding=0) buffer Result{uint data[];};
void main(){uint i=gl_GlobalInvocationID.x;data[i]=(i*1664525u+1013904223u)^0xa5a55a5au;})")});
    U buffer = 0; std::array<U, 64> initial{};
    glGenBuffers(1, &buffer); glBindBuffer(0x90d2, buffer);
    glBufferData(0x90d2, sizeof(initial), initial.data(), 0x88e8);
    glBindBufferBase(0x90d2, 0, buffer); glUseProgram(compute);
    glDispatchCompute(8, 1, 1); glMemoryBarrier(0x2200); glFinish();
    auto mapped = static_cast<const U *>(glMapBufferRange(0x90d2, 0, sizeof(initial), 1));
    require(mapped, "Compute result mapping failed GL=" + hex(glGetError()));
    for (U i = 0; i < 64; ++i) require(mapped[i] == ((i * 1664525u + 1013904223u) ^ 0xa5a55a5au), "Compute readback mismatch at index" + std::to_string(i));
    require(glUnmapBuffer(0x90d2), "glUnmapBuffer reported corrupted data");
    glDeleteBuffers(1, &buffer); glDeleteProgram(compute); glCheck("compute/readback");
    flag("compute_readback", true); number("compute_verified_uint32", initial.size());
    text("stage", "evaluate APK-required AEP extension and limit gates");
    if (aepAdvertised) {
      text("stage", "compile AEP directive shader");
      U s = shader(0x8b30, "#version 310 es\n#extension GL_ANDROID_extension_pack_es31a : require\nprecision highp float;layout(location=0) out vec4 color;void main(){color=vec4(1);}");
      glDeleteShader(s); flag("aep_directive_shader", true);
    }
    flag("aep_query_gate", aepAdvertised && missing.empty() && limits);
    // Core3.1 draw/compute may pass while the APK-required AEP gate fails.
    require(aepAdvertised && missing.empty() && limits, "GLES3.1 draw+compute passed, but APK-required AEP query/limit gate failed");
    text("stage", "complete"); flag("success", true);
  }
};
#undef DECLARE
void modules() {
  HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, GetCurrentProcessId());
  if (snapshot == INVALID_HANDLE_VALUE) return;
  MODULEENTRY32W entry{}; entry.dwSize = sizeof(entry); std::string result = "[";
  if (Module32FirstW(snapshot, &entry)) do {
    if (result.size() > 1) result += ',';
    result += quote(utf8(entry.szExePath));
  } while (Module32NextW(snapshot, &entry));
  CloseHandle(snapshot); report["loaded_modules"] = result + ']';
}
int wmain(int argc, wchar_t **argv) {
  SetErrorMode(SEM_FAILCRITICALERRORS | SEM_NOGPFAULTERRORBOX | SEM_NOOPENFILEERRORBOX);
  flag("success", false); flag("gles31", false); flag("draw_readback", false);
  flag("compute_readback", false); flag("aep_directive_shader", false);
  flag("aep_query_gate", false); text("dependency_kind", "installed VSCode diagnostic DLLs; not project SDK");
  text("requested_backend", "ANGLE Vulkan hardware"); flag("visible_window_created", false);
  int status = 1;
  try { require(argc == 2, "Usage: graphics-probe.exe ABSOLUTE_DLL_DIRECTORY");
    Probe probe;
    try { probe.run(argv[1]); status = 0; }
    catch (...) { modules(); throw; }
    modules();
  } catch (const std::exception &e) { text("failure", e.what()); }
  if (!report.count("loaded_modules")) modules();
  std::cout << "{\n"; bool first = true;
  for (const auto &[k, v] : report) { if (!first) std::cout << ",\n"; first = false; std::cout << "  " << quote(k) << ": " << v; }
  std::cout << "\n}\n"; return status;
}
