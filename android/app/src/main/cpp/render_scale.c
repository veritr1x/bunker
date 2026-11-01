// Upscaling below the screen's own resolution on Android: FSR 1 or SGSR 1.
//
// Unity lowers its resolution with ANativeWindow_setBuffersGeometry, and the
// phone's display hardware stretches the smaller window to the screen with
// plain filtering. With an upscaler chosen, the window keeps the screen's own
// size while Unity is told the size it asked for (setBuffersGeometry,
// ANativeWindow_getWidth/Height, eglQuerySurface), and its drawing to the
// screen (framebuffer 0) goes to a framebuffer of that size instead. When
// Unity swaps, that frame is upscaled into the real screen framebuffer: FSR 1
// (EASU, then RCAS sharpening) or SGSR 1, as GLSL ES 3.0 shaders
// (render_scale_shaders.h), with the GL state Unity left restored after.
//
// The window, surface and swap functions are libunity imports, replaced in its
// GOT (each slot checked to hold the function first); the GL functions Unity
// reads through eglGetProcAddress and dlsym pass through render_scale_wrap
// (egl_sync.c). Unity's queries about framebuffer 0 are answered as if it were
// still the screen's. If anything is missing nothing changes.
#include "render_scale.h"
#include "render_scale_shaders.h"

#include <EGL/egl.h>
#include <GLES3/gl3.h>
#include <android/log.h>
#include <dlfcn.h>
#include <stdint.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>

#define LOG(...) __android_log_print(ANDROID_LOG_INFO, "Bunker", __VA_ARGS__)

// libunity 3.7.1 ARM64 import slots (R_AARCH64_JUMP_SLOT).
enum { kGotSetGeometry = 0x123e800, kGotQuerySurface = 0x123e0d0, kGotSwap = 0x123e2b0, kGotWidth = 0x123e3d0, kGotHeight = 0x123e330 };

static int mode;
static int asked_w, asked_h;   // the size Unity set (0: the window's own)
static int window_w, window_h; // the window's own size
static int upscaling;          // asked is smaller than the window

static int (*real_set_geometry)(void *window, int width, int height, int format);
static EGLBoolean (*real_query)(EGLDisplay display, EGLSurface surface, EGLint attribute, EGLint *value);
static EGLBoolean (*real_swap)(EGLDisplay display, EGLSurface surface);
static int (*real_width)(void *window);
static int (*real_height)(void *window);
static void (*real_bind)(GLenum target, GLuint framebuffer);
static void (*real_get_integerv)(GLenum name, GLint *value);
static void (*real_invalidate)(GLenum target, GLsizei count, const GLenum *attachments);
static void (*real_read_buffer)(GLenum source);
static void (*real_draw_buffers)(GLsizei count, const GLenum *buffers);
static void (*real_attachment_parameter)(GLenum target, GLenum attachment, GLenum name, GLint *value);

// Unity's stand-in screen: a framebuffer of the size it asked for.
static GLuint fbo, color, depth, fbo_w, fbo_h;
static GLuint draw_is_screen = 1, read_is_screen = 1;  // Unity has "framebuffer 0" bound
// The upscaler: programs, and FSR's intermediate full-size image.
static GLuint easu, rcas, sgsr, vao, mid_fbo, mid, mid_w, mid_h;
static GLint u_easu_in, u_easu_out, u_rcas_sharp, u_sgsr_view;
static int failed, frames;

/** Whether Unity should get the stand-in: upscaling and a GL context made. */
static int active(void) { return upscaling && !failed; }

