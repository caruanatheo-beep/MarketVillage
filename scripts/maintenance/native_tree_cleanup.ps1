if(-not ('MarketDeskCleanup.NativeTree' -as [type])){
Add-Type -TypeDefinition @'
using System;
using System.IO;
using System.Runtime.InteropServices;
namespace MarketDeskCleanup {
 public static class NativeTree {
  [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
  struct Entry {
   public uint attributes; public System.Runtime.InteropServices.ComTypes.FILETIME created,accessed,written;
   public uint high,low,tag,reserved;
   [MarshalAs(UnmanagedType.ByValTStr, SizeConst=260)] public string name;
   [MarshalAs(UnmanagedType.ByValTStr, SizeConst=14)] public string alternate;
  }
  [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr FindFirstFileW(string path,out Entry entry);
  [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool FindNextFileW(IntPtr handle,out Entry entry);
  [DllImport("kernel32.dll")] static extern bool FindClose(IntPtr handle);
  [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool DeleteFileW(string path);
  [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool RemoveDirectoryW(string path);
  [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool SetFileAttributesW(string path,uint attributes);
  [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern uint GetFileAttributesW(string path);
  static bool RemoveRealDirectory(string path) {
   uint attributes=GetFileAttributesW(path);
   if(attributes!=0xffffffff && (attributes & 1)!=0) SetFileAttributesW(path,attributes & ~1u);
   return RemoveDirectoryW(path);
  }
  static void Walk(string path,long[] stats) {
   Entry entry; IntPtr handle=FindFirstFileW(path+"\\*",out entry);
   if(handle!=new IntPtr(-1)) {
    try {
     do {
      if(entry.name=="." || entry.name=="..") continue;
      string child=path+"\\"+entry.name;
      bool directory=(entry.attributes & 16)!=0;
      bool redirected=(entry.attributes & 1024)!=0 && (entry.tag & 0x20000000)!=0;
      if(directory) {
       if(redirected) { if(RemoveDirectoryW(child)) stats[2]++; else stats[3]++; }
       else Walk(child,stats);
      } else {
       if(!redirected && (entry.attributes & 1)!=0) SetFileAttributesW(child,entry.attributes & ~1u);
       if(DeleteFileW(child)){stats[0]++;stats[1]+=((long)entry.high<<32)|entry.low;}else stats[3]++;
      }
     }while(FindNextFileW(handle,out entry));
    } finally {FindClose(handle);}
   } else if(Marshal.GetLastWin32Error()!=2 && Marshal.GetLastWin32Error()!=18) stats[3]++;
   if(RemoveRealDirectory(path)) stats[2]++; else stats[3]++;
  }
  public static long[] Remove(string workspace,string target) {
   string root=Path.GetFullPath(workspace).TrimEnd('\\')+"\\";
   string full=Path.GetFullPath(target).TrimEnd('\\');
   if(!full.StartsWith(root,StringComparison.OrdinalIgnoreCase)) throw new ArgumentException("Target outside workspace");
   // A lexical prefix alone does not protect against an ancestor junction.
   for(string ancestor=Path.GetDirectoryName(full); ancestor!=null; ancestor=Path.GetDirectoryName(ancestor)) {
    Entry parent;IntPtr parentHandle=FindFirstFileW("\\\\?\\"+ancestor,out parent);
    if(parentHandle==new IntPtr(-1)) throw new IOException("Cannot verify cleanup ancestor");
    FindClose(parentHandle);
    if((parent.attributes & 1024)!=0 && (parent.tag & 0x20000000)!=0)
     throw new ArgumentException("Cleanup ancestor is redirected");
    if(ancestor.Equals(root.TrimEnd('\\'),StringComparison.OrdinalIgnoreCase)) break;
   }
   long[] result=new long[4];string extended="\\\\?\\"+full;
   Entry top;IntPtr handle=FindFirstFileW(extended,out top);
   if(handle==new IntPtr(-1)) return result;
   FindClose(handle);
   if((top.attributes & 1024)!=0 && (top.tag & 0x20000000)!=0) {
    if(RemoveDirectoryW(extended)) result[2]++; else result[3]++;
   } else Walk(extended,result);
   return result;
  }
 }
}
'@
}
