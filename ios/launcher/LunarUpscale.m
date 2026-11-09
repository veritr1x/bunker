// MetalFX upscaling for the iPhone and iPad build (Pod Programs › Display).
//
// Below the screen's own resolution, Unity sets its CAMetalLayer's drawables to
// that smaller size, renders straight into them and the system stretches them
// to the screen with plain filtering. With upscaling on, Unity's layer keeps
// drawables of the screen's own size while telling Unity the size it asked
// for, and Unity is given a stand-in drawable whose texture has that size.
// When the command buffer that presents it is committed (Unity asks for the
// present before it encodes the interface, so the commit is when the frame is
// complete), MetalFX's spatial scaler writes the frame at full size into the
// real drawable, which is presented at Unity's pace. It is all still Unity's
// one layer, so the system's Metal performance overlay stays on it.
//
// Unity's Metal and layer calls are Objective-C messages, so this replaces
// methods of CAMetalLayer and the device's command buffer class (their method
// tables, not code; iOS does not let an app change its code). Only Unity's
// layer is affected. MetalFX and the textures are checked before anything
// changes; if they do not fit, Unity's layer is left as it was.
#import <Metal/Metal.h>
#if __has_include(<MetalFX/MetalFX.h>)
#import <MetalFX/MetalFX.h>
#import <QuartzCore/QuartzCore.h>
#import <UIKit/UIKit.h>
#import <objc/runtime.h>

API_AVAILABLE(ios(16.0))
static id<MTLFXSpatialScaler> gScaler;
static id<MTLDevice> gDevice;
static CAMetalLayer *gLayer;      // Unity's layer, once its view exists
static CGSize gAsked;             // the size Unity set; the layer itself has gScreen while upscaling
static CGSize gScreen;            // the layer's size in pixels
static CGFloat gScale;            // its screen's pixels per point
static BOOL gUpscaling, gFailed;
static NSUInteger gScalerWidth, gScalerHeight;
static NSMutableArray<id<MTLTexture>> *gStandIns;  // a few textures of Unity's size, used in turn
static NSUInteger gNextStandIn;
static int gUpscaled, gCounts[3];
static double gGapMax, gLast;
static NSString *gLogPath;

void LTDisplayLog(NSString *line);  // LunarWindow.m

// The developer file only (LUNAR_UPSCALE_LOG): hooks, each scaler, the 10-second counts.
static void Stats(NSString *text) {
    if (!gLogPath) return;
    NSString *line = [NSString stringWithFormat:@"%.1f %@\n", CACurrentMediaTime(), text];
    @synchronized (gLogPath) {
        NSFileHandle *f = [NSFileHandle fileHandleForWritingAtPath:gLogPath];
        if (!f) { [line writeToFile:gLogPath atomically:NO encoding:NSUTF8StringEncoding error:nil]; return; }
        [f seekToEndOfFile];
        [f writeData:[line dataUsingEncoding:NSUTF8StringEncoding]];
        [f closeFile];
    }
}

// The server log too: the layer found, MetalFX refusing a size, a hook missing.
static void Note(NSString *text) {
    LTDisplayLog([@"upscaling: " stringByAppendingString:text]);
    if (!gLogPath) return;
    NSString *line = [NSString stringWithFormat:@"%.1f %@\n", CACurrentMediaTime(), text];
    @synchronized (gLogPath) {
        NSFileHandle *f = [NSFileHandle fileHandleForWritingAtPath:gLogPath];
        if (!f) { [line writeToFile:gLogPath atomically:NO encoding:NSUTF8StringEncoding error:nil]; return; }
        [f seekToEndOfFile];
        [f writeData:[line dataUsingEncoding:NSUTF8StringEncoding]];
        [f closeFile];
    }
}

// The drawable Unity gets while upscaling: its texture has Unity's size; everything else is the real drawable's.
@interface LTStandInDrawable : NSProxy
@property (nonatomic, strong) id<CAMetalDrawable> real;
@property (nonatomic, strong) id<MTLTexture> texture;
@end

@implementation LTStandInDrawable
- (NSMethodSignature *)methodSignatureForSelector:(SEL)sel { return [(NSObject *)self.real methodSignatureForSelector:sel]; }
- (void)forwardInvocation:(NSInvocation *)invocation { [invocation invokeWithTarget:self.real]; }
- (BOOL)conformsToProtocol:(Protocol *)protocol { return [(NSObject *)self.real conformsToProtocol:protocol]; }
- (BOOL)respondsToSelector:(SEL)sel { return sel == @selector(texture) || [(NSObject *)self.real respondsToSelector:sel]; }
- (CAMetalLayer *)layer { return self.real.layer; }
@end

static IMP origSetSize, origGetSize, origNext;

