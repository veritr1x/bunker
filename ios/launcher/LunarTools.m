// Tools on iOS. Python is loaded only when Tools opens, so normal play pays
// nothing for it. The Python side is ios/python/ios_runtime.py.
#import "LunarTools.h"
#import <WebKit/WebKit.h>
#include <dlfcn.h>

#pragma mark - Embedded Python

static struct {
    void (*initialize)(int);
    int (*run)(const char *);
    void *(*releaseLock)(void);
    int (*acquire)(void);
    void (*release)(int);
} gPython;
static BOOL gPythonReady;
static void (^gProgress)(NSString *);
static NSString *gResult;

// Called from Python with ctypes.
__attribute__((visibility("default"))) void LunarToolsReport(const char *message) {
    NSString *text = message ? [NSString stringWithUTF8String:message] : nil;
    if (text && gProgress) gProgress(text);
}
__attribute__((visibility("default"))) void LunarToolsResult(const char *json) {
    gResult = json ? [NSString stringWithUTF8String:json] : nil;
}

static NSString *PythonHome(void) { return [NSBundle.mainBundle.bundlePath stringByAppendingPathComponent:@"python"]; }
static NSString *PythonLibrary(void) { return [NSBundle.mainBundle.privateFrameworksPath stringByAppendingPathComponent:@"Python.framework/Python"]; }

BOOL LTToolsAvailable(void) {
    NSFileManager *files = NSFileManager.defaultManager;
    return [files fileExistsAtPath:PythonLibrary()] && [files fileExistsAtPath:[PythonHome() stringByAppendingPathComponent:@"app/ios_runtime.py"]];
}

static NSString *LoadPython(void) {
    if (gPythonReady) return @"";
    if (!LTToolsAvailable()) return @"This build does not include Tools.";
    void *library = dlopen(PythonLibrary().fileSystemRepresentation, RTLD_NOW | RTLD_GLOBAL);
    if (!library) return [NSString stringWithFormat:@"Cannot load Python: %s", dlerror()];
    gPython.initialize = dlsym(library, "Py_InitializeEx");
    gPython.run = dlsym(library, "PyRun_SimpleString");
    gPython.releaseLock = dlsym(library, "PyEval_SaveThread");
    gPython.acquire = dlsym(library, "PyGILState_Ensure");
    gPython.release = dlsym(library, "PyGILState_Release");
    if (!gPython.initialize || !gPython.run || !gPython.releaseLock || !gPython.acquire || !gPython.release) return @"Python is incomplete";
    NSString *home = PythonHome();
    setenv("PYTHONHOME", home.fileSystemRepresentation, 1);
    // Game text is Japanese and English; read and write files as UTF-8.
    int *utf8 = dlsym(library, "Py_UTF8Mode");
    if (utf8) *utf8 = 1;
    setenv("PYTHONUTF8", "1", 1);
    setenv("LC_CTYPE", "UTF-8", 1);
    setenv("PYTHONDONTWRITEBYTECODE", "1", 1);  // The app bundle is read-only.
    setenv("PYTHONNOUSERSITE", "1", 1);
    gPython.initialize(0);  // 0: leave the game's signal handlers alone.
    // Python finds each compiled module next to sys.executable, the game itself.
    NSDictionary *paths = @{@"executable": NSBundle.mainBundle.executablePath,
                            @"packages": [home stringByAppendingPathComponent:@"app_packages"],
                            @"app": [home stringByAppendingPathComponent:@"app"]};
    NSData *json = [NSJSONSerialization dataWithJSONObject:paths options:0 error:nil];
    NSString *bootstrap = [NSString stringWithFormat:
        @"import base64, json, site, sys\n"
        @"paths = json.loads(base64.b64decode('%@'))\n"
        @"sys.executable = paths['executable']\n"
        @"site.addsitedir(paths['packages'])\n"
        @"sys.path.insert(0, paths['app'])\n", [json base64EncodedStringWithOptions:0]];
    int failed = gPython.run(bootstrap.UTF8String);
    gPython.releaseLock();
    gPythonReady = YES;
    return failed ? @"Python could not find the Tools code" : @"";
}

