// The app and the game's window in the server log, for the iPhone and iPad build.
//
// Pod Programs' Export Lunar Tear log has the server's log only. This adds:
// - "[Display]" lines: the Display settings in use, which screen the game is on
//   and its window's size once it settles (a Stage Manager window can be
//   resized, or moved to an external display), the display's mode, the size
//   Unity draws at and the size MetalFX writes, and the upscaler's notes.
// - "[App]" lines: how the previous run ended (the last state it saved), the
//   app going to the background and back, being closed, memory warnings, the
//   device getting hot, external displays, and each update (LunarLauncher.m).
//   A log of many starts said nothing of why: a crash, iOS ending the app in
//   the background, and the player closing it looked the same.
// Lines from before the game's window exists (the log's folder is set when the
// server starts) wait until it does.
#import <QuartzCore/QuartzCore.h>
#import <UIKit/UIKit.h>
#include <os/proc.h>

NSString *LTDisplaySettings(void);  // LunarDisplay.m
CGSize LTUpscaleOutput(void);  // LunarUpscale.m
BOOL LTDisplayKeepShape(void);  // LunarDisplay.m: window=fit
void LTDisplayLog(NSString *line);  // below
extern void LunarLog(char *line);  // the server's log (liblunar)

static NSMutableArray<NSString *> *gWaiting;  // lines from before the log was ready
static BOOL gReady;

/** A line in the server log; from any thread. */
static void LogLine(NSString *text) {
    @synchronized (UIApplication.class) {
        if (!gReady) {
            if (!gWaiting) gWaiting = [NSMutableArray array];
            if (gWaiting.count < 50) [gWaiting addObject:text];
            return;
        }
    }
    LunarLog((char *)text.UTF8String);
}
/** A "[Display]" line in the server log; from any thread. */
void LTDisplayLog(NSString *line) { LogLine([@"[Display] " stringByAppendingString:line]); }
/** An "[App]" line in the server log; from any thread. */
void LTAppLog(NSString *line) { LogLine([@"[App] " stringByAppendingString:line]); }

