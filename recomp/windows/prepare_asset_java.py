"""Create independent APK/UTF-8 stream fixtures for actual NDK Scanner callers."""
import argparse,binascii,json,pathlib,zipfile
HERE=pathlib.Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apk',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,default=HERE.parent/'work/windows-asset-java')
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(a.apk) as z:boot=z.read('assets/bin/Data/boot.config')
    text=boot.decode('utf-8')
    (a.out/'asset_java_sample.h').write_text(f'static const char16_t *kBootText=u{json.dumps(text)};\nstatic constexpr unsigned kBootBytes={len(boot)};\nstatic constexpr unsigned kBootCrc={binascii.crc32(boot)}U;\n')
    with zipfile.ZipFile(a.out/'streams.apk','w') as z:
        for name,data,method in [('unicode.txt','\ufeffA\0é☃😀\n'.encode(),zipfile.ZIP_DEFLATED),('empty.txt',b'',zipfile.ZIP_STORED),('malformed.txt',b'\xc0\xaf',zipfile.ZIP_STORED),('large.txt',('中'*4097).encode(),zipfile.ZIP_DEFLATED)]:z.writestr('assets/'+name,data,compress_type=method)
    print('Prepared exact original boot.config reference and independent stored/deflated Unicode/empty/malformed/large streams.')
if __name__=='__main__':main()