static void SetRealSize(CAMetalLayer *layer, CGSize size) { ((void (*)(id, SEL, CGSize))origSetSize)(layer, @selector(setDrawableSize:), size); }

// Unity's layer is the backing layer of the window's root view.
static void FindLayer(void) {
    static BOOL asked;
    if (gLayer || asked) return;
    asked = YES;
    dispatch_async(dispatch_get_main_queue(), ^{
        for (UIWindow *window in UIApplication.sharedApplication.windows) {
            CALayer *layer = window.rootViewController.view.layer;
            if (![layer isKindOfClass:CAMetalLayer.class]) continue;
            gScale = window.screen.nativeScale;
            gScreen = CGSizeMake(round(layer.bounds.size.width * gScale), round(layer.bounds.size.height * gScale));
            gAsked = ((CGSize (*)(id, SEL))origGetSize)(layer, @selector(drawableSize));
            gLayer = (CAMetalLayer *)layer;
            Note([NSString stringWithFormat:@"Unity's layer: screen %.0fx%.0f, Unity's size %.0fx%.0f", gScreen.width, gScreen.height, gAsked.width, gAsked.height]);
            return;
        }
        asked = NO;  // not up yet: look again on a later frame
    });
}

// Whether to upscale at Unity's size, checked once per size: MetalFX takes these sizes and formats.
static BOOL Prepare(CAMetalLayer *layer) API_AVAILABLE(ios(16.0)) {
    NSUInteger width = (NSUInteger)gAsked.width, height = (NSUInteger)gAsked.height;
    if (gFailed || width == 0 || width >= gScreen.width || height >= gScreen.height) return NO;
    if (gScaler && gScalerWidth == width && gScalerHeight == height && gScaler.outputWidth == (NSUInteger)gScreen.width
        && gScaler.outputHeight == (NSUInteger)gScreen.height) return YES;
    MTLFXSpatialScalerDescriptor *d = [MTLFXSpatialScalerDescriptor new];
    d.inputWidth = width, d.inputHeight = height;
    d.outputWidth = (NSUInteger)gScreen.width, d.outputHeight = (NSUInteger)gScreen.height;
    d.colorTextureFormat = layer.pixelFormat;
    d.outputTextureFormat = layer.pixelFormat;
    d.colorProcessingMode = MTLFXSpatialScalerColorProcessingModePerceptual;
    id<MTLFXSpatialScaler> scaler = [MTLFXSpatialScalerDescriptor supportsDevice:gDevice] ? [d newSpatialScalerWithDevice:gDevice] : nil;
    // A drawable of a layer that isn't framebuffer-only can be written by shaders and render passes.
    MTLTextureUsage drawable = MTLTextureUsageShaderRead | MTLTextureUsageShaderWrite | MTLTextureUsageRenderTarget;
    if (!scaler || layer.framebufferOnly || (scaler.outputTextureUsage & ~drawable)) {
        Note([NSString stringWithFormat:@"MetalFX can't upscale %lux%lu fmt %lu (scaler %@, framebuffer-only %d): plain stretching",
              (unsigned long)width, (unsigned long)height, (unsigned long)layer.pixelFormat, scaler ? @"made" : @"refused", layer.framebufferOnly]);
        gFailed = YES;
        return NO;
    }
    MTLTextureDescriptor *td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:layer.pixelFormat width:width height:height mipmapped:NO];
    td.usage = MTLTextureUsageRenderTarget | MTLTextureUsageShaderRead | MTLTextureUsageShaderWrite | MTLTextureUsagePixelFormatView | scaler.colorTextureUsage;
    td.storageMode = MTLStorageModePrivate;
    NSMutableArray *textures = [NSMutableArray array];
    for (int i = 0; i < 4; i++) [textures addObject:[gDevice newTextureWithDescriptor:td]];
    gStandIns = textures, gNextStandIn = 0;
    gScaler = scaler, gScalerWidth = width, gScalerHeight = height;
    // The developer file only: a drag makes one scaler per size. The server log has the size a
    // window settles at (LTUpscaleOutput, in LunarWindow.m's window line).
    Stats([NSString stringWithFormat:@"MetalFX %lux%lu -> %.0fx%.0f fmt %lu", (unsigned long)width, (unsigned long)height, gScreen.width, gScreen.height,
          (unsigned long)layer.pixelFormat]);
    return YES;
}

// The layer's own size in pixels, from its bounds now: a window resized under Stage Manager,
// or the game moved to an external display, changes it, and not always with a new size from
// Unity. The screen's scale is read on the main thread (UIKit), and kept for the others.
static CGSize LayerPixels(CAMetalLayer *layer) {
    if (NSThread.isMainThread) {
        UIView *view = [(id)layer.delegate isKindOfClass:UIView.class] ? (UIView *)layer.delegate : nil;
        if (view.window.screen) gScale = view.window.screen.nativeScale;
    }
    return gScale > 0 ? CGSizeMake(round(layer.bounds.size.width * gScale), round(layer.bounds.size.height * gScale)) : gScreen;
}

