// Lunar Tear iOS launcher: runs the embedded server inside the game process.
//
// iOS suspends background apps, so a separate server app cannot serve the
// game while it is in front. This framework is loaded by the patched game's
// executable, starts the loopback server before Unity's first request, and
// shows a setup screen when game files are missing or the server fails.
#import <UIKit/UIKit.h>
#import <SystemConfiguration/SystemConfiguration.h>
#import <UniformTypeIdentifiers/UniformTypeIdentifiers.h>
#include <stdlib.h>
#include "liblunar.h"
#include "rebind.h"
#import "LunarTools.h"

static NSString *const kMasterName = @"20240404193219.bin.e";
static NSString *gServerRoot, *gSaves, *gMessage;
static UIWindow *gWindow;
static UIBackgroundTaskIdentifier gBackgroundTask;
static dispatch_queue_t gQueue;
// Tools edits the saves with the server stopped. The game keeps its own copy
// of the player's data, so after Tools it must restart before playing again.
static BOOL gToolsOpen, gRestartNeeded;

#pragma mark - Paths and files

static NSString *Documents(void) {
    return NSSearchPathForDirectoriesInDomains(NSDocumentDirectory, NSUserDomainMask, YES).firstObject;
}
static NSString *MasterPath(void) { return [gServerRoot stringByAppendingPathComponent:[@"assets/release" stringByAppendingPathComponent:kMasterName]]; }
static unsigned long long FileSize(NSString *path) {
    return [[[NSFileManager defaultManager] attributesOfItemAtPath:path error:nil] fileSize];
}
static BOOL HasCatalog(void) {
    for (NSString *p in @[@"assets/revisions/0/ios/list.bin", @"assets/revisions/0/list.bin"])
        if (FileSize([gServerRoot stringByAppendingPathComponent:p]) > 0) return YES;
    return NO;
}

// Copies the bundled, already-patched master data into place once. The asset
// folder the player copies in does not need a release directory.
static void EnsureMaster(void) {
    NSString *target = MasterPath();
    if (FileSize(target) > 0) return;
    NSBundle *bundle = [NSBundle bundleForClass:NSClassFromString(@"LTLauncherViewController")];
    NSString *source = [bundle pathForResource:@"20240404193219" ofType:@"bin.e"];
    if (!source) return;
    NSFileManager *files = [NSFileManager defaultManager];
    [files createDirectoryAtPath:[target stringByDeletingLastPathComponent] withIntermediateDirectories:YES attributes:nil error:nil];
    NSString *pending = [target stringByAppendingString:@".pending"];
    [files removeItemAtPath:pending error:nil];
    if ([files copyItemAtPath:source toPath:pending error:nil])
        rename(pending.fileSystemRepresentation, target.fileSystemRepresentation);
}

static NSString *TakeString(char *value) {
    NSString *text = value ? [NSString stringWithUTF8String:value] : @"Native call failed";
    free(value);
    return text ?: @"";
}
static NSDictionary *Status(void) {
    NSData *json = [TakeString(LunarStatus()) dataUsingEncoding:NSUTF8StringEncoding];
    return [NSJSONSerialization JSONObjectWithData:json options:0 error:nil] ?: @{};
}
static BOOL Running(void) { return [Status()[@"state"] isEqual:@"running"]; }
static NSString *ToolsRoot(void) {
    NSString *support = NSSearchPathForDirectoriesInDomains(NSApplicationSupportDirectory, NSUserDomainMask, YES).firstObject;
    return [support stringByAppendingPathComponent:@"LunarTools"];
}

#pragma mark - Game files used in place

// A folder chosen with "Use in place" stays where the player keeps it. Its
// revisions/0 is linked into assets/, and a bookmark reopens access to it on
// each start, since iOS grants access to a picked folder only until the app quits.
static NSString *const kInPlaceBookmark = @"LTInPlaceBookmark", *const kInPlaceRelative = @"LTInPlaceRelative";
static NSURL *gInPlaceFolder;  // Accessed for as long as the app runs.

static NSString *LinkPath(void);
static void ForgetInPlace(void) {
    [NSUserDefaults.standardUserDefaults removeObjectForKey:kInPlaceBookmark];
    [NSUserDefaults.standardUserDefaults removeObjectForKey:kInPlaceRelative];
}

// Reopens the saved folder and points the link at it. Returns NO when a folder
// is in use but cannot be opened (for example, its USB drive is unplugged).
static BOOL AttachInPlace(void) {
    NSData *bookmark = [NSUserDefaults.standardUserDefaults dataForKey:kInPlaceBookmark];
    NSString *relative = [NSUserDefaults.standardUserDefaults stringForKey:kInPlaceRelative];
    if (!bookmark || !relative) return YES;
    BOOL stale = NO;
    NSURL *folder = [NSURL URLByResolvingBookmarkData:bookmark options:0 relativeToURL:nil bookmarkDataIsStale:&stale error:nil];
    if (!folder) return NO;
    if (![folder.path isEqualToString:gInPlaceFolder.path]) {
        if (![folder startAccessingSecurityScopedResource] && ![NSFileManager.defaultManager isReadableFileAtPath:folder.path]) return NO;
        [gInPlaceFolder stopAccessingSecurityScopedResource];
        gInPlaceFolder = folder;
    }
    if (stale) {
        NSData *fresh = [folder bookmarkDataWithOptions:0 includingResourceValuesForKeys:nil relativeToURL:nil error:nil];
        if (fresh) [NSUserDefaults.standardUserDefaults setObject:fresh forKey:kInPlaceBookmark];
    }
    // The folder may have a new path (renamed, or a drive mounted elsewhere).
    NSString *target = [folder.path stringByAppendingPathComponent:relative];
    NSFileManager *files = NSFileManager.defaultManager;
    NSString *current = [files destinationOfSymbolicLinkAtPath:LinkPath() error:nil];
    if (![current isEqualToString:target]) {
        [files removeItemAtPath:LinkPath() error:nil];  // Removes the link only.
        [files createSymbolicLinkAtPath:LinkPath() withDestinationPath:target error:nil];
    }
    return [files fileExistsAtPath:target];
}

// Returns a message naming each port that failed the self-test, or nil when all passed.
static NSString *SelfTestFailure(NSString *report) {
    NSDictionary *r = [NSJSONSerialization JSONObjectWithData:[report dataUsingEncoding:NSUTF8StringEncoding] options:0 error:nil];
    if ([r[@"ok"] boolValue]) return nil;
    NSMutableString *text = [NSMutableString stringWithString:@"The game could not reach its server:"];
    for (NSDictionary *c in r[@"checks"])
        if (![c[@"ok"] boolValue]) [text appendFormat:@"\n• Port %@ (%@): %@", c[@"port"], c[@"name"], c[@"detail"]];
    return text;
}

// Starts the server; returns an empty string on success.
static NSString *StartServer(void) {
    EnsureMaster();
    if (!AttachInPlace())
        return @"Cannot open your game files folder. Reconnect its drive or put it back, then tap Check again, or choose the files again.";
    if (!HasCatalog()) return @"Choose the game files, then tap Check again.";
    // The ports the game was built for (8003/8080/3000 plus the build's offset).
    int offset = [[NSBundle.mainBundle objectForInfoDictionaryKey:@"LunarPortOffset"] intValue];
    NSString *error = TakeString(LunarSetPortOffset(offset));
    if (error.length) return error;
    error = TakeString(LunarStart((char *)gSaves.fileSystemRepresentation, (char *)gServerRoot.fileSystemRepresentation));
    if (error.length) return error;
    // Confirm the game can reach this server on every port before playing.
    NSString *failure = SelfTestFailure(TakeString(LunarSelfTest()));
    if (failure) { LunarStop(); return failure; }
    return @"";
}

#pragma mark - Airplane-mode reachability

// Unity reports NotReachable with radios off and the asset loader then refuses
// even loopback downloads. Report a local-network connection to Unity only.
static Boolean (*OriginalGetFlags)(SCNetworkReachabilityRef, SCNetworkReachabilityFlags *);
static Boolean (*OriginalSetCallback)(SCNetworkReachabilityRef, SCNetworkReachabilityCallBack, SCNetworkReachabilityContext *);
static SCNetworkReachabilityCallBack gCallbacks[8];
static SCNetworkReachabilityRef gTargets[8];

static SCNetworkReachabilityFlags Reachable(SCNetworkReachabilityFlags flags) {
    return (flags & kSCNetworkReachabilityFlagsReachable) ? flags : kSCNetworkReachabilityFlagsReachable;
}
static Boolean LTGetFlags(SCNetworkReachabilityRef target, SCNetworkReachabilityFlags *flags) {
    SCNetworkReachabilityFlags value = 0;
    if (OriginalGetFlags) OriginalGetFlags(target, &value);
    if (flags) *flags = Reachable(value);
    return true;
}
static void LTCallback(SCNetworkReachabilityRef target, SCNetworkReachabilityFlags flags, void *info) {
    for (int i = 0; i < 8; i++)
        if (gTargets[i] == target && gCallbacks[i]) { gCallbacks[i](target, Reachable(flags), info); return; }
}
static Boolean LTSetCallback(SCNetworkReachabilityRef target, SCNetworkReachabilityCallBack callback, SCNetworkReachabilityContext *context) {
    if (!OriginalSetCallback) return false;
    if (!callback) return OriginalSetCallback(target, NULL, context);
    @synchronized ([NSFileManager class]) {
        for (int i = 0; i < 8; i++)
            if (gTargets[i] == target || !gTargets[i]) { gTargets[i] = target; gCallbacks[i] = callback; return OriginalSetCallback(target, LTCallback, context); }
    }
    return OriginalSetCallback(target, callback, context);
}
static const struct lt_rebinding kReachability[] = {
    {"SCNetworkReachabilityGetFlags", (void *)LTGetFlags, (void **)&OriginalGetFlags},
    {"SCNetworkReachabilitySetCallback", (void *)LTSetCallback, (void **)&OriginalSetCallback},
};

#pragma mark - Importing game files

static volatile BOOL gImporting, gCancelImport;
// 0-1 while copying game files; negative while the total is still unknown.
static volatile double gImportFraction = -1;

