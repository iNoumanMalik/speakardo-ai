import 'dart:io';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:permission_handler/permission_handler.dart';

class OnboardingPermissions {
  OnboardingPermissions._();

  static Future<bool> requestNotifications() async {
    if (kIsWeb) return false;

    try {
      if (Platform.isIOS || Platform.isMacOS) {
        final settings = await FirebaseMessaging.instance.requestPermission(
          alert: true,
          badge: true,
          sound: true,
          provisional: false,
        );
        final status = settings.authorizationStatus;
        return status == AuthorizationStatus.authorized ||
            status == AuthorizationStatus.provisional;
      }

      if (Platform.isAndroid) {
        final status = await Permission.notification.request();
        return status.isGranted;
      }
    } catch (e) {
      debugPrint('Notification permission error: $e');
    }
    return false;
  }

  static Future<bool> requestMicrophone() async {
    if (kIsWeb) return false;

    try {
      final status = await Permission.microphone.request();
      return status.isGranted;
    } catch (e) {
      debugPrint('Microphone permission error: $e');
    }
    return false;
  }
}
