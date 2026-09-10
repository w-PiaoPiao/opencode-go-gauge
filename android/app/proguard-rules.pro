# GoGauge Android — R8 规则 (release 构建开启 minify + resource shrink)

# ---------------------------------------------------------------------------
# kotlinx.serialization
# ---------------------------------------------------------------------------
# 插件会为 @Serializable 类生成 serializer, 但反射查找的 serializer() 入口
# 与 companion 需要保留, 否则 R8 裁掉后会抛
# SerializationException("Serializer for class ... not found")
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.**
-keepclassmembers class kotlinx.serialization.json.** {
    *** Companion;
}
-keepclasseswithmembers class kotlinx.serialization.json.** {
    kotlinx.serialization.KSerializer serializer(...);
}
-keep,includedescriptorclasses class io.github.yphyphyph.gogauge.**$$serializer { *; }
-keepclassmembers class io.github.yphyphyph.gogauge.** {
    *** Companion;
}
-keepclasseswithmembers class io.github.yphyphyph.gogauge.** {
    kotlinx.serialization.KSerializer serializer(...);
}

# ---------------------------------------------------------------------------
# Room
# ---------------------------------------------------------------------------
# Room 生成的 _Impl 由反射实例化; 实体/DAO 依赖注解保留
-keep class * extends androidx.room.RoomDatabase { <init>(); }
-keep @androidx.room.Entity class * { *; }
-dontwarn androidx.room.paging.**

# ---------------------------------------------------------------------------
# OkHttp / Okio
# ---------------------------------------------------------------------------
-dontwarn okhttp3.**
-dontwarn okio.**
-dontwarn org.conscrypt.**
-dontwarn org.bouncycastle.**
-dontwarn org.openjsse.**