static NSString *AssetsPath(void) { return [gServerRoot stringByAppendingPathComponent:@"assets"]; }
static NSString *StagePath(void) { return [gServerRoot stringByAppendingPathComponent:@".assets-importing"]; }
static NSString *PreviousPath(void) { return [gServerRoot stringByAppendingPathComponent:@".assets-previous"]; }
static NSString *LinkPath(void) { return [AssetsPath() stringByAppendingPathComponent:@"revisions/0"]; }
// The player's own folder while it is moved (not copied) into the stage.
static NSString *gMovedFrom;

// Removes the staging folder. A folder moved in from Documents goes back to
// where the player put it instead of being deleted.
static void DiscardStage(void) {
    NSFileManager *files = NSFileManager.defaultManager;
    NSString *moved = [StagePath() stringByAppendingPathComponent:@"revisions/0"];
    if (gMovedFrom && [files fileExistsAtPath:moved] && ![files fileExistsAtPath:gMovedFrom])
        [files moveItemAtPath:moved toPath:gMovedFrom error:nil];
    gMovedFrom = nil;
    [files removeItemAtPath:StagePath() error:nil];
}

// Restores the last complete folder if the app was closed during a swap.
static void RecoverImport(void) {
    NSFileManager *files = NSFileManager.defaultManager;
    if (![files fileExistsAtPath:AssetsPath()] && [files fileExistsAtPath:PreviousPath()])
        [files moveItemAtPath:PreviousPath() toPath:AssetsPath() error:nil];
    DiscardStage();
}

// Accept the assets folder itself or the folder that contains it.
static NSURL *FindAssetsRoot(NSURL *picked) {
    for (NSURL *candidate in @[picked, [picked URLByAppendingPathComponent:@"assets"]])
        for (NSString *catalog in @[@"revisions/0/ios/list.bin", @"revisions/0/list.bin"])
            if ([NSFileManager.defaultManager fileExistsAtPath:[candidate URLByAppendingPathComponent:catalog].path]) return candidate;
    return nil;
}

// Finds revisions/0 in a chosen folder: the extracted dump itself, a folder
// holding "assets", or the "revisions" folder. Only revision 0 is used; the
// raw dump's other revisions are 28 GB of old catalogs and are skipped.
static NSURL *FindRevisionZero(NSURL *picked) {
    for (NSString *path in @[@"revisions/0", @"assets/revisions/0", @"0"]) {
        NSURL *candidate = [picked URLByAppendingPathComponent:path];
        for (NSString *catalog in @[@"ios/list.bin", @"list.bin"])
            if ([NSFileManager.defaultManager fileExistsAtPath:[candidate URLByAppendingPathComponent:catalog].path]) return candidate;
    }
    return nil;
}

// True when an archive path lies under revisions/<n> with n other than 0.
static BOOL OtherRevision(NSString *name) {
    NSArray<NSString *> *parts = name.pathComponents;
    NSUInteger i = [parts indexOfObject:@"revisions"];
    return i != NSNotFound && i + 1 < parts.count && ![parts[i + 1] isEqualToString:@"0"];
}

// Refuses files whose revision 0 folder points at files kept in other revisions.
static NSString *CheckSelfContained(NSString *revisionZero) {
    NSDirectoryEnumerator *walk = [NSFileManager.defaultManager enumeratorAtPath:revisionZero];
    for (NSString *relative in walk) {
        if (![relative.lastPathComponent isEqualToString:@"info.json"]) continue;
        NSData *data = [NSData dataWithContentsOfFile:[revisionZero stringByAppendingPathComponent:relative]
                                              options:NSDataReadingMappedIfSafe error:nil];
        const char *bytes = data.bytes, *end = bytes + data.length, *key = "\"to-revision\"";
        size_t keyLength = strlen(key);
        for (const char *p = bytes; p && p < end; ) {
            p = memmem(p, (size_t)(end - p), key, keyLength);
            if (!p) break;
            p += keyLength;
            while (p < end && (*p == ' ' || *p == ':' || *p == '"')) p++;
            if (p >= end || *p != '0' || (p + 1 < end && p[1] >= '0' && p[1] <= '9'))
                return @"These game files use other revisions. Prepare them on a computer with scripts/prepare_assets.py.";
        }
    }
    return @"";
}

static NSString *LTByteText(unsigned long long bytes) {
    return [NSByteCountFormatter stringFromByteCount:(long long)bytes countStyle:NSByteCountFormatterCountStyleFile];
}

// Time left for a copy. Small files cost far more per byte than large ones,
// so it learns from recent progress how long one file and one byte take on
// this device, then applies that to what remains. Recent samples count most.
// With no file count (archives), it uses the recent byte speed.
typedef struct {
    double totalFiles, totalBytes, started, lastTime, lastFiles, lastBytes;
    double ff, fb, bb, ft, bt, shown;
    double st, sf, sb;  // recent time, files and bytes, including pauses with no progress
} LTEstimate;

static LTEstimate LTEstimateStart(unsigned long long files, unsigned long long bytes) {
    CFAbsoluteTime now = CFAbsoluteTimeGetCurrent();
    return (LTEstimate){.totalFiles = files, .totalBytes = bytes, .started = now, .lastTime = now};
}

// Records progress and returns seconds left, or -1 while still measuring.
static double LTEstimateUpdate(LTEstimate *e, double files, double bytes) {
    double now = CFAbsoluteTimeGetCurrent(), dt = now - e->lastTime, df = files - e->lastFiles, db = bytes - e->lastBytes;
    if (dt > 0) {
        e->ff = e->ff * .995 + df * df; e->fb = e->fb * .995 + df * db; e->bb = e->bb * .995 + db * db;
        e->ft = e->ft * .995 + df * dt; e->bt = e->bt * .995 + db * dt;
        e->st = e->st * .995 + dt; e->sf = e->sf * .995 + df; e->sb = e->sb * .995 + db;
    }
    e->lastTime = now; e->lastFiles = files; e->lastBytes = bytes;
    if (now - e->started < 10 || e->bb <= 0) return -1;
    double perFile = 0, perByte = e->bt / e->bb, det = e->ff * e->bb - e->fb * e->fb;
    if (e->ff > 0 && det > 1e-6 * e->ff * e->bb) {
        perFile = (e->ft * e->bb - e->bt * e->fb) / det;
        perByte = (e->bt * e->ff - e->ft * e->fb) / det;
    }
    if (perFile < 0 || perByte < 0) {  // Too little variety yet: count each file as 1 MB.
        double done = bytes + files * 1e6, total = e->totalBytes + e->totalFiles * 1e6;
        return done > 0 ? (now - e->started) * (total - done) / done : -1;
    }
    // The fit gives the relative cost of a file and a byte. Scale it by the real
    // recent time, so pauses between bursts (as when several archive blocks
    // decompress at once) count too.
    double work = perFile * e->sf + perByte * e->sb, scale = work > 0 ? e->st / work : 1;
    return MAX(0, scale * (perFile * (e->totalFiles - files) + perByte * (e->totalBytes - bytes)));
}

// "8.2 GB of 20.9 GB · 39% · about 4 min left". The bar follows the expected
// time once it is measured, and never moves back.
static NSString *LTProgressText(NSString *verb, LTEstimate *e, unsigned long long files, unsigned long long bytes) {
    double left = LTEstimateUpdate(e, files, bytes), fraction;
    if (left < 0) fraction = (bytes + files * 1e6) / MAX(1.0, e->totalBytes + e->totalFiles * 1e6);
    else { double elapsed = CFAbsoluteTimeGetCurrent() - e->started; fraction = elapsed / MAX(1e-6, elapsed + left); }
    e->shown = MAX(e->shown, MIN(1.0, fraction));
    gImportFraction = e->shown;
    NSString *line = [NSString stringWithFormat:@"%@ %@ of %@ · %d%%", verb, LTByteText(bytes), LTByteText((unsigned long long)e->totalBytes), (int)(e->shown * 100)];
    if (left < 0) return [line stringByAppendingString:@" · estimating time left…"];
    long seconds = lround(left);
    NSString *text = seconds < 60 ? @"under a minute left"
        : seconds < 3600 ? [NSString stringWithFormat:@"about %ld min left", (seconds + 30) / 60]
        : [NSString stringWithFormat:@"about %ld h %ld min left", seconds / 3600, (seconds % 3600 + 30) / 60];
    return [NSString stringWithFormat:@"%@ · %@", line, text];
}

// Archives: one .tar, or pieces named NAME.tar.aa, NAME.tar.ab … (from
// `split`). One large file copies far faster than 200,000 small ones.
static NSArray<NSString *> *ArchiveParts(NSString *path) {
    NSString *name = path.lastPathComponent, *folder = path.stringByDeletingLastPathComponent;
    if ([name.pathExtension.lowercaseString isEqualToString:@"tar"]) return @[path];
    NSRange marker = [name rangeOfString:@".tar." options:NSBackwardsSearch];
    if (marker.location == NSNotFound) return nil;
    NSString *stem = [name substringToIndex:NSMaxRange(marker)];
    NSMutableArray *parts = [NSMutableArray array];
    for (NSString *sibling in [[NSFileManager.defaultManager contentsOfDirectoryAtPath:folder error:nil] sortedArrayUsingSelector:@selector(compare:)])
        if ([sibling hasPrefix:stem]) [parts addObject:[folder stringByAppendingPathComponent:sibling]];
    return parts.count ? parts : nil;
}

// Reads the archive pieces as one stream.
@interface LTPartReader : NSObject
- (instancetype)initWithParts:(NSArray<NSString *> *)parts;
- (BOOL)read:(void *)buffer length:(size_t)length;
@property(nonatomic, readonly) unsigned long long consumed;
@end
@implementation LTPartReader { NSArray<NSString *> *_parts; NSUInteger _index; FILE *_file; }
- (instancetype)initWithParts:(NSArray<NSString *> *)parts { if ((self = [super init])) _parts = parts; return self; }
- (BOOL)read:(void *)buffer length:(size_t)length {
    uint8_t *out = buffer;
    while (length) {
        if (!_file) {
            if (_index >= _parts.count) return NO;
            _file = fopen(_parts[_index++].fileSystemRepresentation, "rb");
            if (!_file) return NO;
        }
        size_t got = fread(out, 1, length, _file);
        out += got; length -= got; _consumed += got;
        if (length) { fclose(_file); _file = NULL; }
    }
    return YES;
}
- (void)dealloc { if (_file) fclose(_file); }
@end

