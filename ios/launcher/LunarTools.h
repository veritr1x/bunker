// Tools: lunar-base's save editors and content presets, run by an embedded
// Python only while Tools is open.
#import <UIKit/UIKit.h>

// True when this build includes the Python runtime.
BOOL LTToolsAvailable(void);
// Starts Python on first use, then the editors. Blocks; call off the main
// thread with the game server stopped. Returns "" and sets url and token, or
// an error. progress receives status text on the calling thread.
NSString *LTToolsStart(NSString *saves, NSString *serverRoot, NSString *toolsRoot, NSString *originalMaster,
                       NSString **url, NSString **token, void (^progress)(NSString *text));
// Stops the editors. Blocks until the current edit finishes. Returns "" or an error.
NSString *LTToolsStop(void);
// A full-screen browser for the editors. close runs when the player taps Close.
UIViewController *LTToolsBrowser(NSString *url, NSString *token, void (^close)(void));