// The full size follows the layer; the scaler and the real drawables are made again for it.
// A full size left behind gave Unity real drawables larger than the size it draws at, so its
// picture sat in their top-left corner with the rest black, frame after frame.
static void Follow(CAMetalLayer *layer) {
    CGSize pixels = LayerPixels(layer);
    if (pixels.width < 1 || pixels.height < 1 || CGSizeEqualToSize(pixels, gScreen)) return;
    gScreen = pixels;
    if (@available(iOS 16.0, *)) gUpscaling = Prepare(layer);
    SetRealSize(layer, gUpscaling ? gScreen : gAsked);
}

static void HookSetSize(CAMetalLayer *layer, SEL sel, CGSize size) {
    if (layer != gLayer) { ((void (*)(id, SEL, CGSize))origSetSize)(layer, sel, size); return; }
    gAsked = size;
    gScreen = LayerPixels(layer);
    if (@available(iOS 16.0, *)) gUpscaling = Prepare(layer);
    SetRealSize(layer, gUpscaling ? gScreen : size);
}

static CGSize HookGetSize(CAMetalLayer *layer, SEL sel) {
    if (layer == gLayer && gUpscaling) return gAsked;  // Unity renders at the size it asked for
    return ((CGSize (*)(id, SEL))origGetSize)(layer, sel);
}

static id HookNext(CAMetalLayer *layer, SEL sel) {
    if (!gLayer) FindLayer();
    if (layer == gLayer && gUpscaling) Follow(layer);
    if (@available(iOS 16.0, *)) {
        if (layer == gLayer && !gUpscaling && !gFailed && Prepare(layer)) {  // the first frame after the layer was found
            gUpscaling = YES;
            SetRealSize(layer, gScreen);
        }
    }
    id<CAMetalDrawable> real = ((id (*)(id, SEL))origNext)(layer, sel);
    if (layer != gLayer || !gUpscaling || !real) return real;
    if (real.texture.width != (NSUInteger)gScreen.width) return real;  // made before the size changed
    LTStandInDrawable *standIn = [LTStandInDrawable alloc];
    standIn.real = real;
    standIn.texture = gStandIns[gNextStandIn++ % gStandIns.count];
    return standIn;
}

// Presenting a stand-in: the upscale and the real present wait for the command buffer's commit.
static const void *kPending = &kPending, *kDuration = &kDuration, *kForm = &kForm;