static unsigned long long Octal(const char *field, size_t length) {
    unsigned long long value = 0;
    for (size_t i = 0; i < length && field[i]; i++)
        if (field[i] >= '0' && field[i] <= '7') value = value * 8 + (unsigned long long)(field[i] - '0');
    return value;
}

// Rejects absolute paths and "..", so an archive cannot write outside `root`.
static NSString *SafeJoin(NSString *root, NSString *relative) {
    if (!relative.length || [relative hasPrefix:@"/"]) return nil;
    for (NSString *part in relative.pathComponents) if ([part isEqualToString:@".."]) return nil;
    return [root stringByAppendingPathComponent:relative];
}

// Extracts ustar, GNU long-name and pax-path entries into `root`.
static NSString *ExtractArchive(NSArray<NSString *> *parts, NSString *root, void (^progress)(NSString *)) {
    LTPartReader *reader = [[LTPartReader alloc] initWithParts:parts];
    unsigned long long total = 0;
    for (NSString *part in parts) total += FileSize(part);
    LTEstimate estimate = LTEstimateStart(0, total);  // A tar has no index of its files.
    NSFileManager *files = NSFileManager.defaultManager;
    char header[512];
    NSMutableData *buffer = [NSMutableData dataWithLength:1 << 20];
    NSString *pendingName = nil;
    NSUInteger zeros = 0;
    CFAbsoluteTime reported = 0;
    while (zeros < 2) {
        if (gCancelImport) return @"Import cancelled. Your previous files were kept.";
        if (![reader read:header length:512]) return zeros ? @"" : @"The archive ended early. Copy every part, then try again.";
        BOOL empty = YES;
        for (int i = 0; i < 512 && empty; i++) empty = header[i] == 0;
        if (empty) { zeros++; continue; }
        zeros = 0;
        unsigned long long size = Octal(header + 124, 12);
        char type = header[156];
        NSString *name = pendingName;
        pendingName = nil;
        if (!name) {
            NSString *base = [[NSString alloc] initWithBytes:header length:strnlen(header, 100) encoding:NSUTF8StringEncoding];
            NSString *prefix = memcmp(header + 257, "ustar", 5) == 0
                ? [[NSString alloc] initWithBytes:header + 345 length:strnlen(header + 345, 155) encoding:NSUTF8StringEncoding] : @"";
            name = prefix.length ? [prefix stringByAppendingPathComponent:base] : base;
        }
        unsigned long long padded = (size + 511) / 512 * 512;
        if (type == 'L' || type == 'x') {
            // Long name records: read the data and apply it to the next entry.
            if (size > 65536) return @"The archive has an invalid header.";
            NSMutableData *data = [NSMutableData dataWithLength:(NSUInteger)padded];
            if (![reader read:data.mutableBytes length:(size_t)padded]) return @"The archive ended early. Copy every part, then try again.";
            NSString *text = [[NSString alloc] initWithBytes:data.bytes length:(NSUInteger)size encoding:NSUTF8StringEncoding] ?: @"";
            if (type == 'L') pendingName = [text stringByTrimmingCharactersInSet:[NSCharacterSet characterSetWithCharactersInString:@"\0"]];
            else for (NSString *record in [text componentsSeparatedByString:@"\n"]) {
                NSRange key = [record rangeOfString:@" path="];
                if (key.location != NSNotFound) pendingName = [record substringFromIndex:NSMaxRange(key)];
            }
            continue;
        }
        if (type == 'g') {  // Global pax header: nothing we use.
            for (unsigned long long left = padded; left; ) {
                size_t chunk = (size_t)MIN(left, (unsigned long long)buffer.length);
                if (![reader read:buffer.mutableBytes length:chunk]) return @"The archive ended early.";
                left -= chunk;
            }
            continue;
        }
        NSString *target = SafeJoin(root, name);
        if (!target) return [@"The archive contains an unsafe path: " stringByAppendingString:name ?: @"?"];
        BOOL skip = OtherRevision(name);  // Only revision 0 is used.
        if (type == '5') {
            if (!skip) [files createDirectoryAtPath:target withIntermediateDirectories:YES attributes:nil error:nil];
            continue;
        }
        BOOL regular = (type == '0' || type == 0) && !skip;
        FILE *out = NULL;
        if (regular) {
            [files createDirectoryAtPath:target.stringByDeletingLastPathComponent withIntermediateDirectories:YES attributes:nil error:nil];
            out = fopen(target.fileSystemRepresentation, "wb");
            if (!out) return [@"Cannot write " stringByAppendingString:name];
        }
        for (unsigned long long left = padded; left; ) {
            size_t chunk = (size_t)MIN(left, (unsigned long long)buffer.length);
            if (![reader read:buffer.mutableBytes length:chunk]) { if (out) fclose(out); return @"The archive ended early. Copy every part, then try again."; }
            unsigned long long used = padded - left;
            if (out && used < size) {
                size_t keep = (size_t)MIN((unsigned long long)chunk, size - used);
                if (fwrite(buffer.bytes, 1, keep, out) != keep) { fclose(out); return @"Not enough free space to import the game files."; }
            }
            left -= chunk;
        }
        if (out && fclose(out) != 0) return @"Not enough free space to import the game files.";
        if (CFAbsoluteTimeGetCurrent() - reported > 0.5) {
            reported = CFAbsoluteTimeGetCurrent();
            progress(LTProgressText(@"Unpacking", &estimate, 0, reader.consumed));
        }
    }
    return @"";
}

// Validates a staged assets folder at `root` (inside the staging folder) and
// swaps it into place, keeping the previous files until the swap succeeds.
static NSString *InstallStaged(NSString *root, void (^progress)(NSString *)) {
    NSFileManager *files = NSFileManager.defaultManager;
    NSError *error = nil;
    BOOL catalog = NO;
    for (NSString *path in @[@"revisions/0/ios/list.bin", @"revisions/0/list.bin"])
        catalog = catalog || FileSize([root stringByAppendingPathComponent:path]) > 0;
    if (!catalog) { DiscardStage(); return @"The copied folder has no catalog. Choose the folder that contains revisions/0."; }
    NSString *aliases = CheckSelfContained([root stringByAppendingPathComponent:@"revisions/0"].stringByResolvingSymlinksInPath);
    if (aliases.length) { DiscardStage(); return aliases; }
    // Keep the current master data (including applied content presets).
    NSString *nextMaster = [root stringByAppendingPathComponent:[@"release" stringByAppendingPathComponent:kMasterName]];
    if (FileSize(nextMaster) == 0 && FileSize(MasterPath()) > 0) {
        [files createDirectoryAtPath:nextMaster.stringByDeletingLastPathComponent withIntermediateDirectories:YES attributes:nil error:nil];
        [files copyItemAtPath:MasterPath() toPath:nextMaster error:nil];
    }
    gImportFraction = -1;
    progress(@"Finishing import…");
    LunarStop();  // Never serve files while their folder is being replaced.
    [files removeItemAtPath:PreviousPath() error:nil];
    if ([files fileExistsAtPath:AssetsPath()] && ![files moveItemAtPath:AssetsPath() toPath:PreviousPath() error:&error])
        { DiscardStage(); return error.localizedDescription; }
    if (![files moveItemAtPath:root toPath:AssetsPath() error:&error]) { RecoverImport(); return error.localizedDescription; }
    [files removeItemAtPath:PreviousPath() error:nil];
    gMovedFrom = nil;  // Installed: nothing to put back.
    ForgetInPlace();  // LinkAssets saves its folder again after this.
    DiscardStage();  // Leftover wrapper when an archive held an assets folder.
    return @"";
}

static unsigned long long FreeSpace(void) {
    NSNumber *value = nil;
    [[NSURL fileURLWithPath:gServerRoot] getResourceValue:&value forKey:NSURLVolumeAvailableCapacityForImportantUsageKey error:nil];
    return value.unsignedLongLongValue;
}

// Uses a chosen folder where it is: revisions/0 is linked, not copied. iCloud
// Drive is refused, since iOS may remove its local copies to save space.
static NSString *LinkAssets(NSURL *picked, void (^progress)(NSString *)) {
    BOOL scoped = [picked startAccessingSecurityScopedResource];
    BOOL keep = NO;
    @try {
        NSNumber *cloud = nil;
        [picked getResourceValue:&cloud forKey:NSURLIsUbiquitousItemKey error:nil];
        if (cloud.boolValue) return @"Folders in iCloud Drive cannot be used in place. Copy the folder instead.";
        NSURL *source = FindRevisionZero(picked);
        if (!source) return @"Choose the extracted game files: the folder that contains revisions/0.";
        NSString *from = source.URLByResolvingSymlinksInPath.path, *base = picked.URLByResolvingSymlinksInPath.path;
        if (![from hasPrefix:[base stringByAppendingString:@"/"]]) return @"Choose the extracted game files: the folder that contains revisions/0.";
        NSData *bookmark = [picked bookmarkDataWithOptions:0 includingResourceValuesForKeys:nil relativeToURL:nil error:nil];
        if (!bookmark) return @"iOS cannot keep access to this folder. Copy it instead.";
        progress(@"Checking the folder…");
        RecoverImport();
        NSFileManager *files = NSFileManager.defaultManager;
        NSError *error = nil;
        NSString *stageRevisions = [StagePath() stringByAppendingPathComponent:@"revisions"];
        if (![files createDirectoryAtPath:stageRevisions withIntermediateDirectories:YES attributes:nil error:&error]
            || ![files createSymbolicLinkAtPath:[stageRevisions stringByAppendingPathComponent:@"0"] withDestinationPath:from error:&error])
            { DiscardStage(); return error.localizedDescription; }
        NSString *failure = InstallStaged(StagePath(), progress);
        if (failure.length) return failure;
        [NSUserDefaults.standardUserDefaults setObject:bookmark forKey:kInPlaceBookmark];
        [NSUserDefaults.standardUserDefaults setObject:[from substringFromIndex:base.length + 1] forKey:kInPlaceRelative];
        [gInPlaceFolder stopAccessingSecurityScopedResource];
        gInPlaceFolder = picked;
        keep = YES;  // The server reads the folder from now on.
        return @"";
    } @finally {
        if (scoped && !keep) [picked stopAccessingSecurityScopedResource];
    }
}

