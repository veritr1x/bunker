package org.lunartear.companion;

import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.provider.DocumentsContract;
import java.io.*;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.ArrayList;
import java.util.List;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

final class FilesStore {
    static final String MASTER = "20240404193219.bin.e";
    interface Progress { void update(String text); boolean cancelled(); }
    static File root(Context c) { return new File(c.getFilesDir(), "server"); }
    static File data(Context c) { return new File(c.getFilesDir(), "saves"); }
    static File assets(Context c) { return new File(root(c), "assets"); }
    static File master(Context c) { return new File(assets(c), "release/" + MASTER); }
    static File list(Context c) {
        File f = new File(assets(c), "revisions/0/android/list.bin");
        return f.isFile() ? f : new File(assets(c), "revisions/0/list.bin");
    }
    static boolean ready(Context c) { return master(c).length() > 0 && list(c).length() > 0; }
    static void ensureBootstrap(Context c) throws IOException {
        if(master(c).length()>0)return;
        mkdir(master(c).getParentFile());
        File tmp=File.createTempFile("bootstrap-",".tmp",master(c).getParentFile());
        try(InputStream in=c.getAssets().open("lunar/"+MASTER);FileOutputStream out=new FileOutputStream(tmp)) {
            byte[] buffer=new byte[65536];int n;while((n=in.read(buffer))!=-1)out.write(buffer,0,n);out.getFD().sync();
            if(master(c).length()==0)move(tmp,master(c));
        } finally {tmp.delete();}
    }
    static void mkdir(File f) throws IOException { if (!f.isDirectory() && !f.mkdirs()) throw new IOException("Cannot create " + f.getName()); }
    static void move(File from, File to) throws IOException {
        Files.move(from.toPath(), to.toPath(), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING);
    }
    // All writes go to private staging locations. A failed import leaves the
    // existing installation and saves intact, including on provider disconnect.
    static void importMaster(Context c, Uri uri, Progress progress) throws Exception {
        File out = master(c); mkdir(out.getParentFile());
        File temp = new File(out.getParentFile(), ".master-import");
        try {
            copy(c, uri, temp, progress, "Importing master data");
            if (temp.length() == 0) throw new IOException("The selected file is empty");
            move(temp, out);
        } finally { temp.delete(); }
    }
    static final class Doc {
        String id, name, mime;
        Doc(String id, String name, String mime) { this.id=id; this.name=name; this.mime=mime; }
        boolean directory() { return DocumentsContract.Document.MIME_TYPE_DIR.equals(mime); }
    }
    static List<Doc> children(Context c, Uri tree, String id) throws IOException {
        List<Doc> docs = new ArrayList<>();
        Uri uri = DocumentsContract.buildChildDocumentsUriUsingTree(tree, id);
        try (Cursor cur = c.getContentResolver().query(uri, new String[]{"document_id", "_display_name", "mime_type"}, null, null, null)) {
            if (cur == null) throw new IOException("Cannot read the selected folder");
            while (cur.moveToNext()) docs.add(new Doc(cur.getString(0),cur.getString(1),cur.getString(2)));
        }
        return docs;
    }
    static void importAssets(Context c, Uri tree, Progress progress) throws Exception {
        File base = root(c); mkdir(base);
        recover(c);
        File stage = new File(base, "assets.importing"), old = new File(base, "assets.previous");
        delete(stage); mkdir(stage);
        try {
            String id = DocumentsContract.getTreeDocumentId(tree);
            // Accept either the assets directory itself or its immediate parent.
            List<Doc> docs = children(c,tree,id);
            for (Doc d : docs) if (d.directory() && d.name.equals("assets")) { id=d.id; break; }
            copyTree(c,tree,id,stage,progress,0);
            File index = new File(stage,"revisions/0/android/list.bin");
            if (index.length()==0 && new File(stage,"revisions/0/list.bin").length()==0)
                throw new IOException("Select the extracted assets folder containing revisions/0/android/list.bin");
            File nextMaster = new File(stage,"release/"+MASTER);
            if (!nextMaster.exists() && master(c).isFile()) {
                mkdir(nextMaster.getParentFile());
                Files.copy(master(c).toPath(), nextMaster.toPath());
            }
            if (progress.cancelled()) throw new IOException("Import cancelled");
            delete(old);
            if (assets(c).exists()) move(assets(c),old);
            try { move(stage,assets(c)); } catch(Exception e) { if(old.exists()) move(old,assets(c)); throw e; }
            delete(old);
        } finally { delete(stage); }
    }
    static void recover(Context c) throws IOException {
        File old = new File(root(c),"assets.previous");
        if (!assets(c).exists() && old.exists()) move(old,assets(c));
    }
    static void copyTree(Context c, Uri tree, String id, File dest, Progress progress, int depth) throws Exception {
        if (depth > 32) throw new IOException("Folder nesting is too deep");
        for (Doc d : children(c,tree,id)) {
            if (progress.cancelled()) throw new IOException("Import cancelled");
            if (d.name==null || d.name.equals(".") || d.name.equals("..") || d.name.contains("/") || d.name.contains("\\")) throw new IOException("Invalid file name in source");
            // This companion serves the Android client only.
            if (d.directory() && d.name.equals("ios") && dest.getParentFile()!=null && dest.getParentFile().getName().equals("revisions")) continue;
            File out = new File(dest,d.name);
            if (d.directory()) { mkdir(out); copyTree(c,tree,d.id,out,progress,depth+1); }
            else copy(c,DocumentsContract.buildDocumentUriUsingTree(tree,d.id),out,progress,"Importing " + d.name);
        }
    }
    static void copy(Context c, Uri uri, File out, Progress progress, String label) throws Exception {
        progress.update(label);
        try (InputStream in = c.getContentResolver().openInputStream(uri); FileOutputStream stream = new FileOutputStream(out)) {
            if (in==null) throw new IOException("Cannot open source file");
            byte[] buffer = new byte[262144]; int n; long total=0;
            while ((n=in.read(buffer))!=-1) {
                if (progress.cancelled()) throw new IOException("Import cancelled");
                stream.write(buffer,0,n); total+=n;
                if (total % (8L*1024*1024)<buffer.length) progress.update(label + " · " + (total/1024/1024) + " MB");
            }
            stream.getFD().sync();
        }
    }
    static void backup(Context c, Uri target) throws Exception {
        String error=NativeBridge.prepareBackup(data(c).getAbsolutePath());
        if(error==null||!error.isEmpty())throw new IOException(error==null?"Cannot prepare save backup":error);
        try (OutputStream raw=c.getContentResolver().openOutputStream(target,"wt")) {
            if(raw==null) throw new IOException("Cannot open backup destination");
            try (ZipOutputStream zip=new ZipOutputStream(raw)) {
                for(String name:new String[]{"game.db","auth.db","auth.key"}) {
                    File f=new File(data(c),name);
                    if(!f.isFile()) continue;
                    zip.putNextEntry(new ZipEntry(name));
                    try(InputStream in=new FileInputStream(f)){byte[] bytes=new byte[65536];int n;while((n=in.read(bytes))!=-1)zip.write(bytes,0,n);}
                    zip.closeEntry();
                }
                zip.putNextEntry(new ZipEntry("README.txt"));
                zip.write("Lunar Tear local saves. Keep game.db, auth.db and auth.key together. Contains account credentials; keep this backup private.\n".getBytes(java.nio.charset.StandardCharsets.UTF_8));
                zip.closeEntry();
            }
        }
    }
    static void delete(File file) {
        File[] children=file.listFiles(); if(children!=null) for(File c:children) delete(c);
        file.delete();
    }
}