static BOOL Hold(id<MTLCommandBuffer> buffer, id drawable, int form, CFTimeInterval duration) {
    if (object_getClass(drawable) != LTStandInDrawable.class) return NO;
    gCounts[form]++;
    objc_setAssociatedObject(buffer, kPending, drawable, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    objc_setAssociatedObject(buffer, kDuration, @(duration), OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    objc_setAssociatedObject(buffer, kForm, @(form), OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    return YES;
}

static void (*origPresent)(id, SEL, id<MTLDrawable>);
static void (*origPresentAfter)(id, SEL, id<MTLDrawable>, CFTimeInterval);
static void (*origPresentAt)(id, SEL, id<MTLDrawable>, CFTimeInterval);

static void HookPresent(id buffer, SEL sel, id<MTLDrawable> drawable) {
    if (!Hold(buffer, drawable, 0, 0)) origPresent(buffer, sel, drawable);
}
static void HookPresentAfter(id buffer, SEL sel, id<MTLDrawable> drawable, CFTimeInterval duration) {
    if (!Hold(buffer, drawable, 1, duration)) origPresentAfter(buffer, sel, drawable, duration);
}
static void HookPresentAt(id buffer, SEL sel, id<MTLDrawable> drawable, CFTimeInterval time) {
    if (!Hold(buffer, drawable, 2, time)) origPresentAt(buffer, sel, drawable, time);
}

static void (*origCommit)(id, SEL);
static void HookCommit(id<MTLCommandBuffer> buffer, SEL sel) {
    LTStandInDrawable *standIn = objc_getAssociatedObject(buffer, kPending);
    if (standIn) {
        id<CAMetalDrawable> real = standIn.real;
        id<MTLTexture> input = standIn.texture;
        // The scaler matches the stand-in and the real drawable unless a size changed during the frame;
        // then that frame isn't upscaled.
        if (@available(iOS 16.0, *)) {
            if (gScaler && input.width == gScalerWidth && input.height == gScalerHeight
                && real.texture.width == gScaler.outputWidth && real.texture.height == gScaler.outputHeight) {
                gScaler.colorTexture = input;
                gScaler.outputTexture = real.texture;
                gScaler.inputContentWidth = input.width, gScaler.inputContentHeight = input.height;
                [gScaler encodeToCommandBuffer:buffer];
                gUpscaled++;
            }
        }
        double now = CACurrentMediaTime();
        if (gLast > 0 && now - gLast > gGapMax) gGapMax = now - gLast;
        gLast = now;
        CFTimeInterval value = [objc_getAssociatedObject(buffer, kDuration) doubleValue];
        switch ([objc_getAssociatedObject(buffer, kForm) intValue]) {
            case 1: origPresentAfter(buffer, @selector(presentDrawable:afterMinimumDuration:), real, value); break;
            case 2: origPresentAt(buffer, @selector(presentDrawable:atTime:), real, value); break;
            default: origPresent(buffer, @selector(presentDrawable:), real);
        }
        objc_setAssociatedObject(buffer, kPending, nil, OBJC_ASSOCIATION_RETAIN_NONATOMIC);
    }
    origCommit(buffer, sel);
}

static IMP Swap(Class cls, SEL sel, IMP hook) {
    Method m = class_getInstanceMethod(cls, sel);
    IMP original = m ? method_setImplementation(m, hook) : NULL;
    NSString *text = [NSString stringWithFormat:@"%@ %@: %@", NSStringFromClass(cls), NSStringFromSelector(sel), m ? @"hooked" : @"missing"];
    if (m) Stats(text); else Note(text);
    return original;
}

void LTUpscaleStart(void) {
    if (getenv("LUNAR_UPSCALE_LOG")) {
        NSString *documents = NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, YES).firstObject;
        gLogPath = [documents stringByAppendingPathComponent:@"upscale-log.txt"];
        [NSFileManager.defaultManager removeItemAtPath:gLogPath error:nil];
    }
    if (@available(iOS 16.0, *)) {} else { Note(@"MetalFX not on this system"); return; }
    gDevice = MTLCreateSystemDefaultDevice();
    Class buffer = object_getClass([[gDevice newCommandQueue] commandBuffer]);
    origSetSize = Swap(CAMetalLayer.class, @selector(setDrawableSize:), (IMP)HookSetSize);
    origGetSize = Swap(CAMetalLayer.class, @selector(drawableSize), (IMP)HookGetSize);
    origNext = Swap(CAMetalLayer.class, @selector(nextDrawable), (IMP)HookNext);
    *(IMP *)&origPresent = Swap(buffer, @selector(presentDrawable:), (IMP)HookPresent);
    *(IMP *)&origPresentAfter = Swap(buffer, @selector(presentDrawable:afterMinimumDuration:), (IMP)HookPresentAfter);
    *(IMP *)&origPresentAt = Swap(buffer, @selector(presentDrawable:atTime:), (IMP)HookPresentAt);
    *(IMP *)&origCommit = Swap(buffer, @selector(commit), (IMP)HookCommit);
    if (gLogPath) {
        // Developer log, every 10 s.
        static dispatch_source_t timer;
        timer = dispatch_source_create(DISPATCH_SOURCE_TYPE_TIMER, 0, 0, dispatch_get_main_queue());
        dispatch_source_set_timer(timer, dispatch_time(DISPATCH_TIME_NOW, 10 * NSEC_PER_SEC), 10 * NSEC_PER_SEC, NSEC_PER_SEC);
        dispatch_source_set_event_handler(timer, ^{
            static int last;
            Stats([NSString stringWithFormat:@"presents: buffer %d, after duration %d, at time %d; upscaled %d (%.1f/s); longest gap %.1f ms; %@",
                  gCounts[0], gCounts[1], gCounts[2], gUpscaled, (gUpscaled - last) / 10.0, gGapMax * 1000,
                  gUpscaling ? @"upscaling" : gFailed ? @"plain (failed)" : @"plain"]);
            last = gUpscaled, gGapMax = 0;
        });
        dispatch_resume(timer);
    }
}

/** The size MetalFX writes, or zero when it isn't upscaling (LunarWindow.m logs it). */
CGSize LTUpscaleOutput(void) { return gUpscaling ? gScreen : CGSizeZero; }

#else
// An SDK without MetalFX (the iOS Simulator's): no upscaling, the system stretches Unity's picture, as on a
// device without MetalFX.
#import <UIKit/UIKit.h>
void LTDisplayLog(NSString *line);  // LunarWindow.m
void LTUpscaleStart(void) { LTDisplayLog(@"Note: MetalFX is not in this build: plain stretching"); }
CGSize LTUpscaleOutput(void) { return CGSizeZero; }
#endif
