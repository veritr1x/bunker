import json,pathlib,unittest
from application_metadata import parse_application_metadata
class MetadataTests(unittest.TestCase):
    def test_actual_apk_audit_if_available(self):
        root=pathlib.Path(__file__).resolve().parent.parent/'work';manifest=root/'apk-application-manifest.txt';resources=root/'apk-application-resources.txt';audit=root/'windows-unity-bootstrap/java-startup/application-manifest-resolved.json'
        if not all(p.is_file() for p in (manifest,resources,audit)):self.skipTest('Actual APK AAPT audit artifacts are optional')
        found=parse_application_metadata(manifest.read_text(),resources.read_text());expected=json.loads(audit.read_text())
        expected=expected['metadata'] if 'metadata' in expected else expected['application_metadata']
        self.assertEqual(len(found),16)
        # Report only agreement, never SDK credential values embedded in this APK.
        self.assertEqual(found,{key:{'type':item['type'],'value':item['value']} for key,item in expected.items()})
    def test_types_resources_and_scope(self):
        manifest='''    E: application (line=1)
      E: meta-data (line=2)
        A: android:name="text"
        A: android:value=@0x7f010001
      E: meta-data (line=3)
        A: android:name="number"
        A: android:value=@0x7f010002
      E: meta-data (line=4)
        A: android:name="resource"
        A: android:resource=@0x7f010001
      E: meta-data (line=5)
        A: android:name="boolean"
        A: android:value=(type 0x12)0xffffffff
      E: activity (line=6)
        E: meta-data (line=7)
          A: android:name="excluded"
          A: android:value="hidden"
'''
        resources='''      resource 0x7f010001 p:string/name: t=0x03 d=0x00000000
        (string8) "value"
      resource 0x7f010002 p:integer/code: t=0x10 d=0x00bdfe98
'''
        values=parse_application_metadata(manifest,resources)
        self.assertEqual(values,{'text':{'type':'string','value':'value'},'number':{'type':'int','value':12451480},'resource':{'type':'int','value':0x7f010001},'boolean':{'type':'boolean','value':True}})
    def test_cycles_duplicates_and_unsupported_types(self):
        prefix='    E: application (line=1)\n      E: meta-data (line=2)\n        A: android:name="key"\n        A: android:value='
        with self.assertRaises(ValueError):parse_application_metadata(prefix+'@0x7f010001','      resource 0x7f010001 p:integer/a: t=0x01 d=0x7f010001')
        with self.assertRaises(ValueError):parse_application_metadata(prefix+'(type 0x04)0x00000000','')
        with self.assertRaises(ValueError):parse_application_metadata(prefix+'"a"\n      E: meta-data (line=3)\n        A: android:name="key"\n        A: android:value="b"','')
if __name__=='__main__':unittest.main()
