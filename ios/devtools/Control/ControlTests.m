// Drives the installed game for device testing from the Mac.
// LUNAR_ACTION: launch | tap | swipe | type | home | gesture | press.
// Coordinates are 0-1 fractions. press taps the element labelled LUNAR_TEXT.
#import <XCTest/XCTest.h>

@interface ControlTests : XCTestCase
@end

@implementation ControlTests
- (NSString *)value:(NSString *)name {
    return NSProcessInfo.processInfo.environment[name] ?: @"";
}
- (XCUICoordinate *)point:(XCUIApplication *)app x:(NSString *)x y:(NSString *)y {
    return [app coordinateWithNormalizedOffset:CGVectorMake(x.doubleValue, y.doubleValue)];
}
- (void)testAction {
    XCUIApplication *app = [[XCUIApplication alloc] initWithBundleIdentifier:[self value:@"LUNAR_BUNDLE_ID"]];
    NSString *action = [self value:@"LUNAR_ACTION"];
    if ([action isEqualToString:@"home"]) { [XCUIDevice.sharedDevice pressButton:XCUIDeviceButtonHome]; return; }
    if ([action isEqualToString:@"launch"]) { [app launch]; return; }
    [app activate];
    if ([action isEqualToString:@"tap"]) {
        [[self point:app x:[self value:@"LUNAR_X"] y:[self value:@"LUNAR_Y"]] tap];
    } else if ([action isEqualToString:@"swipe"]) {
        XCUICoordinate *from = [self point:app x:[self value:@"LUNAR_X"] y:[self value:@"LUNAR_Y"]];
        XCUICoordinate *to = [self point:app x:[self value:@"LUNAR_X2"] y:[self value:@"LUNAR_Y2"]];
        [from pressForDuration:0.05 thenDragToCoordinate:to];
    } else if ([action isEqualToString:@"gesture"]) {
        // The launcher's three-finger double-tap.
        [app.windows.firstMatch tapWithNumberOfTaps:2 numberOfTouches:3];
    } else if ([action isEqualToString:@"press"]) {
        NSPredicate *label = [NSPredicate predicateWithFormat:@"label == %@", [self value:@"LUNAR_TEXT"]];
        XCUIElement *element = [[app descendantsMatchingType:XCUIElementTypeAny] matchingPredicate:label].firstMatch;
        XCTAssertTrue([element waitForExistenceWithTimeout:10], @"No element labelled %@", [self value:@"LUNAR_TEXT"]);
        [element tap];
    } else if ([action isEqualToString:@"type"]) {
        [app typeText:[self value:@"LUNAR_TEXT"]];
    } else {
        XCTFail(@"Unknown LUNAR_ACTION %@", action);
    }
}
@end
