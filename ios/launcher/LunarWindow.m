// The game's window in the server log, for the iPhone and iPad build.
//
// Pod Programs' Export Lunar Tear log has the server's log only. This adds
// "[Display]" lines to it: the Display settings in use, which screen the game
// is on and its window's size once it settles (a Stage Manager window can be
// resized, or moved to an external display), the display's mode, the size
// Unity draws at and the size MetalFX writes, and the upscaler's notes.
// Lines from before the game's window exists (the log's folder is set when
// the server starts) wait until it does.
#import <QuartzCore/QuartzCore.h>
#import <UIKit/UIKit.h>

NSString *LTDisplaySettings(void);  // LunarDisplay.m
CGSize LTUpscaleOutput(void);  // LunarUpscale.m
extern void LunarLog(char *line);  // the server's log (liblunar)

static NSMutableArray<NSString *> *gWaiting;  // lines from before the log was ready
static BOOL gReady;

/** A "[Display]" line in the server log; from any thread. */
void LTDisplayLog(NSString *line) {
    NSString *text = [@"[Display] " stringByAppendingString:line];
    @synchronized (UIApplication.class) {
        if (!gReady) {
            if (!gWaiting) gWaiting = [NSMutableArray array];
            if (gWaiting.count < 50) [gWaiting addObject:text];
            return;
        }
    }
    LunarLog((char *)text.UTF8String);
}

static void LogReady(void) {
    NSArray *waiting;
    @synchronized (UIApplication.class) { gReady = YES; waiting = gWaiting; gWaiting = nil; }
    LunarLog((char *)[@"[Display] settings: " stringByAppendingString:LTDisplaySettings()].UTF8String);
    for (NSString *text in waiting) LunarLog((char *)text.UTF8String);
}

// Unity's window: its root view's layer is a CAMetalLayer.
static UIWindow *GameWindow(void) {
    for (UIScene *scene in UIApplication.sharedApplication.connectedScenes) {
        if (![scene isKindOfClass:UIWindowScene.class]) continue;
        for (UIWindow *window in ((UIWindowScene *)scene).windows)
            if ([window.rootViewController.view.layer isKindOfClass:CAMetalLayer.class]) return window;
    }
    return nil;
}

void LTWindowStart(void) {
    static dispatch_source_t timer;
    timer = dispatch_source_create(DISPATCH_SOURCE_TYPE_TIMER, 0, 0, dispatch_get_main_queue());
    dispatch_source_set_timer(timer, dispatch_time(DISPATCH_TIME_NOW, NSEC_PER_SEC), NSEC_PER_SEC / 2, NSEC_PER_SEC / 10);
    dispatch_source_set_event_handler(timer, ^{
        UIWindow *window = GameWindow();
        UIScreen *screen = window.windowScene.screen;
        if (!window || !screen) return;
        if (!gReady) LogReady();
        // The window once it has kept one size for a second (a drag goes through many).
        CAMetalLayer *layer = (CAMetalLayer *)window.rootViewController.view.layer;
        CGSize mode = screen.currentMode.size, largest = CGSizeZero, upscaled = LTUpscaleOutput();
        for (UIScreenMode *m in screen.availableModes) if (m.size.width * m.size.height > largest.width * largest.height) largest = m.size;
        NSString *state = [NSString stringWithFormat:@"window %.0fx%.0f on %@ %.0fx%.0f @%.0fx (mode %.0fx%.0f, largest %.0fx%.0f); Unity draws %.0fx%.0f%@",
            window.bounds.size.width, window.bounds.size.height, screen == UIScreen.mainScreen ? @"the device's screen" : @"an external display",
            screen.bounds.size.width, screen.bounds.size.height, screen.nativeScale, mode.width, mode.height, largest.width, largest.height,
            layer.drawableSize.width, layer.drawableSize.height,
            upscaled.width > 0 ? [NSString stringWithFormat:@", MetalFX to %.0fx%.0f", upscaled.width, upscaled.height] : @""];
        static NSString *seen, *logged;
        static double since;
        double now = CACurrentMediaTime();
        if (![state isEqual:seen]) { seen = state; since = now; return; }
        if (now - since >= 1 && ![state isEqual:logged]) { logged = state; LTDisplayLog(state); }
    });
    dispatch_resume(timer);
}