static void make_target(void) {
    if (fbo && fbo_w == (GLuint)asked_w && fbo_h == (GLuint)asked_h) return;
    if (!fbo) { glGenFramebuffers(1, &fbo); glGenTextures(1, &color); glGenRenderbuffers(1, &depth); }
    else {  // a new size: new storage
        glDeleteTextures(1, &color); glGenTextures(1, &color);
        glDeleteRenderbuffers(1, &depth); glGenRenderbuffers(1, &depth);
    }
    GLint texture, renderbuffer;
    glGetIntegerv(GL_TEXTURE_BINDING_2D, &texture);
    glGetIntegerv(GL_RENDERBUFFER_BINDING, &renderbuffer);
    glBindTexture(GL_TEXTURE_2D, color);
    glTexStorage2D(GL_TEXTURE_2D, 1, GL_RGBA8, asked_w, asked_h);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    glBindRenderbuffer(GL_RENDERBUFFER, depth);
    glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH24_STENCIL8, asked_w, asked_h);
    real_bind(GL_FRAMEBUFFER, fbo);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, color, 0);
    glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_STENCIL_ATTACHMENT, GL_RENDERBUFFER, depth);
    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) { failed = 1; LOG("Upscaling: framebuffer %dx%d incomplete; plain stretching", asked_w, asked_h); }
    glBindTexture(GL_TEXTURE_2D, (GLuint)texture);
    glBindRenderbuffer(GL_RENDERBUFFER, (GLuint)renderbuffer);
    fbo_w = (GLuint)asked_w, fbo_h = (GLuint)asked_h;
    LOG("Upscaling: Unity draws at %dx%d for the %dx%d screen (%s)", asked_w, asked_h, window_w, window_h, mode == RENDER_SCALE_FSR ? "FSR 1" : "SGSR 1");
}

// --- Unity's window and surface ---------------------------------------------------------

static int set_geometry(void *window, int width, int height, int format) {
    window_w = real_width(window), window_h = real_height(window);
    asked_w = width, asked_h = height;
    upscaling = !failed && width > 0 && height > 0 && (width < window_w || height < window_h);
    // The window keeps its own size (0 x 0) while upscaling.
    return real_set_geometry(window, upscaling ? 0 : width, upscaling ? 0 : height, format);
}
// The window's own size: Unity scales touches by it against the size it draws at.
static int width_of(void *window) { return real_width(window); }
static int height_of(void *window) { return real_height(window); }
static EGLBoolean query(EGLDisplay display, EGLSurface surface, EGLint attribute, EGLint *value) {
    EGLBoolean ok = real_query(display, surface, attribute, value);
    if (ok && value && active()) {
        if (attribute == EGL_WIDTH && *value == window_w) *value = asked_w;
        if (attribute == EGL_HEIGHT && *value == window_h) *value = asked_h;
    }
    return ok;
}

// --- Unity's GL calls about framebuffer 0 -----------------------------------------------

static void bind(GLenum target, GLuint framebuffer) {
    if (framebuffer == 0 && active()) {
        make_target();
        if (!failed) framebuffer = fbo;
    }
    if (target == GL_FRAMEBUFFER || target == GL_DRAW_FRAMEBUFFER) draw_is_screen = framebuffer == 0 || framebuffer == fbo;
    if (target == GL_FRAMEBUFFER || target == GL_READ_FRAMEBUFFER) read_is_screen = framebuffer == 0 || framebuffer == fbo;
    real_bind(target, framebuffer);
}
static void get_integerv(GLenum name, GLint *value) {
    real_get_integerv(name, value);
    if (fbo && (name == GL_DRAW_FRAMEBUFFER_BINDING || name == GL_READ_FRAMEBUFFER_BINDING) && *value == (GLint)fbo) *value = 0;
}
// The screen's attachments are GL_COLOR / GL_DEPTH / GL_STENCIL / GL_BACK; a framebuffer's are attachment points.
static GLenum attachment_of(GLenum a) {
    switch (a) {
        case GL_COLOR: case GL_BACK: return GL_COLOR_ATTACHMENT0;
        case GL_DEPTH: return GL_DEPTH_ATTACHMENT;
        case GL_STENCIL: return GL_STENCIL_ATTACHMENT;
        default: return a;
    }
}
static int on_stand_in(GLenum target) {
    if (!fbo || !active()) return 0;
    return target == GL_READ_FRAMEBUFFER ? read_is_screen : draw_is_screen;
}
static void invalidate(GLenum target, GLsizei count, const GLenum *attachments) {
    if (!on_stand_in(target) || count > 8) { real_invalidate(target, count, attachments); return; }
    GLenum mapped[8];
    for (GLsizei i = 0; i < count; i++) mapped[i] = attachment_of(attachments[i]);
    real_invalidate(target, count, mapped);
}
static void read_buffer(GLenum source) { real_read_buffer(on_stand_in(GL_READ_FRAMEBUFFER) && source == GL_BACK ? GL_COLOR_ATTACHMENT0 : source); }
static void draw_buffers(GLsizei count, const GLenum *buffers) {
    if (on_stand_in(GL_DRAW_FRAMEBUFFER) && count == 1 && buffers[0] == GL_BACK) { GLenum b = GL_COLOR_ATTACHMENT0; real_draw_buffers(1, &b); return; }
    real_draw_buffers(count, buffers);
}
static void attachment_parameter(GLenum target, GLenum attachment, GLenum name, GLint *value) {
    real_attachment_parameter(target, on_stand_in(target) ? attachment_of(attachment) : attachment, name, value);
}

