package org.veritr1x.bunker;

import android.app.Activity;
import android.content.Context;
import android.content.res.ColorStateList;
import android.content.res.Configuration;
import android.graphics.*;
import android.graphics.drawable.*;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.widget.*;

/**
 * The launcher's look, set in code: the Bunker terminal from NieR:Automata.
 * It uses no resources of its own, so it can be added to the game without
 * rebuilding the game's resource table. Light or dark follows the phone.
 */
final class Look {
    final boolean dark;
    final int paper,panel,ink,mid,line,grid,button,onButton,chip,ok,onOk,alert,quiet,onQuiet;
    final float density;
    final Context context;

    private Look(Context c) {
        context=c;
        density=c.getResources().getDisplayMetrics().density;
        String mode=display(c);
        dark="dark".equals(mode)||!"light".equals(mode)&&(c.getResources().getConfiguration().uiMode&Configuration.UI_MODE_NIGHT_MASK)==Configuration.UI_MODE_NIGHT_YES;
        if(dark){
            paper=0xff191813;panel=0xff201f19;ink=0xffd9d3ba;mid=0xffa8a28b;line=0x47d9d3ba;grid=0x09d9d3ba;
            button=0xffd9d3ba;onButton=0xff16150f;chip=0xff3b392f;ok=0xff9da27d;onOk=0xff16150f;alert=0xffe58a78;quiet=0xff2e2c25;onQuiet=0xff857f6c;
        }else{
            paper=0xffd3ceb8;panel=0xffd8d3bd;ink=0xff3a372f;mid=0xff4f4b40;line=0x593a372f;grid=0x0d3a372f;
            button=0xff1e1c18;onButton=0xffe4dfc8;chip=0xffbcb69e;ok=0xff6e7356;onOk=0xffece8d6;alert=0xff7a1c14;quiet=0xffbdb7a0;onQuiet=0xff6e6a5b;
        }
    }
    static Look of(Context c){return new Look(c);}

    /** The player's display choice: "system" (the default), "light" or "dark". */
    static String display(Context c){return c.getSharedPreferences("lunar_look",Context.MODE_PRIVATE).getString("display","system");}
    static void display(Context c,String mode){c.getSharedPreferences("lunar_look",Context.MODE_PRIVATE).edit().putString("display",mode).apply();}

    int dp(float n){return (int)(n*density+.5f);}
    static Typeface mono(){return Typeface.MONOSPACE;}

