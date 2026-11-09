// See LTText.h. Every rule here is BunkerText.java's (and bunker_text.py's); keep them together.
#import "LTText.h"
#include "LTPlurals.h"

static const unichar kStart = 0x1f, kEnd = 0x1e, kSep = 0x1d;  // Said.java's markers
static NSString *const kSlot = @"⁣⁣";  // stands where around:'s slot goes while the text is formatted

@interface LTField : NSObject
@property (nonatomic, copy) NSString *name, *spec, *conversion;
@end
@implementation LTField
@end

/** The text's pieces, literal strings (doubled braces undone) and LTFields; nil where Python's format would
 *  raise ValueError (a single "}", an unclosed "{", a bad conversion). */
static NSArray *Parse(NSString *text) {
    NSMutableArray *parts = [NSMutableArray array];
    NSMutableString *literal = [NSMutableString string];
    NSUInteger i = 0, length = text.length;
    while (i < length) {
        unichar c = [text characterAtIndex:i];
        if (c == '}') {
            if (i + 1 < length && [text characterAtIndex:i + 1] == '}') { [literal appendString:@"}"]; i += 2; continue; }
            return nil;
        }
        if (c != '{') { [literal appendFormat:@"%C", c]; i++; continue; }
        if (i + 1 < length && [text characterAtIndex:i + 1] == '{') { [literal appendString:@"{"]; i += 2; continue; }
        NSUInteger depth = 1, j = i + 1;
        while (j < length && depth > 0) {
            unichar d = [text characterAtIndex:j];
            if (d == '{') depth++;
            else if (d == '}') depth--;
            if (depth > 0) j++;
        }
        if (depth > 0) return nil;
        NSString *inside = [text substringWithRange:NSMakeRange(i + 1, j - i - 1)];
        NSUInteger k = 0;
        BOOL bracket = NO;
        for (; k < inside.length; k++) {
            unichar d = [inside characterAtIndex:k];
            if (d == '[') bracket = YES;
            else if (d == ']') bracket = NO;
            else if (!bracket && (d == ':' || d == '!')) break;
        }
        LTField *field = [LTField new];
        field.name = [inside substringToIndex:k];
        field.conversion = @"";
        field.spec = @"";
        if (k < inside.length && [inside characterAtIndex:k] == '!') {
            if (k + 1 >= inside.length) return nil;
            field.conversion = [inside substringWithRange:NSMakeRange(k + 1, 1)];
            k += 2;
            if (k < inside.length && [inside characterAtIndex:k] != ':') return nil;
        }
        if (k < inside.length) field.spec = [inside substringFromIndex:k + 1];
        [parts addObject:[literal copy]];
        [literal setString:@""];
        [parts addObject:field];
        i = j + 1;
    }
    [parts addObject:[literal copy]];
    return parts;
}

/** text with each {name} filled; nil where Python would raise (a position, a spec, a conversion, a value missing). */
static NSString *Format(NSString *text, NSDictionary *params) {
    NSArray *parts = Parse(text);
    if (!parts) return nil;
    NSMutableString *out = [NSMutableString string];
    for (id part in parts) {
        if ([part isKindOfClass:[NSString class]]) { [out appendString:part]; continue; }
        LTField *field = part;
        id value = params[field.name];
        if (!field.name.length || field.spec.length || field.conversion.length || !value) return nil;
        [out appendString:[value description]];
    }
    return out;
}

static NSMutableDictionary *Params(NSArray *pairs) {
    NSMutableDictionary *params = [NSMutableDictionary dictionary];
    for (NSUInteger i = 0; i + 1 < pairs.count; i += 2) params[[pairs[i] description]] = pairs[i + 1];
    return params;
}

@implementation LTText {
    NSDictionary<NSString *, NSString *> *_english, *_translation;
    NSString *(^_numbers)(double);
}

- (instancetype)initWithEnglish:(NSDictionary *)english translation:(NSDictionary *)translation
                       language:(NSString *)language numbers:(NSString *(^)(double))numbers {
    if ((self = [super init])) {
        _english = english;
        NSMutableDictionary *kept = [NSMutableDictionary dictionary];
        [translation enumerateKeysAndObjectsUsingBlock:^(id key, id value, BOOL *stop) {
            if ([key isKindOfClass:[NSString class]] && [value isKindOfClass:[NSString class]] && [value length]) kept[key] = value;
        }];
        _translation = kept;
        _language = [language copy] ?: @"en";
        _numbers = [numbers copy];
    }
    return self;
}