// --- The upscale at swap ------------------------------------------------------------------

static GLuint compile(GLenum type, const char *source) {
    GLuint shader = glCreateShader(type);
    glShaderSource(shader, 1, &source, NULL);
    glCompileShader(shader);
    GLint ok;
    glGetShaderiv(shader, GL_COMPILE_STATUS, &ok);
    if (!ok) { char log[512]; glGetShaderInfoLog(shader, sizeof log, NULL, log); LOG("Upscaling: shader failed: %s", log); }
    return ok ? shader : 0;
}
static GLuint program(const char *fragment) {
    GLuint v = compile(GL_VERTEX_SHADER, kScaleVertex), f = compile(GL_FRAGMENT_SHADER, fragment);
    if (!v || !f) return 0;
    GLuint p = glCreateProgram();
    glAttachShader(p, v); glAttachShader(p, f);
    glLinkProgram(p);
    glDeleteShader(v); glDeleteShader(f);
    GLint ok;
    glGetProgramiv(p, GL_LINK_STATUS, &ok);
    if (!ok) { char log[512]; glGetProgramInfoLog(p, sizeof log, NULL, log); LOG("Upscaling: program failed: %s", log); return 0; }
    GLint image = glGetUniformLocation(p, "image");
    GLint current;
    glGetIntegerv(GL_CURRENT_PROGRAM, &current);
    glUseProgram(p);
    glUniform1i(image, 0);
    glUseProgram((GLuint)current);
    return p;
}
static int make_upscaler(void) {
    if (vao) return 1;
    if (mode == RENDER_SCALE_FSR) {
        easu = program(kEasuFragment), rcas = program(kRcasFragment);
        if (!easu || !rcas) return 0;
        u_easu_in = glGetUniformLocation(easu, "inSize"), u_easu_out = glGetUniformLocation(easu, "outSize");
        u_rcas_sharp = glGetUniformLocation(rcas, "sharpness");
    } else {
        sgsr = program(kSgsrFragment);
        if (!sgsr) return 0;
        u_sgsr_view = glGetUniformLocation(sgsr, "viewport");
    }
    GLint current;
    glGetIntegerv(GL_VERTEX_ARRAY_BINDING, &current);
    glGenVertexArrays(1, &vao);  // empty: the vertex shader makes the triangle
    glBindVertexArray((GLuint)current);
    return 1;
}
static void make_mid(void) {
    if (mid && mid_w == (GLuint)window_w && mid_h == (GLuint)window_h) return;
    if (mid) glDeleteTextures(1, &mid);
    if (!mid_fbo) glGenFramebuffers(1, &mid_fbo);
    glGenTextures(1, &mid);
    glBindTexture(GL_TEXTURE_2D, mid);
    glTexStorage2D(GL_TEXTURE_2D, 1, GL_RGBA8, window_w, window_h);
    real_bind(GL_FRAMEBUFFER, mid_fbo);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, mid, 0);
    mid_w = (GLuint)window_w, mid_h = (GLuint)window_h;
}