// Runs one ios_runtime call. Arguments and results travel as JSON. Python
// copies the environment once at startup, so arguments go in the code itself.
static NSDictionary *CallRuntime(NSString *function, NSArray *arguments) {
    NSData *data = [NSJSONSerialization dataWithJSONObject:@{@"function": function, @"arguments": arguments} options:0 error:nil];
    NSString *code = [NSString stringWithFormat:
        @"def _lunar_call(encoded):\n"
        @"    import base64, ctypes, json, traceback\n"
        @"    send = ctypes.CDLL(None).LunarToolsResult\n"
        @"    send.argtypes = [ctypes.c_char_p]\n"
        @"    try:\n"
        @"        call = json.loads(base64.b64decode(encoded))\n"
        @"        import ios_runtime\n"
        @"        value = getattr(ios_runtime, call['function'])(*call['arguments'])\n"
        @"        send(json.dumps({'ok': True, 'value': value}).encode())\n"
        @"    except BaseException as error:\n"
        @"        traceback.print_exc()\n"
        @"        frame = traceback.extract_tb(error.__traceback__)[-1]\n"
        @"        where = ' (%%s:%%d)' %% (frame.filename.rsplit('/', 1)[-1], frame.lineno)\n"
        @"        send(json.dumps({'ok': False, 'error': (str(error) or type(error).__name__) + where}).encode())\n"
        @"_lunar_call('%@')\n", [data base64EncodedStringWithOptions:0]];
    gResult = nil;
    int state = gPython.acquire();
    gPython.run(code.UTF8String);
    gPython.release(state);
    NSDictionary *result = gResult ? [NSJSONSerialization JSONObjectWithData:[gResult dataUsingEncoding:NSUTF8StringEncoding] options:0 error:nil] : nil;
    return result ?: @{@"ok": @NO, @"error": @"Tools did not respond"};
}

NSString *LTToolsStart(NSString *saves, NSString *serverRoot, NSString *toolsRoot, NSString *originalMaster,
                       NSString **url, NSString **token, void (^progress)(NSString *text)) {
    gProgress = progress;
    if (progress) progress(gPythonReady ? @"Opening Tools…" : @"Starting Python…");
    NSString *error = LoadPython();
    if (error.length) { gProgress = nil; return error; }
    [NSFileManager.defaultManager createDirectoryAtPath:toolsRoot withIntermediateDirectories:YES attributes:nil error:nil];
    NSDictionary *result = CallRuntime(@"start", @[saves, serverRoot, toolsRoot, originalMaster ?: @""]);
    gProgress = nil;
    if (![result[@"ok"] boolValue]) return result[@"error"];
    NSDictionary *state = [NSJSONSerialization JSONObjectWithData:[result[@"value"] dataUsingEncoding:NSUTF8StringEncoding] options:0 error:nil];
    *url = state[@"url"];
    *token = state[@"token"];
    return url && token && (*url).length ? @"" : @"Tools could not start";
}

NSString *LTToolsStop(void) {
    if (!gPythonReady) return @"";
    NSDictionary *result = CallRuntime(@"stop", @[]);
    return [result[@"ok"] boolValue] ? @"" : result[@"error"];
}

#pragma mark - Editor browser

@interface LTToolsViewController : UIViewController <WKNavigationDelegate, WKUIDelegate, UIDocumentPickerDelegate>
@property(nonatomic, copy) NSString *origin, *token;
@property(nonatomic, copy) void (^onClose)(void);
@property(nonatomic, strong) WKWebView *web;
@end