// The app's state, saved as it changes: the next start reads how this run ended.
static NSString *const kLastState = @"BunkerLastState";
static void SaveState(NSString *state) {
    [NSUserDefaults.standardUserDefaults setObject:state forKey:kLastState];
}
static NSString *MemoryLeft(void) {
    if (@available(iOS 13.0, *)) return [NSString stringWithFormat:@"%zu MB left", os_proc_available_memory() / 1048576];
    return @"";
}
static void WatchApp(void) {
    NSString *last = [NSUserDefaults.standardUserDefaults stringForKey:kLastState];
    NSDictionary *meaning = @{@"active": @"in use: a crash, or iOS stopped it", @"inactive": @"while interrupted: a crash, or iOS stopped it",
                              @"background": @"in the background (iOS ends apps there; usual)", @"closed": @"closed",
                              @"window closed": @"closed (its window was closed)"};
    LTAppLog([NSString stringWithFormat:@"started; the last run ended %@", last ? meaning[last] ?: last : @"(no record: first start of this version's log)"]);
    SaveState(@"active");
    NSNotificationCenter *center = NSNotificationCenter.defaultCenter;
    NSDictionary *events = @{UIApplicationDidEnterBackgroundNotification: @[@"background", @"to the background"],
                             UIApplicationWillEnterForegroundNotification: @[@"inactive", @"back from the background"],
                             UIApplicationDidBecomeActiveNotification: @[@"active", @""],
                             UIApplicationWillResignActiveNotification: @[@"inactive", @""],
                             UIApplicationWillTerminateNotification: @[@"closed", @"closed"]};
    for (NSNotificationName name in events) {
        NSArray *event = events[name];
        [center addObserverForName:name object:nil queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *note) {
            SaveState(event[0]);
            if ([event[1] length]) LTAppLog(event[1]);
        }];
    }
    [center addObserverForName:UIApplicationDidReceiveMemoryWarningNotification object:nil queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *note) {
        LTAppLog([@"memory warning: " stringByAppendingString:MemoryLeft()]);
    }];
    [center addObserverForName:NSProcessInfoThermalStateDidChangeNotification object:nil queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *note) {
        NSArray *states = @[@"nominal", @"fair", @"serious", @"critical"];
        NSInteger state = NSProcessInfo.processInfo.thermalState;
        LTAppLog([@"device heat: " stringByAppendingString:state >= 0 && state < (NSInteger)states.count ? states[state] : @"unknown"]);
    }];
    if (@available(iOS 13.0, *)) {
        [center addObserverForName:UISceneWillConnectNotification object:nil queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *note) {
            UIWindowScene *scene = [note.object isKindOfClass:UIWindowScene.class] ? note.object : nil;
            if (scene && scene.screen != UIScreen.mainScreen) LTAppLog(@"a window opened on an external display");
        }];
        // Closing the game's window (iPadOS windowed apps) ends the app while it is in use, which
        // read as a crash on the next start.
        [center addObserverForName:UISceneDidDisconnectNotification object:nil queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *note) {
            // Moved between screens, the window on the old one goes while another stays.
            for (UIScene *scene in UIApplication.sharedApplication.connectedScenes)
                if (scene != note.object && scene.activationState != UISceneActivationStateUnattached) return;
            SaveState(@"window closed");
            LTAppLog(@"window closed");
        }];
    }
    [center addObserverForName:UIScreenDidConnectNotification object:nil queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *note) {
        UIScreen *screen = note.object;
        LTAppLog([NSString stringWithFormat:@"external display connected: %.0fx%.0f", screen.bounds.size.width, screen.bounds.size.height]);
    }];
    [center addObserverForName:UIScreenDidDisconnectNotification object:nil queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *note) {
        LTAppLog(@"external display disconnected");
    }];
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
    WatchApp();
    static dispatch_source_t timer;
    timer = dispatch_source_create(DISPATCH_SOURCE_TYPE_TIMER, 0, 0, dispatch_get_main_queue());
    dispatch_source_set_timer(timer, dispatch_time(DISPATCH_TIME_NOW, NSEC_PER_SEC), NSEC_PER_SEC / 2, NSEC_PER_SEC / 10);
    dispatch_source_set_event_handler(timer, ^{
        UIWindow *window = GameWindow();
        UIScreen *screen = window.windowScene.screen;
        if (!window || !screen) return;
        if (!gReady) LogReady();
        // Unity makes its window the size of the device's screen. Opened straight onto an external
        // display, whose scene iPadOS calls portrait, that was 834x1210 upright in the middle of a
        // 3008x1630 landscape scene: the picture small and on its end. The window fills its scene.
        CGRect area = window.windowScene.coordinateSpace.bounds;
        if (@available(iOS 26.0, *)) area = window.windowScene.effectiveGeometry.coordinateSpace.bounds;
        if (area.size.width > 0 && area.size.height > 0
            && (fabs(window.frame.size.width - area.size.width) > 1 || fabs(window.frame.size.height - area.size.height) > 1
                || fabs(window.frame.origin.x - area.origin.x) > 1 || fabs(window.frame.origin.y - area.origin.y) > 1)) {
            LTDisplayLog([NSString stringWithFormat:@"window %@ didn't fill its scene %@: resized", NSStringFromCGRect(window.frame), NSStringFromCGRect(area)]);
            window.frame = area;
        }
        // Unity's view keeps its place when its window changes: resized alone, the window held the
        // view at {1087, 209.5}, the game's top-left quarter on screen. The view fills its window.
        UIView *root = window.rootViewController.view;
        if (root && !CGRectEqualToRect(CGRectIntegral(root.frame), CGRectIntegral(window.bounds))) {
            LTDisplayLog([NSString stringWithFormat:@"Unity's view %@ didn't fill its window %@: moved", NSStringFromCGRect(root.frame), NSStringFromCGRect(window.bounds)]);
            root.frame = window.bounds;
            [root setNeedsLayout];
        }
        CAMetalLayer *layer = (CAMetalLayer *)window.rootViewController.view.layer;
        // window=fit: the layer shows the picture at its own shape, centred, with black bars in a
        // window of another one (an iPad's Stage Manager window, a TV); else it stretches it (Unity's own).
        CAMetalLayer *metal = (CAMetalLayer *)window.rootViewController.view.layer;
        if (LTDisplayKeepShape() && ![metal.contentsGravity isEqual:kCAGravityResizeAspect]) {
            metal.contentsGravity = kCAGravityResizeAspect;
            metal.backgroundColor = UIColor.blackColor.CGColor;
        }
        // The window once it has kept one size for a second (a drag goes through many).
        CGSize mode = screen.currentMode.size, largest = CGSizeZero, upscaled = LTUpscaleOutput();
        for (UIScreenMode *m in screen.availableModes) if (m.size.width * m.size.height > largest.width * largest.height) largest = m.size;
        NSString *state = [NSString stringWithFormat:@"window %.0fx%.0f on %@ %.0fx%.0f @%.0fx (mode %.0fx%.0f, largest %.0fx%.0f); Unity draws %.0fx%.0f%@",
            window.bounds.size.width, window.bounds.size.height, screen == UIScreen.mainScreen ? @"the device's screen" : @"an external display",
            screen.bounds.size.width, screen.bounds.size.height, screen.nativeScale, mode.width, mode.height, largest.width, largest.height,
            layer.drawableSize.width, layer.drawableSize.height,
            upscaled.width > 0 ? [NSString stringWithFormat:@", MetalFX to %.0fx%.0f", upscaled.width, upscaled.height] : @""];
        // How the window is laid out, to find why it starts upright on an external display and why
        // the picture can sit off its window: the scene's orientation and size, the window's frame,
        // Unity's view (frame, transform).
        UIView *view = window.rootViewController.view;
        UIWindowScene *scene = window.windowScene;
        UIInterfaceOrientation orientation = UIInterfaceOrientationUnknown;
        CGRect sceneBounds = scene.coordinateSpace.bounds;
        if (@available(iOS 26.0, *)) {
            orientation = scene.effectiveGeometry.interfaceOrientation;
            sceneBounds = scene.effectiveGeometry.coordinateSpace.bounds;
        } else if (@available(iOS 16.0, *)) {
            orientation = scene.effectiveGeometry.interfaceOrientation;
        } else {
            orientation = scene.interfaceOrientation;
        }
        // UIInterfaceOrientation: portrait 1, upside down 2, landscape right 3, landscape left 4.
        NSArray *orientations = @[@"unknown", @"portrait", @"upside down", @"landscape right", @"landscape left"];
        CGAffineTransform t = view.transform;
        // Where the layer puts the picture: its gravity, and with resizeAspect the picture's rect in it.
        CGSize drawable = layer.drawableSize;
        NSString *placed = [layer.contentsGravity isEqual:kCAGravityResizeAspect] && drawable.width > 0 && drawable.height > 0
            ? ({ CGFloat k = MIN(layer.bounds.size.width / drawable.width, layer.bounds.size.height / drawable.height);
                 CGSize shown = CGSizeMake(drawable.width * k, drawable.height * k);
                 NSStringFromCGRect(CGRectMake((layer.bounds.size.width - shown.width) / 2, (layer.bounds.size.height - shown.height) / 2, shown.width, shown.height)); })
            : @"the whole layer";
        state = [state stringByAppendingFormat:@"; layer %@ gravity %@, picture at %@", NSStringFromCGRect(layer.frame), layer.contentsGravity, placed];
        state = [state stringByAppendingFormat:@"; scene %@ %.0fx%.0f, window frame %@, view %@ frame %@%@",
            orientation >= 0 && orientation < (NSInteger)orientations.count ? orientations[orientation] : @"?",
            sceneBounds.size.width, sceneBounds.size.height, NSStringFromCGRect(window.frame), NSStringFromClass(view.class),
            NSStringFromCGRect(view.frame), CGAffineTransformIsIdentity(t) ? @"" : [@" transform " stringByAppendingString:NSStringFromCGAffineTransform(t)]];
        static NSString *seen, *logged;
        static double since;
        double now = CACurrentMediaTime();
        if (![state isEqual:seen]) { seen = state; since = now; return; }
        if (now - since >= 1 && ![state isEqual:logged]) { logged = state; LTDisplayLog(state); }
    });
    dispatch_resume(timer);
}