static void upscale(void) {
    // Unity's state, put back after.
    GLint program_, active_texture, texture, sampler, vertex_array, draw, read, viewport[4];
    GLboolean mask[4], scissor = glIsEnabled(GL_SCISSOR_TEST), blend = glIsEnabled(GL_BLEND), depth_test = glIsEnabled(GL_DEPTH_TEST);
    GLboolean stencil = glIsEnabled(GL_STENCIL_TEST), cull = glIsEnabled(GL_CULL_FACE), discard = glIsEnabled(GL_RASTERIZER_DISCARD);
    glGetIntegerv(GL_CURRENT_PROGRAM, &program_);
    glGetIntegerv(GL_ACTIVE_TEXTURE, &active_texture);
    glActiveTexture(GL_TEXTURE0);
    glGetIntegerv(GL_TEXTURE_BINDING_2D, &texture);
    glGetIntegerv(GL_SAMPLER_BINDING, &sampler);
    glGetIntegerv(GL_VERTEX_ARRAY_BINDING, &vertex_array);
    glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &draw);  // the real bindings (Unity's own reads go through get_integerv)
    glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &read);
    glGetIntegerv(GL_VIEWPORT, viewport);
    glGetBooleanv(GL_COLOR_WRITEMASK, mask);

    if (!make_upscaler()) { failed = 1; LOG("Upscaling: shaders unavailable; plain stretching from the next start"); }
    else {
        glDisable(GL_SCISSOR_TEST); glDisable(GL_BLEND); glDisable(GL_DEPTH_TEST); glDisable(GL_STENCIL_TEST);
        glDisable(GL_CULL_FACE); glDisable(GL_RASTERIZER_DISCARD);
        glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
        glBindSampler(0, 0);
        glBindVertexArray(vao);
        if (mode == RENDER_SCALE_FSR) {
            make_mid();
            real_bind(GL_DRAW_FRAMEBUFFER, mid_fbo);
            glViewport(0, 0, window_w, window_h);
            glUseProgram(easu);
            glUniform2f(u_easu_in, (float)asked_w, (float)asked_h);
            glUniform2f(u_easu_out, (float)window_w, (float)window_h);
            glBindTexture(GL_TEXTURE_2D, color);
            glDrawArrays(GL_TRIANGLES, 0, 3);
            real_bind(GL_DRAW_FRAMEBUFFER, 0);
            glUseProgram(rcas);
            glUniform1f(u_rcas_sharp, 0.87f);  // exp2(-0.2): FSR's usual 0.2 stops
            glBindTexture(GL_TEXTURE_2D, mid);
            glDrawArrays(GL_TRIANGLES, 0, 3);
        } else {
            real_bind(GL_DRAW_FRAMEBUFFER, 0);
            glViewport(0, 0, window_w, window_h);
            glUseProgram(sgsr);
            glUniform4f(u_sgsr_view, 1.0f / (float)asked_w, 1.0f / (float)asked_h, (float)asked_w, (float)asked_h);
            glBindTexture(GL_TEXTURE_2D, color);
            glDrawArrays(GL_TRIANGLES, 0, 3);
        }
    }

    glUseProgram((GLuint)program_);
    glBindTexture(GL_TEXTURE_2D, (GLuint)texture);
    glBindSampler(0, (GLuint)sampler);
    glActiveTexture((GLenum)active_texture);
    glBindVertexArray((GLuint)vertex_array);
    real_bind(GL_DRAW_FRAMEBUFFER, (GLuint)draw);
    real_bind(GL_READ_FRAMEBUFFER, (GLuint)read);
    glViewport(viewport[0], viewport[1], viewport[2], viewport[3]);
    glColorMask(mask[0], mask[1], mask[2], mask[3]);
    if (scissor) glEnable(GL_SCISSOR_TEST);
    if (blend) glEnable(GL_BLEND);
    if (depth_test) glEnable(GL_DEPTH_TEST);
    if (stencil) glEnable(GL_STENCIL_TEST);
    if (cull) glEnable(GL_CULL_FACE);
    if (discard) glEnable(GL_RASTERIZER_DISCARD);
}

