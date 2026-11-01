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
// archive opens the Archive at a timeline link's page (Pod Programs › Schedule).
UIViewController *LTToolsBrowser(NSString *url, NSString *token, void (^close)(void), void (^archive)(NSString *path));
// The Archive: story, records, characters, pictures, movies and music read
// from the game files. Read only, so Lunar Tear and the game keep running.
// Blocks; call off the main thread. Returns "" and sets url and token, or an error.
NSString *LTArchiveStart(NSString *serverRoot, NSString *archiveRoot, NSString **url, NSString **token, void (^progress)(NSString *text));
// Stops the Archive's server so its tables leave the game's memory. Blocks; call off the main thread.
NSString *LTArchiveStop(void);
// After an update, the game data is brought up to this build before the
// server starts (ios_runtime.update_data): the Original calendar's, or the
// Pod Programs preset's, once per version; Android uses the same rule
// (DataUpdate.java). True when saves/calendar.json or
// toolsRoot/patcher/active.json is there and saves/data.updated names another version.
BOOL LTDataNeedsUpdate(NSString *saves, NSString *toolsRoot, NSString *version);
// Starts Python and updates the game data. Blocks; call off the main thread
// with the game server stopped. Returns "" or an error.
NSString *LTUpdateData(NSString *saves, NSString *serverRoot, NSString *toolsRoot, NSString *originalMaster, NSString *version);
/** Builds the next Bunker IPA from the installed app and the release's bundles (bunker_ios_update.py). noticesZip
    is the release's notice pack, or "" to keep the app's. Returns "" or an error. */
NSString *LTBuildUpdate(NSString *app, NSString *frameworkZip, NSString *pythonZip, NSString *shaFramework, NSString *shaPython,
                        NSString *noticesZip, NSString *shaNotices, NSString *output, void (^progress)(NSString *text));
// A full-screen browser for the Archive. close runs when the player taps Close.
// path: the page to open on (a timeline link's), or nil for the home page.
UIViewController *LTArchiveBrowser(NSString *url, NSString *token, NSString *path, void (^close)(void));
