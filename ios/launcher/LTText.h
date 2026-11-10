// Bunker's own words for the iOS launcher: the English catalogue (translations/bunker/en.json) with a pack's
// translations over it, as bunker_text.py (Pod Programs, the Archive) and BunkerText.java (Android) do.
// Foundation only: ios/tools/test_lt_text.py runs it on macOS against android/tools/bunker_text_cases.json.
#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

@interface LTText : NSObject

/** english: the catalogue; translation: the pack's bunker section (non-strings and empty texts are ignored);
 *  language: the pack's BCP 47 tag (plural rules, LTPlurals.c); numbers: how a number is written. */
- (instancetype)initWithEnglish:(NSDictionary *)english translation:(nullable NSDictionary *)translation
                       language:(NSString *)language numbers:(NSString *(^)(double value))numbers;
@property (nonatomic, readonly) NSString *language;

/** key's text with these values (name, value, name, value…); the key itself when the catalogue lacks it. A
 *  translation is used only when its placeholders are exactly the English's. */
- (NSString *)t:(NSString *)key pairs:(NSArray *)pairs;
/** As t:, with what to show when the catalogue lacks key. */
- (NSString *)t:(NSString *)key fallback:(NSString *)fallback pairs:(NSArray *)pairs;
/** key counted n times ({n} written the language's way); a translation missing a form gives English throughout. */
- (NSString *)count:(NSString *)key n:(long long)n pairs:(NSArray *)pairs;
/** A sentence around a control or link: its text before and after {slot}. */
- (NSArray<NSString *> *)around:(NSString *)key slot:(NSString *)slot pairs:(NSArray *)pairs;
- (NSString *)number:(double)value;
/** A size as the launchers write every size ("8.2 GB", "350 MB", "1 KB"), as BunkerText.size. */
- (NSString *)size:(long long)bytes;

/** A reference to key with these values, put in words later (said:), in the language of that moment.
 *  The same encoding as Said.java. */
+ (NSString *)saidText:(NSString *)key pairs:(NSArray *)pairs;
+ (NSString *)saidCount:(NSString *)key n:(long long)n pairs:(NSArray *)pairs;
/** said with each reference put in words by these texts; any other message as it is; nil gives "". */
- (NSString *)said:(nullable NSString *)said;

/** How language writes numbers: CLDR via NSNumberFormatter, Latin digits, up to three decimals. */
+ (NSString *(^)(double value))numbersFor:(NSString *)language;
/** The placeholders in text as "name|spec|conversion", sorted; nil when text is not a valid format. */
+ (nullable NSArray<NSString *> *)fields:(NSString *)text;

@end

NS_ASSUME_NONNULL_END