// True for a .7z or .zip, which the Go bridge unpacks.
static BOOL IsGoArchive(NSString *path) {
    unsigned char magic[6] = {0};
    FILE *file = fopen(path.fileSystemRepresentation, "rb");
    if (!file) return NO;
    size_t n = fread(magic, 1, sizeof magic, file);
    fclose(file);
    return (n == 6 && !memcmp(magic, "7z\xbc\xaf\x27\x1c", 6)) || (n >= 4 && !memcmp(magic, "PK\x03\x04", 4));
}

// Unpacks revision 0 from a .7z or .zip of the resource dump with the shared
// Go code (the same as Android), then installs it like a folder.
static NSString *ImportGoArchive(NSString *path, void (^progress)(NSString *)) {
    RecoverImport();
    __block NSString *result = nil;
    dispatch_semaphore_t finished = dispatch_semaphore_create(0);
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
        result = TakeString(LunarImportArchive((char *)path.fileSystemRepresentation, (char *)StagePath().fileSystemRepresentation));
        dispatch_semaphore_signal(finished);
    });
    LTEstimate estimate = {0};
    while (dispatch_semaphore_wait(finished, dispatch_time(DISPATCH_TIME_NOW, 500 * NSEC_PER_MSEC))) {
        if (gCancelImport) LunarCancelImport();
        NSDictionary *state = [NSJSONSerialization JSONObjectWithData:[TakeString(LunarImportProgress()) dataUsingEncoding:NSUTF8StringEncoding] options:0 error:nil];
        unsigned long long done = [state[@"done"] unsignedLongLongValue], total = [state[@"total"] unsignedLongLongValue];
        unsigned long long files = [state[@"files"] unsignedLongLongValue];
        if (!total) { progress(@"Reading the archive…"); continue; }
        if (!estimate.started) estimate = LTEstimateStart([state[@"totalFiles"] unsignedLongLongValue], total);
        estimate.totalFiles = [state[@"totalFiles"] doubleValue]; estimate.totalBytes = total;
        progress(LTProgressText(@"Unpacking", &estimate, files, done));
    }
    if (result.length) { DiscardStage(); return result; }
    return InstallStaged(StagePath(), progress);
}

// Copies a user-chosen folder or archive into the app. Every write goes to a
// staging folder; the playable files are replaced only after a complete copy.
static NSString *ImportAssets(NSURL *picked, void (^progress)(NSString *)) {
    BOOL scoped = [picked startAccessingSecurityScopedResource];
    NSFileManager *files = NSFileManager.defaultManager;
    @try {
        NSNumber *isFolder = nil;
        [picked getResourceValue:&isFolder forKey:NSURLIsDirectoryKey error:nil];
        if (!isFolder.boolValue) {
            if (IsGoArchive(picked.path)) return ImportGoArchive(picked.path, progress);
            NSArray<NSString *> *parts = ArchiveParts(picked.path);
            if (!parts) return @"Choose the extracted game files folder, or the .7z or .zip of the resource dump.";
            unsigned long long total = 0;
            for (NSString *part in parts) total += FileSize(part);
            if (FreeSpace() < total + 1000000000ULL)
                return [NSString stringWithFormat:@"Not enough free space. Unpacking needs about %@ free.", LTByteText(total + 1000000000ULL)];
            RecoverImport();
            [files createDirectoryAtPath:StagePath() withIntermediateDirectories:YES attributes:nil error:nil];
            NSString *failure = ExtractArchive(parts, StagePath(), progress);
            if (failure.length) { [files removeItemAtPath:StagePath() error:nil]; return failure; }
            NSURL *unpacked = FindAssetsRoot([NSURL fileURLWithPath:StagePath()]);
            if (!unpacked) { [files removeItemAtPath:StagePath() error:nil]; return @"The archive has no catalog. Use an archive of the prepared assets folder."; }
            return InstallStaged(unpacked.path, progress);
        }
        NSURL *source = FindRevisionZero(picked);
        if (!source) return @"Choose the extracted game files: the folder that contains revisions/0.";
        NSString *from = source.URLByResolvingSymlinksInPath.path, *target = [AssetsPath() stringByAppendingPathComponent:@"revisions/0"].stringByResolvingSymlinksInPath;
        if ([from isEqualToString:target]) return @"";  // Already in place, e.g. copied in with Finder.
        if ([from hasPrefix:[target stringByAppendingString:@"/"]] || [target hasPrefix:[from stringByAppendingString:@"/"]])
            return @"Choose a folder outside the game's own files.";
        RecoverImport();
        NSError *error = nil;
        if (![files createDirectoryAtPath:StagePath() withIntermediateDirectories:YES attributes:nil error:&error]) return error.localizedDescription;
        // Files already in NieR's Documents (copied in with Finder or the Files
        // app) are moved instead of copied: instant, and no second 21 GB.
        NSString *documents = [gServerRoot.stringByResolvingSymlinksInPath stringByAppendingString:@"/"];
        if ([from hasPrefix:documents] && ![[from substringFromIndex:documents.length] hasPrefix:@"."]) {
            if (FileSize([from stringByAppendingPathComponent:@"list.bin"]) == 0 && FileSize([from stringByAppendingPathComponent:@"ios/list.bin"]) == 0)
                { DiscardStage(); return @"The folder has no catalog. Choose the folder that contains revisions/0."; }
            NSString *aliases = CheckSelfContained(from);
            if (aliases.length) { DiscardStage(); return aliases; }
            progress(@"Moving the game files…");
            NSString *revisionStage = [StagePath() stringByAppendingPathComponent:@"revisions/0"];
            [files createDirectoryAtPath:revisionStage.stringByDeletingLastPathComponent withIntermediateDirectories:YES attributes:nil error:nil];
            if (![files moveItemAtPath:from toPath:revisionStage error:&error]) { DiscardStage(); return error.localizedDescription; }
            gMovedFrom = from;
            return InstallStaged(StagePath(), progress);
        }
        // List everything first, so the copy can show how much is left.
        __block NSError *walkError = nil;
        NSDirectoryEnumerator *walk = [files enumeratorAtURL:source includingPropertiesForKeys:@[NSURLIsDirectoryKey, NSURLFileSizeKey]
            options:0 errorHandler:^BOOL(NSURL *url, NSError *failure) { walkError = failure; return NO; }];
        NSUInteger base = source.URLByStandardizingPath.pathComponents.count;
        NSMutableArray<NSURL *> *items = [NSMutableArray array];
        NSMutableArray<NSString *> *relatives = [NSMutableArray array];
        NSMutableArray<NSNumber *> *sizes = [NSMutableArray array];  // -1 for folders
        unsigned long long total = 0;
        CFAbsoluteTime reported = 0;
        for (NSURL *url in walk) {
            if (gCancelImport) { [files removeItemAtPath:StagePath() error:nil]; return @"Import cancelled. Your previous files were kept."; }
            NSArray *parts = url.URLByStandardizingPath.pathComponents;
            if (parts.count <= base) continue;
            NSNumber *directory = nil, *size = nil;
            [url getResourceValue:&directory forKey:NSURLIsDirectoryKey error:nil];
            [url getResourceValue:&size forKey:NSURLFileSizeKey error:nil];
            [items addObject:url];
            [relatives addObject:[NSString pathWithComponents:[parts subarrayWithRange:NSMakeRange(base, parts.count - base)]]];
            [sizes addObject:directory.boolValue ? @(-1) : @(size.longLongValue)];
            if (!directory.boolValue) total += size.unsignedLongLongValue;
            if (CFAbsoluteTimeGetCurrent() - reported > 0.5) {
                reported = CFAbsoluteTimeGetCurrent();
                progress([NSString stringWithFormat:@"Reading the folder… %lu files · %@", (unsigned long)items.count, LTByteText(total)]);
            }
        }
        if (walkError) { [files removeItemAtPath:StagePath() error:nil]; return [@"Cannot read the folder: " stringByAppendingString:walkError.localizedDescription]; }
        if (FreeSpace() < total + 1000000000ULL)
            { [files removeItemAtPath:StagePath() error:nil]; return [NSString stringWithFormat:@"Not enough free space. Copying needs about %@ free.", LTByteText(total + 1000000000ULL)]; }
        NSString *revisionStage = [StagePath() stringByAppendingPathComponent:@"revisions/0"];
        if (![files createDirectoryAtPath:revisionStage withIntermediateDirectories:YES attributes:nil error:&error])
            { [files removeItemAtPath:StagePath() error:nil]; return error.localizedDescription; }
        unsigned long long bytes = 0, copied = 0, fileCount = 0;
        for (NSNumber *size in sizes) if (size.longLongValue >= 0) fileCount++;
        LTEstimate estimate = LTEstimateStart(fileCount, total);
        reported = 0;
        for (NSUInteger i = 0; i < items.count; i++) {
            if (gCancelImport) { [files removeItemAtPath:StagePath() error:nil]; return @"Import cancelled. Your previous files were kept."; }
            NSString *destination = [revisionStage stringByAppendingPathComponent:relatives[i]];
            long long size = sizes[i].longLongValue;
            BOOL ok = size < 0
                ? [files createDirectoryAtPath:destination withIntermediateDirectories:YES attributes:nil error:&error]
                : [files copyItemAtPath:items[i].path toPath:destination error:&error];
            if (!ok) { [files removeItemAtPath:StagePath() error:nil]; return [@"Import failed: " stringByAppendingString:error.localizedDescription]; }
            if (size >= 0) { bytes += (unsigned long long)size; copied++; }
            if (CFAbsoluteTimeGetCurrent() - reported > 0.5) {
                reported = CFAbsoluteTimeGetCurrent();
                progress(LTProgressText(@"Copying", &estimate, copied, bytes));
            }
        }
        return InstallStaged(StagePath(), progress);
    } @finally {
        if (scoped) [picked stopAccessingSecurityScopedResource];
    }
}

#pragma mark - Setup screen