+ (NSArray<NSString *> *)fields:(NSString *)text {
    NSArray *parts = Parse(text);
    if (!parts) return nil;
    NSMutableArray *found = [NSMutableArray array];
    for (id part in parts)
        if ([part isKindOfClass:[LTField class]]) {
            LTField *f = part;
            [found addObject:[NSString stringWithFormat:@"%@|%@|%@", f.name, f.spec, f.conversion]];
        }
    return [found sortedArrayUsingSelector:@selector(compare:)];
}

static BOOL SameFields(NSArray *a, NSArray *b) { return a == b || (a && b && [a isEqualToArray:b]); }

- (NSString *)t:(NSString *)key pairs:(NSArray *)pairs { return [self t:key fallback:key pairs:pairs]; }

- (NSString *)t:(NSString *)key fallback:(NSString *)fallback pairs:(NSArray *)pairs {
    NSString *base = _english[key];
    if (![base isKindOfClass:[NSString class]]) return fallback;
    NSDictionary *params = Params(pairs);
    NSString *translated = _translation[key];
    if (translated && SameFields([LTText fields:translated], [LTText fields:base])) {
        NSString *done = Format(translated, params);
        if (done) return done;
    }
    return Format(base, params) ?: base;
}

/** The translation's forms of key when they cover every category the language uses for whole numbers and take
 *  only placeholders the English .other has (a form may leave out {n}); otherwise nil (English is used). */
- (NSDictionary<NSString *, NSString *> *)formsOf:(NSString *)key {
    NSString *other = _english[[key stringByAppendingString:@".other"]];
    if (!other || !_translation.count) return nil;
    NSArray *allowedList = [LTText fields:other];
    if (!allowedList) return nil;
    NSSet *allowed = [NSSet setWithArray:allowedList];
    NSMutableDictionary *forms = [NSMutableDictionary dictionary];
    const char *needed[6];
    int count = lt_plural_categories(_language.UTF8String, needed);
    for (int i = 0; i < count; i++) {
        NSString *category = @(needed[i]);
        NSString *text = _translation[[NSString stringWithFormat:@"%@.%@", key, category]];
        NSArray *found = text ? [LTText fields:text] : nil;
        if (!found || ![[NSSet setWithArray:found] isSubsetOfSet:allowed]) return nil;
        forms[category] = text;
    }
    for (NSString *category in @[@"zero", @"one", @"two", @"few", @"many", @"other"]) {  // extra forms are kept too
        NSString *text = _translation[[NSString stringWithFormat:@"%@.%@", key, category]];
        if (forms[category] || !text) continue;
        NSArray *found = [LTText fields:text];
        if (found && [[NSSet setWithArray:found] isSubsetOfSet:allowed]) forms[category] = text;
    }
    return forms;
}

- (NSString *)count:(NSString *)key n:(long long)n pairs:(NSArray *)pairs {
    NSMutableDictionary *params = Params(pairs);
    if (!params[@"n"]) params[@"n"] = _numbers((double)n);
    NSDictionary *forms = [self formsOf:key];
    NSString *form = forms[@(lt_plural_category(_language.UTF8String, n))];
    if (form) {
        NSString *done = Format(form, params);
        if (done) return done;
    }
    NSString *base = _english[[key stringByAppendingString:n == 1 ? @".one" : @".other"]];
    if (!base) return [key stringByAppendingString:@".other"];
    return Format(base, params) ?: base;
}

- (NSArray<NSString *> *)around:(NSString *)key slot:(NSString *)slot pairs:(NSArray *)pairs {
    NSArray *withSlot = [pairs arrayByAddingObjectsFromArray:@[slot, kSlot]];
    NSString *text = [self t:key pairs:withSlot];
    if ([text componentsSeparatedByString:kSlot].count != 2) {
        NSString *base = _english[key] ?: key;
        text = Format(base, Params(withSlot)) ?: base;
    }
    NSRange at = [text rangeOfString:kSlot];
    if (at.location == NSNotFound) return @[text, @""];
    return @[[text substringToIndex:at.location], [text substringFromIndex:NSMaxRange(at)]];
}

