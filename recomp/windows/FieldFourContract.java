import java.lang.reflect.Field;
import java.lang.reflect.Modifier;
public final class FieldFourContract {
  public static class Base { public int integer; public static String staticText; }
  public static final class Derived extends Base {}
  private static int checks;
  static void check(boolean value){if(!value)throw new AssertionError();++checks;}
  private static native Field nativeField(Class<?> owner,boolean stat);
  private static native Object nativeFour(int form,boolean flag);
  public static Object four(Class<?> owner,String name,String signature,boolean flag){
    check(owner==Base.class&&name.equals("integer")&&signature.equals("I"));
    return flag?owner:name;
  }
  public static void main(String[] args){
    System.load(args[0]);
    for(Class<?> owner:new Class<?>[]{Base.class,Derived.class})for(boolean stat:new boolean[]{false,true}){
      Field f=nativeField(owner,stat);
      check(f.getDeclaringClass()==Base.class);
      check(f.getName().equals(stat?"staticText":"integer"));
      check(f.getType()==(stat?String.class:int.class));
      check(Modifier.isStatic(f.getModifiers())==stat);
    }
    for(boolean flag:new boolean[]{false,true})for(int form=0;form<3;++form){Object result=nativeFour(form,flag);check(flag?result==Base.class:result.equals("integer"));}
    System.out.println("JDK-FIELD-FOUR-PASS checks="+checks+" JNI_ToFromField=4 inherited_owner=1 static=1 fourarg_forms=3");
  }
}