@interface LTLauncherViewController : UIViewController <UIDocumentPickerDelegate>
@property(nonatomic, strong) UILabel *files, *server, *detail;
@property(nonatomic, strong) UIButton *choose, *cancel, *check, *back, *more, *quit;
@property(nonatomic) NSInteger pickerMode;  // 0 folder to copy, 1 master data, 2 export, 3 save backup, 4 folder to use in place, 5 archive
@property(nonatomic, strong) UIActivityIndicatorView *spinner;
@property(nonatomic, strong) UIProgressView *bar;
@end

static UIColor *Ink(void) { return [UIColor colorWithRed:0.19 green:0.21 blue:0.19 alpha:1]; }
static UIColor *Muted(void) { return [UIColor colorWithRed:0.42 green:0.43 blue:0.39 alpha:1]; }
static UIColor *Green(void) { return [UIColor colorWithRed:0.33 green:0.40 blue:0.33 alpha:1]; }

@implementation LTLauncherViewController
- (UILabel *)label:(NSString *)text size:(CGFloat)size color:(UIColor *)color bold:(BOOL)bold {
    UILabel *label = [UILabel new];
    label.text = text;
    label.numberOfLines = 0;
    label.textColor = color;
    label.font = bold ? [UIFont boldSystemFontOfSize:size] : [UIFont systemFontOfSize:size];
    label.adjustsFontForContentSizeCategory = YES;
    return label;
}
- (UIView *)card:(NSInteger)number title:(NSString *)title status:(UILabel *)status accessory:(UIView *)accessory {
    UIView *card = [UIView new];
    card.backgroundColor = UIColor.whiteColor;
    card.layer.cornerRadius = 20;
    UILabel *badge = [self label:@(number).stringValue size:18 color:Green() bold:YES];
    badge.textAlignment = NSTextAlignmentCenter;
    badge.backgroundColor = [UIColor colorWithRed:0.93 green:0.94 blue:0.91 alpha:1];
    badge.layer.cornerRadius = 20;
    badge.clipsToBounds = YES;
    UIStackView *text = [[UIStackView alloc] initWithArrangedSubviews:@[[self label:title size:18 color:Ink() bold:YES], status]];
    text.axis = UILayoutConstraintAxisVertical;
    text.spacing = 4;
    UIStackView *row = [[UIStackView alloc] initWithArrangedSubviews:accessory ? @[badge, text, accessory] : @[badge, text]];
    [text setContentHuggingPriority:UILayoutPriorityDefaultLow forAxis:UILayoutConstraintAxisHorizontal];
    row.spacing = 16;
    row.alignment = UIStackViewAlignmentCenter;
    row.translatesAutoresizingMaskIntoConstraints = NO;
    [card addSubview:row];
    [NSLayoutConstraint activateConstraints:@[
        [badge.widthAnchor constraintEqualToConstant:40], [badge.heightAnchor constraintEqualToConstant:40],
        [row.leadingAnchor constraintEqualToAnchor:card.leadingAnchor constant:18],
        [row.trailingAnchor constraintEqualToAnchor:card.trailingAnchor constant:-18],
        [row.topAnchor constraintEqualToAnchor:card.topAnchor constant:18],
        [row.bottomAnchor constraintEqualToAnchor:card.bottomAnchor constant:-18],
    ]];
    return card;
}
- (UIButton *)button:(NSString *)title primary:(BOOL)primary action:(SEL)action {
    UIButton *button = [UIButton buttonWithType:UIButtonTypeSystem];
    [button setTitle:title forState:UIControlStateNormal];
    button.titleLabel.font = [UIFont boldSystemFontOfSize:17];
    [button setTitleColor:primary ? UIColor.whiteColor : Green() forState:UIControlStateNormal];
    button.backgroundColor = primary ? Green() : [UIColor colorWithRed:0.93 green:0.94 blue:0.91 alpha:1];
    button.layer.cornerRadius = 16;
    [button.heightAnchor constraintGreaterThanOrEqualToConstant:52].active = YES;
    [button addTarget:self action:action forControlEvents:UIControlEventTouchUpInside];
    return button;
}
- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [UIColor colorWithRed:0.96 green:0.95 blue:0.91 alpha:1];
    self.files = [self label:@"" size:14 color:Muted() bold:NO];
    self.server = [self label:@"" size:14 color:Muted() bold:NO];
    self.detail = [self label:@"" size:14 color:Muted() bold:NO];
    UILabel *title = [self label:@"Lunar Tear" size:30 color:Ink() bold:NO];
    title.font = [UIFont fontWithName:@"Georgia" size:30] ?: title.font;
    // Like Android: a small Choose / Change button inside the Game files card.
    self.choose = [UIButton buttonWithType:UIButtonTypeSystem];
    [self.choose setTitle:@"Choose" forState:UIControlStateNormal];
    self.choose.titleLabel.font = [UIFont systemFontOfSize:14 weight:UIFontWeightMedium];
    [self.choose setTitleColor:Green() forState:UIControlStateNormal];
    self.choose.backgroundColor = [UIColor colorWithRed:0.93 green:0.94 blue:0.91 alpha:1];
    self.choose.layer.cornerRadius = 12;
    self.choose.contentEdgeInsets = UIEdgeInsetsMake(0, 14, 0, 14);
    self.choose.accessibilityLabel = @"Choose game files";
    [self.choose.heightAnchor constraintEqualToConstant:48].active = YES;
    [self.choose setContentCompressionResistancePriority:UILayoutPriorityRequired forAxis:UILayoutConstraintAxisHorizontal];
    [self.choose setContentHuggingPriority:UILayoutPriorityRequired forAxis:UILayoutConstraintAxisHorizontal];
    [self.choose addTarget:self action:@selector(chooseOrCancel) forControlEvents:UIControlEventTouchUpInside];
    self.cancel = [self button:@"Cancel import" primary:YES action:@selector(chooseOrCancel)];
    self.check = [self button:@"Check again" primary:NO action:@selector(retry)];
    self.back = [self button:@"Back to game" primary:YES action:@selector(close)];
    self.quit = [self button:@"Close game" primary:YES action:@selector(quitGame)];
    self.more = [UIButton buttonWithType:UIButtonTypeSystem];
    [self.more setTitle:@"⋮" forState:UIControlStateNormal];
    self.more.titleLabel.font = [UIFont systemFontOfSize:30];
    [self.more setTitleColor:Ink() forState:UIControlStateNormal];
    self.more.accessibilityLabel = @"More options";
    self.more.showsMenuAsPrimaryAction = YES;
    [self.more.widthAnchor constraintEqualToConstant:48].active = YES;
    [self.more.heightAnchor constraintEqualToConstant:48].active = YES;
    UIStackView *header = [[UIStackView alloc] initWithArrangedSubviews:@[title, self.more]];
    header.alignment = UIStackViewAlignmentCenter;
    self.spinner = [[UIActivityIndicatorView alloc] initWithActivityIndicatorStyle:UIActivityIndicatorViewStyleMedium];
    self.spinner.hidesWhenStopped = YES;
    self.bar = [[UIProgressView alloc] initWithProgressViewStyle:UIProgressViewStyleDefault];
    self.bar.progressTintColor = Green();
    self.bar.trackTintColor = [UIColor colorWithRed:0.86 green:0.87 blue:0.83 alpha:1];
    [self.bar.heightAnchor constraintEqualToConstant:8].active = YES;
    self.bar.layer.cornerRadius = 4;
    self.bar.clipsToBounds = YES;
    self.bar.hidden = YES;
    UIStackView *stack = [[UIStackView alloc] initWithArrangedSubviews:@[
        header, [self card:1 title:@"Game files" status:self.files accessory:self.choose],
        [self card:2 title:@"Server" status:self.server accessory:nil],
        self.detail, self.bar, self.spinner, self.back, self.quit, self.cancel, self.check]];
    stack.axis = UILayoutConstraintAxisVertical;
    stack.spacing = 14;
    [stack setCustomSpacing:24 afterView:header];
    stack.translatesAutoresizingMaskIntoConstraints = NO;
    UIScrollView *scroll = [UIScrollView new];
    scroll.translatesAutoresizingMaskIntoConstraints = NO;
    [self.view addSubview:scroll];
    [scroll addSubview:stack];
    UILayoutGuide *safe = self.view.safeAreaLayoutGuide;
    // Fill the screen up to a readable maximum. This must beat the labels'
    // compression resistance, or the cards collapse to a narrow column.
    NSLayoutConstraint *width = [stack.widthAnchor constraintEqualToAnchor:scroll.frameLayoutGuide.widthAnchor constant:-48];
    width.priority = UILayoutPriorityRequired - 1;
    [stack.widthAnchor constraintLessThanOrEqualToAnchor:scroll.frameLayoutGuide.widthAnchor constant:-48].active = YES;
    [NSLayoutConstraint activateConstraints:@[
        [scroll.leadingAnchor constraintEqualToAnchor:safe.leadingAnchor], [scroll.trailingAnchor constraintEqualToAnchor:safe.trailingAnchor],
        [scroll.topAnchor constraintEqualToAnchor:safe.topAnchor], [scroll.bottomAnchor constraintEqualToAnchor:safe.bottomAnchor],
        [stack.topAnchor constraintEqualToAnchor:scroll.contentLayoutGuide.topAnchor constant:24],
        [stack.bottomAnchor constraintEqualToAnchor:scroll.contentLayoutGuide.bottomAnchor constant:-24],
        [stack.centerXAnchor constraintEqualToAnchor:scroll.centerXAnchor], width,
        [stack.widthAnchor constraintLessThanOrEqualToConstant:520],
    ]];
    [self refresh];
}
- (void)refresh {
    BOOL catalog = HasCatalog(), master = FileSize(MasterPath()) > 0;
    self.files.text = gImporting ? @"Importing…" : catalog && master ? @"Ready" : catalog ? @"Master data missing" : @"Choose your game files";
    [self.choose setTitle:catalog ? @"Change" : @"Choose" forState:UIControlStateNormal];
    self.check.enabled = !gImporting;
    BOOL measured = gImporting && gImportFraction >= 0;
    self.bar.hidden = !measured;
    if (measured) [self.bar setProgress:(float)gImportFraction animated:YES];
    self.spinner.alpha = measured ? 0 : 1;  // The bar shows progress instead.
    self.check.alpha = gImporting ? .45 : 1;
    NSDictionary *status = Status();
    NSString *state = status[@"state"];
    BOOL running = [state isEqual:@"running"];
    self.server.text = gToolsOpen ? @"Stopped for Tools" : gRestartNeeded ? @"Stopped · restart the game"
        : running ? @"Running" : [state isEqual:@"starting"] ? @"Starting…" : catalog ? @"Not running" : @"Waiting for files";
    self.back.hidden = !running || gImporting;
    self.quit.hidden = !gRestartNeeded;
    self.check.hidden = running || gRestartNeeded || gToolsOpen;
    self.choose.hidden = gImporting || gRestartNeeded || gToolsOpen;
    self.cancel.hidden = !gImporting;
    self.more.menu = [self optionsMenu:running];
    NSString *device = UIDevice.currentDevice.model;  // "iPhone" or "iPad"
    self.detail.text = gMessage.length ? gMessage : [NSString stringWithFormat:
        @"Choose the resource dump's .7z, or an extracted folder to copy or use in place, from Files, iCloud Drive or a USB drive. "
        @"Copying needs about 25 GB free. You can also drag a prepared assets folder onto NieR in Finder (your %@ › Files), then tap Check again.", device];
    if (running && !gMessage.length) self.detail.text = @"The server is running on this device. Tap Back to game to keep playing.";
    if (gRestartNeeded && !gMessage.length)
        self.detail.text = @"Your changes are saved. The game must restart to load them: tap Close game, then open NieR again.";
}
- (UIMenu *)optionsMenu:(BOOL)running {
    BOOL idle = !gImporting && !gToolsOpen;
    __weak typeof(self) weakSelf = self;
    UIAction *(^item)(NSString *, NSString *, BOOL, void (^)(void)) = ^UIAction *(NSString *title, NSString *icon, BOOL enabled, void (^handler)(void)) {
        UIAction *action = [UIAction actionWithTitle:title image:[UIImage systemImageNamed:icon] identifier:nil handler:^(UIAction *a) { handler(); }];
        if (!enabled) action.attributes = UIMenuElementAttributesDisabled;
        return action;
    };
    UIAction *tools = LTToolsAvailable()
        ? item(@"Tools", @"wrench.and.screwdriver", idle && HasCatalog() && !self.spinner.isAnimating, ^{ [weakSelf confirmTools]; })
        : item(@"Tools (not in this build)", @"wrench.and.screwdriver", NO, ^{});
    UIAction *server = gRestartNeeded ? item(@"Start server", @"play.circle", NO, ^{}) : running
        ? item(@"Stop server", @"stop.circle", idle, ^{ [weakSelf stopServer]; })
        : item(@"Start server", @"play.circle", idle && HasCatalog(), ^{ [weakSelf retry]; });
    UIAction *master = item(@"Import master data", @"square.and.arrow.down", idle && !gRestartNeeded, ^{ [weakSelf pick:1]; });
    UIAction *restore = item(@"Import save backup", @"tray.and.arrow.down", idle, ^{ [weakSelf confirmSaveImport]; });
    UIAction *backup = item(@"Export save backup", @"square.and.arrow.up", idle && FileSize([gSaves stringByAppendingPathComponent:@"game.db"]) > 0, ^{ [weakSelf exportSaves]; });
    UIAction *log = item(@"Server log", @"doc.text", YES, ^{ [weakSelf showLog]; });
    UIAction *check = item(@"Check server", @"checkmark.shield", running, ^{ [weakSelf checkServer]; });
    UIAction *settings = item(@"App settings", @"gear", YES, ^{
        [UIApplication.sharedApplication openURL:[NSURL URLWithString:UIApplicationOpenSettingsURLString] options:@{} completionHandler:nil];
    });
    UIAction *help = item(@"Help", @"questionmark.circle", YES, ^{ [weakSelf help]; });
    UIAction *about = item(@"About", @"info.circle", YES, ^{ [weakSelf about]; });
    return [UIMenu menuWithTitle:@"" children:@[
        [UIMenu menuWithTitle:@"" image:nil identifier:nil options:UIMenuOptionsDisplayInline children:@[tools, server]],
        [UIMenu menuWithTitle:@"" image:nil identifier:nil options:UIMenuOptionsDisplayInline children:@[master, backup, restore]],
        [UIMenu menuWithTitle:@"" image:nil identifier:nil options:UIMenuOptionsDisplayInline children:@[check, log, settings, help, about]],
    ]];
}
- (void)alert:(NSString *)title message:(NSString *)message {
    UIAlertController *alert = [UIAlertController alertControllerWithTitle:title message:message preferredStyle:UIAlertControllerStyleAlert];
    [alert addAction:[UIAlertAction actionWithTitle:@"Close" style:UIAlertActionStyleCancel handler:nil]];
    [self presentViewController:alert animated:YES completion:nil];
}
- (void)help {
    [self alert:@"Help" message:
        @"Choose the game files once: the resource dump's .7z, or an extracted folder to copy or use in place. Master data is already included. The server starts with the game and runs only on this device.\n\n"
        @"Three-finger double-tap during play opens this screen. Export a save backup before deleting the app.\n\n"
        @"Import save backup (in ⋮) restores a backup from this or another device, including Android.\n\n"
        @"Tools (in ⋮) edits your saves and unlocks content. It stops the server while open, and the game restarts afterwards to load the changes.\n\n"
        @"Stopping the server, importing master data or exporting saves disconnects the game. Close NieR from the app switcher and open it again to continue."];
}
- (void)about {
    UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"Lunar Tear"
        message:@"Offline companion · 0.1.0\nAll-in-one build by veritr1x\ngithub.com/veritr1x\n\nBased on Lunar Tear by Walter-Sparrow.\nMIT License · Copyright 2026 Ilya Groshev."
        preferredStyle:UIAlertControllerStyleAlert];
    [alert addAction:[UIAlertAction actionWithTitle:@"Open GitHub" style:UIAlertActionStyleDefault handler:^(UIAlertAction *a) {
        [UIApplication.sharedApplication openURL:[NSURL URLWithString:@"https://github.com/veritr1x"] options:@{} completionHandler:nil];
    }]];
    [alert addAction:[UIAlertAction actionWithTitle:@"Close" style:UIAlertActionStyleCancel handler:nil]];
    [self presentViewController:alert animated:YES completion:nil];
}
- (void)busy:(NSString *)message work:(NSString *(^)(void))work done:(void (^)(NSString *error))done {
    gMessage = message;
    [self.spinner startAnimating];
    [self refresh];
    dispatch_async(gQueue, ^{
        NSString *error = work();
        dispatch_async(dispatch_get_main_queue(), ^{
            [self.spinner stopAnimating];
            gMessage = error.length ? error : @"";
            [self refresh];
            if (done) done(error);
        });
    });
}
- (void)confirmTools {
    UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"Open Tools?"
        message:@"Tools stops the game server so it can edit your saves and content. When you close Tools, the game restarts to load your changes."
        preferredStyle:UIAlertControllerStyleAlert];
    [alert addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];
    [alert addAction:[UIAlertAction actionWithTitle:@"Open Tools" style:UIAlertActionStyleDefault handler:^(UIAlertAction *a) { [self openTools]; }]];
    [self presentViewController:alert animated:YES completion:nil];
}
- (void)openTools {
    gToolsOpen = YES;
    __block NSString *url = nil, *token = nil;
    NSString *original = [[NSBundle bundleForClass:self.class] pathForResource:@"original-master" ofType:@"bin.e"];
    [self busy:@"Stopping the game server…" work:^NSString *{
        LunarStop();
        NSString *error = TakeString(LunarPrepareBackup((char *)gSaves.fileSystemRepresentation));
        if (error.length) return error;
        return LTToolsStart(gSaves, gServerRoot, ToolsRoot(), original, &url, &token, ^(NSString *text) {
            dispatch_async(dispatch_get_main_queue(), ^{ gMessage = text; [self refresh]; });
        });
    } done:^(NSString *error) {
        if (error.length) {
            // Nothing was edited, so the game can carry on.
            gToolsOpen = NO;
            gMessage = [@"Tools could not open: " stringByAppendingString:error];
            dispatch_async(gQueue, ^{ StartServer(); dispatch_async(dispatch_get_main_queue(), ^{ [self refresh]; }); });
            [self refresh];
            return;
        }
        gMessage = @"Tools is open.";
        [self refresh];
        __weak typeof(self) weakSelf = self;
        [self presentViewController:LTToolsBrowser(url, token, ^{ [weakSelf closeTools]; }) animated:YES completion:nil];
    }];
}
- (void)closeTools {
    [self dismissViewControllerAnimated:YES completion:nil];
    [self busy:@"Closing Tools…" work:^NSString *{ return LTToolsStop(); } done:^(NSString *error) {
        gToolsOpen = NO;
        gRestartNeeded = YES;
        gMessage = error.length ? [@"Tools closed with an error: " stringByAppendingString:error] : @"";
        [self refresh];
    }];
}
- (void)quitGame {
    // Restarting is the only way to drop the game's copy of the old save.
    exit(0);
}
- (void)stopServer {
    [self busy:@"Stopping the server and saving progress…" work:^NSString *{ LunarStop(); return @""; } done:^(NSString *error) {
        gMessage = @"Server stopped. Your saves are stored on this device.";
        [self refresh];
    }];
}
- (void)pick:(NSInteger)mode {
    self.pickerMode = mode;
    NSArray<UTType *> *types = mode == 0 || mode == 4 ? @[UTTypeFolder] : mode == 5 ? @[UTTypeArchive, UTTypeData]
        : mode == 3 ? @[UTTypeZIP, UTTypeData] : @[UTTypeItem];
    UIDocumentPickerViewController *picker = [[UIDocumentPickerViewController alloc] initForOpeningContentTypes:types];
    picker.delegate = self;
    picker.allowsMultipleSelection = NO;
    [self presentViewController:picker animated:YES completion:nil];
}
- (void)importMaster:(NSURL *)picked {
    [self busy:@"Importing master data…" work:^NSString *{
        BOOL scoped = [picked startAccessingSecurityScopedResource];
        NSString *pending = [MasterPath() stringByAppendingString:@".import"];
        NSFileManager *files = NSFileManager.defaultManager;
        [files removeItemAtPath:pending error:nil];
        NSError *error = nil;
        BOOL copied = [files copyItemAtURL:picked toURL:[NSURL fileURLWithPath:pending] error:&error];
        if (scoped) [picked stopAccessingSecurityScopedResource];
        if (!copied) return error.localizedDescription;
        unsigned long long size = FileSize(pending);
        if (size < 1000000 || size > 32000000) { [files removeItemAtPath:pending error:nil]; return @"Choose the 20240404193219.bin.e master-data file."; }
        LunarStop();
        [files createDirectoryAtPath:MasterPath().stringByDeletingLastPathComponent withIntermediateDirectories:YES attributes:nil error:nil];
        if (rename(pending.fileSystemRepresentation, MasterPath().fileSystemRepresentation) != 0) return @"Cannot replace master data";
        return StartServer();
    } done:^(NSString *error) {
        if (!error.length) { gMessage = @"Master data imported. Close NieR from the app switcher and open it again to load it."; [self refresh]; }
    }];
}
- (void)confirmSaveImport {
    UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"Import a save backup?"
        message:@"This replaces the save on this device with the backup you choose: a ZIP from Export save backup (on iPhone, iPad or Android), or a game.db file. "
                @"Your current save is kept in Files › NieR › saves.before-import. The game restarts afterwards."
        preferredStyle:UIAlertControllerStyleAlert];
    [alert addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];
    [alert addAction:[UIAlertAction actionWithTitle:@"Choose backup" style:UIAlertActionStyleDefault handler:^(UIAlertAction *a) { [self pick:3]; }]];
    [self presentViewController:alert animated:YES completion:nil];
}
- (void)importSave:(NSURL *)picked {
    BOOL wasRunning = Running();
    [self busy:@"Importing the save…" work:^NSString *{
        // Copy it first: the picked file may live in iCloud or on a USB drive.
        NSString *copy = [NSTemporaryDirectory() stringByAppendingPathComponent:@"save-import"];
        NSFileManager *files = NSFileManager.defaultManager;
        [files removeItemAtPath:copy error:nil];
        BOOL scoped = [picked startAccessingSecurityScopedResource];
        NSError *error = nil;
        BOOL copied = [files copyItemAtURL:picked toURL:[NSURL fileURLWithPath:copy] error:&error];
        if (scoped) [picked stopAccessingSecurityScopedResource];
        if (!copied) return error.localizedDescription;
        LunarStop();  // Saves must be closed before they are replaced.
        NSString *failure = TakeString(LunarImportSaves((char *)gSaves.fileSystemRepresentation, (char *)copy.fileSystemRepresentation));
        [files removeItemAtPath:copy error:nil];
        return failure;
    } done:^(NSString *error) {
        if (error.length) {
            // Nothing was replaced, so the game can carry on.
            if (wasRunning) dispatch_async(gQueue, ^{ StartServer(); dispatch_async(dispatch_get_main_queue(), ^{ [self refresh]; }); });
            return;
        }
        // The game still holds the old player's data until it restarts.
        gRestartNeeded = YES;
        gMessage = @"Save imported. Tap Close game, then open NieR again to play it. Your previous save is in Files › NieR › saves.before-import.";
        [self refresh];
    }];
}
- (void)exportSaves {
    __block NSURL *archive = nil;
    BOOL wasRunning = Running();
    [self busy:@"Preparing your save backup…" work:^NSString *{
        LunarStop();  // Flush the databases before copying them.
        NSString *error = TakeString(LunarPrepareBackup((char *)gSaves.fileSystemRepresentation));
        NSFileManager *files = NSFileManager.defaultManager;
        NSDateFormatter *format = [NSDateFormatter new];
        format.dateFormat = @"yyyyMMdd-HHmm";
        format.locale = [NSLocale localeWithLocaleIdentifier:@"en_US_POSIX"];
        NSString *name = [@"lunar-tear-saves-" stringByAppendingString:[format stringFromDate:NSDate.date]];
        NSString *folder = [NSTemporaryDirectory() stringByAppendingPathComponent:name];
        if (!error.length) {
            [files removeItemAtPath:folder error:nil];
            [files createDirectoryAtPath:folder withIntermediateDirectories:YES attributes:nil error:nil];
            for (NSString *file in @[@"game.db", @"auth.db", @"auth.key"]) {
                NSString *source = [gSaves stringByAppendingPathComponent:file];
                if ([files fileExistsAtPath:source]) [files copyItemAtPath:source toPath:[folder stringByAppendingPathComponent:file] error:nil];
            }
            [@"Lunar Tear local saves. Keep game.db, auth.db and auth.key together. Contains account credentials; keep this backup private.\n"
                writeToFile:[folder stringByAppendingPathComponent:@"README.txt"] atomically:YES encoding:NSUTF8StringEncoding error:nil];
            // Reading a folder "for uploading" makes Foundation produce a ZIP of it.
            __block NSString *zipError = nil;
            NSError *coordination = nil;
            [[NSFileCoordinator new] coordinateReadingItemAtURL:[NSURL fileURLWithPath:folder] options:NSFileCoordinatorReadingForUploading error:&coordination byAccessor:^(NSURL *zipped) {
                NSURL *target = [NSURL fileURLWithPath:[folder stringByAppendingPathExtension:@"zip"]];
                [files removeItemAtURL:target error:nil];
                NSError *copyError = nil;
                if ([files copyItemAtURL:zipped toURL:target error:&copyError]) archive = target;
                else zipError = copyError.localizedDescription;
            }];
            [files removeItemAtPath:folder error:nil];
            error = coordination.localizedDescription ?: zipError ?: @"";
        }
        NSString *restart = wasRunning ? StartServer() : @"";
        return error.length ? error : restart;
    } done:^(NSString *error) {
        if (error.length || !archive) return;
        self.pickerMode = 2;
        UIDocumentPickerViewController *picker = [[UIDocumentPickerViewController alloc] initForExportingURLs:@[archive] asCopy:YES];
        picker.delegate = self;
        [self presentViewController:picker animated:YES completion:nil];
    }];
}
- (void)close {
    gMessage = @"";
    gWindow.hidden = YES;
    gWindow = nil;
}
- (void)retry {
    self.check.enabled = NO;
    [self.spinner startAnimating];
    gMessage = @"Starting the server…";
    [self refresh];
    dispatch_async(gQueue, ^{
        NSString *error = StartServer();
        dispatch_async(dispatch_get_main_queue(), ^{
            [self.spinner stopAnimating];
            self.check.enabled = YES;
            gMessage = error.length ? error : @"";
            [self refresh];
            if (!error.length) [self dismiss];
        });
    });
}
- (void)chooseOrCancel {
    if (gImporting) { gCancelImport = YES; gMessage = @"Cancelling…"; [self refresh]; return; }
    // The same three choices as on Android.
    UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"Choose the game files"
        message:@"Copying keeps the game working if the folder is moved later and needs about 21 GB free. In place needs no space, but the folder must stay where it is (and its drive connected). The archive is the resource dump's .7z or a .zip of it."
        preferredStyle:UIAlertControllerStyleAlert];
    [alert addAction:[UIAlertAction actionWithTitle:@"Extracted folder: copy into NieR" style:UIAlertActionStyleDefault handler:^(UIAlertAction *a) { [self pick:0]; }]];
    [alert addAction:[UIAlertAction actionWithTitle:@"Extracted folder: use in place" style:UIAlertActionStyleDefault handler:^(UIAlertAction *a) { [self pick:4]; }]];
    [alert addAction:[UIAlertAction actionWithTitle:@"Archive (.7z or .zip)" style:UIAlertActionStyleDefault handler:^(UIAlertAction *a) { [self pick:5]; }]];
    [alert addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];
    [self presentViewController:alert animated:YES completion:nil];
}
- (void)documentPicker:(UIDocumentPickerViewController *)controller didPickDocumentsAtURLs:(NSArray<NSURL *> *)urls {
    NSURL *picked = urls.firstObject;
    if (self.pickerMode == 2) {
        gMessage = @"Backup saved. Keep it somewhere safe.";
        [self refresh];
        return;
    }
    if (self.pickerMode == 1) { if (picked) [self importMaster:picked]; return; }
    if (self.pickerMode == 3) { if (picked) [self importSave:picked]; return; }
    if (!picked || gImporting) return;
    // A folder already in NieR's own files is moved in either case, which is instant.
    NSString *documents = [gServerRoot.stringByResolvingSymlinksInPath stringByAppendingString:@"/"];
    BOOL link = self.pickerMode == 4 && ![picked.URLByResolvingSymlinksInPath.path hasPrefix:documents];
    [self startImport:picked link:link];
}
- (void)startImport:(NSURL *)picked link:(BOOL)link {
    if (gImporting) return;
    gImporting = YES;
    gCancelImport = NO;
    gImportFraction = -1;
    gMessage = @"Keep NieR open until the import finishes.";
    [self.spinner startAnimating];
    [self refresh];
    UIApplication *app = UIApplication.sharedApplication;
    app.idleTimerDisabled = YES;  // A 20 GB copy takes several minutes.
    __block UIBackgroundTaskIdentifier task = [app beginBackgroundTaskWithName:@"Lunar Tear import" expirationHandler:^{
        gCancelImport = YES;
        [app endBackgroundTask:task];
        task = UIBackgroundTaskInvalid;
    }];
    dispatch_async(gQueue, ^{
        void (^progress)(NSString *) = ^(NSString *text) {
            dispatch_async(dispatch_get_main_queue(), ^{ gMessage = text; [self refresh]; });
        };
        NSString *error = link ? LinkAssets(picked, progress) : ImportAssets(picked, progress);
        if (!error.length) error = StartServer();
        dispatch_async(dispatch_get_main_queue(), ^{
            gImporting = NO;
            app.idleTimerDisabled = NO;
            if (task != UIBackgroundTaskInvalid) { [app endBackgroundTask:task]; task = UIBackgroundTaskInvalid; }
            [self.spinner stopAnimating];
            gMessage = error;
            [self refresh];
            if (!error.length) [self dismiss];
        });
    });
}
- (void)dismiss {
    // Unity's first attempts may have failed while files were missing.
    // Closing and reopening the game retries cleanly from the title screen.
    UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"Server running"
        message:@"If the game shows a connection error, close NieR from the app switcher and open it again." preferredStyle:UIAlertControllerStyleAlert];
    [alert addAction:[UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleDefault handler:^(UIAlertAction *action) {
        gWindow.hidden = YES;
        gWindow = nil;
    }]];
    [self presentViewController:alert animated:YES completion:nil];
}
// Shows whether the game can reach this server on each of its ports.
- (void)checkServer {
    dispatch_async(dispatch_get_global_queue(QOS_CLASS_USER_INITIATED, 0), ^{
        NSString *report = TakeString(LunarSelfTest());
        NSDictionary *r = [NSJSONSerialization JSONObjectWithData:[report dataUsingEncoding:NSUTF8StringEncoding] options:0 error:nil];
        NSMutableString *text = [NSMutableString string];
        for (NSDictionary *c in r[@"checks"]) {
            [text appendFormat:@"%@ %@ · port %@\n", [c[@"ok"] boolValue] ? @"✓" : @"✗", c[@"name"], c[@"port"]];
            if (![c[@"ok"] boolValue]) [text appendFormat:@"   %@\n", c[@"detail"]];
        }
        dispatch_async(dispatch_get_main_queue(), ^{
            [self alert:[r[@"ok"] boolValue] ? @"Server is reachable" : @"Server check failed"
                message:[text stringByTrimmingCharactersInSet:NSCharacterSet.whitespaceAndNewlineCharacterSet]];
        });
    });
}
- (void)showLog {
    NSString *logs = Status()[@"logs"];
    UIViewController *viewer = [UIViewController new];
    UITextView *text = [UITextView new];
    text.editable = NO;
    text.font = [UIFont monospacedSystemFontOfSize:12 weight:UIFontWeightRegular];
    text.text = logs.length ? logs : @"No server log yet.";
    viewer.view = text;
    viewer.title = @"Server log";
    UINavigationController *navigation = [[UINavigationController alloc] initWithRootViewController:viewer];
    viewer.navigationItem.rightBarButtonItem = [[UIBarButtonItem alloc] initWithBarButtonSystemItem:UIBarButtonSystemItemDone target:self action:@selector(closeLog)];
    [self presentViewController:navigation animated:YES completion:nil];
}
- (void)closeLog { [self dismissViewControllerAnimated:YES completion:nil]; }
@end

