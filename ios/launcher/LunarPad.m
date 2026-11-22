#import <GameController/GameController.h>
#import <QuartzCore/QuartzCore.h>
#import <UIKit/UIKit.h>
#import <WebKit/WebKit.h>
#include "controller_actions.h"
#include <math.h>

UIWindow *LTPadWindow(void);
void LTPadToggle(void);
void LTPadBack(void);

// Feed only Unity's view responder, which converts touches into engine input.
// Each stick/face-button contact keeps its identity for the whole gesture.
@interface LTGameTouch : UITouch
@property(nonatomic, weak) UIView *surface;
@property(nonatomic) CGPoint point, previous;
@property(nonatomic) UITouchPhase state;
@property(nonatomic) NSTimeInterval time;
@end
@implementation LTGameTouch
- (UIView *)view { return self.surface; }
- (UIWindow *)window { return self.surface.window; }
- (CGPoint)locationInView:(UIView *)view { return [self.surface convertPoint:self.point toView:view]; }
- (CGPoint)previousLocationInView:(UIView *)view { return [self.surface convertPoint:self.previous toView:view]; }
- (CGPoint)preciseLocationInView:(UIView *)view { return [self locationInView:view]; }
- (CGPoint)precisePreviousLocationInView:(UIView *)view { return [self previousLocationInView:view]; }
- (NSTimeInterval)timestamp { return self.time; }
- (UITouchPhase)phase { return self.state; }
- (UITouchType)type { return UITouchTypeDirect; }
- (NSUInteger)tapCount { return 1; }
- (CGFloat)majorRadius { return 1; }
- (CGFloat)majorRadiusTolerance { return 0; }
- (CGFloat)force { return 1; }
- (CGFloat)maximumPossibleForce { return 1; }
@end

@interface LTPadEvent : UIEvent
@property(nonatomic, copy) NSSet<UITouch *> *contacts;
@end
@implementation LTPadEvent
- (NSSet<UITouch *> *)allTouches { return self.contacts; }
- (NSSet<UITouch *> *)touchesForView:(UIView *)view {
    NSMutableSet *set = [NSMutableSet set];
    for (UITouch *touch in self.contacts) if (touch.view == view) [set addObject:touch];
    return set;
}
- (NSSet<UITouch *> *)touchesForWindow:(UIWindow *)window {
    NSMutableSet *set = [NSMutableSet set];
    for (UITouch *touch in self.contacts) if (touch.window == window) [set addObject:touch];
    return set;
}
- (NSArray<UITouch *> *)coalescedTouchesForTouch:(UITouch *)touch { return @[touch]; }
- (NSArray<UITouch *> *)predictedTouchesForTouch:(UITouch *)touch { return @[]; }
- (UIEventType)type { return UIEventTypeTouches; }
- (NSTimeInterval)timestamp { return self.contacts.anyObject.timestamp; }
@end

static CGPoint Axis(GCControllerDirectionPad *axis, CGFloat dead) {
    CGFloat x = axis.xAxis.value, y = -axis.yAxis.value;
    CGFloat len = hypot(x, y);
    CGFloat scale = len > dead ? (MIN(1, len) - dead) / ((1 - dead) * len) : 0;
    return CGPointMake(x * scale, y * scale);
}
static id Ancestor(UIView *view, Class cls) {
    for (; view; view = view.superview) if ([view isKindOfClass:cls]) return view;
    return nil;
}
static BOOL IsSony(GCExtendedGamepad *pad) {
    return [pad isKindOfClass:GCDualShockGamepad.class] || [pad isKindOfClass:NSClassFromString(@"GCDualSenseGamepad")];
}

