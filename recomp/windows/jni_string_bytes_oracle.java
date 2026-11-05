import java.nio.charset.Charset;
import java.util.HexFormat;
public class jni_string_bytes_oracle {
 static final HexFormat HEX=HexFormat.of();
 static String units(String s){StringBuilder b=new StringBuilder();for(int i=0;i<s.length();++i)b.append(String.format("%04x",(int)s.charAt(i)));return b.toString();}
 static String fromUnits(String h){char[]c=new char[h.length()/4];for(int i=0;i<c.length;++i)c[i]=(char)Integer.parseInt(h.substring(i*4,i*4+4),16);return new String(c);}
 static void decode(String name,String h)throws Exception{String s=new String(HEX.parseHex(h),name);System.out.println("D|"+name+"|"+h+"|"+units(s));}
 static void encode(String name,String h)throws Exception{System.out.println("E|"+name+"|"+h+"|"+HEX.formatHex(fromUnits(h).getBytes(name)));}
 interface Action{void call()throws Exception;}
 static void exception(String label,Action a){try{a.call();System.out.println("X|"+label+"|NONE");}catch(Exception e){System.out.println("X|"+label+"|"+e.getClass().getName());}}
 public static void main(String[]args)throws Exception{
  System.out.println("JDK|"+System.getProperty("java.runtime.version"));
  for(String h:new String[]{"","00","410042","7fc280dfbfe0a080ed9fbfee8080efbfbff0908080f48fbfbf","c0af","e08080","eda080","e18041","e180","f0908041","f4908080","f5808080","80bf","e228a1","f09f9880"})decode("UTF-8",h);
  for(String name:new String[]{"UTF-16","UTF-16BE","UTF-16LE"})for(String h:new String[]{"","00410000","feff0041","fffe4100","d83dde00","d8000041","dc000041","d800","00","004100","d80000"})decode(name,h);
  for(String h:new String[]{"3dd800de","00d84100","00dc4100","00d800","410000"})decode("UTF-16LE",h);decode("UTF-16","fffe3dd800de");
  for(String name:new String[]{"US-ASCII","ISO-8859-1"})for(String h:new String[]{"","00417f80a0ff","8081feff"})decode(name,h);
  for(String name:new String[]{"UTF-8","UTF-16","UTF-16BE","UTF-16LE","US-ASCII","ISO-8859-1"})for(String h:new String[]{"","00000041007f008000ff0100","d83dde00","d800","dc00","d8000041dc00"})encode(name,h);
  String[]aliases={"utf8","uTf-8","UTF16","unicode","UnicodeBig","UnicodeBigUnmarked","UnicodeLittleUnmarked","ASCII","ISO8859_1","ISO_8859_1","Latin1"};
  for(String name:aliases){System.out.println("A|"+name+"|"+Charset.forName(name).name());decode(name,"4100");encode(name,"004100ff");}
  exception("ctor-null-bytes",()->new String((byte[])null,"UTF-8"));exception("ctor-null-name",()->new String(new byte[0],(String)null));exception("encode-null-name",()->"x".getBytes((String)null));
  exception("ctor-invalid-name",()->new String(new byte[0],"bad charset"));exception("encode-invalid-name",()->"x".getBytes(""));
 }
}