static void ShowLauncher(void) {
    if (gWindow) { [(LTLauncherViewController *)gWindow.rootViewController refresh]; return; }
    UIWindow *window = nil;
    if (@available(iOS 13.0, *)) {
        for (UIScene *scene in UIApplication.sharedApplication.connectedScenes)
            if ([scene isKindOfClass:UIWindowScene.class]) { window = [[UIWindow alloc] initWithWindowScene:(UIWindowScene *)scene]; break; }
    }
    if (!window) window = [[UIWindow alloc] initWithFrame:UIScreen.mainScreen.bounds];
    window.windowLevel = UIWindowLevelAlert + 1;
    window.rootViewController = [LTLauncherViewController new];
    window.hidden = NO;
    gWindow = window;
}

#pragma mark - Opening the launcher during play

// Three-finger double-tap anywhere opens the launcher. It observes touches
// without cancelling them, so the game still receives every touch.
@interface LTGestureTarget : NSObject
@end
@implementation LTGestureTarget
- (void)open:(UITapGestureRecognizer *)gesture {
    if (gesture.state == UIGestureRecognizerStateRecognized) { gMessage = @""; ShowLauncher(); }
}
@end
static LTGestureTarget *gGestureTarget;

static void InstallGesture(void) {
    if (!gGestureTarget) gGestureTarget = [LTGestureTarget new];
    NSMutableArray<UIWindow *> *windows = [NSMutableArray array];
    for (UIScene *scene in UIApplication.sharedApplication.connectedScenes)
        if ([scene isKindOfClass:UIWindowScene.class]) [windows addObjectsFromArray:((UIWindowScene *)scene).windows];
    for (UIWindow *window in windows) {
        if (window == gWindow) continue;
        BOOL present = NO;
        for (UIGestureRecognizer *existing in window.gestureRecognizers) present = present || [existing.name isEqual:@"LunarTearOpen"];
        if (present) continue;
        UITapGestureRecognizer *tap = [[UITapGestureRecognizer alloc] initWithTarget:gGestureTarget action:@selector(open:)];
        tap.name = @"LunarTearOpen";
        tap.numberOfTouchesRequired = 3;
        tap.numberOfTapsRequired = 2;
        tap.cancelsTouchesInView = NO;
        tap.delaysTouchesBegan = NO;
        tap.delaysTouchesEnded = NO;
        [window addGestureRecognizer:tap];
    }
}