@interface LTPad : NSObject
@end
@implementation LTPad {
    GCController *_controller;
    CADisplayLink *_frames;
    __weak UIWindow *_window;
    CGSize _size;
    CGPoint _point, _down;
    UIView *_cursor;
    LTGameTouch *_move, *_press;
    __weak UIView *_uiPress;
    BOOL _dragged;
    CFTimeInterval _lastFrame, _anchoredAt;
    NSUInteger _mask;
    GCControllerButtonInput *_launcherButton;
    GCSystemGestureState _previousGesture;
}
- (void)touch:(LTGameTouch *)touch phase:(UITouchPhase)phase at:(CGPoint)point {
    touch.previous = phase == UITouchPhaseBegan ? point : touch.point;
    touch.point = point; touch.state = phase; touch.time = NSProcessInfo.processInfo.systemUptime;
    NSMutableSet *all = [NSMutableSet setWithObject:touch];
    if (_move) [all addObject:_move];
    if (_press) [all addObject:_press];
    LTPadEvent *event = [LTPadEvent new]; event.contacts = all;
    NSSet *changed = [NSSet setWithObject:touch];
    switch (phase) {
        case UITouchPhaseBegan: [touch.surface touchesBegan:changed withEvent:event]; break;
        case UITouchPhaseMoved: [touch.surface touchesMoved:changed withEvent:event]; break;
        case UITouchPhaseEnded: [touch.surface touchesEnded:changed withEvent:event]; break;
        case UITouchPhaseCancelled: [touch.surface touchesCancelled:changed withEvent:event]; break;
        default: break;
    }
    touch.state = UITouchPhaseStationary;
}
- (void)cancel {
    if (_move) { [self touch:_move phase:UITouchPhaseCancelled at:_move.point]; _move = nil; }
    if (_press) { [self touch:_press phase:UITouchPhaseCancelled at:_press.point]; _press = nil; }
    _uiPress = nil; [_cursor removeFromSuperview]; _lastFrame = 0;
    bunker_pad_request(BUNKER_PAD_CLEAR);
}
- (void)cursor {
    if (!_cursor) {
        _cursor = [[UIView alloc] initWithFrame:CGRectMake(0, 0, 16, 16)];
        _cursor.userInteractionEnabled = NO; _cursor.isAccessibilityElement = NO;
        _cursor.layer.cornerRadius = 8; _cursor.layer.borderColor = UIColor.whiteColor.CGColor;
        _cursor.layer.borderWidth = 2; _cursor.layer.shadowColor = UIColor.blackColor.CGColor;
        _cursor.layer.shadowOpacity = 1; _cursor.layer.shadowRadius = 1; _cursor.layer.shadowOffset = CGSizeZero;
    }
    if (_cursor.superview != _window) [_window addSubview:_cursor];
    _cursor.center = _point;
}
- (void)scroll:(UIScrollView *)scroll x:(CGFloat)dx y:(CGFloat)dy {
    if (!scroll || !scroll.scrollEnabled) return;
    UIEdgeInsets inset = scroll.adjustedContentInset;
    CGPoint offset = scroll.contentOffset;
    offset.x = MAX(-inset.left, MIN(scroll.contentSize.width - scroll.bounds.size.width + inset.right, offset.x + dx));
    offset.y = MAX(-inset.top, MIN(scroll.contentSize.height - scroll.bounds.size.height + inset.bottom, offset.y + dy));
    [scroll setContentOffset:offset animated:NO];
}
- (void)activate:(UIView *)view {
    WKWebView *web = Ancestor(view, WKWebView.class);
    if (web) {
        CGPoint p = [_window convertPoint:_point toView:web];
        // Use the visual viewport for pages which are zoomed or use a desktop viewport.
        [web callAsyncJavaScript:@"const v=visualViewport; const el=document.elementFromPoint(x*v.width,y*v.height); if(el){el.focus?.();el.click?.();}"
            arguments:@{@"x":@(p.x / MAX(1,web.bounds.size.width)), @"y":@(p.y / MAX(1,web.bounds.size.height))}
            inFrame:nil inContentWorld:WKContentWorld.pageWorld completionHandler:nil];
        return;
    }
    UIControl *control = Ancestor(view, UIControl.class);
    if (control && control.enabled) {
        if ([control isKindOfClass:UITextField.class]) [control becomeFirstResponder];
        else if ([control isKindOfClass:UIButton.class] && ((UIButton *)control).showsMenuAsPrimaryAction) {
            if (@available(iOS 17.4,*)) [control performPrimaryAction];
            else [control accessibilityActivate];
        } else [control sendActionsForControlEvents:UIControlEventTouchUpInside];
        return;
    }
    for (UIView *v = view; v; v = v.superview) if ([v accessibilityActivate]) break;
}
- (NSUInteger)buttons {
    GCExtendedGamepad *p = _controller.extendedGamepad;
    return (p.buttonA.isPressed ? 1 : 0) | (p.buttonB.isPressed ? 2 : 0) |
           (p.buttonY.isPressed ? 4 : 0) | (_launcherButton.isPressed ? 8 : 0);
}
- (void)sample {
    UIWindow *window = LTPadWindow();
    NSUInteger mask = [self buttons];
    if (!window || window != _window || !CGSizeEqualToSize(_size, window.bounds.size)) {
        [self cancel];
        _point = CGPointMake(window.bounds.size.width * .5, window.bounds.size.height * .5);
        _window = window; _size = window.bounds.size; _mask = mask;
    }
    if (!window || _size.width < 1 || _size.height < 1) return;
    NSUInteger pressed = mask & ~_mask, released = _mask & ~mask;
    _mask = mask;
    if (pressed & 8) { [self cancel]; LTPadToggle(); return; }
    UIView *root = window.rootViewController.view;
    UIView *hit = [window hitTest:_point withEvent:nil];
    BOOL game = [root.layer isKindOfClass:CAMetalLayer.class] && (hit == root || [hit isDescendantOfView:root]) &&
                !Ancestor(hit, WKWebView.class) && !window.rootViewController.presentedViewController;
    if (pressed & 2) {
        WKWebView *page = Ancestor(hit, WKWebView.class);
        if (page.canGoBack) [page goBack];
        else if (game || ([root.layer isKindOfClass:CAMetalLayer.class] && !window.rootViewController.presentedViewController))
            bunker_pad_request(BUNKER_PAD_BACK);
        else LTPadBack();
        return;
    }
    if (game && (pressed & 4)) bunker_pad_request(BUNKER_PAD_SKIP);
    if (pressed & 1) {
        [self cursor];
        if (game) {
            _press = [LTGameTouch new]; _press.surface = root;
            [self touch:_press phase:UITouchPhaseBegan at:[window convertPoint:_point toView:root]];
        } else { _uiPress = hit; _down = _point; _dragged = NO; }
    }
    if (released & 1) {
        if (_press) { [self touch:_press phase:UITouchPhaseEnded at:_press.point]; _press = nil; }
        else if (_uiPress && !_dragged && (hit == _uiPress || [hit isDescendantOfView:_uiPress] || [_uiPress isDescendantOfView:hit])) [self activate:_uiPress];
        _uiPress = nil;
    }
}
- (void)frame:(CADisplayLink *)link {
    [self sample];
    UIWindow *window = _window;
    if (!window || window != LTPadWindow()) return;
    CFTimeInterval now = link.timestamp, dt = _lastFrame ? MIN(.05, now - _lastFrame) : 1./60;
    _lastFrame = now;
    GCExtendedGamepad *p = _controller.extendedGamepad;
    CGPoint aim = Axis(p.rightThumbstick, .265);
    if (aim.x || aim.y) {
        CGPoint before = _point;
        _point.x = MAX(0,MIN(_size.width-1,_point.x + aim.x*_size.height*dt));
        _point.y = MAX(0,MIN(_size.height-1,_point.y + aim.y*_size.height*dt));
        [self cursor];
        if (_press) [self touch:_press phase:UITouchPhaseMoved at:[window convertPoint:_point toView:_press.surface]];
        if (_uiPress && (_dragged || hypot(_point.x-_down.x,_point.y-_down.y)>5)) {
            _dragged = YES;
            [self scroll:Ancestor(_uiPress, UIScrollView.class) x:before.x-_point.x y:before.y-_point.y];
        }
    }
    CGPoint stick = Axis(p.dpad, 0);
    if (!stick.x && !stick.y) stick = Axis(p.leftThumbstick, .24);
    UIView *root = window.rootViewController.view, *hit = [window hitTest:_point withEvent:nil];
    BOOL game = [root.layer isKindOfClass:CAMetalLayer.class] && !window.rootViewController.presentedViewController && !Ancestor(hit, WKWebView.class);
    if (_move && (!game || (!stick.x && !stick.y))) {
        [self touch:_move phase:game ? UITouchPhaseEnded : UITouchPhaseCancelled at:_move.point]; _move = nil;
    }
    if (!stick.x && !stick.y) return;
    if (!game) {
        [self scroll:Ancestor(hit, UIScrollView.class) x:stick.x*900*dt y:stick.y*900*dt];
        return;
    }
    CGSize size = root.bounds.size;
    CGPoint anchor = CGPointMake(size.width*.22, size.height*.70);
    if (!_move) {
        _move = [LTGameTouch new]; _move.surface = root; _anchoredAt = now;
        [self touch:_move phase:UITouchPhaseBegan at:anchor];
    } else if (now - _anchoredAt >= .2) {
        [self touch:_move phase:UITouchPhaseMoved at:CGPointMake(anchor.x + stick.x*size.height*.15, anchor.y + stick.y*size.height*.15)];
    }
}
- (void)bind:(GCController *)controller {
    _controller = controller;
    GCExtendedGamepad *p = controller.extendedGamepad;
    _launcherButton = IsSony(p) ? p.buttonMenu : p.buttonOptions;
    _previousGesture = _launcherButton.preferredSystemGestureState;
    if (_launcherButton.isBoundToSystemGesture) _launcherButton.preferredSystemGestureState = GCSystemGestureStateDisabled;
    _mask = [self buttons];
    _frames = [CADisplayLink displayLinkWithTarget:self selector:@selector(frame:)];
    [_frames addToRunLoop:NSRunLoop.mainRunLoop forMode:NSRunLoopCommonModes];
}
- (void)attach {
    if (_controller || UIApplication.sharedApplication.applicationState != UIApplicationStateActive) return;
    for (GCController *c in GCController.controllers) if (c.extendedGamepad) { [self bind:c]; break; }
}
- (void)detach {
    [self cancel]; [_frames invalidate]; _frames = nil;
    _launcherButton.preferredSystemGestureState = _previousGesture;
    _launcherButton = nil;
    _controller = nil; _window = nil; _size = CGSizeZero;
}
- (void)start {
    NSNotificationCenter *center = NSNotificationCenter.defaultCenter;
    for (NSString *name in @[GCControllerDidConnectNotification, UIApplicationDidBecomeActiveNotification])
        [center addObserverForName:name object:nil queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *note) { [self attach]; }];
    [center addObserverForName:GCControllerDidDisconnectNotification object:nil queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *note) {
        if (note.object == self->_controller) { [self detach]; [self attach]; }
    }];
    [center addObserverForName:UIApplicationWillResignActiveNotification object:nil queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *note) { [self detach]; }];
    [self attach];
}
@end

void LTPadStart(void) {
    static LTPad *pad;
    dispatch_async(dispatch_get_main_queue(), ^{ pad = [LTPad new]; [pad start]; });
}