- (NSString *)number:(double)value { return _numbers(value); }

- (NSString *)size:(long long)bytes {
    NSString *unit = bytes >= 1000000000LL ? @"gb" : bytes >= 1000000LL ? @"mb" : @"kb";
    double value = bytes / ([unit isEqual:@"gb"] ? 1e9 : [unit isEqual:@"mb"] ? 1e6 : 1e3);
    value = MAX(1, value < 100 ? round(value * 10) / 10.0 : round(value));
    return [self t:[@"launcher.size." stringByAppendingString:unit] pairs:@[@"n", _numbers(value)]];
}

+ (NSString *(^)(double))numbersFor:(NSString *)language {
    NSNumberFormatter *format = [NSNumberFormatter new];
    NSString *identifier = [NSLocale canonicalLocaleIdentifierFromString:language.length ? language : @"en"];
    format.locale = [NSLocale localeWithLocaleIdentifier:[identifier stringByAppendingString:@"@numbers=latn"]];
    format.numberStyle = NSNumberFormatterDecimalStyle;
    format.maximumFractionDigits = 3;
    format.roundingMode = NSNumberFormatterRoundHalfUp;  // as Intl.NumberFormat and bunker_numbers
    return ^NSString *(double value) { return [format stringFromNumber:@(value)] ?: [NSString stringWithFormat:@"%g", value]; };
}

#pragma mark - Said

static NSString *Clean(NSString *s) {
    NSCharacterSet *marks = [NSCharacterSet characterSetWithCharactersInString:[NSString stringWithFormat:@"%C%C%C", kStart, kEnd, kSep]];
    return [[s componentsSeparatedByCharactersInSet:marks] componentsJoinedByString:@""];
}

static NSString *Make(NSString *key, NSString *n, NSArray *pairs) {
    NSMutableString *out = [NSMutableString stringWithFormat:@"%C%@%C%@", kStart, Clean(key), kSep, n];
    for (id part in pairs) [out appendFormat:@"%C%@", kSep, Clean([part description])];
    [out appendFormat:@"%C", kEnd];
    return out;
}

+ (NSString *)saidText:(NSString *)key pairs:(NSArray *)pairs { return Make(key, @"", pairs); }
+ (NSString *)saidCount:(NSString *)key n:(long long)n pairs:(NSArray *)pairs { return Make(key, @(n).stringValue, pairs); }

- (NSString *)said:(NSString *)said {
    if (!said) return @"";
    NSMutableString *out = [NSMutableString string];
    NSUInteger i = 0;
    NSString *start = [NSString stringWithFormat:@"%C", kStart], *end = [NSString stringWithFormat:@"%C", kEnd];
    while (i < said.length) {
        NSRange open = [said rangeOfString:start options:0 range:NSMakeRange(i, said.length - i)];
        if (open.location == NSNotFound) { [out appendString:[said substringFromIndex:i]]; break; }
        [out appendString:[said substringWithRange:NSMakeRange(i, open.location - i)]];
        NSRange close = [said rangeOfString:end options:0 range:NSMakeRange(open.location, said.length - open.location)];
        if (close.location == NSNotFound) { [out appendString:Clean([said substringFromIndex:open.location])]; break; }
        NSString *reference = [said substringWithRange:NSMakeRange(open.location + 1, close.location - open.location - 1)];
        NSArray *parts = [reference componentsSeparatedByString:[NSString stringWithFormat:@"%C", kSep]];
        if (parts.count >= 2) {
            NSArray *pairs = [parts subarrayWithRange:NSMakeRange(2, parts.count - 2)];
            NSString *n = parts[1];
            if (!n.length) [out appendString:[self t:parts[0] pairs:pairs]];
            else {
                NSScanner *scan = [NSScanner scannerWithString:n];
                long long count;
                if ([scan scanLongLong:&count] && scan.isAtEnd) [out appendString:[self count:parts[0] n:count pairs:pairs]];
            }
        }
        i = NSMaxRange(close);
    }
    return out;
}

@end