#pragma mark - Lifecycle

static void EnteredBackground(void) {
    // The sign-in page opens in Safari, which sends the game to the background.
    // Ask iOS for the short extension it allows so that page can still load.
    UIApplication *app = UIApplication.sharedApplication;
    if (gBackgroundTask != UIBackgroundTaskInvalid) return;
    gBackgroundTask = [app beginBackgroundTaskWithName:@"Lunar Tear sign-in" expirationHandler:^{
        [app endBackgroundTask:gBackgroundTask];
        gBackgroundTask = UIBackgroundTaskInvalid;
    }];
}
static void BecameActive(void) {
    if (gBackgroundTask != UIBackgroundTaskInvalid) {
        [UIApplication.sharedApplication endBackgroundTask:gBackgroundTask];
        gBackgroundTask = UIBackgroundTaskInvalid;
    }
    InstallGesture();
    if (gImporting) { ShowLauncher(); return; }  // Always show how far the import has got.
    if (gToolsOpen || gRestartNeeded || Running()) { if (gWindow) [(LTLauncherViewController *)gWindow.rootViewController refresh]; return; }
    // iOS can reclaim listening sockets during a long suspension; restart then.
    dispatch_async(gQueue, ^{
        NSString *error = HasCatalog() ? StartServer() : @"";
        dispatch_async(dispatch_get_main_queue(), ^{
            if (error.length || !HasCatalog()) { gMessage = error; ShowLauncher(); }
        });
    });
}