static EGLBoolean swap(EGLDisplay display, EGLSurface surface) {
    if (active() && fbo && real_bind) {
        upscale();
        if (++frames == 1) LOG("Upscaling: first upscaled frame");
    }
    return real_swap(display, surface);
}

void *render_scale_wrap(const char *name, void *function) {
    if (!mode || !function || !name) return function;
    // Unity's frame pacing (Swappy) swaps through a looked-up eglSwapBuffers.
    if (!strcmp(name, "eglSwapBuffers")) { if (!real_swap) real_swap = function; return (void *)swap; }
    if (!strcmp(name, "glBindFramebuffer")) { real_bind = function; return (void *)bind; }
    if (!strcmp(name, "glGetIntegerv")) { real_get_integerv = function; return (void *)get_integerv; }
    if (!strcmp(name, "glInvalidateFramebuffer")) { real_invalidate = function; return (void *)invalidate; }
    if (!strcmp(name, "glReadBuffer")) { real_read_buffer = function; return (void *)read_buffer; }
    if (!strcmp(name, "glDrawBuffers")) { real_draw_buffers = function; return (void *)draw_buffers; }
    if (!strcmp(name, "glGetFramebufferAttachmentParameteriv")) { real_attachment_parameter = function; return (void *)attachment_parameter; }
    return function;
}

static int redirect(uint8_t *base, uintptr_t offset, void **original, void *replacement) {
    void **slot = (void **)(base + offset);
    uintptr_t page = (uintptr_t)sysconf(_SC_PAGESIZE), start = (uintptr_t)slot & ~(page - 1);
    if (*slot == replacement) return 0;
    if (mprotect((void *)start, page, PROT_READ | PROT_WRITE)) return -1;
    *original = *slot;
    *slot = replacement;
    return 0;
}

const char *render_scale_init(int chosen) {
    if (chosen != RENDER_SCALE_FSR && chosen != RENDER_SCALE_SGSR) return NULL;
    void *unity = dlopen("libunity.so", RTLD_NOW), *anchor = unity ? dlsym(unity, "JNI_OnLoad") : NULL;
    Dl_info info;
    if (!anchor || !dladdr(anchor, &info)) return "Upscaling: Unity library not found";
    uint8_t *base = info.dli_fbase;
    void *android = dlopen("libandroid.so", RTLD_NOW), *egl = dlopen("libEGL.so", RTLD_NOW);
    // Each slot must hold the function it imports.
    struct { uintptr_t got; void *library; const char *name; void **original; void *hook; } slots[] = {
        {kGotSetGeometry, android, "ANativeWindow_setBuffersGeometry", (void **)&real_set_geometry, (void *)set_geometry},
        {kGotQuerySurface, egl, "eglQuerySurface", (void **)&real_query, (void *)query},
        {kGotSwap, egl, "eglSwapBuffers", (void **)&real_swap, (void *)swap},
        {kGotWidth, android, "ANativeWindow_getWidth", (void **)&real_width, (void *)width_of},
        {kGotHeight, android, "ANativeWindow_getHeight", (void **)&real_height, (void *)height_of},
    };
    for (size_t i = 0; i < sizeof slots / sizeof *slots; i++) {
        void *expected = slots[i].library ? dlsym(slots[i].library, slots[i].name) : NULL;
        void *now = *(void **)(base + slots[i].got);
        if (!expected || (now != expected && now != slots[i].hook)) return "Upscaling: unsupported Unity library; plain stretching";
    }
    for (size_t i = 0; i < sizeof slots / sizeof *slots; i++)
        if (redirect(base, slots[i].got, slots[i].original, slots[i].hook)) return "Upscaling: could not write Unity's imports";
    mode = chosen;
    LOG("Upscaling: %s ready", mode == RENDER_SCALE_FSR ? "FSR 1" : "SGSR 1");
    return NULL;
}
