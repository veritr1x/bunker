package org.lunartear.companion;

import android.app.Activity;
import android.graphics.*;
import android.graphics.drawable.Icon;
import android.view.View;
import android.view.Window;

/**
 * The launcher's look, set in code. It uses no resources of its own, so it can
 * be added to the game without rebuilding the game's resource table.
 */
final class Look {
    private Look() {}
    /** Light bars to match the launcher's paper background. */
    static void apply(Activity activity) {
        Window window=activity.getWindow();
        window.setNavigationBarColor(0xfff4f1e9);
        window.getDecorView().setSystemUiVisibility(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR);
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
