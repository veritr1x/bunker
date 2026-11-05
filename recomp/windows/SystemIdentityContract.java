public final class SystemIdentityContract {
  static int checks;
  static void check(boolean b) { if (!b) throw new AssertionError(); ++checks; }
  static final class OverrideHash { int calls; public int hashCode() { ++calls; return 0x13579; } }
  public static void main(String[] args) throws Exception {
    check(System.identityHashCode(null)==0);
    Object value=new Object(),alias=value;
    int hash=System.identityHashCode(value);
    check(System.identityHashCode(alias)==hash);
    check(value.toString().equals("java.lang.Object@"+Integer.toHexString(hash)));
    OverrideHash overridden=new OverrideHash();
    check(overridden.hashCode()==0x13579 && overridden.calls==1);
    int identity=System.identityHashCode(overridden);
    check(System.identityHashCode(overridden)==identity && overridden.calls==1);
    for(Object object:new Object[]{new String("same content"),new String("same content"),new byte[4],new Object[2],Object.class}) {
      int own=System.identityHashCode(object);
      for(int i=0;i<3;++i)check(System.identityHashCode(object)==own);
    }
    java.util.concurrent.atomic.AtomicBoolean stable=new java.util.concurrent.atomic.AtomicBoolean(true);
    Thread worker=new Thread(()->{for(int i=0;i<3;++i)if(System.identityHashCode(alias)!=hash)stable.set(false);});
    worker.start();worker.join();check(stable.get());
    System.out.println("JDK-IDENTITY-CONTRACT-PASS checks="+checks+" nullzero=1 aliases=1 overridebypass=1 arraysclasses=1 thread=1 default_toString=1");
  }
}