    /** System bars in the paper colour, with icons that stay readable on it. */
    void apply(Activity activity) {
        Window window=activity.getWindow();
        window.setStatusBarColor(paper);
        window.setNavigationBarColor(paper);
        window.getDecorView().setSystemUiVisibility(dark?0:View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
    }

    /** The paper: a flat colour under a faint square grid. */
    Drawable paper() {
        int step=Math.max(3,dp(3));
        Bitmap tile=Bitmap.createBitmap(step,step,Bitmap.Config.ARGB_8888);
        Canvas c=new Canvas(tile);c.drawColor(paper);
        Paint p=new Paint();p.setColor(grid);
        c.drawRect(0,step-1,step,step,p);c.drawRect(step-1,0,step,step,p);
        BitmapDrawable d=new BitmapDrawable(context.getResources(),tile);
        d.setTileModeXY(Shader.TileMode.REPEAT,Shader.TileMode.REPEAT);
        return d;
    }

    /** A framed panel: a 2dp border, with corner brackets reaching out at top left and bottom right. */
    Drawable frame(){return frame(2);}
    /** A heavier frame for panels that float over the dimmed screen, such as the ⋮ menu. */
    Drawable floating(){return frame(3);}
    private Drawable frame(int strokeDp) {
        final int inset=dp(6),stroke=dp(strokeDp),bracket=dp(strokeDp+1),arm=dp(12+strokeDp);
        return new Drawable(){
            final Paint fill=new Paint(),edge=new Paint(),mark=new Paint();
            { fill.setColor(panel);edge.setColor(ink);edge.setStyle(Paint.Style.STROKE);edge.setStrokeWidth(stroke);mark.setColor(ink); }
            @Override public void draw(Canvas c){
                Rect b=getBounds();
                RectF r=new RectF(b.left+inset,b.top+inset,b.right-inset,b.bottom-inset);
                c.drawRect(r,fill);
                if(dark){Paint glow=new Paint(Paint.ANTI_ALIAS_FLAG);glow.setColor(0x10d9d3ba);glow.setStyle(Paint.Style.STROKE);glow.setStrokeWidth(dp(6));c.drawRect(r,glow);}
                c.drawRect(r.left+stroke/2f,r.top+stroke/2f,r.right-stroke/2f,r.bottom-stroke/2f,edge);
                float l=b.left,t=b.top,rr=b.right,bb=b.bottom;
                c.drawRect(l,t,l+arm,t+bracket,mark);c.drawRect(l,t,l+bracket,t+arm,mark);
                c.drawRect(rr-arm,bb-bracket,rr,bb,mark);c.drawRect(rr-bracket,bb-arm,rr,bb,mark);
            }
            @Override public void setAlpha(int a){}
            @Override public void setColorFilter(ColorFilter f){}
            @Override public int getOpacity(){return PixelFormat.TRANSLUCENT;}
        };
    }
    /** Padding inside frame(), so content clears the border and its brackets. */
    int framePadding(){return dp(6+14);}

    TextView text(String value,float size,int color){
        TextView v=new TextView(context);v.setText(value);v.setTextSize(size);v.setTextColor(color);v.setLineSpacing(dp(2),1);return v;
    }
    TextView monoText(String value,float size,int color){
        TextView v=text(value,size,color);v.setTypeface(mono());v.setLetterSpacing(.06f);return v;
    }

    /** [ TITLE ────── ] */
    LinearLayout header(String title){
        LinearLayout row=new LinearLayout(context);row.setGravity(Gravity.BOTTOM);
        TextView open=text("[",15,ink);open.setTypeface(null,Typeface.BOLD);row.addView(open);
        TextView name=text(title.toUpperCase(),14,ink);name.setTypeface(null,Typeface.BOLD);name.setLetterSpacing(.3f);
        if(dark)name.setShadowLayer(dp(4),0,0,0x55d9d3ba);
        LinearLayout.LayoutParams np=new LinearLayout.LayoutParams(-2,-2);np.setMargins(dp(10),0,dp(10),0);row.addView(name,np);
        View rule=new View(context);rule.setBackgroundColor(ink);
        LinearLayout.LayoutParams rp=new LinearLayout.LayoutParams(0,dp(1),1);rp.setMargins(0,0,dp(8),dp(6));row.addView(rule,rp);
        TextView close=text("]",15,ink);close.setTypeface(null,Typeface.BOLD);row.addView(close);
        return row;
    }

    /** A status chip such as RUNNING or READY. */
    TextView chip(){
        TextView v=monoText("",11,ink);v.setPadding(dp(7),dp(2),dp(7),dp(2));v.setLetterSpacing(.1f);return v;
    }
    void chip(TextView v,String value,int background,int color){v.setText(value);v.setBackgroundColor(background);v.setTextColor(color);}

    private RippleDrawable pressable(Drawable base,int ripple){return new RippleDrawable(ColorStateList.valueOf(ripple),base,null);}
    /** The solid command button: DEPLOY, CREATE BACKUP. */
    Button solid(String label){
        Button b=new Button(context);b.setText(label);b.setAllCaps(false);b.setTextColor(onButton);b.setTextSize(15);b.setTypeface(null,Typeface.BOLD);b.setLetterSpacing(.32f);
        GradientDrawable base=new GradientDrawable();base.setColor(button);b.setBackground(pressable(base,dark?0x33000000:0x33ffffff));
        b.setStateListAnimator(null);return b;
    }
    /** The outlined button: ⋮, CHANGE, CLOSE. */
    Button outlined(String label){
        Button b=new Button(context);b.setText(label);b.setAllCaps(false);b.setTextColor(ink);b.setTextSize(12);b.setTypeface(null,Typeface.BOLD);b.setLetterSpacing(.2f);
        b.setMinWidth(0);b.setMinimumWidth(0);b.setMinHeight(0);b.setMinimumHeight(0);b.setPadding(dp(12),0,dp(12),0);
        GradientDrawable base=new GradientDrawable();base.setColor(0);base.setStroke(dp(2),ink);b.setBackground(pressable(base,line));
        b.setStateListAnimator(null);return b;
    }

    /** The import bar: 20 blocks filling left to right. */
    static final class Segments extends View {
        private final Look look;
        private int permille;
        Segments(Look look){super(look.context);this.look=look;}
        void setPermille(int value){permille=Math.max(0,Math.min(1000,value));setContentDescription(permille/10+" percent");invalidate();}
        @Override protected void onDraw(Canvas c){
            int n=20,gap=look.dp(3),filled=Math.round(permille/1000f*n);float w=(getWidth()-gap*(n-1))/(float)n;Paint p=new Paint();
            for(int i=0;i<n;i++){p.setColor(i<filled?look.ink:(look.dark?0x2ed9d3ba:0x2e3a372f));float x=i*(w+gap);c.drawRect(x,0,x+w,getHeight(),p);}
        }
    }

    /** The footer: a double rule and the sign-off. */
    LinearLayout footer(){
        LinearLayout f=new LinearLayout(context);f.setOrientation(LinearLayout.VERTICAL);
        View a=new View(context);a.setBackgroundColor(ink);f.addView(a,new LinearLayout.LayoutParams(-1,dp(1)));
        View b=new View(context);b.setBackgroundColor(ink);LinearLayout.LayoutParams bp=new LinearLayout.LayoutParams(-1,dp(1));bp.setMargins(0,dp(2),0,0);f.addView(b,bp);
        TextView sign=text(dark?"OPERATOR LINK // STANDING BY":"END OF TRANSMISSION // GLORY TO MANKIND",10,mid);sign.setLetterSpacing(.24f);sign.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams sp=new LinearLayout.LayoutParams(-1,-2);sp.setMargins(0,dp(14),0,dp(18));f.addView(sign,sp);
        return f;
    }

    /** The crescent moon, as a monochrome notification icon. */
    static Icon moon() {
        Bitmap bitmap=Bitmap.createBitmap(96,96,Bitmap.Config.ARGB_8888);
        Canvas canvas=new Canvas(bitmap);canvas.scale(2,2);
        Paint paint=new Paint(Paint.ANTI_ALIAS_FLAG);paint.setColor(Color.WHITE);
        canvas.drawCircle(24,24,22,paint);
        Path crescent=new Path();
        crescent.moveTo(31,10);crescent.cubicTo(18,8,10,18,14,29);crescent.cubicTo(17,38,29,41,36,33);crescent.cubicTo(23,36,17,20,31,10);crescent.close();
        paint.setXfermode(new PorterDuffXfermode(PorterDuff.Mode.CLEAR));
        canvas.drawPath(crescent,paint);
        return Icon.createWithBitmap(bitmap);
    }
}
