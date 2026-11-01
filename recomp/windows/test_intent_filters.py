import pathlib,unittest
from intent_filters import parse_main_activity_filters
class MainFilters(unittest.TestCase):
    prefix='E: manifest (line=1)\n  E: application (line=2)\n'
    activity='''    E: activity (line=3)
      A: android:name=".Main"
      E: intent-filter (line=4)
        E: action (line=5)
          A: android:name="android.intent.action.MAIN"
        E: category (line=6)
          A: android:name="android.intent.category.LAUNCHER"
'''
    def test_main_scope_defaults_and_qualification(self):
        text=self.prefix+self.activity+'    E: receiver (line=7)\n      E: intent-filter (line=8)\n        E: action (line=9)\n          A: android:name="android.intent.action.MAIN"\n'
        self.assertEqual(parse_main_activity_filters(text,'app'),[{'component':'app.Main','enabled':True,'categories':['android.intent.category.LAUNCHER']}])
    def test_explicit_disabled_and_unknown_main_constructs(self):
        text=self.prefix+self.activity.replace('      A: android:name=".Main"','      A: android:enabled=(type 0x12)0x0\n      A: android:name="Main"')
        self.assertFalse(parse_main_activity_filters(text,'app')[0]['enabled'])
        for activity in (self.activity.replace('E: activity ','E: activity-alias '),self.activity+'        E: data (line=7)\n          A: android:scheme="custom"\n'):
            with self.assertRaises(ValueError):parse_main_activity_filters(self.prefix+activity,'app')
        with self.assertRaises(ValueError):parse_main_activity_filters(self.prefix+self.activity.replace('".Main"','@0x7f010001'),'app')
    def test_actual_apk_if_available(self):
        source=pathlib.Path(__file__).resolve().parent.parent/'work/apk-application-manifest.txt'
        if not source.is_file():self.skipTest('Actual AAPT manifest is optional')
        rows=parse_main_activity_filters(source.read_text(),'com.square_enix.android_googleplay.nierspww')
        self.assertEqual(rows,[{'component':'com.google.firebase.MessagingUnityPlayerActivity','enabled':True,'categories':['android.intent.category.LAUNCHER','android.intent.category.LEANBACK_LAUNCHER']}])
if __name__=='__main__':unittest.main()