@implementation LTToolsViewController
- (void)viewDidLoad {
    [super viewDidLoad];
    self.title = @"Tools";
    self.view.backgroundColor = [UIColor colorWithRed:0.96 green:0.95 blue:0.91 alpha:1];
    self.navigationItem.leftBarButtonItem = [[UIBarButtonItem alloc] initWithTitle:@"Close" style:UIBarButtonItemStyleDone target:self action:@selector(close)];
    WKWebViewConfiguration *configuration = [WKWebViewConfiguration new];
    // Nothing persists between sessions; each session has a new token.
    configuration.websiteDataStore = WKWebsiteDataStore.nonPersistentDataStore;
    self.web = [[WKWebView alloc] initWithFrame:CGRectZero configuration:configuration];
    self.web.navigationDelegate = self;
    self.web.UIDelegate = self;
    self.web.allowsBackForwardNavigationGestures = YES;
    self.web.opaque = NO;
    self.web.backgroundColor = self.view.backgroundColor;
    self.web.translatesAutoresizingMaskIntoConstraints = NO;
    [self.view addSubview:self.web];
    [NSLayoutConstraint activateConstraints:@[
        [self.web.leadingAnchor constraintEqualToAnchor:self.view.leadingAnchor],
        [self.web.trailingAnchor constraintEqualToAnchor:self.view.trailingAnchor],
        [self.web.topAnchor constraintEqualToAnchor:self.view.safeAreaLayoutGuide.topAnchor],
        [self.web.bottomAnchor constraintEqualToAnchor:self.view.bottomAnchor],
    ]];
    NSURL *origin = [NSURL URLWithString:self.origin];
    NSHTTPCookie *cookie = [NSHTTPCookie cookieWithProperties:@{
        NSHTTPCookieName: @"lunar_tools", NSHTTPCookieValue: self.token, NSHTTPCookieDomain: origin.host,
        NSHTTPCookiePath: @"/", @"HttpOnly": @YES, NSHTTPCookieSameSitePolicy: NSHTTPCookieSameSiteStrict}];
    __weak typeof(self) weakSelf = self;
    [configuration.websiteDataStore.httpCookieStore setCookie:cookie completionHandler:^{
        [weakSelf.web loadRequest:[NSURLRequest requestWithURL:[origin URLByAppendingPathComponent:@"/"]]];
    }];
}
- (BOOL)local:(NSURL *)url {
    NSURL *origin = [NSURL URLWithString:self.origin];
    return [url.scheme isEqual:@"http"] && [url.host isEqual:origin.host] && [url.port isEqual:origin.port];
}
- (void)close {
    self.navigationItem.leftBarButtonItem.enabled = NO;
    [self.web stopLoading];
    if (self.onClose) self.onClose();
}
- (void)webView:(WKWebView *)webView decidePolicyForNavigationAction:(WKNavigationAction *)action decisionHandler:(void (^)(WKNavigationActionPolicy))handler {
    // Only the local editors; nothing in Tools links out.
    handler([self local:action.request.URL] || [action.request.URL.absoluteString isEqual:@"about:blank"] ? WKNavigationActionPolicyAllow : WKNavigationActionPolicyCancel);
}
- (void)webView:(WKWebView *)webView decidePolicyForNavigationResponse:(WKNavigationResponse *)response decisionHandler:(void (^)(WKNavigationResponsePolicy))handler {
    NSHTTPURLResponse *http = [response.response isKindOfClass:NSHTTPURLResponse.class] ? (NSHTTPURLResponse *)response.response : nil;
    NSString *disposition = [http valueForHTTPHeaderField:@"Content-Disposition"];
    if (response.isForMainFrame && [disposition.lowercaseString hasPrefix:@"attachment"]) {
        handler(WKNavigationResponsePolicyCancel);
        [self download:response.response.URL name:response.response.suggestedFilename];
        return;
    }
    handler(WKNavigationResponsePolicyAllow);
}
// Fetch the file with the session cookie, then let the player choose where to save it.
- (void)download:(NSURL *)url name:(NSString *)name {
    NSMutableURLRequest *request = [NSMutableURLRequest requestWithURL:url];
    [request setValue:[@"lunar_tools=" stringByAppendingString:self.token] forHTTPHeaderField:@"Cookie"];
    NSURLSessionDownloadTask *task = [NSURLSession.sharedSession downloadTaskWithRequest:request completionHandler:^(NSURL *location, NSURLResponse *response, NSError *error) {
        NSURL *target = nil;
        if (!error && [(NSHTTPURLResponse *)response statusCode] == 200) {
            NSString *folder = [NSTemporaryDirectory() stringByAppendingPathComponent:NSUUID.UUID.UUIDString];
            [NSFileManager.defaultManager createDirectoryAtPath:folder withIntermediateDirectories:YES attributes:nil error:nil];
            target = [NSURL fileURLWithPath:[folder stringByAppendingPathComponent:name.lastPathComponent.length ? name.lastPathComponent : @"download"]];
            if (![NSFileManager.defaultManager moveItemAtURL:location toURL:target error:nil]) target = nil;
        }
        dispatch_async(dispatch_get_main_queue(), ^{
            if (!target) { [self message:@"Export failed" text:error.localizedDescription ?: @"The file could not be prepared."]; return; }
            UIDocumentPickerViewController *picker = [[UIDocumentPickerViewController alloc] initForExportingURLs:@[target] asCopy:YES];
            picker.delegate = self;
            [self presentViewController:picker animated:YES completion:nil];
        });
    }];
    [task resume];
}
- (void)message:(NSString *)title text:(NSString *)text {
    UIAlertController *alert = [UIAlertController alertControllerWithTitle:title message:text preferredStyle:UIAlertControllerStyleAlert];
    [alert addAction:[UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleDefault handler:nil]];
    [self presentViewController:alert animated:YES completion:nil];
}
- (void)webView:(WKWebView *)webView didFailProvisionalNavigation:(WKNavigation *)navigation withError:(NSError *)error {
    if (error.code != NSURLErrorCancelled) [self message:@"Unable to open Tools" text:@"Close Tools and try again."];
}
- (void)webView:(WKWebView *)webView runJavaScriptAlertPanelWithMessage:(NSString *)message initiatedByFrame:(WKFrameInfo *)frame completionHandler:(void (^)(void))handler {
    UIAlertController *alert = [UIAlertController alertControllerWithTitle:nil message:message preferredStyle:UIAlertControllerStyleAlert];
    [alert addAction:[UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleDefault handler:^(UIAlertAction *a) { handler(); }]];
    [self presentViewController:alert animated:YES completion:nil];
}
- (void)webView:(WKWebView *)webView runJavaScriptConfirmPanelWithMessage:(NSString *)message initiatedByFrame:(WKFrameInfo *)frame completionHandler:(void (^)(BOOL))handler {
    UIAlertController *alert = [UIAlertController alertControllerWithTitle:nil message:message preferredStyle:UIAlertControllerStyleAlert];
    [alert addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:^(UIAlertAction *a) { handler(NO); }]];
    [alert addAction:[UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleDefault handler:^(UIAlertAction *a) { handler(YES); }]];
    [self presentViewController:alert animated:YES completion:nil];
}
- (void)webView:(WKWebView *)webView runJavaScriptTextInputPanelWithPrompt:(NSString *)prompt defaultText:(NSString *)text initiatedByFrame:(WKFrameInfo *)frame completionHandler:(void (^)(NSString *))handler {
    UIAlertController *alert = [UIAlertController alertControllerWithTitle:nil message:prompt preferredStyle:UIAlertControllerStyleAlert];
    [alert addTextFieldWithConfigurationHandler:^(UITextField *field) { field.text = text; }];
    [alert addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:^(UIAlertAction *a) { handler(nil); }]];
    [alert addAction:[UIAlertAction actionWithTitle:@"OK" style:UIAlertActionStyleDefault handler:^(UIAlertAction *a) { handler(alert.textFields.firstObject.text); }]];
    [self presentViewController:alert animated:YES completion:nil];
}
@end

UIViewController *LTToolsBrowser(NSString *url, NSString *token, void (^close)(void)) {
    LTToolsViewController *tools = [LTToolsViewController new];
    tools.origin = url;
    tools.token = token;
    tools.onClose = close;
    UINavigationController *navigation = [[UINavigationController alloc] initWithRootViewController:tools];
    navigation.modalPresentationStyle = UIModalPresentationFullScreen;
    navigation.overrideUserInterfaceStyle = UIUserInterfaceStyleLight;  // The editors are light-themed.
    return navigation;
}