__attribute__((constructor)) static void LunarTearLoad(void) {
    @autoreleasepool {
        gQueue = dispatch_queue_create("org.lunartear.server", DISPATCH_QUEUE_SERIAL);
        gBackgroundTask = UIBackgroundTaskInvalid;
        gServerRoot = Documents();
        gSaves = [gServerRoot stringByAppendingPathComponent:@"saves"];
        RecoverImport();
        // Automation only: developer tools can launch with this variable to run
        // the same import the folder picker uses. Players cannot set it.
        const char *importFrom = getenv("LUNAR_IMPORT_FROM");
        if (importFrom && *importFrom) {
            NSString *source = [NSString stringWithUTF8String:importFrom];
            if (!source.isAbsolutePath) source = [gServerRoot stringByAppendingPathComponent:source];  // Relative to Documents.
            BOOL removeSource = getenv("LUNAR_IMPORT_DELETE") != NULL;
            gImporting = YES;
            dispatch_async(gQueue, ^{
                NSString *(*import)(NSURL *, void (^)(NSString *)) = getenv("LUNAR_IMPORT_LINK") ? LinkAssets : ImportAssets;
                NSString *error = import([NSURL fileURLWithPath:source], ^(NSString *text) {
                    NSLog(@"[LunarTear] %@", text);
                    dispatch_async(dispatch_get_main_queue(), ^{
                        gMessage = text;
                        if (gWindow) [(LTLauncherViewController *)gWindow.rootViewController refresh];
                    });
                });
                NSLog(@"[LunarTear] import result: %@", error.length ? error : @"ok");
                // Automation copies archives into Documents; remove them once unpacked.
                if (!error.length && removeSource)
                    for (NSString *part in ArchiveParts(source) ?: (IsGoArchive(source) ? @[source] : @[])) [NSFileManager.defaultManager removeItemAtPath:part error:nil];
                gImporting = NO;
                gMessage = error.length ? error : @"";
                dispatch_async(dispatch_get_main_queue(), ^{ if (gWindow) [(LTLauncherViewController *)gWindow.rootViewController refresh]; });
            });
        }
        lt_rebind_image_symbols("UnityFramework.framework/UnityFramework", kReachability, sizeof(kReachability) / sizeof(kReachability[0]));
        // Start before Unity boots. Wait briefly so its first request finds the
        // server, but never long enough to trip the launch watchdog.
        dispatch_semaphore_t started = dispatch_semaphore_create(0);
        const char *saveFrom = getenv("LUNAR_IMPORT_SAVE");
        NSString *saveSource = saveFrom && *saveFrom ? [NSString stringWithUTF8String:saveFrom] : nil;
        dispatch_async(gQueue, ^{
            // Automation only, like LUNAR_IMPORT_FROM: import a save backup
            // before the server starts. Go must not be called on this thread.
            if (saveSource) {
                NSString *source = saveSource.isAbsolutePath ? saveSource : [gServerRoot stringByAppendingPathComponent:saveSource];
                NSString *result = TakeString(LunarImportSaves((char *)gSaves.fileSystemRepresentation, (char *)source.fileSystemRepresentation));
                NSLog(@"[LunarTear] save import result: %@", result.length ? result : @"ok");
            }
            NSString *error = StartServer();
            gMessage = error;
            dispatch_semaphore_signal(started);
            // An import at launch may have left the launcher open; show the result.
            dispatch_async(dispatch_get_main_queue(), ^{ if (gWindow) [(LTLauncherViewController *)gWindow.rootViewController refresh]; });
        });
        dispatch_semaphore_wait(started, dispatch_time(DISPATCH_TIME_NOW, 8 * NSEC_PER_SEC));
        NSNotificationCenter *center = NSNotificationCenter.defaultCenter;
        [center addObserverForName:UIApplicationDidBecomeActiveNotification object:nil queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *n) { BecameActive(); }];
        [center addObserverForName:UIApplicationDidEnterBackgroundNotification object:nil queue:NSOperationQueue.mainQueue usingBlock:^(NSNotification *n) { EnteredBackground(); }];
        [center addObserverForName:UIApplicationWillTerminateNotification object:nil queue:nil usingBlock:^(NSNotification *n) { LunarStop(); }];
    }
}
