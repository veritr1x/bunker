// The game's picture in a window of any shape, for the iPad build.
//
// With Stage Manager the game's window can be resized, or moved to an external
// display and made full screen there. Twice a second this hands the window's
// size in pixels to LTDisplayFitWindow (LunarDisplay.m), which gives the game's
// picture the window's shape; the game drew in the iPad screen's shape and it
// was stretched to the window.
#import <QuartzCore/QuartzCore.h>
#import <UIKit/UIKit.h>

NSString *LTDisplayFitWindow(CGSize pixels);  // LunarDisplay.m

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
        CGFloat scale = window.windowScene.screen.nativeScale;
        if (!window || scale <= 0) return;
        NSString *fit = LTDisplayFitWindow(CGSizeMake(round(window.bounds.size.width * scale), round(window.bounds.size.height * scale)));
        if (fit) NSLog(@"[LunarTear] %@", fit);
    });
    dispatch_resume(timer);
}
