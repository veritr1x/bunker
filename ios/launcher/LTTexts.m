// See LTTexts.h; Android's Texts.java does the same.
#import "LTTexts.h"

static const unsigned long long kMaxPack = 8 * 1024 * 1024;  // a loaded pack is untrusted: larger ones are ignored

static NSString *gCatalogue, *gServerRoot;
static NSDictionary *gEnglish;
static LTText *gText, *gEnglishOnly;
static NSString *gLanguage = @"en", *gStamp;
static NSLocale *gLocale;
static NSInteger gGeneration;
static CFAbsoluteTime gChecked;

static NSString *PackPath(void) { return gServerRoot ? [gServerRoot stringByAppendingPathComponent:@"translation/active.json"] : nil; }

static NSString *StampOf(NSString *path) {
    NSDictionary *attributes = path ? [NSFileManager.defaultManager attributesOfItemAtPath:path error:nil] : nil;
    return attributes ? [NSString stringWithFormat:@"%llu:%f", attributes.fileSize, attributes.fileModificationDate.timeIntervalSince1970] : @"none";
}

/** A language tag as bunker_language.CODE accepts it ("pt-BR", "zh-Hans"). */
static BOOL GoodTag(NSString *tag) {
    static NSRegularExpression *code;
    static dispatch_once_t once;
    dispatch_once(&once, ^{ code = [NSRegularExpression regularExpressionWithPattern:@"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8}){0,3}$" options:0 error:nil]; });
    return [tag isKindOfClass:[NSString class]] && [code numberOfMatchesInString:tag options:0 range:NSMakeRange(0, tag.length)] == 1;
}

static void Load(void) {
    if (!gEnglish) {
        NSData *data = gCatalogue ? [NSData dataWithContentsOfFile:gCatalogue] : nil;
        id all = data ? [NSJSONSerialization JSONObjectWithData:data options:0 error:nil] : nil;
        gEnglish = [all isKindOfClass:[NSDictionary class]] ? all : @{};
        if (!gEnglish.count) NSLog(@"[LunarTear] Bunker's catalogue is missing from the framework");
    }
    NSString *path = PackPath();
    gStamp = StampOf(path);
    gChecked = CFAbsoluteTimeGetCurrent();
    gGeneration++;
    NSDictionary *words = @{};
    NSString *tag = @"en";
    NSDictionary *attributes = path ? [NSFileManager.defaultManager attributesOfItemAtPath:path error:nil] : nil;
    if (attributes && attributes.fileSize <= kMaxPack) {
        NSFileHandle *file = [NSFileHandle fileHandleForReadingAtPath:path];
        NSData *data = [file readDataUpToLength:kMaxPack + 1 error:nil];
        [file closeFile];
        if (data.length > kMaxPack) data = nil;  // it grew past the limit since it was looked at
        id pack = data ? [NSJSONSerialization JSONObjectWithData:data options:0 error:nil] : nil;
        id bunker = [pack isKindOfClass:[NSDictionary class]] ? pack[@"bunker"] : nil;
        if ([bunker isKindOfClass:[NSDictionary class]]) words = bunker;  // LTText drops non-strings and empty texts
        id said = [pack isKindOfClass:[NSDictionary class]] ? pack[@"language"] : nil;
        if ([words count] && GoodTag(said)) tag = said;
    }
    gLanguage = tag;
    gLocale = [NSLocale localeWithLocaleIdentifier:tag];
    gText = [[LTText alloc] initWithEnglish:gEnglish translation:words language:tag numbers:[LTText numbersFor:tag]];
}

static LTText *Current(void) {
    @synchronized ([LTText class]) {
        if (!gText) Load();
        else if (CFAbsoluteTimeGetCurrent() - gChecked >= 1) {
            gChecked = CFAbsoluteTimeGetCurrent();
            if (![StampOf(PackPath()) isEqualToString:gStamp]) Load();
        }
        return gText;
    }
}

void LTTextsUse(NSString *catalogue, NSString *serverRoot) {
    @synchronized ([LTText class]) {
        gCatalogue = [catalogue copy];
        gServerRoot = [serverRoot copy];
        gEnglish = nil;
        gEnglishOnly = nil;
        Load();
    }
}

NSString *LTT(NSString *key, NSArray *pairs) { return [Current() t:key pairs:pairs]; }
NSString *LTTFallback(NSString *key, NSString *fallback, NSArray *pairs) { return [Current() t:key fallback:fallback pairs:pairs]; }
NSString *LTTCount(NSString *key, long long n, NSArray *pairs) { return [Current() count:key n:n pairs:pairs]; }
NSString *TSaid(NSString *said) { return [Current() said:said]; }
NSString *TNumber(double value) { return [Current() number:value]; }
NSString *TSize(long long bytes) { return [Current() size:bytes]; }

NSString *TInEnglish(NSString *said) {
    Current();
    @synchronized ([LTText class]) {
        if (!gEnglishOnly) gEnglishOnly = [[LTText alloc] initWithEnglish:gEnglish ?: @{} translation:nil language:@"en" numbers:[LTText numbersFor:@"en"]];
        return [gEnglishOnly said:said];
    }
}

NSString *TUpper(NSString *text) {
    Current();
    @synchronized ([LTText class]) { return [text uppercaseStringWithLocale:gLocale]; }
}

NSString *TLanguage(void) {
    Current();
    @synchronized ([LTText class]) { return gLanguage; }
}

void LTTextsRecheck(void) {
    @synchronized ([LTText class]) { gChecked = 0; }
    Current();
}

NSInteger TGeneration(void) {
    Current();
    @synchronized ([LTText class]) { return gGeneration; }
}
