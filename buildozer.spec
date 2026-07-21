[app]
title = Phone Scanner AI
package.name = phonescanner
package.domain = org.scanner
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0
requirements = python3,kivy,pyjnius
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 21
android.ndk = 25b
android.sdk_path = /home/runner/.buildozer/android/platform/android-sdk
android.ndk_path = /home/runner/.buildozer/android/platform/android-ndk-r25b
android.accept_sdk_license = True

# أضف هذين السطرين لضمان جلب أحدث إصلاحات المتطلبات وتوافقها:
p4a.branch = master
log_level = 2
