// The iOS launcher's words: the English catalogue in LunarTear.framework (bunker_en.json, from
// translations/bunker/en.json) with the pack Pod Programs activated over it (<server root>/translation/active.json,
// the file Pod Programs and the Archive read). One language for Bunker: the phone's own is never used.
// Foundation only, so ios/tools/test_lt_text.py runs it on macOS. Safe from any thread.
#import <Foundation/Foundation.h>
#import "LTText.h"

/** Where the catalogue and the server folder are (the launcher, once it knows its Documents folder). */
void LTTextsUse(NSString *catalogue, NSString *serverRoot);

NSString *LTT(NSString *key, NSArray *pairs);
NSString *LTTCount(NSString *key, long long n, NSArray *pairs);
NSString *LTTFallback(NSString *key, NSString *fallback, NSArray *pairs);
/** key's text with these values: T(@"launcher.x", @"name", value…). */
#define T(key, ...) LTT(key, @[__VA_ARGS__])
#define TCount(key, count, ...) LTTCount(key, count, @[__VA_ARGS__])
/** A reference put in words when shown (TSaid): for words kept and drawn later. */
#define Said(key, ...) [LTText saidText:key pairs:@[__VA_ARGS__]]
#define SaidCount(key, count, ...) [LTText saidCount:key n:count pairs:@[__VA_ARGS__]]

/** Words set earlier (Said) in the language of now; any other message as it is. */
NSString *TSaid(NSString *said);
/** As TSaid, in English whatever the pack: for logs. */
NSString *TInEnglish(NSString *said);
/** text in capitals, the pack's language's way ("İ" in Turkish). */
NSString *TUpper(NSString *text);
NSString *TNumber(double value);
NSString *TSize(long long bytes);
/** The language of the words (BCP 47), "en" without a pack. */
NSString *TLanguage(void);
/** Changes each time the pack is read again (a language chosen in Pod Programs): a screen built at another
 *  number builds itself again. Any lookup notices a new pack (the file is looked at at most once a second). */
NSInteger TGeneration(void);
/** Looks at the pack file now (after Pod Programs may have chosen a language), not within the second. */
void LTTextsRecheck(void);
