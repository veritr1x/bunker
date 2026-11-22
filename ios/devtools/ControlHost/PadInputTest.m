// Simulator integration test for the native controller bridge. Unity's responder
// is represented by a Metal-backed view which records both simultaneous fingers.
#import "../../launcher/LunarPad.m"

static UIWindow *window;
static int back, skip, taps;
UIWindow *LTPadWindow(void) { return window; }
void LTPadBack(void) { back++; }
void LTPadToggle(void) {}
void bunker_pad_request(int action) {
    if (action == BUNKER_PAD_BACK) back++;
    if (action == BUNKER_PAD_SKIP) skip++;
}
@interface Recorder : UIView
@property(nonatomic) int began, moved, ended, cancelled, maxCount;
@property(nonatomic) CGPoint last;
@property(nonatomic) CGFloat farthestX;
@end
@implementation Recorder
+ (Class)layerClass { return CAMetalLayer.class; }
- (void)touchesBegan:(NSSet *)touches withEvent:(UIEvent *)event {
    self.began++;
    self.maxCount = MAX(self.maxCount, (int)[event touchesForView:self].count);
}
- (void)touchesMoved:(NSSet *)touches withEvent:(UIEvent *)event {
    self.moved++; self.last = [touches.anyObject locationInView:self];
    self.farthestX = MAX(self.farthestX, self.last.x);
}
- (void)touchesEnded:(NSSet *)touches withEvent:(UIEvent *)event { self.ended++; }
- (void)touchesCancelled:(NSSet *)touches withEvent:(UIEvent *)event { self.cancelled++; }
@end
@interface Clock : NSObject
@property(nonatomic) CFTimeInterval timestamp;
@end
@implementation Clock
@end

#define CHECK(c) if (!(c)) return @#c
static NSString *check(void) {
    Recorder *game = [Recorder new];
    window.rootViewController.view = game;
    [window layoutIfNeeded];
    GCController *device = [GCController controllerWithExtendedGamepad];
    GCExtendedGamepad *p = device.extendedGamepad;
    CHECK(p && device.isSnapshot);
    LTPad *bridge = [LTPad new]; [bridge bind:device]; [bridge sample];
    Clock *clock = [Clock new];
    void (^frame)(double) = ^(double t){ clock.timestamp=t; [bridge frame:(CADisplayLink *)clock]; };
    [p.leftThumbstick setValueForXAxis:1 yAxis:0];
    frame(1); frame(1.25);
    CHECK(game.began == 1 && game.moved == 1 && game.last.x > game.bounds.size.width*.22);
    [p.rightThumbstick setValueForXAxis:.8 yAxis:.3];
    [p.buttonA setValue:1]; frame(1.30);
    CHECK(game.began == 2 && game.maxCount == 2 && game.farthestX > game.bounds.size.width*.5);
    [p.buttonA setValue:0]; frame(1.35);
    CHECK(game.ended == 1);
    [p.leftThumbstick setValueForXAxis:0 yAxis:0];
    [p.rightThumbstick setValueForXAxis:0 yAxis:0]; frame(1.4);
    CHECK(game.ended == 2);
    [p.dpad setValueForXAxis:-1 yAxis:0]; frame(1.45); frame(1.7);
    CHECK(game.began == 3 && game.last.x < game.bounds.size.width*.22);
    [p.buttonB setValue:1]; frame(1.75);
    [p.buttonY setValue:1]; frame(1.8); frame(1.85);
    CHECK(back == 1 && skip == 1);
    [bridge detach]; CHECK(game.cancelled == 1);
    [p.buttonB setValue:0]; [p.buttonY setValue:0]; [p.dpad setValueForXAxis:0 yAxis:0];
    UIView *menu = [UIView new]; window.rootViewController.view = menu;
    UIButton *button = [UIButton buttonWithType:UIButtonTypeSystem]; [menu addSubview:button];
    [window layoutIfNeeded]; button.frame = menu.bounds;
    [button addAction:[UIAction actionWithHandler:^(UIAction *action){ taps++; }] forControlEvents:UIControlEventTouchUpInside];
    [bridge bind:device]; [bridge sample];
    [p.buttonA setValue:1]; frame(2); [p.buttonA setValue:0]; frame(2.05);
    CHECK(taps == 1 && game.began == 3);
    [bridge detach]; return @"PASS";
}
@interface Scene : UIResponder <UIWindowSceneDelegate>
@end
@implementation Scene
- (void)scene:(UIScene *)scene willConnectToSession:(UISceneSession *)session options:(UISceneConnectionOptions *)options {
    window = [[UIWindow alloc] initWithWindowScene:(UIWindowScene *)scene];
    window.rootViewController = [UIViewController new]; [window makeKeyAndVisible];
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW,NSEC_PER_SEC),dispatch_get_main_queue(),^{
        NSString *result;
        @try { result = check(); } @catch (NSException *exception) { result = exception.description; }
        NSURL *documents = [NSFileManager.defaultManager URLsForDirectory:NSDocumentDirectory inDomains:NSUserDomainMask].firstObject;
        [result writeToURL:[documents URLByAppendingPathComponent:@"result"] atomically:YES encoding:NSUTF8StringEncoding error:nil];
    });
}
@end
@interface App : UIResponder <UIApplicationDelegate>
@end
@implementation App
@end
int main(int argc,char **argv) { @autoreleasepool { return UIApplicationMain(argc, argv, nil, @"App"); } }
