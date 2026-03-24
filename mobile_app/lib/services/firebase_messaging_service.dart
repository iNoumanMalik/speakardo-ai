import 'dart:io';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';

import 'device_service.dart';

class FirebaseMessagingService {
  static final DeviceService _deviceService = DeviceService();
  static bool _bootstrapped = false;

  static Future<void> initializeAndRegisterToken() async {
    if (_bootstrapped) {
      return;
    }
    _bootstrapped = true;

    final messaging = FirebaseMessaging.instance;

    await messaging.requestPermission(
      alert: true,
      badge: true,
      sound: true,
      provisional: false,
    );

    FirebaseMessaging.onMessage.listen((RemoteMessage message) {
      debugPrint('Foreground notification: ${message.notification?.title}');
    });

    final token = await messaging.getToken();
    if (token == null || token.isEmpty) {
      debugPrint('FCM token unavailable');
      return;
    }

    debugPrint('FCM TOKEN: $token');

    try {
      await _deviceService.registerDeviceToken(
        token: token,
        userId: null,
        platform: _platformName(),
      );
    } catch (e) {
      debugPrint('Failed to register FCM token: $e');
    }
  }

  static String _platformName() {
    if (kIsWeb) {
      return 'web';
    }
    if (Platform.isAndroid) {
      return 'android';
    }
    if (Platform.isIOS) {
      return 'ios';
    }
    return 'unknown';
  }
}
